import { expect, test, type Page, type Route } from "@playwright/test";
import { deflateSync } from "node:zlib";

// Round-9 judge regressions owned by the web slice: the backup start keeps focus and announces start and outcome
// (J2 M2), an Inbox OCR retry stays on screen and announces its result (J2 M3), field hints are descriptions, not part
// of the name (J2/J3 L1), a found sticker is announced, a wrong setup key marks the key field, the agent form resets,
// one tag-create button, kept drafts survive another person signing in and show the person's own value beside a newer
// one, a save refused with 409 shows the same conflict choice (J2 M1, prepared before the API check lands), the
// semantic-search warning is one sentence, and a revoked agent says why (J3 L2, L3). States that are hard to reach on
// a shared stack are simulated with page.route.
const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

test.use({ serviceWorkers: "block" });

async function signIn(page: Page) {
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
}

const FAKE_ID = "00000000-0000-4000-8000-0000000000f9";

function fakeDocument(overrides: Record<string, unknown> = {}) {
  return {
    id: FAKE_ID, title: "Round nine letter", original_name: "letter.pdf", version_number: 1,
    duplicate_of: null, duplicate_reviewed_at: null, source: "web", status: "ready", archive_available: true,
    error: "", created_at: "2026-11-19T09:00:00Z", trashed_at: null, document_date: null, correspondent: null,
    document_type: null, correspondent_origin: "none", document_type_origin: "none", action_status: "none",
    action_due_date: null, action_note: "", action_completed_at: null, tags: [], physical_copies: [], snippet: "",
    snippet_source: null, email: null, asn: null, split_parent: null, is_split_source: false, storage_path: null,
    access: "owner", shared_by: null, processing_warning: null, warning: "", processing_warning_reviewed_at: null,
    ...overrides,
  };
}

async function csrf(page: Page) {
  return { "X-CSRFToken": (await page.context().cookies()).find((cookie) => cookie.name === "csrftoken")?.value ?? "" };
}

/** A small PNG whose pixels depend on `seed`, so these tests never make exact copies of other specs' files. */
function uniquePng(seed: string) {
  const crcTable = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
  const crc = (bytes: Buffer) => { let c = 0xffffffff; for (const byte of bytes) c = crcTable[(c ^ byte) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
  const chunk = (type: string, data: Buffer) => {
    const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
    const out = Buffer.alloc(8 + data.length + 4);
    out.writeUInt32BE(data.length, 0); body.copy(out, 4); out.writeUInt32BE(crc(body), 8 + data.length);
    return out;
  };
  const width = 64, height = 64;
  let hash = 2166136261;
  for (const char of seed) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619) >>> 0;
  const rows = Buffer.alloc((width * 3 + 1) * height);
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const offset = y * (width * 3 + 1) + 1 + x * 3;
    rows[offset] = (hash >>> 16) & 0xff; rows[offset + 1] = (x * 4) & 0xff; rows[offset + 2] = (y * 4 + (hash & 0xff)) & 0xff;
  }
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0); header.writeUInt32BE(height, 4); header[8] = 8; header[9] = 2;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", header), chunk("IDAT", deflateSync(rows)), chunk("IEND", Buffer.alloc(0))]);
}

async function uploadReady(page: Page, name: string): Promise<string> {
  const response = await page.request.post("/api/documents", {
    headers: await csrf(page),
    multipart: { document: { name: `${name}.png`, mimeType: "image/png", buffer: uniquePng(name) } },
  });
  expect(response.status()).toBe(202);
  const id = (await response.json()).id as string;
  await expect.poll(async () => (await (await page.request.get(`/api/documents/${id}`)).json()).status, { timeout: 90000 }).toBe("ready");
  return id;
}

test("Back up now keeps focus on the button and announces the start and the outcome", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  let state: "none" | "running" | "complete" = "none";
  const run = (status: string) => ({ id: "r9-backup", status, trigger: "manual", snapshot_name: status === "complete" ? "snapshot-r9" : "", error: "", created_at: new Date().toISOString(), can_cancel: false, can_retry: false, retry_of: null });
  let polls = 0;
  await page.route("**/api/backups", (route: Route) => {
    if (route.request().method() === "POST") {
      state = "running";
      return route.fulfill({ status: 202, json: { id: "r9-backup", status: "pending" } });
    }
    if (state === "running" && ++polls >= 2) state = "complete";
    return route.fulfill({ json: { schedule: "02:30 Europe/Rome", runs: state === "none" ? [] : [run(state)] } });
  });
  await page.route("**/api/browse-exports", (route: Route) => route.fulfill({ json: { runs: [] } }));
  await page.goto("/backups");
  const button = page.getByRole("button", { name: "Back up now" });
  await button.focus();
  await page.keyboard.press("Enter");
  const live = page.locator("p.visually-hidden[role=status]").filter({ hasText: /Backup/ });
  await expect(live).toHaveText(/Backup started/);
  const running = page.getByRole("button", { name: /Backup running…|Starting…/ });
  await expect(running).toBeFocused(); // not <body>
  await expect(running).toHaveAttribute("aria-disabled", "true");
  await expect(live).toHaveText(/Backup finished/, { timeout: 15_000 });
  await expect(page.getByRole("button", { name: "Back up now" })).toBeFocused();
});

test("Inbox: a retried OCR keeps its card as retrying and announces a new failure", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  let phase: "failed" | "retrying" | "failed-again" = "failed";
  let checks = 0;
  await page.route((url) => url.pathname === "/api/documents" && url.searchParams.get("view") === "exceptions", (route: Route) =>
    route.fulfill({ json: { documents: phase === "retrying" ? [] : [fakeDocument({ status: "failed", error: "The PDF could not be read." })], next_cursor: null } }));
  await page.route(`**/api/documents/${FAKE_ID}/retry`, (route: Route) => {
    phase = "retrying";
    return route.fulfill({ status: 202, json: { status: "pending" } });
  });
  await page.route(`**/api/documents/${FAKE_ID}`, (route: Route) => {
    if (phase === "retrying" && ++checks >= 2) phase = "failed-again";
    return route.fulfill({ json: fakeDocument(phase === "retrying" ? { status: "processing" } : { status: "failed", error: "The PDF is damaged." }) });
  });
  await page.goto("/inbox");
  const row = page.locator(".exception-row").filter({ hasText: "Round nine letter" });
  await row.getByRole("button", { name: "Retry OCR" }).click();
  const status = page.locator("[role=status][aria-live=polite]").filter({ hasText: /OCR/ });
  await expect(status).toContainText("OCR restarted");
  // The card stays, marked as retrying, even though the server no longer lists it as an exception.
  await expect(row).toContainText("Reading the file again…");
  await expect(row.getByRole("button", { name: "Retrying OCR…" })).toHaveAttribute("aria-disabled", "true");
  await expect(status).toContainText("OCR for “Round nine letter” failed again: The PDF is damaged.", { timeout: 15_000 });
  await expect(row).toContainText("OCR could not finish: The PDF is damaged.");
  await expect(row.getByRole("button", { name: "Retry OCR" })).not.toHaveAttribute("aria-disabled", "true");
});

test("field hints describe the field instead of joining its accessible name", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  await page.goto("/people");
  const name = page.getByRole("textbox", { name: "Name", exact: true });
  await expect(name).toBeVisible();
  await expect(name).toHaveAccessibleDescription("Optional");
  // By role and name: getByLabel matches the label's whole text, which still contains the (aria-hidden) hint.
  const admin = page.getByRole("textbox", { name: "Your password", exact: true });
  await expect(admin).toHaveAccessibleName("Your password");
  await expect(admin).toHaveAccessibleDescription(/Needed to add people/);
  // The hint is still shown.
  await expect(page.getByText("Optional").first()).toBeVisible();
});

test("a found sticker is announced, not only a missing one", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  await page.route("**/api/stickers/R-ROUND9", (route: Route) => route.fulfill({ json: {
    copy: { id: "c1", sticker_code: "R-ROUND9", location_id: "l1", location_path: ["Study", "Blue box"], missing_at: null, created_at: "2026-11-19T09:00:00Z" },
    document: { id: FAKE_ID, title: "Round nine letter" },
  } }));
  await page.goto("/paper");
  await page.getByLabel("Sticker code").fill("R-ROUND9");
  await page.getByLabel("Sticker code").press("Enter");
  await expect(page.locator(".location-notice[role=status]")).toHaveText("Found “Round nine letter”. Place: Study / Blue box.");
});

test("a wrong setup key marks the setup key field, not the username and password", async ({ page }) => {
  await page.route("**/api/session", (route: Route) => route.request().method() === "GET"
    ? route.fulfill({ json: { authenticated: false, username: null, owner: false, setup_required: true } })
    : route.fallback());
  await page.route("**/api/setup", (route: Route) => route.fulfill({ status: 403, json: { error: "Invalid setup key" } }));
  await page.goto("/");
  await page.getByLabel("Username").fill("owner-r9");
  await page.getByLabel("Password", { exact: true }).fill("a-long-password-r9");
  await page.getByLabel("Setup key").fill("wrong");
  await page.getByRole("button", { name: /Create archive/ }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByLabel("Setup key")).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByLabel("Username")).not.toHaveAttribute("aria-invalid", "true");
  await expect(page.getByLabel("Password", { exact: true })).not.toHaveAttribute("aria-invalid", "true");
});

test.describe("Italian", () => {
  test.use({ locale: "it-IT" });
  test("the Inbox eyebrow is natural Italian", async ({ page }) => {
    test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
    await page.addInitScript(() => { try { localStorage.setItem("ripiano.language", "it"); } catch { /* ignore */ } });
    await page.goto("/");
    await page.getByLabel("Nome utente").fill(username!);
    await page.getByLabel("Password").fill(password!);
    await page.getByRole("button", { name: "Accedi" }).click();
    // Signed in before moving on, or the next navigation cancels the sign-in request.
    await expect(page.getByRole("button", { name: "Accedi" })).toHaveCount(0);
    await expect(page.locator("#main-content")).toBeVisible();
    await page.goto("/inbox");
    await expect(page.getByText("SOLO QUANDO SERVE IL TUO INTERVENTO")).toBeVisible();
    await expect(page.getByText("SOLO QUANDO SERVI TU")).toHaveCount(0);
  });
});

test("the agent form starts from safe defaults again after an agent is created", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const grants: Record<string, unknown>[] = [];
  await page.route("**/api/agents", (route: Route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as { name: string; scopes: string[] };
      const grant = { id: "g-r9", name: body.name, scopes: body.scopes, filter_tag_id: null, filter_tag_name: null, expires_at: new Date(Date.now() + 86400000 * 30).toISOString(), revoked_at: null, last_used_at: null, created_at: new Date().toISOString() };
      grants.push(grant);
      return route.fulfill({ status: 201, json: { ...grant, token: "rpa_round9_token" } });
    }
    return route.fulfill({ json: { grants } });
  });
  await page.route("**/api/agents/events", (route: Route) => route.fulfill({ json: { events: [] } }));
  await page.goto("/agents");
  await page.getByLabel("Name", { exact: true }).fill("Local full");
  await page.getByRole("checkbox", { name: "Read OCR text" }).check();
  await page.getByLabel("Your password (to create an agent token)").fill("anything-r9");
  await page.getByRole("button", { name: "Create agent token" }).click();
  await expect(page.getByLabel("New agent token")).toHaveValue("rpa_round9_token");
  await expect(page.getByRole("checkbox", { name: "Read OCR text" })).not.toBeChecked();
  await expect(page.getByRole("checkbox", { name: "Find document titles and tags" })).toBeChecked();
  await expect(page.getByLabel("Document access")).toHaveValue("");
});

test("a revoked agent says why", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const now = new Date().toISOString();
  const later = new Date(Date.now() + 86400000 * 30).toISOString();
  const grant = (id: string, reason: string | null) => ({ id, name: `agent ${id}`, scopes: ["documents:search"], filter_tag_id: null, filter_tag_name: null, expires_at: later, revoked_at: now, revoked_reason: reason, last_used_at: null, created_at: now });
  await page.route("**/api/agents", (route: Route) => route.fulfill({ json: { grants: [grant("a", "password_changed"), grant("b", null), grant("c", "something_new")] } }));
  await page.route("**/api/agents/events", (route: Route) => route.fulfill({ json: { events: [] } }));
  await page.goto("/agents");
  await page.locator("summary[data-agent-inactive=summary]").click();
  const cards = page.locator(".agent-inactive .agent-card");
  await expect(cards).toHaveCount(3);
  await expect(cards.nth(0)).toContainText("Revoked because your password changed");
  await expect(cards.nth(1)).toContainText("Revoked");
  await expect(cards.nth(2)).toContainText("Revoked");
  await expect(cards.nth(1)).not.toContainText("because");
});

test("the semantic-search database requirement is calm help, shown only when an option other than Off is chosen", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  await page.route("**/api/semantic-settings", (route: Route) => route.request().method() === "GET" ? route.fulfill({ json: {
    mode: "off", ollama_url: "", model_name: "", keep_loaded: false, effective_model: null, defaults: { ollama: "", nas: "" },
    database_supported: false, storage_ready: false, documents: { total: 0, waiting: null, indexed: null }, last_error: "", last_error_at: null,
  } }) : route.fallback());
  await page.goto("/agents");
  const card = page.locator(".semantic-card");
  await expect(card.getByRole("radio", { name: /^Off/ })).toBeChecked();
  // Off (the default): nothing about the database, and nothing that looks like an error.
  await expect(card.getByText("pgvector/pgvector:pg17")).toHaveCount(0);
  await expect(card.locator(".inline-error")).toHaveCount(0);
  await card.getByRole("radio", { name: /Ollama on another computer/ }).check();
  const note = card.locator(".semantic-note");
  await expect(note).toBeVisible();
  await expect(note).toContainText("Search by meaning needs a database image with the pgvector extension.");
  await expect(card.locator(".inline-error")).toHaveCount(0);
  await expect(card.getByRole("alert")).toHaveCount(0);
  // One flowing sentence: the image name sits inside the text, not in a column of its own (every width).
  await expect(note.locator("> *")).toHaveCount(1);
  expect(await note.evaluate((element) => getComputedStyle(element).display)).toBe("block");
  const code = (await note.locator("code").boundingBox())!;
  const text = (await note.locator("> span").boundingBox())!;
  expect(code.x).toBeGreaterThanOrEqual(text.x);
  expect(code.x + code.width).toBeLessThanOrEqual(text.x + text.width + 1);
  await card.getByRole("radio", { name: /^Off/ }).check();
  await expect(note).toHaveCount(0);
});

test("a kept draft stays for its person when someone else signs in, and nothing about it is shown", async ({ page, context }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.evaluate((id) => sessionStorage.setItem("ripiano.keptDraft", JSON.stringify([{ username: "someone-else-r9", draft: {
    documentId: id, keptAt: Date.now(), changes: { title: { from: "Old", to: "Private title" } }, tagsAdded: [], tagsRemoved: [], note: "",
  } }])), FAKE_ID);
  await page.reload();
  await signIn(page);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByText("Private title")).toHaveCount(0);
  // While another person is signed in, the draft is held in memory only: nothing readable in this tab's storage.
  expect(await page.evaluate(() => sessionStorage.getItem("ripiano.keptDraft"))).toBeNull();
  // That session ends: the draft is kept for its person again, without the username in clear text, and the
  // sign-in screen does not offer to discard someone else's edits (round-9 review L1).
  await context.clearCookies({ name: "sessionid" });
  await page.getByRole("textbox", { name: "Search documents" }).fill("anything");
  await expect(page.getByText("Unsaved changes to a document are kept in this window for 12 hours")).toBeVisible();
  await expect(page.getByRole("button", { name: "Discard them" })).toHaveCount(0);
  const kept = await page.evaluate(() => sessionStorage.getItem("ripiano.keptDraft"));
  expect(kept).toContain("Private title");
  expect(kept).not.toContain("someone-else-r9");
});

test("a kept draft that clashes shows the person's own value beside the newer one, and can use it", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r9-draft-${Date.now()}-${testInfo.project.name}`;
  const id = await uploadReady(page, name);
  // A draft kept when the session ended, whose title edit started from a value the server no longer has.
  await page.evaluate(([documentId, user]) => sessionStorage.setItem("ripiano.keptDraft", JSON.stringify({ username: user, draft: {
    documentId, keptAt: Date.now(), changes: { title: { from: "An older title", to: "My typed title" } }, tagsAdded: [], tagsRemoved: [], note: "",
  } })), [id, username!]);
  await page.reload();
  const dialog = page.getByRole("dialog");
  const title = dialog.getByRole("textbox", { name: "Title" });
  await expect(title).toHaveValue(name);
  const conflict = dialog.locator(".draft-conflict-list li").filter({ hasText: "Title" });
  await expect(conflict).toContainText(`Newer value: ${name}`);
  await expect(conflict).toContainText("Your value: My typed title");
  await conflict.getByRole("button", { name: "Use my value for Title" }).click();
  await expect(title).toHaveValue("My typed title");
  await expect(dialog.locator(".draft-restored")).toContainText("Your value is back in Title. It is not saved yet.");
  await expect(dialog.locator(".draft-restored")).toBeFocused();
  expect((await (await page.request.get(`/api/documents/${id}`)).json()).title).toBe(name); // nothing saved yet
});

test("a save refused with 409 keeps the edits, shows the newer document, and offers the person's own value", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r9-conflict-${Date.now()}-${testInfo.project.name}`;
  const id = await uploadReady(page, name);
  await page.goto(`/?document=${id}`);
  const dialog = page.getByRole("dialog");
  const title = dialog.getByRole("textbox", { name: "Title" });
  await expect(title).toHaveValue(name);
  // Another tab saves first (title and date); this tab's first save is refused with 409 until the API check lands.
  const other = await page.request.patch(`/api/documents/${id}`, { headers: await csrf(page), data: { title: `${name} tab A`, document_date: "2026-01-02" } });
  expect(other.ok()).toBe(true);
  let refused = 0;
  await page.route(`**/api/documents/${id}`, (route: Route) => {
    if (route.request().method() !== "PATCH" || refused > 0) return route.fallback();
    refused += 1;
    return route.fulfill({ status: 409, json: { error: "This document changed since you opened it.", code: "edit_conflict" } });
  });
  await title.fill(`${name} tab B`);
  await dialog.getByRole("button", { name: "Save changes" }).click();
  const box = dialog.locator(".draft-restored");
  await expect(box).toContainText("Someone else saved this document while you were editing it.");
  await expect(box).toBeFocused();
  await expect(title).toHaveValue(`${name} tab A`);
  await expect(dialog.getByLabel("Document date")).toHaveValue("2026-01-02"); // their change, which this tab did not touch
  const conflict = box.locator(".draft-conflict-list li").filter({ hasText: "Title" });
  await expect(conflict).toContainText(`Your value: ${name} tab B`);
  await conflict.getByRole("button", { name: "Use my value for Title" }).click();
  await expect(title).toHaveValue(`${name} tab B`);
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const saved = await (await page.request.get(`/api/documents/${id}`)).json();
  expect(saved.title).toBe(`${name} tab B`);
  expect(saved.document_date).toBe("2026-01-02"); // the other tab's change survived
});

test("with no tags yet the document dialog offers one way to create a tag, inline", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r9-notags-${Date.now()}-${testInfo.project.name}`;
  const id = await uploadReady(page, name);
  await page.route((url) => url.pathname === "/api/tags", (route: Route) => route.request().method() === "GET" ? route.fulfill({ json: { tags: [] } }) : route.fallback());
  await page.goto(`/?document=${id}`);
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("No tags yet.")).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Create your first tag" })).toHaveCount(0);
  await dialog.getByRole("button", { name: "Create a tag" }).click();
  await expect(dialog.getByLabel("New tag name")).toBeFocused();
});

// J2 M1 against the real API: two tabs of one person edit the same document. The second save is refused instead of
// overwriting, shows the newer value beside this tab's value, and saves only after the person chose.
test("two tabs: the second save shows the conflict and the choice instead of overwriting", async ({ page, context }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r9-twotab-${Date.now()}-${testInfo.project.name}`;
  const id = await uploadReady(page, name);
  const other = await context.newPage();
  await page.goto(`/?document=${id}`);
  await other.goto(`/?document=${id}`);
  const dialogA = page.getByRole("dialog");
  const dialogB = other.getByRole("dialog");
  await expect(dialogA.getByRole("textbox", { name: "Title" })).toHaveValue(name);
  await expect(dialogB.getByRole("textbox", { name: "Title" })).toHaveValue(name);

  // Tab A renames the document and saves.
  await dialogA.getByRole("textbox", { name: "Title" }).fill(`${name} from A`);
  await dialogA.getByRole("button", { name: "Save changes" }).click();
  await expect(dialogA).toHaveCount(0);

  // Tab B, still showing the old details, renames it differently and sets a date. The person is looking at it.
  await other.bringToFront();
  await dialogB.getByRole("textbox", { name: "Title" }).fill(`${name} from B`);
  await dialogB.getByLabel("Document date").fill("2026-03-04");
  const refused = other.waitForResponse((response) => response.url().endsWith(`/api/documents/${id}`) && response.request().method() === "PATCH");
  await dialogB.getByRole("button", { name: "Save changes" }).click();
  const response = await refused;
  expect(response.status()).toBe(409);
  const body = await response.json();
  expect(body.code).toBe("edit_conflict");
  expect(body.conflicting_fields).toEqual(["title"]);
  expect(body.document.title).toBe(`${name} from A`);

  const box = dialogB.locator(".draft-restored");
  await expect(box).toContainText("Someone else saved this document while you were editing it.");
  await expect(box).toBeFocused();
  const conflict = box.locator(".draft-conflict-list li").filter({ hasText: "Title" });
  await expect(conflict).toContainText(`Newer value: ${name} from A`);
  await expect(conflict).toContainText(`Your value: ${name} from B`);
  // The form shows the newer title, keeps this tab's date, and nothing was overwritten on the server.
  await expect(dialogB.getByRole("textbox", { name: "Title" })).toHaveValue(`${name} from A`);
  await expect(dialogB.getByLabel("Document date")).toHaveValue("2026-03-04");
  let saved = await (await page.request.get(`/api/documents/${id}`)).json();
  expect(saved.title).toBe(`${name} from A`);
  expect(saved.document_date).not.toBe("2026-03-04");

  await conflict.getByRole("button", { name: "Use my value for Title" }).click();
  await dialogB.getByRole("button", { name: "Save changes" }).click();
  await expect(dialogB).toHaveCount(0);
  saved = await (await page.request.get(`/api/documents/${id}`)).json();
  expect(saved.title).toBe(`${name} from B`);
  expect(saved.document_date).toBe("2026-03-04");
  await other.close();
});

// Edits to different details do not clash: the second tab's save goes through and both changes are kept.
test("two tabs: changes to different details are both kept without a conflict", async ({ page, context }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r9-twotab-merge-${Date.now()}-${testInfo.project.name}`;
  const id = await uploadReady(page, name);
  const other = await context.newPage();
  await page.goto(`/?document=${id}`);
  await other.goto(`/?document=${id}`);
  const dialogA = page.getByRole("dialog");
  const dialogB = other.getByRole("dialog");
  await expect(dialogA.getByRole("textbox", { name: "Title" })).toHaveValue(name);
  await expect(dialogB.getByRole("textbox", { name: "Title" })).toHaveValue(name);
  await dialogA.getByRole("textbox", { name: "Title" }).fill(`${name} renamed`);
  await dialogA.getByRole("button", { name: "Save changes" }).click();
  await expect(dialogA).toHaveCount(0);
  await other.bringToFront();
  await dialogB.getByLabel("Document date").fill("2026-05-06");
  await dialogB.getByRole("button", { name: "Save changes" }).click();
  await expect(dialogB).toHaveCount(0);
  const saved = await (await page.request.get(`/api/documents/${id}`)).json();
  expect(saved.title).toBe(`${name} renamed`);
  expect(saved.document_date).toBe("2026-05-06");
  await other.close();
});

// J3 M1: a document whose worker stopped is flagged `stalled` by /api/jobs (simulated here). The Library row says so
// calmly, announces it politely, and offers Retry and Cancel.
test("Library: an interrupted document says it will be tried again and offers Retry and Cancel", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const title = `r9-stalled-${Date.now()}-${testInfo.project.name}`;
  let status = "processing";
  let stalled = true;
  const posts: string[] = [];
  const item = () => fakeDocument({ title, original_name: `${title}.pdf`, status, archive_available: false, error: status === "failed" ? "Processing was cancelled." : "" });
  await page.route((url) => url.pathname === "/api/documents" && !url.searchParams.get("view"), async (route: Route) => {
    if (route.request().method() !== "GET") return route.fallback();
    const response = await route.fetch();
    const body = await response.json();
    return route.fulfill({ response, json: { ...body, documents: [item(), ...(body.documents ?? [])] } });
  });
  await page.route((url) => url.pathname === "/api/jobs", (route: Route) => route.fulfill({ json: {
    documents_waiting: { total: status === "failed" ? 0 : 1, items: status === "failed" ? [] : [{ id: FAKE_ID, title, status, since: "2026-11-19T09:00:00Z", stalled, can_retry: stalled, can_cancel: stalled || status === "pending" }] },
    documents_failed: { total: 0, items: [] }, purges: [], training: null, workflow_failures: [],
  } }));
  await page.route(`**/api/documents/${FAKE_ID}/retry`, (route: Route) => {
    posts.push("retry");
    status = "pending";
    stalled = false;
    return route.fulfill({ status: 202, json: item() });
  });
  await page.route(`**/api/documents/${FAKE_ID}/cancel-processing`, (route: Route) => {
    posts.push("cancel");
    status = "failed";
    stalled = false;
    return route.fulfill({ json: { id: FAKE_ID, status, error: "Processing was cancelled." } });
  });
  await page.goto("/");
  const row = page.locator(`.document-row[data-document-id="${FAKE_ID}"]`);
  await expect(row.locator(".doc-stalled")).toHaveText("Taking longer than usual. Processing was interrupted and will be tried again by itself.");
  await expect(row.locator(".status")).toHaveText("Processing");
  await expect(row.locator(".doc-error")).toHaveCount(0);
  await expect(page.locator("p[aria-live='polite']").filter({ hasText: "One document is taking longer than usual." })).toBeAttached();
  const retry = row.getByRole("button", { name: `Retry processing of ${title}.pdf now` });
  const cancel = row.getByRole("button", { name: `Cancel processing of ${title}.pdf` });
  await expect(cancel).toBeVisible();
  // Both are comfortable touch targets on a phone.
  for (const button of [retry, cancel]) {
    const size = await button.boundingBox();
    expect(Math.min(size!.width, size!.height)).toBeGreaterThanOrEqual(testInfo.project.name === "mobile" ? 44 : 24);
  }
  await retry.click();
  await expect(page.locator("p[aria-live='polite']").filter({ hasText: `“${title}” is queued again.` })).toBeAttached();
  await expect(row.locator(".doc-stalled")).toHaveCount(0);
  await expect(retry).toHaveCount(0);
  await expect(row.locator(".document-title-button")).toBeFocused();
  expect(posts).toEqual(["retry"]);

  // Interrupted again: Cancel takes it out of the queue; it stays in the archive as not processed.
  status = "processing";
  stalled = true;
  await page.reload();
  await expect(row.locator(".doc-stalled")).toBeVisible();
  await row.getByRole("button", { name: `Cancel processing of ${title}.pdf` }).click();
  await expect(page.locator("p[aria-live='polite']").filter({ hasText: "was taken out of the queue" })).toBeAttached();
  await expect(row.locator(".doc-stalled")).toHaveCount(0);
  await expect(row.locator(".status")).toHaveText("Needs attention");
  expect(posts).toEqual(["retry", "cancel"]);
});

test("Background jobs: an interrupted document is shown calmly with Retry and Cancel", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const title = `r9-stalled-job-${Date.now()}-${testInfo.project.name}`;
  let waiting: Record<string, unknown>[] = [
    { id: FAKE_ID, title, status: "processing", since: "2026-11-19T09:00:00Z", stalled: true, can_retry: true, can_cancel: true },
    { id: "00000000-0000-4000-8000-0000000000fa", title: `${title} busy`, status: "processing", since: "2026-11-19T09:05:00Z", stalled: false, can_retry: false, can_cancel: false },
  ];
  let retried = 0;
  await page.route((url) => url.pathname === "/api/jobs", (route: Route) => route.fulfill({ json: {
    documents_waiting: { total: waiting.length, items: waiting }, documents_failed: { total: 0, items: [] }, purges: [], training: null, workflow_failures: [],
  } }));
  await page.route(`**/api/documents/${FAKE_ID}/retry`, (route: Route) => {
    retried += 1;
    waiting = waiting.map((entry) => entry.id === FAKE_ID ? { ...entry, status: "pending", stalled: false, can_retry: false, can_cancel: true } : entry);
    return route.fulfill({ status: 202, json: fakeDocument({ title, status: "pending" }) });
  });
  await page.goto("/overview");
  const card = page.locator(".jobs-card");
  const stalledRow = card.locator("li").filter({ hasText: title }).first();
  await expect(stalledRow).toContainText("Taking longer than usual");
  await expect(stalledRow).toContainText("It was interrupted and will be tried again by itself.");
  await expect(card.locator("p[aria-live='polite']")).toContainText("One document is taking longer than usual.");
  await expect(card.getByRole("alert")).toHaveCount(0);
  await expect(stalledRow.getByRole("button", { name: `Cancel processing of ${title}`, exact: true })).toBeVisible();
  // A document that is simply being processed has neither button.
  const busyRow = card.locator("li").filter({ hasText: `${title} busy` });
  await expect(busyRow).toContainText("Being processed since");
  await expect(busyRow.getByRole("button", { name: /Retry|Cancel/ })).toHaveCount(0);
  await stalledRow.getByRole("button", { name: `Retry processing of ${title} now` }).click();
  await expect(card.getByRole("status").filter({ hasText: `“${title}” is queued again.` })).toBeVisible();
  await expect(stalledRow).toContainText("Queued since");
  await expect(card.locator("p[aria-live='polite']")).toHaveText("");
  expect(retried).toBe(1);
});

// Only changed details are sent: here the date changed elsewhere (as when OCR finishes and fills it in while the
// dialog is open) and this tab only renamed the document, so the save is not refused and does not send the date
// (which would mark a detected date the person never saw as set by hand; round-9 review L2).
test("a save of details this person changed is not refused for a date changed elsewhere, and does not send the date", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r9-cleanmerge-${Date.now()}-${testInfo.project.name}`;
  const id = await uploadReady(page, name);
  await page.goto(`/?document=${id}`);
  const dialog = page.getByRole("dialog");
  const title = dialog.getByRole("textbox", { name: "Title" });
  await expect(title).toHaveValue(name);
  const elsewhere = await page.request.patch(`/api/documents/${id}`, { headers: await csrf(page), data: { document_date: "2026-07-08" } });
  expect(elsewhere.ok()).toBe(true);
  const statuses: number[] = [];
  const bodies: Record<string, unknown>[] = [];
  page.on("response", (response) => {
    if (response.url().endsWith(`/api/documents/${id}`) && response.request().method() === "PATCH") {
      statuses.push(response.status());
      bodies.push(response.request().postDataJSON() as Record<string, unknown>);
    }
  });
  await title.fill(`${name} renamed`);
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog).toHaveCount(0);
  expect(statuses).toEqual([200]);
  expect(Object.keys(bodies[0]).sort()).toEqual(["base_version", "title"]);
  const saved = await (await page.request.get(`/api/documents/${id}`)).json();
  expect(saved.title).toBe(`${name} renamed`);
  expect(saved.document_date).toBe("2026-07-08");
});

// A refused save that merges cleanly is saved without asking: both tabs set the same date, and this tab also renamed
// the document. The second request no longer sends the date, which is not this person's change any more.
test("a save refused for a detail both set to the same value is merged and saved without a question", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r9-samemerge-${Date.now()}-${testInfo.project.name}`;
  const id = await uploadReady(page, name);
  await page.goto(`/?document=${id}`);
  const dialog = page.getByRole("dialog");
  const title = dialog.getByRole("textbox", { name: "Title" });
  await expect(title).toHaveValue(name);
  const elsewhere = await page.request.patch(`/api/documents/${id}`, { headers: await csrf(page), data: { document_date: "2026-07-08" } });
  expect(elsewhere.ok()).toBe(true);
  const statuses: number[] = [];
  const bodies: Record<string, unknown>[] = [];
  page.on("response", (response) => {
    if (response.url().endsWith(`/api/documents/${id}`) && response.request().method() === "PATCH") {
      statuses.push(response.status());
      bodies.push(response.request().postDataJSON() as Record<string, unknown>);
    }
  });
  await title.fill(`${name} renamed`);
  await dialog.getByLabel("Document date").fill("2026-07-08");
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog).toHaveCount(0);
  expect(statuses).toEqual([409, 200]);
  expect(Object.keys(bodies[1]).sort()).toEqual(["base_version", "title"]);
  const saved = await (await page.request.get(`/api/documents/${id}`)).json();
  expect(saved.title).toBe(`${name} renamed`);
  expect(saved.document_date).toBe("2026-07-08");
});

// Judge 1 round 9, H1 (dialog part): Retry OCR works again once /api/jobs flags the document as interrupted.
test("document dialog: Retry OCR is available for an interrupted document and says what is going on", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const title = `r9-stalled-dialog-${Date.now()}-${testInfo.project.name}`;
  let stalled = false;
  let status = "processing";
  let reprocessed = 0;
  await page.route(`**/api/documents/${FAKE_ID}`, (route: Route) => route.request().method() === "GET"
    ? route.fulfill({ json: fakeDocument({ title, status, archive_available: false }) }) : route.fallback());
  await page.route(`**/api/documents/${FAKE_ID}/**`, (route: Route) => {
    if (route.request().url().endsWith("/reprocess")) {
      reprocessed += 1;
      status = "pending";
      stalled = false;
      return route.fulfill({ status: 202, json: fakeDocument({ title, status, archive_available: false }) });
    }
    // The dialog's side panels (notes, pages, links…) have nothing to show for this made-up document.
    return new URL(route.request().url()).pathname.endsWith("/notes")
      ? route.fulfill({ json: { notes: [], next_offset: null } }) : route.fulfill({ status: 404, json: { error: "Document not found" } });
  });
  await page.route((url) => url.pathname === "/api/jobs", (route: Route) => route.fulfill({ json: {
    documents_waiting: { total: 1, items: [{ id: FAKE_ID, title, status, since: "2026-11-19T09:00:00Z", stalled, can_retry: stalled, can_cancel: stalled || status === "pending" }] },
    documents_failed: { total: 0, items: [] }, purges: [], training: null, workflow_failures: [],
  } }));
  await page.goto(`/?document=${FAKE_ID}`);
  const dialog = page.getByRole("dialog");
  const retry = dialog.getByRole("button", { name: "Retry OCR" });
  // Simply processing: the button waits, as before.
  await expect(retry).toHaveAttribute("aria-disabled", "true");
  await expect(dialog.locator("#detail-ocr-preparing")).toHaveText("OCR is being prepared. The original is available above.");
  // Interrupted: reopened, the dialog says so and the button works.
  stalled = true;
  await page.reload();
  await expect(dialog.locator("#detail-ocr-preparing")).toContainText("Processing was interrupted and will be tried again by itself");
  await expect(dialog.locator("#detail-ocr-preparing")).toHaveAttribute("aria-live", "polite");
  await expect(retry).not.toHaveAttribute("aria-disabled", "true");
  await retry.click();
  await expect.poll(() => reprocessed).toBe(1);
  await expect(dialog.locator("#detail-ocr-preparing")).toHaveText("OCR is being prepared. The original is available above.");
});

// Judge 1 round 9, M1: an upload that hangs while the server is away says so within seconds, and still completes.
test("an upload that hangs while Ripiano is unreachable says so, then completes by itself", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r9-hang-${Date.now()}-${testInfo.project.name}`;
  let down = true;
  await page.route("**/livez", (route: Route) => down ? route.abort("connectionrefused") : route.fallback());
  let release: () => void = () => undefined;
  const held = new Promise<void>((resolve) => { release = resolve; });
  await page.route((url) => url.pathname === "/api/documents", async (route: Route) => {
    if (route.request().method() !== "POST") return route.fallback();
    await held; // the proxy keeps the request open while the server restarts
    return route.fallback();
  });
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.png`, mimeType: "image/png", buffer: uniquePng(name) });
  const banner = page.locator(".upload-progress[role='status']");
  await expect(banner).toContainText("Adding 1 of 1…");
  await expect(banner).toContainText("Ripiano can't be reached; trying again…", { timeout: 20000 });
  await expect(banner).toHaveAttribute("aria-live", "polite");
  down = false;
  release();
  await expect(page.getByText("Added 1 document.")).toBeVisible({ timeout: 30000 });
  await expect(page.getByText("Ripiano can't be reached; trying again…")).toHaveCount(0);
});

// Judge 1 round 9, L4: a too-short password gets the app's message in the app's language, not the browser's.
for (const [language, message, field, userField] of [
  ["en", "Use at least 12 characters for the password.", "Password", "Username"],
  ["it", "Usa almeno 12 caratteri per la password.", "Password", "Nome utente"],
] as const) {
  test(`a too-short password shows the app's own message (${language})`, async ({ page }) => {
    test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
    await signIn(page);
    await page.evaluate((value) => localStorage.setItem("ripiano.language", value), language);
    await page.goto("/people");
    const form = page.locator("form.people-form");
    await form.getByRole("textbox", { name: userField, exact: true }).fill("someone-new");
    const input = form.getByRole("textbox", { name: field, exact: true });
    await input.pressSequentially("short"); // typed, as a person does: the browser then checks the length
    const shown = await input.evaluate((element: HTMLInputElement) => { element.form!.reportValidity(); return element.validationMessage; });
    expect(shown).toBe(message);
    // Long enough: nothing is held against the field any more.
    await input.pressSequentially("-but-long-enough");
    expect(await input.evaluate((element: HTMLInputElement) => element.checkValidity())).toBe(true);
  });
}
