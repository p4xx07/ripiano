"""Judge 1, round 10 (.omo/evidence/judge-1-round-10-report.md), API side.

M1: suggestions for the parts of a split scan were driven by the words of the scan's file name. L2: a plain
archive number finds its document. L3: a sticker code typed without its prefix is found.
"""

import hashlib
import itertools
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.utils import timezone

from archive.auto_filing import apply_learned_filing
from archive.classification import _terms, file_name_words, filing_suggestions
from archive.learning import _examples, features
from archive.models import (AutoFilingPolicy, Correspondent, Document, DocumentTag, DocumentType, DocumentVersion, FilingModel, Location,
                            PhysicalCopy, Tag)

User = get_user_model()
PASSWORD = "secure-password-1"
counter = itertools.count()


def document(owner, name, text, title=None, **fields):
    digest = hashlib.sha256(f"{name}{next(counter)}".encode()).hexdigest()
    return Document.objects.create(
        owner=owner, title=title or name.rsplit(".", 1)[0], original_name=name, original_path=f"originals/{digest[:2]}/{digest}.pdf",
        original_mime="application/pdf", original_sha256=digest, original_size=10, status=Document.Status.READY, extracted_text=text, **fields)


def split_scan(owner, stem, texts, title=None):
    """The documents the barcode split leaves behind: the hidden scan and one part per text (tasks._split)."""
    scan = document(owner, f"{stem}.pdf", " ".join(texts), title=title, is_split_source=True)
    parts = [document(owner, f"{stem[:80]}-{number}.pdf", text, title=f"{scan.title} ({number}/{len(texts)})", split_parent=scan)
             for number, text in enumerate(texts, start=1)]
    return scan, parts


def file_as_bank_letter(owner, target):
    sender = Correspondent.objects.create(owner=owner, name="Quokka Meadow Bank")
    kind = DocumentType.objects.create(owner=owner, name="Letter")
    tag = Tag.objects.create(owner=owner, name="bank")
    target.correspondent, target.correspondent_origin = sender, Document.FilingOrigin.MANUAL
    target.document_type, target.document_type_origin = kind, Document.FilingOrigin.MANUAL
    target.save()
    DocumentTag.objects.create(document=target, tag=tag, origin=DocumentTag.Origin.MANUAL)
    return sender, kind, tag


NOTHING = {"tags": [], "correspondents": [], "document_types": []}


@pytest.mark.django_db
def test_parts_of_one_scan_are_not_suggested_each_others_filing_because_of_the_scan_file_name():
    """M1 as reported: the invoice in part (2/2) was offered the bank letter's sender, type and tag."""
    owner = User.objects.create_user("owner", password=PASSWORD)
    _, (letter, invoice) = split_scan(owner, "barcode-batch-desktop", ["Separator test letter quokka meadow", "Separator test invoice wombat harbour"])
    file_as_bank_letter(owner, letter)

    assert filing_suggestions(invoice) == NOTHING

    # A part whose text really is like the letter's is still suggested, for words of the text only.
    _, (_, second_letter) = split_scan(owner, "barcode-batch-mobile", ["Cover page", "Separator test letter quokka meadow branch"])
    suggestions = filing_suggestions(second_letter)
    assert [item["name"] for item in suggestions["correspondents"]] == ["Quokka Meadow Bank"]
    assert [item["name"] for item in suggestions["document_types"]] == ["Letter"]
    assert [item["name"] for item in suggestions["tags"]] == ["bank"]
    shared = set(suggestions["tags"][0]["shared_terms"])
    assert shared <= {"separator", "test", "letter", "quokka", "meadow"} and not shared & {"barcode", "batch", "desktop", "mobile"}


@pytest.mark.django_db
def test_file_name_words_are_ignored_in_a_title_wherever_the_name_came_from():
    owner = User.objects.create_user("owner", password=PASSWORD)
    body = "Quarterly statement for the meadow account"

    # A scan name longer than the part file name keeps (80 characters): the part's own file name lost the last words.
    long_stem = "household-paperwork-scanned-upstairs-" + "x" * 40 + "-kitchen-drawer-autumn"
    _, (first, second) = split_scan(owner, long_stem, [body + " in spring", "Minutes of the residents meeting about heating costs"])
    assert "autumn" not in _terms(first.original_name)  # the cut is what this case is about
    file_as_bank_letter(owner, first)
    assert filing_suggestions(second) == NOTHING

    # A replaced file: the title is still the first upload's file name.
    replaced = document(owner, "corrected.pdf", "Notes from the allotment committee about water", title="household paperwork kitchen drawer autumn")
    DocumentVersion.objects.create(document=replaced, number=1, note="", original_name="household paperwork kitchen drawer autumn.pdf",
                                   original_path="versions/a.pdf", original_mime="application/pdf", original_sha256="b" * 64, original_size=1,
                                   created_at=timezone.now())
    assert filing_suggestions(replaced) == NOTHING
    assert file_name_words([{"id": replaced.id, "original_name": replaced.original_name, "split_parent__original_name": None}])[replaced.id] >= {
        "corrected", "household", "paperwork", "kitchen", "drawer", "autumn"}

    # Words a person wrote into the title of a part count, and so do file-name words that are also in the text.
    first.title = "Meadow account statement (1/2)"
    first.save(update_fields=["title"])
    renamed = document(owner, "statement-scan.pdf", "Statement balance carried forward", title="Meadow account statement")
    shared = set(filing_suggestions(renamed)["tags"][0]["shared_terms"])
    assert shared == {"meadow", "account", "statement"}


@override_settings(RIPIANO_BARCODE_SEPARATOR="PATCHT", RIPIANO_BARCODE_ASN_PREFIX="ASN")
def test_codes_printed_under_control_barcodes_are_not_content_words():
    assert _terms("PATCHT ASN00042 asn 900011 Invoice wombat harbour") == {"invoice", "wombat", "harbour"}
    with override_settings(RIPIANO_BARCODE_SEPARATOR="NEXT-DOCUMENT", RIPIANO_BARCODE_ASN_PREFIX="ARCH-"):
        assert _terms("next document ARCH0042 patcht invoice") == {"patcht", "invoice"}


@pytest.mark.django_db
def test_the_learned_model_is_not_trained_or_asked_with_file_name_words():
    owner = User.objects.create_user("owner", password=PASSWORD)
    _, (letter, invoice) = split_scan(owner, "barcode-batch-desktop", ["Separator test letter quokka meadow", "Separator test invoice wombat harbour"])
    sender, _, _ = file_as_bank_letter(owner, letter)

    assert [example["terms"] for example in _examples(owner.id)] == [{"separator", "test", "letter", "quokka", "meadow"}]
    assert features(invoice.title, invoice.extracted_text, upload_words={"barcode", "batch", "desktop"}) == {"separator", "test", "invoice", "wombat", "harbour"}

    # Automatic filing and the suggestion list both hand the model the file-name words to leave out.
    AutoFilingPolicy.objects.create(owner=owner, enabled=True)
    FilingModel.objects.create(owner=owner, status=FilingModel.Status.READY, payload=b"test model", trained_at=timezone.now(),
                               metrics={"correspondents": {"ready": True, "auto_precision": 0.98, "auto_tested_suggestions": 25}})
    for target in ("archive.auto_filing", "archive.learning"):
        with patch(f"{target}._load", return_value={"trained": True}), patch(f"{target}.predict", return_value={}) as predict:
            if target == "archive.auto_filing":
                apply_learned_filing(invoice.id)
            else:
                filing_suggestions(invoice)
        assert predict.call_args.args[4] == {"barcode", "batch", "desktop"}, target


@pytest.mark.django_db
def test_a_plain_archive_number_finds_its_document():
    """L2: "900011" found nothing; only asn:900011 did."""
    owner, other = User.objects.create_user("owner", password=PASSWORD), User.objects.create_user("other", password=PASSWORD)
    numbered = document(owner, "letter.pdf", "Quokka meadow letter", asn=900011)
    document(owner, "invoice.pdf", "Wombat harbour invoice", asn=42)
    mentioned = document(owner, "note.pdf", "Reference 900011 on the envelope")
    document(other, "theirs.pdf", "Somebody else's letter", asn=900011)
    client = Client()
    client.force_login(owner)

    def found(query):
        response = client.get("/api/documents", {"q": query})
        assert response.status_code == 200, response.content
        return {item["id"] for item in response.json()["documents"]}

    assert found("900011") == {str(numbered.id), str(mentioned.id)}  # the number in a text still matches as before
    assert found("ASN00900011") == {str(numbered.id)} and found("asn 900011") == {str(numbered.id)}
    assert found("asn:900011") == {str(numbered.id)}
    assert found("9001") == set() and found("900011 letter") == set()


@pytest.mark.django_db
def test_a_sticker_code_typed_without_its_prefix_is_found():
    """L3: "MUD3PLDT" was "Sticker not found"."""
    owner, other = User.objects.create_user("owner", password=PASSWORD), User.objects.create_user("other", password=PASSWORD)
    shelf = Location.objects.create(owner=owner, name="Study shelf", sticker_code="L-RAB7CDEF")
    paper = document(owner, "letter.pdf", "Quokka meadow letter")
    PhysicalCopy.objects.create(document=paper, sticker_code="R-MUD3PLDT", location=shelf)
    PhysicalCopy.objects.create(document=document(other, "theirs.pdf", "Their letter"), sticker_code="R-ZZZZ2222")
    client = Client()
    client.force_login(owner)

    for typed in ("R-MUD3PLDT", "MUD3PLDT", "mud3pldt", "RMUD3PLDT", "r mud3pldt"):
        response = client.get(f"/api/stickers/{typed}")
        assert response.status_code == 200 and response.json()["document"]["id"] == str(paper.id), typed
    for typed in ("L-RAB7CDEF", "RAB7CDEF", "lrab7cdef"):
        response = client.get(f"/api/locations/lookup/{typed}")
        assert response.status_code == 200 and response.json()["location"]["name"] == "Study shelf", typed
    assert client.get("/api/stickers/MUD3PLD").status_code == 404  # no partial matches
    assert client.get("/api/stickers/ZZZZ2222").status_code == 404  # someone else's sticker stays unknown


@pytest.mark.django_db
def test_a_document_with_almost_no_words_gets_no_suggestions_without_loading_examples(django_assert_num_queries):
    owner = User.objects.create_user("blank-owner", password=PASSWORD)
    blank = document(owner, "scan 0001.pdf", "")
    with django_assert_num_queries(1):
        assert filing_suggestions(blank) == {"tags": [], "correspondents": [], "document_types": []}
