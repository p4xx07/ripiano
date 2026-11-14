# Optional local Mac classifier

This worker connects to Ripiano through MCP and asks a locally running Ollama model to choose from existing tags. It is optional: the NAS keeps importing, OCRing, searching, and applying phrase rules while the Mac is off. The worker remembers processed document IDs in a local SQLite file, so the next run catches up after missed days. It stores no document text in that file.

The model must be installed in Ollama separately. Ripiano does not download a model or send documents to a hosted model endpoint by default. The worker accepts only loopback Ollama URLs unless `allow_remote_model` is explicitly set. A work-managed Mac may still be monitored by its administrator.

## Setup on the Mac

1. Install `uv` and Ollama, and install a model of your choice in Ollama. Verify the model works locally before scheduling.
2. In Ripiano, create a named agent with **Find document titles and tags**, **Read OCR text**, and **Add or remove tags**. For a restricted worker, set the document tag filter. Copy the one-time token.
3. Save the token to `~/.local/share/ripiano-classifier/token` with file permissions `0600`.
4. Create `~/.config/ripiano-classifier/config.json`:

```json
{
  "mcp_url": "https://your-ripiano-host/mcp",
  "model": "your-installed-ollama-model",
  "ollama_url": "http://127.0.0.1:11434",
  "auto_apply": "0"
}
```

5. From this directory, run `uv run python classify.py`. The first run is a dry run and prints counts only. Set `"auto_apply": "1"` to add high-confidence tags. User corrections are preserved: a tag the user removed is not re-added by the worker.
6. Run `uv run python make_launch_agent.py` to generate a macOS LaunchAgent scheduled daily at 10:00 local time and at login. Load it using the `launchctl bootstrap` command printed by the script. The token is kept in its separate file, not in the plist.

The script reads `RIPIANO_MCP_URL`, `OLLAMA_MODEL`, `OLLAMA_URL`, `RIPIANO_TOKEN_FILE`, `RIPIANO_AUTO_APPLY`, and `RIPIANO_STATE_FILE` environment variables as overrides. Its state defaults to `~/.local/share/ripiano-classifier/state.sqlite3`. It never creates new tags, deletes originals, or removes existing tags. If you change the taxonomy and want to reclassify old files, delete the local state database while the worker is stopped; changes remain idempotent in Ripiano.

The model's self-reported confidence is **not calibrated**. The 0.9 threshold, exact OCR evidence check, and existing-tag restriction are safeguards, not an accuracy guarantee. Review model-applied tags on representative private documents before enabling unattended filing. The official [Ollama chat API](https://github.com/ollama/ollama/blob/main/docs/api.md) accepts a JSON schema in `format`; the worker validates the returned IDs and evidence again before writing through MCP.
