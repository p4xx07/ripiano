from datetime import date
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings

from archive.models import BrowseExportRun, Correspondent, StoragePath
from archive.storage_paths import render, validate_template
from archive.tasks import build_browse_export
from archive.test_browse_export import make_document


@pytest.mark.parametrize(("template", "problem"), [
    ("{correspondent}/{year}", ""),
    ("/absolute", "Use folder names"),
    ("a/../b", "Use folder names"),
    ("{secret}", "Unknown placeholder"),
    ("a/b/c/d/e/f/g", "at most 6"),
    ("a/b/c/d/e/f/", ""),
])
def test_templates_are_validated(template, problem):
    message = validate_template(template)
    assert (problem in message) if problem else message == ""


@pytest.mark.django_db
def test_storage_paths_shape_the_browse_copy_and_stay_owner_scoped(tmp_path):
    owner = get_user_model().objects.create_superuser("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    media, backup = tmp_path / "media", tmp_path / "backup"
    document, original, _ = make_document(owner, media, title="Bolletta: maggio")
    plain, _, _ = make_document(owner, media, title="Loose note", name="note.pdf")
    acme = Correspondent.objects.create(owner=owner, name="Acme/Energy")
    document.correspondent = acme
    document.document_date = date(2025, 5, 10)
    document.save(update_fields=["correspondent", "document_date"])
    client = Client()
    client.force_login(owner)
    assert client.post("/api/storage-paths", {"name": "By sender", "template": "{secret}"}, content_type="application/json").status_code == 400
    created = client.post("/api/storage-paths", {"name": "By sender", "template": "{correspondent}/{year}/{month}"}, content_type="application/json")
    assert created.status_code == 201
    path_id = created.json()["id"]
    assert client.post("/api/storage-paths", {"name": "by sender", "template": "{year}"}, content_type="application/json").status_code == 409
    assert render("{correspondent}/{year}/{month}", document) == ["Acme-Energy", "2025", "05"]
    document.title = "con"
    assert render("{title}/../{title}", document) == ["con_", "None", "con_"]  # ".." never becomes a parent-directory step
    document.title = "😀" * 80 + "--" + str(document.id)
    rendered = render("{title}", document)[0]
    assert len(rendered.encode("utf-8")) <= 180 and "--" not in rendered

    intruder = Client()
    intruder.force_login(other)
    assert intruder.get("/api/storage-paths").json()["storage_paths"] == []
    assert intruder.patch(f"/api/documents/{document.id}", {"storage_path_id": path_id}, content_type="application/json").status_code == 404
    other_doc, _, _ = make_document(other, media, name="theirs.pdf")
    assert intruder.patch(f"/api/documents/{other_doc.id}", {"storage_path_id": path_id}, content_type="application/json").json()["error"] == "Storage path not found"
    assert intruder.delete(f"/api/storage-paths/{path_id}").status_code == 404

    assigned = client.patch(f"/api/documents/{document.id}", {"storage_path_id": path_id}, content_type="application/json").json()
    assert assigned["storage_path"] == {"id": path_id, "name": "By sender"}
    with override_settings(MEDIA_ROOT=media, RIPIANO_BACKUP_ROOT=backup):
        with patch("archive.browse_views.build_browse_export.delay"):
            run_id = client.post("/api/browse-exports").json()["id"]
        build_browse_export(run_id)
    run = BrowseExportRun.objects.get(pk=run_id)
    assert run.status == BrowseExportRun.Status.COMPLETE
    root = backup / "browse" / "owners" / str(owner.pk) / "complete" / run.folder_name / "documents"
    placed = root / "Acme-Energy" / "2025" / "05" / f"Bolletta- maggio--{document.id}" / "original.pdf"
    assert placed.read_bytes() == original
    assert list(root.glob(f"*/Loose note--{plain.id}"))  # documents without a path keep the year layout
    assert client.delete(f"/api/storage-paths/{path_id}").status_code == 200
    document.refresh_from_db()
    assert document.storage_path is None and StoragePath.objects.count() == 0
