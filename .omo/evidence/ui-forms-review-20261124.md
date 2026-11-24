# Email, learned suggestions, and People form review — 2026-11-24

Scope: document email form, learned filing card, Storage paths explanation, and the owner's report that People still looked unstyled after the previous merge. Checked the completed diff separately from implementation and used a clean Chrome context on the isolated synthetic stack.

## Findings

- **Email form:** `EmailDocumentPanel` omitted the shared `detail-label` class on three `Field` components. The labels and controls therefore used browser defaults. The message textarea also lacked the matching border, padding, and focus style. The form now uses the shared field layout, and the API exposes the configured SMTP From address so the form can show the actual sender. The account's email remains Reply-To when present. The local SMTP host is a fake mail server, so local test sends do not reach the internet.
- **Learned suggestions:** `.tag-create-card label` had higher specificity than `.learning-auto-option`, putting the checkbox above its text. The card now has a two-column checkbox row and compact, full-width per-field results. The copy starts with the action needed to teach Ripiano and explains that turning on automatic filing makes no changes until its quality gates are met.
- **People:** the current `PeoplePanel` already applies `detail-label`. In clean Chrome, all four fields compute to `display: grid` and their inputs span the label width. The owner's screenshot shows an older render; a still-open PWA tab is the likely cause. No People source change was needed. Reload the existing tab to activate the newer client bundle.
- **Storage paths:** the UI now says that a template only shapes a later **Build browse copy**, and it names both ways to assign it: a document's More filing options or a workflow. Originals stay in place.

## Evidence and verification

- API `archive/test_bundles.py` and `archive/test_api_contract.py`: **6 passed**. The test asserts the GET From address, the actual sent From address, and Reply-To.
- `npx tsc --noEmit -p .`: exit 0. `npm run build`: exit 0; the existing Vite large-chunk advisory remains.
- Isolated Chrome: email form's three labels computed to `grid`, textarea border to `solid`, and the configured From address appeared. Screenshot: [email-fixed.png](../../qa-artifacts/20261124-ui-forms/email-fixed.png).
- Isolated Chrome: learned option computed to two columns on desktop and mobile, with no horizontal overflow. Screenshots: [desktop](../../qa-artifacts/20261124-ui-forms/learning-desktop.png), [mobile](../../qa-artifacts/20261124-ui-forms/learning-mobile.png).
- Playwright `e2e/learning.spec.ts`: **1 passed, 1 skipped** on mobile and **1 passed, 1 skipped** on desktop. The layout assertion checks that the checkbox and its title share a row and the panel does not overflow.
- Isolated Chrome People fields: `display: grid`, full-width inputs. Screenshot: [people-clean.png](../../qa-artifacts/20261124-ui-forms/people-clean.png).
- `git diff --check`: exit 0.

The original open tab could not be inspected directly in this session; the stale-client diagnosis is an inference from its screenshot and the clean-browser result. There is no known high or medium finding in these changes. The local email service remains a fake SMTP test server.
