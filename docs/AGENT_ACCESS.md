# Agent access

Ripiano serves MCP at the same origin as the PWA, under `/mcp`. The owner signs in to Ripiano, opens **Agents**, and creates a named grant. The token is displayed once. Paste it into the MCP client as a bearer token; never give the client the owner's password. Create a different grant for each client or device. The first implementation uses manual tokens, so clients that require an automatic OAuth sign-in flow are not yet supported.

Permissions are checked on every call:

| Permission | Tools | Data exposed |
| --- | --- | --- |
| Find document titles and tags | `search_documents` | Titles, dates, status, tags, senders, and document types. Search matches titles only unless OCR-text permission is also granted. |
| Read OCR text | `get_document_text`, `semantic_search` | Text of a selected document in 20,000-character pages. Also enables full-text search in `search_documents` when that tool is granted. `semantic_search` (only while the optional semantic search is on) returns the passages most related in meaning to a question, best passage per document, within the grant's document filter. |
| Add or remove tags | `list_tags`, `change_document_tags` | Tag names and explicit changes to selected documents. Other tags stay in place. Tags can be given by ID or by exact name (any case, the owner's tags only); a name that matches several tags is refused. |
| Set sender and document type | `list_filing_options`, `set_document_filing` | Existing sender/type names and one-field changes to selected documents. Human and input-rule choices cannot be replaced. |

Optionally restrict the grant to documents carrying one exact tag. Nested child tags do not broaden an agent grant when someone moves a tag in the hierarchy. The restriction is checked on every document call. Taxonomy names returned by `list_tags` and `list_filing_options` remain account-wide when those permissions are granted, even for a tag-restricted agent. Sender/type choices made by an agent are marked as such in the document and survive phrase-rule reclassification; a human can correct them. Grants expire after 1–365 days and can be revoked immediately in Ripiano. The activity list records agent name, action, document ID, outcome, and time; it does not store document text. A revoked token cannot be recovered or reused. When Ripiano ended a grant rather than its owner, the agents list says why in `revoked_reason`: `password_changed` (the owner's password was changed or reset, D11) or `account_off` (the account was turned off, D9); it is `null` for a grant revoked by hand or still active. Revoked and expired agents are listed under a closed **Revoked or expired (N)** group; **Remove** deletes such an agent together with its activity-log entries (the privacy-friendlier choice: nothing about what it read is kept). Because the log is the audit trail, **Remove** asks for the owner's password, like creating an agent (docs/DECISIONS.md D10): `DELETE /api/agents/<id>?forget=1` with the JSON body `{"password": "..."}`. A missing or malformed body answers 400 `Invalid JSON`; a wrong password answers 400 `Your password is not correct`; too many wrong attempts answer 429 `Too many attempts. Wait a few minutes and try again.` (failed attempts count towards the sign-in limit); an agent that is still active answers 409 `Revoke this agent before removing it`. Revoking (`DELETE /api/agents/<id>` without `forget`) needs no password. Changes it made remain in each document's own history.

The MCP transport uses the [official Python SDK's Streamable HTTP and bearer authentication](https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/docs/run/authorization.md). Ripiano stores a SHA-256 hash of each high-entropy token. The MCP container has read-only access to the media volume and only the web service is published by Compose. Use HTTPS through the NAS reverse proxy or Tailscale to reach it from a Mac or Pi. The local test origin can use HTTP; production settings require HTTPS.

Ripiano itself sends no document content to an AI provider. A client that calls `get_document_text` receives that content and may forward it to its model provider. A locally hosted model avoids that provider transfer, but a work-managed computer may still be monitored by its administrator. Give cloud clients only the permissions and document filter you intend.

## Test with a client

The MCP URL is shown on the token card. A compatible client must send `Authorization: Bearer <token>` to that URL. The [SDK client transport guide](https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/docs/client/transports.md) shows how to provide the header through `httpx2.AsyncClient`. After connecting, `tools/list` contains only tools covered by that grant; a call to another tool returns a permission error. Revoking the grant makes the next request return HTTP 401.

## Who can connect agents, and tags that guard other agents

Every signed-in person can create agents for their own archive under **Agents**; an agent only ever sees its creator's documents, and only that person sees its grants and activity. Creating an agent asks for your password, and changing your password revokes every agent (and every personal API token, public share link, and bundle; docs/DECISIONS.md D11), so a stolen session cannot leave a long-lived agent behind. An admin resetting your password, or turning your account off, does the same; turning the account on again does not bring old agents, tokens, or sessions back. Turning semantic search on or off stays with the archive owner.

A tag used as an agent's document filter decides what that agent may read. To keep one agent from widening or narrowing another agent's view, an agent can never add or remove a tag that is the filter of another active agent; only a person can. Its own filter tag and ordinary tags are unaffected. Requests an agent was refused still name the document in the owner's activity log.

## Workflows started by an agent's change

An agent's tag, sender, or type change can make one of your workflows match. Such a run still does what stays inside your archive (tags, sender, type, fields, title, a note, a follow-up), but it never discloses the document: **sharing with people or groups, the webhook, and the email are held back** (docs/DECISIONS.md D12). Otherwise an agent that may only add tags could cause a private document to be shared or sent out.

Exactly when something is held back:

- **The run the agent's own change starts** ("when updated" workflows): always.
- **Any later run, whoever or whatever starts it** — the daily pass of a scheduled workflow, your next edit of the document, a bulk change — **while the workflow's tag, sender, or type condition is met by a value an agent set.** Ripiano remembers who set each tag, sender, and type. Saving the document with its tag list unchanged, or editing its title, does not make the agent's tag yours.
- What such a run files itself (tags it adds, a sender or type it sets) is marked as coming from an agent too, so a second workflow that matches on it is held back in the same way.

What releases it:

- **You set the value yourself:** add that tag to the document (the one-tap add, the bulk "add tag" action, or remove it and add it again), or choose the sender or type yourself. Your change starts "when updated" workflows as usual, now with nothing held back; a scheduled workflow completes on its next daily pass.
- **Run now** on the workflow for that document: your explicit choice, nothing is held back.

A held-back run does not use up the workflow's one-time webhook and email: they are sent once, with the first run that is allowed to send them. The note a workflow adds is still added only once. The workflow's run history says what was held back ("skipped sharing (an agent made the change; …)", "skipped webhook …", "skipped email …") and the API marks the run `held_back`; a run in which nothing else happened is listed as *skipped*. Nothing is sent later by itself. Workflows whose conditions do not involve an agent-set tag, sender, or type run for your own changes exactly as before.
