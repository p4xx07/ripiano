# Agent access

Ripiano serves MCP at the same origin as the PWA, under `/mcp`. The owner signs in to Ripiano, opens **Agents**, and creates a named grant. The token is displayed once. Paste it into the MCP client as a bearer token; never give the client the owner's password. Create a different grant for each client or device. The first implementation uses manual tokens, so clients that require an automatic OAuth sign-in flow are not yet supported.

Permissions are checked on every call:

| Permission | Tools | Data exposed |
| --- | --- | --- |
| Find document titles and tags | `search_documents` | Titles, dates, status, tags, senders, and document types. Search matches titles only unless OCR-text permission is also granted. |
| Read OCR text | `get_document_text` | Text of a selected document in 20,000-character pages. Also enables full-text search in `search_documents` when that tool is granted. |
| Add or remove tags | `list_tags`, `change_document_tags` | Tag names and explicit changes to selected documents. Other tags stay in place. |
| Set sender and document type | `list_filing_options`, `set_document_filing` | Existing sender/type names and one-field changes to selected documents. Human and input-rule choices cannot be replaced. |

Optionally restrict the grant to documents carrying one exact tag. Nested child tags do not broaden an agent grant when someone moves a tag in the hierarchy. The restriction is checked on every document call. Taxonomy names returned by `list_tags` and `list_filing_options` remain account-wide when those permissions are granted, even for a tag-restricted agent. Sender/type choices made by an agent are marked as such in the document and survive phrase-rule reclassification; a human can correct them. Grants expire after 1–365 days and can be revoked immediately in Ripiano. The activity list records agent name, action, document ID, outcome, and time; it does not store document text. A revoked token cannot be recovered or reused.

The MCP transport uses the [official Python SDK's Streamable HTTP and bearer authentication](https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/docs/run/authorization.md). Ripiano stores a SHA-256 hash of each high-entropy token. The MCP container has read-only access to the media volume and only the web service is published by Compose. Use HTTPS through the NAS reverse proxy or Tailscale to reach it from a Mac or Pi. The local test origin can use HTTP; production settings require HTTPS.

Ripiano itself sends no document content to an AI provider. A client that calls `get_document_text` receives that content and may forward it to its model provider. A locally hosted model avoids that provider transfer, but a work-managed computer may still be monitored by its administrator. Give cloud clients only the permissions and document filter you intend.

## Test with a client

The MCP URL is shown on the token card. A compatible client must send `Authorization: Bearer <token>` to that URL. The [SDK client transport guide](https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/docs/client/transports.md) shows how to provide the header through `httpx2.AsyncClient`. After connecting, `tools/list` contains only tools covered by that grant; a call to another tool returns a permission error. Revoking the grant makes the next request return HTTP 401.
