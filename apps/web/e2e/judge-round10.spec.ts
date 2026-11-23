import { expect, test, type Page, type Route } from "@playwright/test";

// Round-10 judge regressions owned by the web slice (judge 2 M1–M3 and L1–L4, judge 3 L5): Save also adds a typed
// note, the edit-conflict list is laid out as separate lines, a save that gets no answer gives up with a message, a
// 503 with a JSON message shows that message, focus stays put after sharing, a shared save, "Add location" and a
// Library OCR retry, the unsaved-changes question offers "Save changes", and the Italian and naming points. All
// states are simulated with page.route on a made-up document, so nothing is left on the shared stack.
const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

test.use({ serviceWorkers: "block" });

async function signIn(page: Page, italian = false) {
  await page.goto("/");
  await page.evaluate((language) => localStorage.setItem("ripiano.language", language), italian ? "it" : "en");
  await page.reload();
  await page.getByLabel(italian ? "Nome utente" : "Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: italian ? "Accedi" : "Sign in" }).click();
  await expect(page.locator("#main-content h1")).toBeVisible();
}

const FAKE_ID = "00000000-0000-4000-8000-0000000000fa";

function fakeDocument(overrides: Record<string, unknown> = {}) {
  return {
    id: FAKE_ID, title: "Round ten letter", original_name: "round-ten.pdf", version_number: 1,
    duplicate_of: null, duplicate_reviewed_at: null, source: "web", status: "ready", archive_available: true,
    error: "", created_at: "2026-11-20T09:00:00Z", trashed_at: null, document_date: null, correspondent: null,
    document_type: null, correspondent_origin: "none", document_type_origin: "none", action_status: "none",
    action_due_date: null, action_note: "", action_completed_at: null, tags: [], physical_copies: [], snippet: "",
    snippet_source: null, email: null, asn: null, split_parent: null, is_split_source: false, storage_path: null,
    access: "owner", shared_by: null, processing_warning: null, warning: "", processing_warning_reviewed_at: null,
    ...overrides,
  };
}

type Fake = {
  document: Record<string, unknown>;
  notes: { id: string; body: string; author: string; created_at: string }[];
  patches: Record<string, unknown>[];
  /** Answer a PATCH differently (return undefined for the default: apply the change). */
  onPatch?: (route: Route, body: Record<string, unknown>) => Promise<unknown> | undefined;
  /** Answer a note POST differently. */
  onNote?: (route: Route) => Promise<unknown> | undefined;
};

/** A made-up document served entirely by the test: details, notes and (empty) side panels. */
async function mockDocument(page: Page, overrides: Record<string, unknown> = {}): Promise<Fake> {
  const fake: Fake = { document: fakeDocument(overrides), notes: [], patches: [] };
  await page.route(`**/api/documents/${FAKE_ID}`, (route: Route) => {
    if (route.request().method() === "GET") return route.fulfill({ json: fake.document });
    if (route.request().method() !== "PATCH") return route.fallback();
    const body = route.request().postDataJSON() as Record<string, unknown>;
    const custom = fake.onPatch?.(route, body);
    if (custom) return custom;
    fake.patches.push(body);
    const { base_version: _version, ...changes } = body;
    fake.document = { ...fake.document, ...changes };
    return route.fulfill({ json: fake.document });
  });
  await page.route(`**/api/documents/${FAKE_ID}/**`, (route: Route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/notes")) {
      if (route.request().method() === "POST") {
        const custom = fake.onNote?.(route);
        if (custom) return custom;
        const note = { id: `note-${fake.notes.length + 1}`, body: (route.request().postDataJSON() as { body: string }).body, author: username ?? "me", created_at: "2026-11-20T10:00:00Z" };
        fake.notes.unshift(note);
        return route.fulfill({ status: 201, json: note });
      }
      return route.fulfill({ json: { notes: fake.notes, next_offset: null } });
    }
    if (path.endsWith("/filing-suggestions")) return route.fulfill({ json: { tags: [], correspondents: [], document_types: [] } });
    return route.fulfill({ status: 404, json: { error: "Document not found" } });
  });
  return fake;
}

async function openFake(page: Page) {
  await page.goto(`/?document=${FAKE_ID}`);
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { level: 2 })).toBeVisible();
  if (await dialog.locator(".detail-advanced-toggle").count()) await dialog.locator(".detail-advanced-toggle").click();
  return dialog;
}

test("Save changes also adds the note typed in New note", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const fake = await mockDocument(page);
  const dialog = await openFake(page);
  await dialog.getByLabel("New note").fill("Call the office on Monday");
  await dialog.getByRole("textbox", { name: "Title" }).fill("Round ten letter, renamed");
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(fake.notes.map((note) => note.body)).toEqual(["Call the office on Monday"]);
  expect(fake.patches).toHaveLength(1);
  expect(fake.patches[0].title).toBe("Round ten letter, renamed");
});

test("when the typed note cannot be added, Save keeps the dialog open with the note and the edits", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const fake = await mockDocument(page);
  let refuse = true;
  fake.onNote = (route) => refuse ? route.fulfill({ status: 400, json: { error: "Notes are limited to 2000 characters" } }) : undefined;
  const dialog = await openFake(page);
  const note = dialog.getByLabel("New note");
  const title = dialog.getByRole("textbox", { name: "Title" });
  await note.fill("A note that is refused");
  await title.fill("Edited title");
  await dialog.getByRole("button", { name: "Save changes" }).click();
  const alert = dialog.locator("[aria-labelledby=document-notes-heading] > [role=alert]");
  await expect(alert).toContainText("Notes are limited to 2000 characters.");
  await expect(alert).toContainText("The note was not added, so nothing has been saved yet.");
  await expect(note).toHaveValue("A note that is refused");
  await expect(note).toBeFocused();
  await expect(title).toHaveValue("Edited title");
  expect(fake.patches).toHaveLength(0);
  // Trying again saves both.
  refuse = false;
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(fake.notes).toHaveLength(1);
  expect(fake.patches[0].title).toBe("Edited title");
});

test("the edit-conflict list shows the field, both values and the button on separate lines", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page, true);
  const fake = await mockDocument(page, { title: "Titolo iniziale" });
  fake.onPatch = (route) => route.fulfill({ status: 409, json: {
    error: "Questo documento è cambiato.", code: "edit_conflict", document: { ...fake.document, title: "Titolo dalla scheda 2" },
  } });
  const dialog = await openFake(page);
  await dialog.getByRole("textbox", { name: "Titolo" }).fill("Titolo dalla scheda 1");
  await dialog.getByRole("button", { name: "Salva modifiche" }).click();
  const item = dialog.locator(".draft-conflict-list li");
  await expect(item).toHaveCount(1);
  const heading = item.getByRole("heading", { name: "Titolo" });
  const newer = item.getByText("Valore più recente: Titolo dalla scheda 2", { exact: true });
  const mine = item.getByText("Il tuo valore: Titolo dalla scheda 1", { exact: true });
  const button = item.getByRole("button", { name: "Usa il mio valore per Titolo" });
  const boxes = [];
  for (const part of [heading, newer, mine, button]) {
    await expect(part).toBeVisible();
    boxes.push((await part.boundingBox())!);
  }
  // Each piece starts below the one before it: nothing shares a line.
  for (let index = 1; index < boxes.length; index += 1) {
    expect(boxes[index].y).toBeGreaterThanOrEqual(boxes[index - 1].y + boxes[index - 1].height - 1);
  }
  if (testInfo.project.name === "mobile") expect(boxes[3].height).toBeGreaterThanOrEqual(44);
  // The accessibility tree has them as separate elements too, not one run-on text.
  const tree = await item.ariaSnapshot();
  expect(tree).toContain("heading \"Titolo\"");
  expect(tree).toMatch(/paragraph: .*Valore più recente: Titolo dalla scheda 2/);
  expect(tree).toMatch(/paragraph: .*Il tuo valore: Titolo dalla scheda 1/);
  expect(tree).not.toContain("scheda 2Il tuo valore");
  // No horizontal overflow from long values.
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

test("a save that gets no answer gives up after the time limit, says so, and keeps the dialog and the edits", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.setTimeout(90_000);
  await signIn(page);
  const fake = await mockDocument(page);
  let hang = true;
  // Never answered, like a stopped server behind the proxy.
  fake.onPatch = () => hang ? new Promise(() => {}) : undefined;
  const dialog = await openFake(page);
  const title = dialog.getByRole("textbox", { name: "Title" });
  await title.fill("Typed while the server was away");
  const save = dialog.getByRole("button", { name: /Save changes|Saving/ });
  await save.click();
  await expect(dialog.locator(":scope > .inline-error")).toHaveText("Ripiano can't be reached right now. Your changes are still here; try again.", { timeout: 30_000 });
  await expect(title).toHaveValue("Typed while the server was away");
  await expect(save).toHaveText(/Save changes/);
  await expect(save).not.toHaveAttribute("aria-disabled", "true");
  // The server is back: the same edit saves.
  hang = false;
  await save.click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(fake.patches[0].title).toBe("Typed while the server was away");
});

test("a 503 with a message from the server shows that message, not 'unexpected reply'", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const fake = await mockDocument(page);
  fake.onPatch = (route) => route.fulfill({ status: 503, json: { error: "Ripiano cannot reach its database right now. Try again in a minute." } });
  const dialog = await openFake(page);
  const title = dialog.getByRole("textbox", { name: "Title" });
  await title.fill("Edited during an outage");
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog.locator(":scope > .inline-error")).toContainText("Ripiano cannot reach its database right now. Try again in a minute.");
  await expect(dialog).not.toContainText("unexpected reply");
  await expect(title).toHaveValue("Edited during an outage");
});

test("the unsaved-changes question offers Save changes, which saves and closes", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const fake = await mockDocument(page);
  const dialog = await openFake(page);
  await dialog.getByRole("textbox", { name: "Title" }).fill("Saved from the question");
  await dialog.getByLabel("New note").fill("And a note");
  await page.keyboard.press("Escape");
  const question = page.getByRole("alertdialog", { name: "You have unsaved changes." });
  // Focus still starts on "Keep editing"; Esc still means keep editing.
  await expect(question.getByRole("button", { name: "Keep editing" })).toBeFocused();
  await expect(question.getByRole("button")).toHaveText([/Keep editing/, /Save changes/, /Discard changes/]);
  await page.keyboard.press("Escape");
  await expect(question).toHaveCount(0);
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await question.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(fake.patches[0].title).toBe("Saved from the question");
  expect(fake.notes.map((note) => note.body)).toEqual(["And a note"]);
});

test("Save changes from the question shows a refusal in the form and keeps the edits", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const fake = await mockDocument(page);
  fake.onPatch = (route) => route.fulfill({ status: 400, json: { error: "That archive number is already in use" } });
  const dialog = await openFake(page);
  const title = dialog.getByRole("textbox", { name: "Title" });
  await title.fill("Refused title");
  await page.keyboard.press("Escape");
  await page.getByRole("alertdialog").getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("alertdialog")).toHaveCount(0);
  await expect(dialog.locator(":scope > .inline-error")).toContainText("That archive number is already in use.");
  await expect(title).toHaveValue("Refused title");
  expect(await page.evaluate(() => document.activeElement !== document.body)).toBe(true);
});

test("sharing a document keeps keyboard focus in the sharing controls and announces it", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  await mockDocument(page);
  const grants: unknown[] = [];
  await page.route(`**/api/documents/${FAKE_ID}/access`, (route: Route) => {
    if (route.request().method() === "POST") grants.push({ id: 1, level: "view", target: { kind: "person", id: 9901, name: "marta-r10", active: true } });
    return route.fulfill({ json: { grants } });
  });
  await page.route("**/api/people", (route: Route) => route.request().method() === "GET"
    ? route.fulfill({ json: { admin: true, people: [{ id: 9901, username: "marta-r10", name: "", is_active: true, is_admin: false, last_login: null, groups: [] }], groups: [] } })
    : route.fallback());
  const dialog = await openFake(page);
  const panel = dialog.locator(".access-panel");
  await panel.locator("summary").click();
  const chooser = panel.getByLabel("Person or group");
  await chooser.selectOption({ label: "marta-r10" });
  const share = panel.getByRole("button", { name: "Share" });
  await share.focus();
  await page.keyboard.press("Enter");
  await expect(panel.getByRole("status")).toContainText("marta-r10");
  await expect(panel.locator(".share-list li")).toHaveCount(1);
  await expect(chooser).toBeFocused();
});

test("saving a shared document keeps focus on Save, announces it, and adds the typed note", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page, true);
  const fake = await mockDocument(page, { access: "edit", shared_by: "paola", shared_by_id: 9902, action_status: "done" });
  await page.route("**/api/shared-filing", (route: Route) => route.fulfill({ json: { tags: [], correspondents: [], document_types: [] } }));
  const dialog = await openFake(page);
  // The follow-up state has the same name here as in the owner's dialog.
  await expect(dialog.getByLabel("Da fare").locator("option:checked")).toHaveText("Completato");
  await dialog.getByRole("textbox", { name: "Titolo" }).fill("Titolo del secondo membro");
  await dialog.getByLabel("Nuova nota").fill("Nota del secondo membro");
  const save = dialog.getByRole("button", { name: /Salva modifiche|Salvataggio/ });
  await save.focus();
  await page.keyboard.press("Enter");
  await expect(dialog.getByRole("status").filter({ hasText: "Modifiche salvate." })).toBeVisible();
  await expect(save).toBeFocused();
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(fake.patches[0].title).toBe("Titolo del secondo membro");
  expect(fake.notes.map((note) => note.body)).toEqual(["Nota del secondo membro"]);
  await expect(dialog.getByLabel("Nuova nota")).toHaveValue("");
});

test("Add location pressed as a button keeps focus on it and announces the new location", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const locations: unknown[] = [];
  await page.route("**/api/locations", (route: Route) => {
    if (route.request().method() !== "POST") return route.fulfill({ json: { locations } });
    const created = { id: "00000000-0000-4000-8000-00000000a010", name: "Round ten shelf", sticker_code: "L-ROUND10", parent_id: null, path: ["Round ten shelf"], description: "" };
    locations.push(created);
    return route.fulfill({ status: 201, json: created });
  });
  await page.goto("/paper");
  const form = page.locator("form").filter({ hasText: "Inside" });
  await form.getByRole("textbox", { name: "Name" }).fill("Round ten shelf");
  const add = form.getByRole("button", { name: /Add/ });
  await add.focus();
  await page.keyboard.press("Space");
  await expect(page.getByRole("status").filter({ hasText: "Added “Round ten shelf” at the top level." })).toBeAttached();
  await expect(add).toBeFocused();
});

test("Library: Retry OCR moves focus to the row title and announces the start and a second failure", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page, true);
  const title = `r10-retry-${Date.now()}`;
  let status = "failed";
  let lists = 0;
  const item = () => fakeDocument({
    title, original_name: `${title}.pdf`, status, archive_available: false, error: status === "failed" ? "Il PDF è danneggiato." : "",
    tags: [{ id: "t1", name: "casa", color: "#2f6f4f", origin: "manual" }, { id: "t2", name: "tasse", color: "#6f2f4f", origin: "manual" }, { id: "t3", name: "utenze", color: "#2f4f6f", origin: "manual" }],
  });
  await page.route((url) => url.pathname === "/api/documents" && !url.searchParams.get("view"), async (route: Route) => {
    if (route.request().method() !== "GET") return route.fallback();
    // After the retry the document is pending for one list load, then has failed again.
    if (status === "pending" && ++lists >= 2) status = "failed";
    const response = await route.fetch();
    const body = await response.json();
    return route.fulfill({ response, json: { ...body, documents: [item(), ...(body.documents ?? [])] } });
  });
  await page.route((url) => url.pathname === "/api/jobs", (route: Route) => route.fulfill({ json: {
    documents_waiting: { total: 0, items: [] }, documents_failed: { total: 0, items: [] }, purges: [], training: null, workflow_failures: [],
  } }));
  await page.route(`**/api/documents/${FAKE_ID}/retry`, (route: Route) => {
    status = "pending";
    lists = 0;
    return route.fulfill({ status: 202, json: item() });
  });
  // A long Library does not reload by itself: the retried document is then asked for by its id.
  await page.route(`**/api/documents/${FAKE_ID}`, (route: Route) => {
    if (status === "pending" && ++lists >= 2) status = "failed";
    return route.fulfill({ json: item() });
  });
  await page.goto("/");
  const row = page.locator(`.document-row[data-document-id="${FAKE_ID}"]`);
  // One tag beyond those shown is "+1 altra" (singular); two are "+2 altre".
  await expect(row.locator(".more-tags:visible")).toHaveText(/^\+(1 altra|2 altre)$/);
  const retry = row.getByRole("button", { name: `Riprova l'OCR di ${title}.pdf` });
  await retry.focus();
  await page.keyboard.press("Enter");
  const live = page.locator("p[aria-live='polite']");
  await expect(live.filter({ hasText: `OCR riavviato per “${title}”.` })).toBeAttached();
  await expect(row.locator(".document-title-button")).toBeFocused();
  await expect(live.filter({ hasText: `L'OCR di “${title}” non è riuscito di nuovo: Il PDF è danneggiato.` })).toBeAttached({ timeout: 20_000 });
});

test("backup snapshots are headed by their date and time, with the snapshot ID as secondary text", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page, true);
  const snapshot = "20261119T234107987200Z-de673080";
  await page.route("**/api/backups", (route: Route) => route.request().method() === "GET"
    ? route.fulfill({ json: { schedule: "02:00", runs: [{ id: "r10-backup", status: "complete", trigger: "manual", snapshot_name: snapshot, error: "", created_at: "2026-11-19T23:41:07Z", can_cancel: false, can_retry: false, retry_of: null }] } })
    : route.fallback());
  await page.route("**/api/browse-exports", (route: Route) => route.request().method() === "GET" ? route.fulfill({ json: { runs: [] } }) : route.fallback());
  await page.goto("/backups");
  const row = page.locator(".backup-list .document-row");
  const heading = row.getByRole("heading", { level: 3 });
  await expect(heading).toHaveText(/^Backup del .*2026/);
  await expect(heading).not.toContainText(snapshot);
  await expect(row.locator(".backup-snapshot-id")).toHaveText(`Snapshot ${snapshot}`);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

test("Inbox retry buttons carry the document name in their accessible name", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page, true);
  await page.route((url) => url.pathname === "/api/documents" && url.searchParams.get("view") === "exceptions", (route: Route) =>
    route.fulfill({ json: { documents: [fakeDocument({ title: "Bolletta di ottobre", status: "failed", error: "Il PDF non è leggibile." })], next_cursor: null } }));
  await page.goto("/inbox");
  await expect(page.getByRole("button", { name: "Riprova l'OCR di “Bolletta di ottobre”", exact: true })).toBeVisible();
});

test("creating a sender or a type inline is announced, like creating a tag", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  await mockDocument(page);
  await page.route("**/api/correspondents", (route: Route) => route.request().method() === "POST"
    ? route.fulfill({ status: 201, json: { id: "00000000-0000-4000-8000-00000000c010", name: "Round Ten Utility" } }) : route.fallback());
  await page.route("**/api/document-types", (route: Route) => route.request().method() === "POST"
    ? route.fulfill({ status: 201, json: { id: "00000000-0000-4000-8000-00000000d010", name: "Round Ten Bill" } }) : route.fallback());
  const dialog = await openFake(page);
  const status = dialog.locator("p.visually-hidden[role=status]");
  await dialog.locator("#detail-add-sender").click();
  await dialog.locator("#detail-new-sender").fill("Round Ten Utility");
  await page.keyboard.press("Enter");
  await expect(status).toHaveText("Sender Round Ten Utility created and chosen. Save changes to keep it on this document.");
  await expect(dialog.locator("#detail-correspondent")).toBeFocused();
  await dialog.locator("#detail-add-type").click();
  await dialog.locator("#detail-new-type").fill("Round Ten Bill");
  await page.keyboard.press("Enter");
  await expect(status).toHaveText("Type Round Ten Bill created and chosen. Save changes to keep it on this document.");
  await expect(dialog.locator("#detail-document-type")).toBeFocused();
});

test("with nothing to suggest yet, the document dialog says when suggestions will appear", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  await mockDocument(page);
  const dialog = await openFake(page);
  const hint = dialog.locator(".filing-suggestions-hint");
  await expect(hint).toHaveText("Suggestions appear here after you have filed a few similar documents.");
  // Once the document is being filed by hand, the hint steps aside.
  const sender = dialog.locator("#detail-correspondent");
  if (await sender.locator("option").count() > 1) {
    await sender.selectOption({ index: 1 });
    await expect(hint).toHaveCount(0);
  }
});

// Round-10 review M3: giving up on a request does not stop it on the server, so a retried create must be recognisable.
test("a note POST that times out is retried with the same Idempotency-Key, and the stored note is shown first", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.setTimeout(120_000);
  await signIn(page);
  const fake = await mockDocument(page);
  const keys: (string | undefined)[] = [];
  let attempt = 0;
  fake.onNote = (route) => {
    keys.push(route.request().headers()["idempotency-key"]);
    attempt += 1;
    if (attempt === 1) {
      // The server stores the note but its answer never arrives.
      fake.notes.unshift({ id: "note-slow", body: "Stored although the answer was late", author: username ?? "me", created_at: "2026-11-20T10:00:00Z" });
      return new Promise(() => {});
    }
    // Same key again: the server answers with the first result instead of creating a second note.
    if (attempt === 2) return route.fulfill({ status: 201, json: fake.notes[0] });
    return undefined;
  };
  const dialog = await openFake(page);
  const note = dialog.getByLabel("New note");
  const title = dialog.getByRole("textbox", { name: "Title" });
  await note.fill("Stored although the answer was late");
  await title.fill("Title saved on the second try");
  const save = dialog.getByRole("button", { name: /Save changes|Saving/ });
  await save.click();
  // While Save is posting the draft, "Add note" cannot post it a second time.
  await expect(dialog.getByRole("button", { name: "Add note" })).toHaveAttribute("aria-disabled", "true");
  await expect(dialog.locator("[aria-labelledby=document-notes-heading] > [role=alert]")).toContainText("Ripiano can't be reached right now. Your changes are still here; try again.", { timeout: 30_000 });
  // The notes were reloaded: the one the server did store is visible before the person tries again.
  await expect(dialog.locator(".note-list li")).toHaveCount(1);
  await expect(note).toHaveValue("Stored although the answer was late");
  expect(fake.patches).toHaveLength(0);
  await save.click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBeTruthy();
  expect(keys[0]!.length).toBeLessThanOrEqual(64);
  expect(keys[1]).toBe(keys[0]);
  expect(fake.notes).toHaveLength(1);
  expect(fake.patches[0].title).toBe("Title saved on the second try");
});

test("a new action gets a new Idempotency-Key: after an answer, and when the text changes after a failure", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const fake = await mockDocument(page);
  const keys: (string | undefined)[] = [];
  let drop = false;
  fake.onNote = (route) => {
    keys.push(route.request().headers()["idempotency-key"]);
    return drop ? route.abort("connectionreset") : undefined;
  };
  const dialog = await openFake(page);
  const note = dialog.getByLabel("New note");
  const add = dialog.getByRole("button", { name: "Add note" });
  // Answered: the same words typed again are a second note, with its own key.
  for (const expected of [1, 2]) {
    await note.fill("Same words");
    await add.click();
    await expect(dialog.locator(".note-list li")).toHaveCount(expected);
  }
  expect(keys[1]).not.toBe(keys[0]);
  // The connection drops: trying the same text again reuses the key; changing the text does not.
  drop = true;
  await note.fill("Dropped words");
  await add.click();
  await expect(dialog.locator("[aria-labelledby=document-notes-heading] > [role=alert]")).toBeVisible();
  await expect.poll(() => keys.length).toBe(3);
  await add.click();
  await expect.poll(() => keys.length).toBe(4);
  expect(keys[3]).toBe(keys[2]);
  await note.fill("Dropped words, edited");
  await add.click();
  await expect.poll(() => keys.length).toBe(5);
  expect(keys[4]).not.toBe(keys[2]);
});

test("when the note is stored but the details are refused, the dialog says which is which and does not post the note again", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const fake = await mockDocument(page);
  let refuse = true;
  fake.onPatch = (route) => refuse ? route.fulfill({ status: 400, json: { error: "That archive number is already in use" } }) : undefined;
  const dialog = await openFake(page);
  await dialog.getByLabel("New note").fill("Kept even though the details were refused");
  await dialog.getByRole("textbox", { name: "Title" }).fill("Refused, then saved");
  const save = dialog.getByRole("button", { name: "Save changes" });
  await save.click();
  const alert = dialog.locator(":scope > .inline-error");
  await expect(alert).toHaveText("That archive number is already in use. Your note was added. The other changes are not saved yet.");
  await expect(dialog).not.toContainText("nothing has been saved");
  await expect(dialog.getByLabel("New note")).toHaveValue("");
  await expect(dialog.locator(".note-list li")).toHaveCount(1);
  refuse = false;
  await save.click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(fake.notes).toHaveLength(1);
  expect(fake.patches[0].title).toBe("Refused, then saved");
});

// ---- Round-10 judge 1 (web): H2 upload kept before it is sent, M2 Inbox explanations shown whole, M3 an existing
// name typed into "Add a type" / "Create a tag" chooses the existing one. ----

/** How many files this browser keeps for upload (the on-device queue). */
async function queuedUploads(page: Page) {
  return page.evaluate(() => new Promise<number>((resolve) => {
    const open = indexedDB.open("ripiano-uploads", 1);
    open.onupgradeneeded = () => open.result.createObjectStore("pending", { keyPath: "id" });
    open.onerror = () => resolve(-1);
    open.onsuccess = () => {
      const count = open.result.transaction("pending", "readonly").objectStore("pending").count();
      count.onsuccess = () => { open.result.close(); resolve(count.result); };
      count.onerror = () => { open.result.close(); resolve(-1); };
    };
  }));
}

/** Whether leaving the page now would ask first. */
async function leavingAsks(page: Page) {
  return page.evaluate(() => {
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    return event.defaultPrevented;
  });
}

test("an upload cut off by a reload stays on the device, is announced as waiting, and is sent once with the same scan ID", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  // The server is "down": the proxy holds the first request open, answers 502 after the reload, then is back.
  let server: "holding" | "down" | "up" = "holding";
  const posts: { scanId: string; server: string }[] = [];
  await page.route((url) => url.pathname === "/api/documents", async (route: Route) => {
    if (route.request().method() !== "POST") return route.fallback();
    posts.push({ scanId: (await route.request().headerValue("x-ripiano-scan-id")) ?? "", server });
    if (server === "holding") return undefined; // never answered: the reload cuts it off
    if (server === "down") return route.fulfill({ status: 502, contentType: "text/html", body: "<html><body>502 Bad Gateway</body></html>" });
    return route.fulfill({ status: 202, json: fakeDocument({ title: "Kept across a reload", status: "processing" }) });
  });
  expect(await leavingAsks(page)).toBe(false);
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `r10-h2-${testInfo.project.name}.png`, mimeType: "image/png", buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==", "base64") });
  await expect(page.locator(".upload-progress[role='status']")).toContainText("Adding 1 of 1…");
  await expect.poll(() => posts.length).toBe(1);
  // Already on the device while the request is still open, but not yet called "waiting"; leaving asks first.
  expect(await queuedUploads(page)).toBe(1);
  await expect(page.getByText("waiting to upload")).toHaveCount(0);
  expect(await leavingAsks(page)).toBe(true);

  page.on("dialog", (dialog) => void dialog.accept()); // "Leave site?" — leave anyway
  server = "down";
  await page.reload();
  const banner = page.locator(".upload-progress").filter({ hasText: "1 file is waiting to upload" });
  await expect(banner).toBeVisible();
  await expect.poll(() => posts.filter((post) => post.server === "down").length).toBeGreaterThan(0);
  expect(await queuedUploads(page)).toBe(1);

  server = "up";
  await banner.getByRole("button", { name: "Send now" }).click();
  await expect(page.getByText("waiting to upload")).toHaveCount(0);
  await expect.poll(() => queuedUploads(page)).toBe(0);
  expect(posts.filter((post) => post.server === "up")).toHaveLength(1); // sent once
  expect(posts[0].scanId).toMatch(/^[0-9a-f-]{36}$/);
  expect(new Set(posts.map((post) => post.scanId)).size).toBe(1); // every attempt is the same scan: no second copy
  expect(await leavingAsks(page)).toBe(false);
});

test("an upload the server confirms leaves nothing in the device queue, and one it refuses is reported, not kept", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  let refuse = false;
  await page.route((url) => url.pathname === "/api/documents", (route: Route) => {
    if (route.request().method() !== "POST") return route.fallback();
    return refuse
      ? route.fulfill({ status: 415, json: { error: "This file type is not supported" } })
      : route.fulfill({ status: 202, json: fakeDocument({ title: "Confirmed upload", status: "processing" }) });
  });
  const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==", "base64");
  const choose = async (name: string) => {
    const add = page.getByRole("button", { name: "Add document", exact: true });
    if (await add.isVisible()) await add.click();
    else await page.getByRole("button", { name: "Add", exact: true }).click();
    const chooser = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: /Browse files/ }).click();
    await (await chooser).setFiles({ name, mimeType: "image/png", buffer: png });
  };
  await choose(`r10-h2-ok-${testInfo.project.name}.png`);
  await expect(page.locator(".upload-done")).toBeVisible();
  expect(await queuedUploads(page)).toBe(0);
  refuse = true;
  await choose(`r10-h2-refused-${testInfo.project.name}.png`);
  await expect(page.locator(".upload-report")).toContainText("This file type is not supported");
  expect(await queuedUploads(page)).toBe(0);
  await expect(page.getByText("waiting to upload")).toHaveCount(0);
});

test("Inbox explanations are shown whole, on as many lines as they need", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const failure = "Text recognition failed for this file. The original is safe; try OCR again, or replace the file with a better scan.";
  const warning = "This PDF is damaged, so some of its pages may be missing. Open it to check the pages, then mark it as checked or replace it.";
  await page.route((url) => url.pathname === "/api/documents" && url.searchParams.get("view") === "exceptions", (route: Route) =>
    route.fulfill({ json: { documents: [
      fakeDocument({ title: "Garbage scan", status: "failed", error: failure }),
      fakeDocument({ id: "00000000-0000-4000-8000-0000000000fb", title: "Truncated letter", processing_warning: "damaged", warning }),
    ], next_cursor: null } }));
  await page.goto("/inbox");
  for (const [selector, text] of [[".exception-row p.doc-error", `OCR could not finish: ${failure}`], [".exception-row p.doc-warning", warning]]) {
    const line = page.locator(selector);
    await expect(line).toHaveText(text);
    const box = await line.evaluate((element) => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      const info = element.closest(".document-info")!.getBoundingClientRect();
      return { whiteSpace: style.whiteSpace, scrollWidth: element.scrollWidth, clientWidth: element.clientWidth, left: rect.left, right: rect.right, infoLeft: info.left, infoRight: info.right, viewport: document.documentElement.clientWidth, pageWidth: document.documentElement.scrollWidth };
    });
    expect(box.whiteSpace).toBe("normal");
    expect(box.scrollWidth).toBeLessThanOrEqual(box.clientWidth); // nothing cut off
    expect(box.left).toBeGreaterThanOrEqual(box.infoLeft - 1);
    expect(box.right).toBeLessThanOrEqual(box.infoRight + 1);
    expect(box.right).toBeLessThanOrEqual(box.viewport);
    expect(box.pageWidth).toBeLessThanOrEqual(box.viewport); // and the page does not scroll sideways
  }
});

const EXISTING_TYPE = { id: "00000000-0000-4000-8000-00000000d020", name: "Invoice" };
const EXISTING_TAG = { id: "00000000-0000-4000-8000-00000000e020", name: "bills", color: "#4b6bfb", description: "", barcode_value: "", parent_id: null };

test("typing an existing name into Add a type or Create a tag chooses the existing one, and Save keeps it", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const fake = await mockDocument(page);
  let creates = 0;
  await page.route("**/api/document-types", (route: Route) => {
    if (route.request().method() === "POST") { creates += 1; return route.fulfill({ status: 409, json: { error: "This name already exists" } }); }
    return route.fulfill({ json: { document_types: [EXISTING_TYPE] } });
  });
  await page.route("**/api/tags", (route: Route) => {
    if (route.request().method() === "POST") { creates += 1; return route.fulfill({ status: 409, json: { error: "A tag with that name already exists" } }); }
    return route.fulfill({ json: { tags: [EXISTING_TAG] } });
  });
  const dialog = await openFake(page);
  const status = dialog.locator("p.visually-hidden[role=status]");
  await expect(dialog.locator("#detail-document-type option")).toHaveCount(2);
  await dialog.locator("#detail-add-type").click();
  await dialog.locator("#detail-new-type").fill("  invoice ");
  await page.keyboard.press("Enter");
  await expect(status).toHaveText("Type Invoice already exists, so it is chosen. Save changes to keep it on this document.");
  await expect(dialog.locator("#detail-document-type")).toHaveValue(EXISTING_TYPE.id);
  await expect(dialog.locator("#detail-document-type")).toBeFocused();
  await expect(dialog.locator("#detail-new-type")).toHaveCount(0);
  await dialog.locator("#detail-add-tag").click();
  await dialog.locator("#detail-new-tag").fill("BILLS");
  await dialog.getByRole("button", { name: "Create tag", exact: true }).click();
  await expect(status).toHaveText("Tag bills already exists, so it is chosen. Save changes to keep it on this document.");
  await expect(dialog.locator(`#detail-tag-${EXISTING_TAG.id}`)).toBeChecked();
  await expect(dialog.getByText("already exists").and(dialog.locator(":not([role=status])"))).toHaveCount(0); // no refusal on screen
  expect(creates).toBe(0); // nothing was sent only to be refused
  await dialog.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect.poll(() => fake.patches.length).toBe(1);
  expect(fake.patches[0].document_type_id).toBe(EXISTING_TYPE.id);
  expect(JSON.stringify(fake.patches[0])).toContain(EXISTING_TAG.id);
});

test("when the server says the name already exists, the list is loaded again and the existing type or tag is chosen", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const fake = await mockDocument(page);
  // Created meanwhile somewhere else: the lists loaded with the dialog do not have them yet.
  let known = false;
  await page.route("**/api/document-types", (route: Route) => {
    if (route.request().method() === "POST") { known = true; return route.fulfill({ status: 409, json: { error: "This name already exists" } }); }
    return route.fulfill({ json: { document_types: known ? [EXISTING_TYPE] : [] } });
  });
  let tagKnown = false;
  await page.route("**/api/tags", (route: Route) => {
    if (route.request().method() === "POST") { tagKnown = true; return route.fulfill({ status: 409, json: { error: "A tag with that name already exists" } }); }
    return route.fulfill({ json: { tags: tagKnown ? [EXISTING_TAG] : [] } });
  });
  const dialog = await openFake(page);
  const status = dialog.locator("p.visually-hidden[role=status]");
  await dialog.locator("#detail-add-type").click();
  await dialog.locator("#detail-new-type").fill("Invoice");
  await page.keyboard.press("Enter");
  await expect(status).toHaveText("Type Invoice already exists, so it is chosen. Save changes to keep it on this document.");
  await expect(dialog.locator("#detail-document-type")).toHaveValue(EXISTING_TYPE.id);
  await dialog.locator("#detail-add-tag").click();
  await dialog.locator("#detail-new-tag").fill("Bills");
  await page.keyboard.press("Enter");
  await expect(status).toHaveText("Tag bills already exists, so it is chosen. Save changes to keep it on this document.");
  await expect(dialog.locator(`#detail-tag-${EXISTING_TAG.id}`)).toBeChecked();
  await expect(dialog.getByText("This name already exists")).toHaveCount(0); // no refusal left on screen
  await expect(dialog.getByText("A tag with that name already exists")).toHaveCount(0);
  await dialog.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect.poll(() => fake.patches.length).toBe(1);
  expect(fake.patches[0].document_type_id).toBe(EXISTING_TYPE.id);
  expect(JSON.stringify(fake.patches[0])).toContain(EXISTING_TAG.id);
});

test("Italian: an existing type typed again is chosen and announced", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page, true);
  await mockDocument(page);
  // The create request is faked too, so this test can never add a real type to the account.
  let creates = 0;
  await page.route("**/api/document-types", (route: Route) => {
    if (route.request().method() === "GET") return route.fulfill({ json: { document_types: [{ ...EXISTING_TYPE, name: "Fattura" }] } });
    creates += 1;
    return route.fulfill({ status: 409, json: { error: "Esiste già un tipo con questo nome" } });
  });
  const dialog = await openFake(page);
  // Wait for the type list, so the typed name is compared with it (the test was flaky when Enter came first).
  await expect(dialog.locator(`#detail-document-type option[value="${EXISTING_TYPE.id}"]`)).toHaveCount(1);
  await dialog.locator("#detail-add-type").click();
  await dialog.locator("#detail-new-type").fill("fattura");
  await page.keyboard.press("Enter");
  await expect(dialog.locator("p.visually-hidden[role=status]")).toHaveText("Il tipo Fattura esiste già ed è stato scelto. Salva le modifiche per tenerlo su questo documento.");
  await expect(dialog.locator("#detail-document-type")).toHaveValue(EXISTING_TYPE.id);
  expect(creates).toBe(0);
});

// Review of the H2 fix (M-1, L-4): an upload still running when the person on this device changes sends nothing more,
// and signing out during an upload asks what to do with the files kept on the device.
test("after someone else signs in mid-upload, the remaining files are not sent and stay kept for the person who chose them", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const other = "r10-someone-else";
  let otherSignedIn = false;
  // After the second sign-in the server's session answer names another person (the test has one account).
  await page.route("**/api/session", async (route: Route) => {
    if (route.request().method() !== "GET" || !otherSignedIn) return route.fallback();
    const response = await route.fetch();
    const body = await response.json() as { authenticated: boolean; username: string | null };
    return route.fulfill({ response, json: body.authenticated ? { ...body, username: other } : body });
  });
  const posts: string[] = [];
  let release: () => void = () => undefined;
  const held = new Promise<void>((resolve) => { release = resolve; });
  await page.route((url) => url.pathname === "/api/documents", async (route: Route) => {
    if (route.request().method() !== "POST") return route.fallback();
    posts.push((await route.request().headerValue("x-ripiano-scan-id")) ?? "");
    await held; // the first file is still on its way while the person changes
    return route.fulfill({ status: 502, contentType: "text/html", body: "<html><body>502 Bad Gateway</body></html>" });
  });
  const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==", "base64");
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles([1, 2, 3].map((part) => ({ name: `r10-m1-${testInfo.project.name}-${part}.png`, mimeType: "image/png", buffer: png })));
  await expect.poll(() => posts.length).toBe(1);
  expect(await queuedUploads(page)).toBe(3);

  // Signing out during the upload asks about the three files on the device, although none is "waiting" yet (L-4).
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.locator(".sign-out-confirm")).toContainText("3 files have not been uploaded yet and are stored on this device.");
  await page.getByRole("button", { name: "Keep them and sign out", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();

  otherSignedIn = true;
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator("#main-content h1")).toBeVisible();
  await expect(page.locator(".profile-name")).toContainText(other);

  release(); // the first request ends; the loop would now go on to files 2 and 3
  await page.waitForTimeout(5000); // longer than the first automatic retry (3 s)
  expect(posts).toHaveLength(1); // nothing was sent into the other person's account
  const owners = await page.evaluate(() => new Promise<string[]>((resolve) => {
    const open = indexedDB.open("ripiano-uploads", 1);
    open.onsuccess = () => {
      const all = open.result.transaction("pending", "readonly").objectStore("pending").getAll();
      all.onsuccess = () => { open.result.close(); resolve((all.result as { owner: string }[]).map((item) => item.owner)); };
    };
  }));
  expect(owners).toEqual([username, username, username]); // all three still kept for the person who chose them
  await expect(page.getByText("waiting to upload")).toHaveCount(0); // and not shown as the other person's
  await expect(page.locator(".upload-report")).toHaveCount(0);
});
