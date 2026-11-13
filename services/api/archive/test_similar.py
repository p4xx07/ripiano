import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from archive.models import Document


def make(owner, title, text, sha="0", status="ready", **values):
    return Document.objects.create(owner=owner, title=title, original_name=f"{title}.pdf", original_path="originals/aa/x.pdf",
                                   original_mime="application/pdf", original_sha256=sha * 64, original_size=1, status=status,
                                   extracted_text=text, processed_at=timezone.now(), **values)


@pytest.mark.django_db
def test_similar_documents_rank_by_distinctive_words_and_flag_likely_duplicates():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    other = get_user_model().objects.create_user("other", password="secure-password-2")
    text = "Condominio Girasole rendiconto spese riscaldamento ascensore pulizie scale quota millesimi"
    target = make(owner, "Rendiconto 2025", text, sha="a")
    near = make(owner, "Rendiconto 2025 copia", text + " pagina", sha="b")
    related = make(owner, "Preventivo condominio", "Condominio Girasole preventivo riscaldamento ascensore lavori", sha="c")
    make(owner, "Pizza menu", "margherita diavola capricciosa quattro formaggi", sha="d")
    make(owner, "Old", text, sha="e", trashed_at=timezone.now())
    make(other, "Theirs", text, sha="f")
    client = Client()
    client.force_login(owner)
    similar = client.get(f"/api/documents/{target.id}/similar").json()["similar"]
    assert [item["id"] for item in similar] == [str(near.id), str(related.id)]
    assert similar[0]["likely_duplicate"] is True and similar[1]["likely_duplicate"] is False
    assert "riscaldamento" in similar[1]["shared_terms"]
    intruder = Client()
    intruder.force_login(other)
    assert intruder.get(f"/api/documents/{target.id}/similar").status_code == 404
