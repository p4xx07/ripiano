import hashlib
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.utils import timezone

from archive.models import Document, ShareLink


def make_document(owner, media, name):
    content = b"%PDF-1.4\nprivate original\n"
    path = media / "originals" / "ab" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    document = Document.objects.create(
        owner=owner, title="Private document", original_name=name,
        original_path=f"originals/ab/{name}", original_mime="application/pdf",
        original_sha256=hashlib.sha256(content).hexdigest(), original_size=len(content),
        status=Document.Status.READY,
    )
    return document, content, path


@pytest.mark.django_db
def test_share_link_exposes_only_verified_original_until_revoked_or_trashed(tmp_path):
    owner = get_user_model().objects.create_user("share-owner", password="secure-password-1")
    other = get_user_model().objects.create_user("share-other", password="secure-password-2")
    media = tmp_path / "media"
    document, original, path = make_document(owner, media, "policy.pdf")
    owner_client = Client()
    owner_client.force_login(owner)
    stranger = Client()
    with override_settings(MEDIA_ROOT=media, PUBLIC_ORIGIN="https://archive.example"):
        assert stranger.get(f"/api/documents/{document.id}/shares").status_code == 401
        created = owner_client.post(f"/api/documents/{document.id}/shares", {"expires_in_days": 7}, content_type="application/json")
        assert created.status_code == 201
        data = created.json()
        token = data["url"].rsplit("/", 1)[-1]
        assert data["url"].startswith("https://archive.example/api/share-links/")
        share = ShareLink.objects.get(pk=data["id"])
        assert share.token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert token not in share.token_hash
        listed = owner_client.get(f"/api/documents/{document.id}/shares").json()["shares"]
        assert len(listed) == 1 and "url" not in listed[0]
        download = stranger.get(f"/api/share-links/{token}")
        assert download.status_code == 200
        assert b"".join(download.streaming_content) == original
        assert download["Cache-Control"] == "no-store"
        assert download["Referrer-Policy"] == "no-referrer"
        assert download["X-Content-Type-Options"] == "nosniff"
        assert "policy.pdf" in download["Content-Disposition"]
        assert stranger.get("/api/share-links/invalid").status_code == 404
        owner_client.force_login(other)
        assert owner_client.get(f"/api/documents/{document.id}/shares").status_code == 404
        assert owner_client.delete(f"/api/documents/{document.id}/shares/{share.id}").status_code == 404
        owner_client.force_login(owner)
        path.write_bytes(b"changed")
        assert stranger.get(f"/api/share-links/{token}").status_code == 503
        path.write_bytes(original)
        assert owner_client.post(f"/api/documents/{document.id}/trash").status_code == 200
        assert stranger.get(f"/api/share-links/{token}").status_code == 404
        assert owner_client.post(f"/api/documents/{document.id}/restore").status_code == 200
        assert stranger.get(f"/api/share-links/{token}").status_code == 404
        share.refresh_from_db()
        assert share.revoked_at is not None


@pytest.mark.django_db
def test_share_expiry_validation_bulk_trash_and_revoke(tmp_path):
    owner = get_user_model().objects.create_user("share-owner-2", password="secure-password-1")
    media = tmp_path / "media"
    first, _, _ = make_document(owner, media, "first.pdf")
    second, _, _ = make_document(owner, media, "second.pdf")
    client = Client()
    client.force_login(owner)
    with override_settings(MEDIA_ROOT=media, PUBLIC_ORIGIN="https://archive.example"):
        for days in (0, 31, True, "7"):
            assert client.post(f"/api/documents/{first.id}/shares", {"expires_in_days": days}, content_type="application/json").status_code == 400
        assert client.post(f"/api/documents/{first.id}/shares", data="bad", content_type="application/json").status_code == 400
        first_link = client.post(f"/api/documents/{first.id}/shares", {"expires_in_days": 1}, content_type="application/json").json()
        second_link = client.post(f"/api/documents/{second.id}/shares", {"expires_in_days": 30}, content_type="application/json").json()
        first_token = first_link["url"].rsplit("/", 1)[-1]
        second_token = second_link["url"].rsplit("/", 1)[-1]
        ShareLink.objects.filter(pk=first_link["id"]).update(expires_at=timezone.now() - timedelta(seconds=1))
        assert Client().get(f"/api/share-links/{first_token}").status_code == 404
        assert client.delete(f"/api/documents/{second.id}/shares/{second_link['id']}").status_code == 200
        assert Client().get(f"/api/share-links/{second_token}").status_code == 404
        third_link = client.post(f"/api/documents/{first.id}/shares", {"expires_in_days": 7}, content_type="application/json").json()
        assert client.post("/api/documents/bulk-trash", {"action": "trash", "document_ids": [str(first.id), str(second.id)]}, content_type="application/json").status_code == 200
        assert ShareLink.objects.get(pk=third_link["id"]).revoked_at is not None
        assert Client().get(third_link["url"].replace("https://archive.example", "")).status_code == 404


@pytest.mark.django_db(transaction=True)
def test_revocation_waits_until_in_flight_authorization_opens_file(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from django.db import connection
    from archive import share_views

    if connection.vendor != "postgresql":
        pytest.skip("Row-lock ordering requires PostgreSQL")
    owner = get_user_model().objects.create_user("concurrent-share-owner", password="secure-password-1")
    media = tmp_path / "media"
    document, original, _ = make_document(owner, media, "concurrent.pdf")
    client = Client()
    client.force_login(owner)
    with override_settings(MEDIA_ROOT=media, PUBLIC_ORIGIN="https://archive.example"):
        created = client.post(f"/api/documents/{document.id}/shares", {"expires_in_days": 7}, content_type="application/json").json()
        url = created["url"].replace("https://archive.example", "")
        authorization_reached = Event()
        continue_open = Event()
        revoke_started = Event()
        save_reached = Event()
        original_media_path = share_views._media_path
        original_save = ShareLink.save

        def pause_before_open(*args, **kwargs):
            authorization_reached.set()
            assert continue_open.wait(5)
            return original_media_path(*args, **kwargs)

        def observe_revoke(self, *args, **kwargs):
            if str(self.pk) == created["id"] and kwargs.get("update_fields") == ["revoked_at"]:
                save_reached.set()
            return original_save(self, *args, **kwargs)

        monkeypatch.setattr(share_views, "_media_path", pause_before_open)
        monkeypatch.setattr(ShareLink, "save", observe_revoke)

        def download():
            response = Client().get(url)
            return response.status_code, b"".join(response.streaming_content) if response.status_code == 200 else b""

        def revoke():
            other_client = Client()
            other_client.force_login(owner)
            revoke_started.set()
            return other_client.delete(f"/api/documents/{document.id}/shares/{created['id']}").status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            reading = pool.submit(download)
            assert authorization_reached.wait(5)
            revoking = pool.submit(revoke)
            assert revoke_started.wait(5)
            try:
                assert not save_reached.wait(0.3)
            finally:
                continue_open.set()
            assert reading.result(timeout=5) == (200, original)
            assert revoking.result(timeout=5) == 200
        assert Client().get(url).status_code == 404
