# Interim manual QA — c8a4a37

This is an interim watched-folder review. It is not a release score: native Android real-device validation and the Paperless parity hard gate remain open.

## manualQa

### surfaceEvidence

| scenario id | criterion | surface | exact invocation | verdict | artifactRefs |
| --- | --- | --- | --- | --- | --- |
| WF-001 | R1 safe intake / health | running Docker stack | `curl -i --max-time 10 http://localhost:18080/healthz` | PASS | `A1`, `A2` |
| WF-002 | R1 external input / watched folder | running Docker stack + API | `docker logs --since 10m ripiano-watched_folder-1`; authenticated `GET /api/documents?q=from-nas` | PASS | `A3`, `A4` |
| WF-003 | R1 recovery / idempotency | watched-folder service restart + archive query | restart was performed on the synthetic watcher; query found one exact `from-nas.png` record with `source=folder`, `status=ready` | PASS | `A3`, `A4` |
| WF-004 | test evidence | API test suite | `RIPIANO_DEBUG=1 uv run pytest -q archive/test_watch_folder.py` | PASS | `A5` |

### adversarialCases

| scenario id | criterion | adversarial class | expected behavior | verdict | artifactRefs |
| --- | --- | --- | --- | --- | --- |
| WF-A01 | input boundary | unsupported extension | `.txt` is ignored and does not enter the archive | PASS | `A6` |
| WF-A02 | input boundary | symlink escape | a symlink in the watched folder is ignored; no linked file is imported | PASS | `A6` |
| WF-A03 | duplicate/restart | same stable file after watcher restart | one source-keyed document remains; no duplicate is created | PASS | `A3`, `A4` |
| WF-A04 | incomplete-write guard | file changes between observed passes | no import occurs until size and mtime are stable; covered by the focused test | PASS | `A5` |
| WF-A05 | path safety | path traversal/symlinked path | resolved path must remain below the watched root and `O_NOFOLLOW` is used | PASS | `A7` |

## artifactRefs

| id | kind | description | path |
| --- | --- | --- | --- |
| A1 | HTTP transcript | `/healthz` returned HTTP 200 and JSON status ok | `qa-artifacts/c8a4a37/healthz.txt` |
| A2 | runtime transcript | API, database, broker, and watcher containers were running; API healthy | `qa-artifacts/c8a4a37/stack.txt` |
| A3 | service transcript | watcher imported one synthetic NAS document | `qa-artifacts/c8a4a37/watch-folder.log` |
| A4 | HTTP/data transcript | authenticated archive query found exactly one ready folder document | `qa-artifacts/c8a4a37/watched-folder-docs.json` |
| A5 | test transcript | focused watcher test passed | `qa-artifacts/c8a4a37/test-watch-folder.txt` |
| A6 | adversarial transcript | unsupported file and symlink produced no imported records | `qa-artifacts/c8a4a37/adversarial.json` |
| A7 | source inspection | path confinement, symlink rejection, stable fingerprint, and idempotency implementation | `services/api/archive/management/commands/watch_folder.py:29` |

## Findings

No watched-folder correctness defect was observed in this pass. The service uses a read-only mount in Compose, waits for a stable `(size, mtime_ns)` pair, rejects symlinks and paths escaping the root, and keys imports by owner/source/path/content. The test was synthetic and did not validate Synology ACL behavior or a physical NAS mount. The `RIPIANO_WATCH_PATH` directory must exist and be readable before enabling the profile.
