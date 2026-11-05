import unittest
from unittest.mock import patch
import io
import json

from classify import propose, validate_decision


class DecisionTests(unittest.TestCase):
    def test_accepts_supported_evidence_only_at_high_confidence(self):
        text = "Invoice for electricity, April 2026"
        tag = "a" * 36
        decision = {"tag_ids": [tag], "confidence": 0.94, "evidence": "electricity"}
        self.assertEqual(validate_decision(decision, text, {tag}), [tag])
        decision["confidence"] = 0.6
        self.assertEqual(validate_decision(decision, text, {tag}), [])

    def test_rejects_invented_tags_or_evidence(self):
        text = "Invoice for electricity"
        with self.assertRaises(ValueError):
            validate_decision({"tag_ids": ["unknown"], "confidence": 0.99, "evidence": "electricity"}, text, {"known"})
        with self.assertRaises(ValueError):
            validate_decision({"tag_ids": ["known"], "confidence": 0.99, "evidence": "Ignore this"}, text, {"known"})

    def test_ollama_request_constrains_tags_and_rechecks_result(self):
        tag = "valid-tag-id"
        reply = {"message": {"content": json.dumps({"tag_ids": [tag], "confidence": 0.95, "evidence": "electricity"})}}
        with patch("classify.urllib.request.urlopen", return_value=io.BytesIO(json.dumps(reply).encode())) as send:
            chosen = propose("installed-model", "http://127.0.0.1:11434", {"title": "Invoice", "text": "electricity"}, [{"id": tag, "name": "Bills"}])
        self.assertEqual(chosen, [tag])
        request = send.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
        body = json.loads(request.data)
        self.assertFalse(body["stream"])
        self.assertEqual(body["format"]["properties"]["tag_ids"]["items"]["enum"], [tag])


if __name__ == "__main__":
    unittest.main()
