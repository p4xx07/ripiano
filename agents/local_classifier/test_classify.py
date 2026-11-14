import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import io
import json

from classify import propose, propose_filing, run, validate_decision, validate_filing_decision


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


class FilingTests(unittest.TestCase):
    def test_filing_choice_requires_an_existing_id_and_exact_ocr_evidence(self):
        decision = {"correspondent_id": "council-id", "document_type_id": "notice-id",
                    "confidence": 0.95, "evidence": "Council tax notice"}
        text = "Council tax notice for 2026"
        self.assertEqual(validate_filing_decision(decision, text, {"council-id"}, {"notice-id"}),
                         {"correspondent_id": "council-id", "document_type_id": "notice-id"})
        with self.assertRaises(ValueError):
            validate_filing_decision({**decision, "document_type_id": "invented"}, text, {"council-id"}, {"notice-id"})
        with self.assertRaises(ValueError):
            validate_filing_decision({**decision, "evidence": "not in the document"}, text, {"council-id"}, {"notice-id"})
        self.assertEqual(validate_filing_decision({**decision, "confidence": 0.7}, text,
                                                  {"council-id"}, {"notice-id"}), {})

    def test_ollama_schema_excludes_already_set_fields(self):
        decision = {"correspondent_id": "", "document_type_id": "notice-id",
                    "confidence": 0.96, "evidence": "tax notice"}
        reply = {"message": {"content": json.dumps(decision)}}
        with patch("classify.urllib.request.urlopen", return_value=io.BytesIO(json.dumps(reply).encode())) as send:
            chosen = propose_filing("local-model", "http://127.0.0.1:11434",
                                    {"title": "Tax", "text": "A tax notice from the council"},
                                    [], [{"id": "notice-id", "name": "Notice"}])
        self.assertEqual(chosen["document_type_id"], "notice-id")
        body = json.loads(send.call_args.args[0].data)
        self.assertEqual(body["format"]["properties"]["correspondent_id"]["enum"], [""])
        self.assertEqual(body["format"]["properties"]["document_type_id"]["enum"], ["", "notice-id"])

    def test_daily_worker_requires_separate_consent_and_remembers_applied_filing(self):
        document = {"id": "document-id", "title": "Council notice", "status": "ready",
                    "correspondent": None, "document_type": {"id": "already-set", "name": "Notice"}}
        called = []
        proposed = []

        class FakeClient:
            async def list_tools(self):
                names = ["search_documents", "get_document_text", "list_filing_options", "set_document_filing"]
                return SimpleNamespace(tools=[SimpleNamespace(name=name) for name in names])

        class FakeContext:
            async def __aenter__(self):
                return FakeClient()

            async def __aexit__(self, *_args):
                return False

        async def fake_call(_client, name, arguments):
            called.append((name, arguments))
            if name == "list_filing_options":
                return {"correspondents": [{"id": "council-id", "name": "Council"}],
                        "document_types": [{"id": "notice-id", "name": "Notice"}], "next_offset": None}
            if name == "search_documents":
                return {"documents": [document], "next_offset": None}
            if name == "get_document_text":
                return {"text": "Council tax notice for 2026"}
            if name == "set_document_filing":
                return {"document_id": "document-id", **arguments}
            raise AssertionError(name)

        def fake_proposal(_model, _url, _document, senders, types):
            proposed.append((senders, types))
            return {"correspondent_id": "council-id", "document_type_id": ""}

        with tempfile.TemporaryDirectory() as directory, patch.dict("classify.os.environ", {"RIPIANO_STATE_FILE": str(Path(directory) / "state.db")}):
            with patch("classify.config", return_value=("https://archive.example/mcp", "local-model", "rpa_token",
                                                       "http://127.0.0.1:11434", False, False)) as settings, \
                 patch("classify.Client", return_value=FakeContext()), \
                 patch("classify.streamable_http_client", return_value=object()), \
                 patch("classify.call", side_effect=fake_call), \
                 patch("classify.propose_filing", side_effect=fake_proposal):
                asyncio.run(run())
                self.assertFalse(any(name == "set_document_filing" for name, _ in called))
                settings.return_value = ("https://archive.example/mcp", "local-model", "rpa_token",
                                         "http://127.0.0.1:11434", False, True)
                asyncio.run(run())
                self.assertEqual([args for name, args in called if name == "set_document_filing"],
                                 [{"document_id": "document-id", "correspondent_id": "council-id", "only_if_empty": True}])
                asyncio.run(run())
        self.assertEqual(len(proposed), 2)
        self.assertEqual(sum(name == "get_document_text" for name, _ in called), 2)
        self.assertEqual(proposed[0][1], [])  # the existing document type was never offered for replacement


if __name__ == "__main__":
    unittest.main()
