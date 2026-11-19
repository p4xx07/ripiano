# Security

Ripiano handles private documents and is currently a development build. Do not use the draft branch as a production archive for irreplaceable files. The release gate requires a security review and a restored NAS backup before personal documents are added.

If you find a vulnerability, use GitHub's private vulnerability reporting for this repository when it is available, or contact the repository owner privately. Do not publish a real document, an access token, a bot token, a backup, or an exploitable proof of concept in a public issue. A report should include the affected commit, a synthetic reproduction, and the practical impact.

Expected boundaries: native scan uploads go only to the operator's configured Ripiano HTTPS origin; named MCP grants are scoped and revocable; Telegram is opt-in and handles forwarded files before Ripiano receives them; the optional local classifier sends OCR text to the operator's configured Ollama endpoint. Review these boundaries when changing intake or agent code.
