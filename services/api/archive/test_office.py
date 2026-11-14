import hashlib
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from pypdf import PdfWriter

from archive.models import Document
from archive.office import OFFICE_TYPES, OfficeConversionError, convert_office, inspect_office
from archive.storage import InvalidDocument, save_original
from archive.tasks import process_document


def package_bytes(main_part, *, macro=False):
    data = BytesIO()
    with ZipFile(data, "w", ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", "<Types/>")
        package.writestr(main_part, "<document/>")
        if macro:
            package.writestr("word/vbaProject.bin", b"macro")
    return data.getvalue()


def test_office_inspection_accepts_ooxml_and_rejects_wrong_container(tmp_path):
    for extension, (mime, main_part) in OFFICE_TYPES.items():
        path = tmp_path / f"report{extension}"
        path.write_bytes(package_bytes(main_part))
        assert inspect_office(path, path.name) == (extension, mime)
        assert inspect_office(path, "report.pdf") is None
    wrong = tmp_path / "wrong.docx"
    wrong.write_bytes(package_bytes("xl/workbook.xml"))
    with pytest.raises(ValueError, match="invalid"):
        inspect_office(wrong, wrong.name)
    wrong.write_bytes(package_bytes("word/document.xml", macro=True))
    with pytest.raises(ValueError, match="invalid"):
        inspect_office(wrong, wrong.name)


@pytest.mark.django_db
def test_office_original_is_preserved_and_converted_pdf_enters_ocr_pipeline(tmp_path):
    owner = get_user_model().objects.create_user("office-owner", password="secure-password-1")
    original = Path(__file__).resolve().parents[3] / "apps" / "web" / "e2e" / "fixtures" / "office-letter.docx"
    content = original.read_bytes()
    media = tmp_path / "media"
    with override_settings(MEDIA_ROOT=media):
        path, mime, _, size = save_original(SimpleUploadedFile(original.name, content))
        assert mime == OFFICE_TYPES[".docx"][0] and size == len(content)
        assert (media / path).read_bytes() == content
        document = Document.objects.create(
            owner=owner, title="Office letter", original_name=original.name, original_path=path,
            original_mime=mime, original_sha256=hashlib.sha256(content).hexdigest(), original_size=size,
        )

        def fake_convert(source, name, supplied_mime, destination):
            assert source.read_bytes() == content and name == original.name and supplied_mime == mime
            writer = PdfWriter()
            writer.add_blank_page(width=612, height=792)
            with Path(destination).open("wb") as output:
                writer.write(output)

        def fake_ocr(args, **kwargs):
            assert args[args.index("--output-type") + 1] == "pdf"
            Path(args[-1]).write_bytes(Path(args[-2]).read_bytes())

        with patch("archive.tasks.convert_office", side_effect=fake_convert), patch("archive.tasks.subprocess.run", side_effect=fake_ocr):
            process_document(str(document.id))
        document.refresh_from_db()
        assert document.status == Document.Status.READY
        assert (media / document.archive_path).read_bytes().startswith(b"%PDF-")
        assert (media / document.original_path).read_bytes() == content
        client = Client()
        client.force_login(owner)
        exported = client.get(f"/api/documents/{document.id}/export")
        assert exported.status_code == 200
        with ZipFile(BytesIO(b"".join(exported.streaming_content))) as bundle:
            assert bundle.read("original.docx") == content
            assert bundle.read("searchable.pdf").startswith(b"%PDF-")
        with pytest.raises(InvalidDocument, match="invalid"):
            save_original(SimpleUploadedFile("invalid.docx", b"not a document"))


def test_office_converter_limits_output_and_cleans_failed_files(tmp_path, monkeypatch):
    source = tmp_path / "source.docx"
    source.write_bytes(b"office bytes")
    target = tmp_path / "converted.pdf"
    real_client = httpx.Client

    def client_with_response(body, content_type="application/pdf"):
        return real_client(transport=httpx.MockTransport(lambda request: httpx.Response(200, headers={"content-type": content_type}, content=body)))

    with override_settings(RIPIANO_CONVERTER_URL="http://converter:3000"):
        monkeypatch.setattr("archive.office.httpx.Client", lambda **kwargs: client_with_response(b"%PDF-1.4\nmock"))
        convert_office(source, source.name, OFFICE_TYPES[".docx"][0], target)
        assert target.read_bytes().startswith(b"%PDF-")
        target.unlink()
        monkeypatch.setattr("archive.office.httpx.Client", lambda **kwargs: client_with_response(b"not pdf"))
        with pytest.raises(OfficeConversionError, match="invalid PDF"):
            convert_office(source, source.name, OFFICE_TYPES[".docx"][0], target)
        assert not target.exists()
