# Optional local Mac classifier

This worker connects to Ripiano through MCP and asks a locally running Ollama model to choose from existing tags, senders, and document types. It is optional: the NAS keeps importing, OCRing, searching, and applying phrase rules while the Mac is off. The worker remembers applied tag decisions and sender/type decisions in a local SQLite file, so the next run catches up after missed days. Sender/type decisions are reconsidered when OCR is reprocessed, the title or filing choices change, or the configured model name changes. It stores no document text in that file.

The model must be installed in Ollama separately. Ripiano does not download a model or send documents to a hosted model endpoint by default. The worker accepts only loopback Ollama URLs unless `allow_remote_model` is explicitly set. A work-managed Mac may still be monitored by its administrator.

## Setup on the Mac

1. Install `uv` and Ollama, and install a model of your choice in Ollama. Verify the model works locally before scheduling.
2. In Ripiano, create a named agent with **Find document titles and tags** and **Read OCR text**. Grant **Add or remove tags** for tag filing and/or **Set sender and document type** for those fields. These are separate permissions; grant only the fields the worker may change. For a restricted worker, set the document tag filter. Copy the one-time token.
3. Save the token to `~/.local/share/ripiano-classifier/token` with file permissions `0600`.
4. Create `~/.config/ripiano-classifier/config.json`:

```json
{
  "mcp_url": "https://your-ripiano-host/mcp",
  "model": "your-installed-ollama-model",
  "ollama_url": "http://127.0.0.1:11434",
  "auto_apply": "0",
  "auto_apply_filing": "0"
}
```

5. From this directory, run `uv run python classify.py`. The first run is a dry run and prints counts only. Set `"auto_apply": "1"` to add high-confidence tags; set `"auto_apply_filing": "1"` separately to fill empty sender and document-type fields. The worker chooses only existing filing values, never overwrites a field already set in the document, and the MCP server protects human and input-rule choices and removed tags. If another agent fills a field during a run, the worker counts it as already filled and continues with later documents. Test on representative documents before enabling either write setting.
6. Run `uv run python make_launch_agent.py` to generate a macOS LaunchAgent scheduled daily at 10:00 local time and at login. Load it using the `launchctl bootstrap` command printed by the script. The token is kept in its separate file, not in the plist.

The script reads `RIPIANO_MCP_URL`, `OLLAMA_MODEL`, `OLLAMA_URL`, `RIPIANO_TOKEN_FILE`, `RIPIANO_AUTO_APPLY`, `RIPIANO_AUTO_APPLY_FILING`, and `RIPIANO_STATE_FILE` environment variables as overrides. Its state defaults to `~/.local/share/ripiano-classifier/state.sqlite3`. It never creates new tags, senders, or types, deletes originals, or removes existing tags. Tag decisions are remembered per document; to revisit old tags after changing the taxonomy, delete the local state database while the worker is stopped. Sender/type decisions use a fingerprint of the OCR processing time, title, current fields, choices, and configured model name, so changing those inputs triggers a new proposal without deleting state. Unchanged daily runs skip the OCR-text download. Applied changes remain idempotent in Ripiano.

The model's self-reported confidence is **not calibrated**. The 0.9 threshold, exact OCR evidence check, and restriction to existing filing choices are safeguards, not an accuracy guarantee. The worker fetches the first 20,000 OCR characters and sends at most 12,000 of them to the model. It offers up to 200 existing senders and 200 document types to the model. It may call the local model twice for a document when it has both tag and sender/type permissions. Review model-applied values on representative private documents before enabling unattended filing. The official [Ollama chat API](https://github.com/ollama/ollama/blob/main/docs/api.md) accepts a JSON schema in `format`; the worker validates the returned IDs and evidence again before writing through MCP.
