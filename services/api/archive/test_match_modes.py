from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from archive.classification import apply_rules, rule_matches, validate_pattern
from archive.models import ClassificationRule, Correspondent, Document, DocumentTag, FilingRule, Tag

TEXT = "fattura n. 2026/115 — enel energia spa — importo 120,00 eur — scadenza 30/11/2026".casefold()


@pytest.mark.parametrize(("pattern", "match", "expected"), [
    ("enel energia", "phrase", True),
    ("energia enel", "phrase", False),
    ("acea enel", "any", True),
    ("acea hera", "any", False),
    ("enel fattura", "all", True),
    ("enel acea", "all", False),
    ("ener", "any", False),  # whole words only
    (r"fattura n\. \d{4}/\d+", "regex", True),
    (r"^bolletta", "regex", False),
    ("enell energya", "fuzzy", True),
    ("telecom italia", "fuzzy", False),
])
def test_each_match_mode(pattern, match, expected):
    assert rule_matches(pattern, match, "text", "", TEXT) is expected


def test_unsafe_or_invalid_patterns_are_refused():
    assert "not a valid" in validate_pattern("fattura (", "regex")
    assert "empty text" in validate_pattern("a*", "regex")
    assert "up to 6 words" in validate_pattern("one two three four five six seven", "fuzzy")
    assert validate_pattern("---", "any") == "Add at least one word"
    assert validate_pattern("x", "magic") == "Choose how the rule matches"
    assert validate_pattern(r"\d{4}", "regex") == ""


@pytest.mark.django_db
def test_rules_with_match_modes_file_documents_through_the_api():
    owner = get_user_model().objects.create_user("owner", password="secure-password-1")
    bills = Tag.objects.create(owner=owner, name="Bills")
    enel = Correspondent.objects.create(owner=owner, name="Enel")
    client = Client()
    client.force_login(owner)
    with patch("archive.metadata_views.reclassify_tag_candidates.delay") as queued:
        created = client.post("/api/rules", {"tag_id": str(bills.id), "pattern": r"fattura n\. \d+", "match": "regex"}, content_type="application/json")
    assert created.status_code == 201 and created.json()["match"] == "regex"
    assert queued.call_args[0][2] == [{"pattern": r"fattura n\. \d+", "field": "either", "match": "regex"}]
    assert client.post("/api/rules", {"tag_id": str(bills.id), "pattern": "(", "match": "regex"}, content_type="application/json").status_code == 400
    with patch("archive.metadata_views.reclassify_filing_candidates.delay"):
        filing = client.post("/api/filing-rules", {"kind": "correspondent", "target_id": str(enel.id), "pattern": "enell energya", "match": "fuzzy"}, content_type="application/json")
    assert filing.status_code == 201, filing.json()
    document = Document.objects.create(owner=owner, title="Scan 12", original_name="s.pdf", original_path="originals/aa/s.pdf", original_mime="application/pdf",
                                       original_sha256="0" * 64, original_size=1, status=Document.Status.READY, extracted_text=TEXT, processed_at=timezone.now())
    apply_rules(document)
    document.refresh_from_db()
    assert document.correspondent == enel and DocumentTag.objects.filter(document=document, tag=bills).exists()
    assert set(ClassificationRule.objects.values_list("match", flat=True)) == {"regex"} and FilingRule.objects.get().match == "fuzzy"


def test_slow_patterns_are_cut_off_instead_of_blocking_a_worker():
    import time

    hostile = [("((a+))+b", "a" * 5000), ("(a|a)*b", "a" * 5000), (r"\d+\d+\d+;", "1" * 50000), (r"\s*\s*\s*\s*x", " " * 50000)]
    started = time.monotonic()
    for pattern, text in hostile:
        assert rule_matches(pattern, "regex", "text", "", text) is False
    assert time.monotonic() - started < 5
    started = time.monotonic()
    assert rule_matches("a b c d e f", "fuzzy", "text", "", " ".join(["x"] * 20000)) is False
    assert time.monotonic() - started < 5


def test_regex_rules_follow_full_case_folding():
    assert rule_matches("Straße", "regex", "text", "", "strasse 12".casefold()) is True
    assert rule_matches("Straße", "phrase", "text", "", "STRASSE 12".casefold()) is True
