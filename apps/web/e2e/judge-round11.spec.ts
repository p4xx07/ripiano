import { expect, test, type Page, type Route } from "@playwright/test";

// Round-11 judge regressions owned by the web slice. Judge 3: M1 a jump to the filing suggestions near the top of the
// document on a phone, M2 move or mark a paper copy right on the sticker result, L1 workflow summaries in plain English,
// L2 "offline" only when the device has no connection. Judge 2: M3 (same as judge 3 M2, from the label's QR address),
// L1 Overview plurals, L2 "No backup yet" for the owner, L3 locations in tree order, L5 one name for NAS folders.
// Every state is simulated with page.route on made-up records, so nothing is created or left on the shared stack.
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

const exact = (path: string) => (url: URL) => url.pathname === path;

const FAKE_ID = "00000000-0000-4000-8000-0000000000fb";

function fakeDocument(overrides: Record<string, unknown> = {}) {
  return {
    id: FAKE_ID, title: "Round eleven letter", original_name: "round-eleven.pdf", version_number: 1,
    duplicate_of: null, duplicate_reviewed_at: null, source: "web", status: "ready", archive_available: true,
    error: "", created_at: "2026-11-20T09:00:00Z", trashed_at: null, document_date: null, correspondent: null,
    document_type: null, correspondent_origin: "none", document_type_origin: "none", action_status: "none",
    action_due_date: null, action_note: "", action_completed_at: null, tags: [], physical_copies: [], snippet: "",
    snippet_source: null, email: null, asn: null, split_parent: null, is_split_source: false, storage_path: null,
    access: "owner", shared_by: null, processing_warning: null, warning: "", processing_warning_reviewed_at: null,
    ...overrides,
  };
}

const SUGGESTIONS = {
  tags: [{ id: "00000000-0000-4000-8000-00000000e111", name: "r11-bills", example: { id: "x1", title: "Earlier bill" }, shared_terms: ["invoice", "total"], similarity: 0.5 }],
  correspondents: [{ id: "00000000-0000-4000-8000-00000000c111", name: "r11-power-company", example: { id: "x1", title: "Earlier bill" }, shared_terms: ["invoice"], similarity: 0.5 }],
  document_types: [{ id: "00000000-0000-4000-8000-00000000d111", name: "r11-invoice", example: { id: "x1", title: "Earlier bill" }, shared_terms: ["total"], similarity: 0.5 }],
};

/** A made-up document with three filing suggestions; everything it loads is answered by the test. */
async function mockDocumentWithSuggestions(page: Page) {
  await page.route(`**/api/documents/${FAKE_ID}`, (route: Route) => route.request().method() === "GET"
    ? route.fulfill({ json: fakeDocument() }) : route.fallback());
  await page.route(`**/api/documents/${FAKE_ID}/**`, (route: Route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/notes")) return route.fulfill({ json: { notes: [], next_offset: null } });
    if (path.endsWith("/filing-suggestions")) return route.fulfill({ json: SUGGESTIONS });
    return route.fulfill({ status: 404, json: { error: "Document not found" } });
  });
}

test("judge 3 M1: on a phone a link near the top jumps to the filing suggestions; on a wide screen it is not needed", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  await mockDocumentWithSuggestions(page);
  await page.goto(`/?document=${FAKE_ID}`);
  const dialog = page.getByRole("dialog");
  const section = dialog.getByRole("region", { name: "Suggested from your documents" });
  await expect(section).toBeAttached();
  const jump = dialog.getByRole("button", { name: "3 filing suggestions · Go to them" });
  if (testInfo.project.name === "mobile") {
    // The link comes before the preview, in reading and focus order.
    const before = await jump.evaluate((node) => {
      const preview = document.querySelector("[role=dialog] .detail-preview");
      return Boolean(preview && node.compareDocumentPosition(preview) & Node.DOCUMENT_POSITION_FOLLOWING);
    });
    expect(before).toBe(true);
    await expect(jump).toBeInViewport();
    await jump.click();
    await expect(section).toBeFocused();
    await expect(section).toBeInViewport();
    // The next Tab reaches the first suggestion.
    await page.keyboard.press("Tab");
    await expect(dialog.getByRole("button", { name: "Add tag: r11-bills", exact: true })).toBeFocused();
    await page.screenshot({ path: testInfo.outputPath("r11-mobile-suggestions-jump.png") });
  } else {
    // The preview sits beside the form, so the suggestions are already near the top and the link is hidden.
    await expect(jump).toBeHidden();
    await expect(section).toBeVisible();
  }
});

test("judge 3 M1 Italian: the jump link is translated", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.skip(testInfo.project.name !== "mobile", "The link is shown on narrow screens only");
  await signIn(page, true);
  await mockDocumentWithSuggestions(page);
  await page.goto(`/?document=${FAKE_ID}`);
  await expect(page.getByRole("dialog").getByRole("button", { name: "3 suggerimenti di archiviazione · Vai" })).toBeVisible();
});

type FakeLocation = { id: string; name: string; sticker_code: string; parent_id: string | null; path: string[]; description: string };
const SHELF: FakeLocation = { id: "00000000-0000-4000-8000-00000000a111", name: "R11 Studio shelf", sticker_code: "L-R11SHELF", parent_id: null, path: ["R11 Studio shelf"], description: "" };
const BOX = { id: "00000000-0000-4000-8000-00000000a112", name: "A box", sticker_code: "L-R11BOXAA", parent_id: SHELF.id, path: ["R11 Studio shelf", "A box"], description: "" };
const DRAWER = { id: "00000000-0000-4000-8000-00000000a113", name: "R11 Kitchen drawer", sticker_code: "L-R11DRAWR", parent_id: null, path: ["R11 Kitchen drawer"], description: "" };
const STICKER = "R-R11CARD1";
const COPY_ID = "00000000-0000-4000-8000-00000000b111";

type CopyState = { location: FakeLocation | null; missing: boolean; patches: { path: string; body: Record<string, unknown> }[] };

/** Three made-up locations (served in leaf-name order, as the API does) and one paper copy on the shelf. */
async function mockPaper(page: Page): Promise<CopyState> {
  const state: CopyState = { location: SHELF, missing: false, patches: [] };
  const copy = () => ({
    id: COPY_ID, document_id: FAKE_ID, sticker_code: STICKER, location_id: state.location?.id ?? null,
    location_path: state.location?.path ?? [], missing_at: state.missing ? "2026-11-20T10:00:00Z" : null, created_at: "2026-11-20T09:00:00Z",
  });
  await page.route(exact("/api/locations"), (route: Route) => route.request().method() === "GET"
    ? route.fulfill({ json: { locations: [BOX, DRAWER, SHELF] } }) : route.fallback());
  await page.route(exact(`/api/stickers/${STICKER}`), (route: Route) => route.fulfill({ json: { copy: copy(), document: { id: FAKE_ID, title: "Round eleven letter" } } }));
  await page.route(exact(`/api/copies/${COPY_ID}`), (route: Route) => {
    const body = route.request().postDataJSON() as { location_id: string | null };
    state.patches.push({ path: "move", body });
    if (state.missing) return route.fulfill({ status: 409, json: { error: "Mark this paper copy found before moving it" } });
    state.location = [SHELF, BOX, DRAWER].find((item) => item.id === body.location_id) ?? null;
    return route.fulfill({ json: copy() });
  });
  await page.route(exact(`/api/copies/${COPY_ID}/status`), (route: Route) => {
    const body = route.request().postDataJSON() as { missing: boolean };
    state.patches.push({ path: "status", body });
    state.missing = body.missing;
    return route.fulfill({ json: copy() });
  });
  return state;
}

test("judge 3 M2 / judge 2 M3: the label's QR address opens a result card that moves the paper copy in two taps", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const state = await mockPaper(page);
  // What a phone's camera app opens from the printed label.
  await page.goto(`/?sticker=${STICKER}`);
  const card = page.locator(".sticker-result").filter({ hasText: STICKER });
  await expect(card).toContainText("Round eleven letter");
  await expect(card).toContainText("R11 Studio shelf");
  const list = card.getByRole("combobox", { name: `New location for paper copy ${STICKER}` });
  await expect(list).toHaveValue(SHELF.id);
  await expect(list).toBeInViewport();
  // Moving to where it already is says so and sends nothing.
  await card.getByRole("button", { name: `Move paper copy ${STICKER}` }).click();
  await expect(page.locator(".location-notice")).toHaveText(`Paper copy ${STICKER} is already there. Choose another location first.`);
  expect(state.patches).toHaveLength(0);
  await list.selectOption({ label: "R11 Kitchen drawer" });
  await card.getByRole("button", { name: `Move paper copy ${STICKER}` }).click();
  await expect(page.locator(".location-notice")).toHaveText(`Paper copy ${STICKER} moved to R11 Kitchen drawer. If its sticker shows the old location, print it again.`);
  await expect(card).toContainText("R11 Kitchen drawer");
  expect(state.patches).toEqual([{ path: "move", body: { location_id: DRAWER.id } }]);
  await expect(card.getByRole("link", { name: `Print sticker ${STICKER}` })).toHaveAttribute("href", `/api/copies/${COPY_ID}/label`);
  await expect(card.getByRole("button", { name: /Open document/ })).toBeVisible();
  await card.screenshot({ path: testInfo.outputPath("r11-sticker-result-actions.png") });
});

test("judge 3 M2: the sticker result marks the copy missing and found again, and hides Move while it is missing", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const state = await mockPaper(page);
  await page.goto("/paper");
  await page.getByRole("textbox", { name: "Sticker code" }).fill(STICKER);
  await page.getByRole("button", { name: "Find", exact: true }).click();
  const card = page.locator(".sticker-result").filter({ hasText: STICKER });
  await card.getByRole("button", { name: `Mark missing: paper copy ${STICKER}` }).click();
  await expect(page.locator(".location-notice")).toContainText(`Paper copy ${STICKER} marked missing.`);
  await expect(card).toContainText("This paper copy was marked missing.");
  await expect(card).toContainText("Mark it found before changing its location.");
  await expect(card.getByRole("combobox", { name: `New location for paper copy ${STICKER}` })).toHaveCount(0);
  await card.getByRole("button", { name: `Mark found: paper copy ${STICKER}` }).click();
  await expect(page.locator(".location-notice")).toContainText(`Paper copy ${STICKER} marked found. You can move it now.`);
  await expect(card.getByRole("combobox", { name: `New location for paper copy ${STICKER}` })).toBeVisible();
  expect(state.patches).toEqual([{ path: "status", body: { missing: true } }, { path: "status", body: { missing: false } }]);
});

test("judge 3 M2 Italian: the sticker result actions are translated", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page, true);
  await mockPaper(page);
  await page.goto(`/?sticker=${STICKER}`);
  const card = page.locator(".sticker-result").filter({ hasText: STICKER });
  await expect(card.getByRole("combobox", { name: `Nuova posizione per la copia cartacea ${STICKER}` })).toBeVisible();
  await expect(card.getByRole("button", { name: `Sposta la copia cartacea ${STICKER}` })).toBeVisible();
  await expect(card.getByRole("button", { name: `Segna come mancante: copia cartacea ${STICKER}` })).toBeVisible();
  await expect(card.getByRole("link", { name: `Stampa adesivo ${STICKER}` })).toBeVisible();
});

test("judge 2 L3: locations are listed in tree order, each box right under its shelf", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  await mockPaper(page);
  await page.goto(`/?sticker=${STICKER}`);
  await expect(page.locator(".location-list .location-path")).toHaveText(["R11 Kitchen drawer", "R11 Studio shelf", "R11 Studio shelf / A box"]);
  const options = page.locator(".sticker-result").getByRole("combobox", { name: `New location for paper copy ${STICKER}` }).locator("option");
  await expect(options).toHaveText(["No location", "R11 Kitchen drawer", "R11 Studio shelf", "R11 Studio shelf / A box"]);
});

const FLOW_TAG = { id: "00000000-0000-4000-8000-00000000e112", name: "Family", color: "#2f6f4f", description: "", barcode_value: "", parent_id: null };
const FLOW_SENDER = { id: "00000000-0000-4000-8000-00000000c112", name: "City office", document_count: 0 };
const FLOW_TYPE = { id: "00000000-0000-4000-8000-00000000d112", name: "Notice", document_count: 0 };

async function mockWorkflows(page: Page) {
  const flow = {
    id: "00000000-0000-4000-8000-00000000f111", name: "R11 summary", enabled: true, order: 0, trigger: "updated", schedule_field: "created",
    schedule_days: 30, filter_sources: ["folder"], filter_filename: "*.pdf", filter_text: "", filter_tag_id: FLOW_TAG.id,
    filter_correspondent_id: FLOW_SENDER.id, filter_document_type_id: FLOW_TYPE.id, add_tag_ids: [], remove_tag_ids: [],
    set_correspondent_id: null, set_document_type_id: null, set_needs_action: false, action_note: "", add_note: "Check", webhook_url: "",
    email_to: "", email_attach: false, pdf_password_count: 0, title_template: "", set_storage_path_id: null, set_custom_fields: [], share_with: [],
  };
  await page.route(exact("/api/workflows"), (route: Route) => route.request().method() === "GET"
    ? route.fulfill({ json: { workflows: [flow], runs: [] } }) : route.fallback());
  await page.route(exact("/api/tags"), (route: Route) => route.request().method() === "GET" ? route.fulfill({ json: { tags: [FLOW_TAG] } }) : route.fallback());
  await page.route(exact("/api/correspondents"), (route: Route) => route.request().method() === "GET" ? route.fulfill({ json: { correspondents: [FLOW_SENDER] } }) : route.fallback());
  await page.route(exact("/api/document-types"), (route: Route) => route.request().method() === "GET" ? route.fulfill({ json: { document_types: [FLOW_TYPE] } }) : route.fallback());
}

test("judge 3 L1 / judge 2 L5: workflow summaries read as sentences and name the NAS folder like the Library", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  await mockWorkflows(page);
  await page.goto("/workflows");
  const card = page.locator(".mail-card").filter({ hasText: "R11 summary" });
  await expect(card).toContainText(
    "When I change a document, if it came from a NAS folder and its file name matches *.pdf and it is tagged Family and its sender is City office and its type is Notice: add a note.",
  );
  await expect(page.getByRole("group", { name: "Came from" }).getByRole("checkbox", { name: "NAS folder" })).toBeAttached();
  await expect(page.getByRole("group", { name: "Came from" }).getByRole("checkbox", { name: "WebDAV" })).toBeAttached();
});

test("judge 3 L1 Italian: workflow summaries read as sentences", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page, true);
  await mockWorkflows(page);
  await page.goto("/workflows");
  const card = page.locator(".mail-card").filter({ hasText: "R11 summary" });
  await expect(card).toContainText("se proviene da una cartella del NAS e il nome del file corrisponde a *.pdf e ha l'etichetta Family e il mittente è City office e il tipo è Notice");
});

function overview(backup: { status: string; at: string } | null) {
  return {
    documents: { total: 4, ready: 4, waiting: 0, failed: 0, warnings: 0, needs_action: 1, overdue: 1, untagged: 0, duplicates: 1, bytes: 1024 },
    monthly: [], by_type: [], by_source: { folder: 1, web: 3 }, top_tags: [],
    health: { backup, mailboxes: { total: 1, with_errors: 1 }, workflows: { enabled: 1, failed_last_week: 1 }, queues: { celery: 0, maintenance: 0 } },
  };
}

test("judge 2 L1/L2: Overview says '1 exact copy', and the owner sees 'No backup yet' with a way to Backups", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  let backup: { status: string; at: string } | null = null;
  await page.route(exact("/api/overview"), (route: Route) => route.fulfill({ json: overview(backup) }));
  await page.route(exact("/api/jobs"), (route: Route) => route.fulfill({ json: {
    documents_waiting: { total: 0, items: [] }, documents_failed: { total: 0, items: [] }, purges: [], training: null, workflow_failures: [],
  } }));
  await page.goto("/overview");
  const attention = page.locator(".overview-attention");
  await expect(attention).toContainText("1 exact copy to review");
  await expect(attention).toContainText("1 follow-up is overdue");
  await expect(attention).toContainText("1 mailbox has a problem");
  await expect(attention).toContainText("1 workflow run failed this week");
  await expect(attention).not.toContainText("Backups are visible to the archive owner.");
  await expect(page.getByText("NAS folder").first()).toBeVisible();
  const toBackups = attention.getByRole("button", { name: "No backup yet · Open Backups" });
  await toBackups.click();
  await expect(page).toHaveURL(/\/backups$/);
  // A backup that is still running is described in words, not as a raw status.
  backup = { status: "running", at: "2026-11-20T09:00:00Z" };
  await page.goto("/overview");
  await expect(attention).toContainText("Last backup: in progress");
});

test("judge 3 L2: with the server down the screen says Ripiano can't be reached, and 'offline' only when the device is", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  await page.route("**/api/**", (route) => route.abort("internetdisconnected"));
  await page.reload().catch(() => undefined);
  await expect(page.getByRole("heading", { name: "Ripiano can't be reached" })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "This device is online, but the Ripiano server is not answering" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "You're offline" })).toHaveCount(0);
  // The device itself has no connection.
  await page.addInitScript(() => Object.defineProperty(Navigator.prototype, "onLine", { configurable: true, get: () => false }));
  await page.reload().catch(() => undefined);
  await expect(page.getByRole("heading", { name: "You're offline" })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "This device has no connection right now." })).toBeVisible();
  await page.unroute("**/api/**");
});

// ---- Judge 1 (round 11), web findings ----

test("judge 1 M1: Storage paths and the sender/type forms have visible labels, the app's field style, and a template hint", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  await page.route(exact("/api/storage-paths"), (route: Route) => route.request().method() === "GET"
    ? route.fulfill({ json: { storage_paths: [], placeholders: ["correspondent", "year"] } }) : route.fallback());
  await page.goto("/tags");
  const card = page.getByRole("region", { name: "Storage paths" });
  await expect(card.getByText("Storage path name", { exact: true })).toBeVisible();
  await expect(card.getByText("Folder template", { exact: true })).toBeVisible();
  const template = card.getByRole("textbox", { name: "Folder template" });
  await expect(template).toHaveValue("{correspondent}/{year}");
  await expect(template).toHaveAccessibleDescription(/separated by \/.*\{correspondent\}\/\{year\} gives, for example, City office\/2026/);
  await expect(card.locator("#storage-template-hint")).toContainText("You can use {correspondent} {year}");
  for (const input of [card.getByRole("textbox", { name: "Storage path name" }), template]) {
    expect(await input.evaluate((node) => getComputedStyle(node).borderTopLeftRadius)).not.toBe("0px");
  }
  // The new sender and type fields have visible labels too (same names the other specs use).
  await expect(page.locator(".filing-new-name").filter({ hasText: "New sender name" })).toBeVisible();
  await expect(page.locator(".filing-new-name").filter({ hasText: "New type name" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "New sender name" })).toBeVisible();
});

test("judge 1 M1 Italian: the Storage paths labels and hint are translated", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page, true);
  await page.route(exact("/api/storage-paths"), (route: Route) => route.request().method() === "GET"
    ? route.fulfill({ json: { storage_paths: [], placeholders: ["correspondent", "year"] } }) : route.fallback());
  await page.goto("/tags");
  const card = page.getByRole("region", { name: "Percorsi di archiviazione" });
  await expect(card.getByText("Modello di cartella", { exact: true })).toBeVisible();
  await expect(card.getByRole("textbox", { name: "Modello di cartella" })).toHaveAccessibleDescription(/separate da \//);
});

const ROW_IDS = ["00000000-0000-4000-8000-0000000001a1", "00000000-0000-4000-8000-0000000001a2", "00000000-0000-4000-8000-0000000001a3"];

/** A Library of three made-up documents, each of which opens in the dialog. */
async function mockLibrary(page: Page) {
  const docs = ROW_IDS.map((id, index) => fakeDocument({ id, title: `r11-row-${index + 1}`, original_name: `r11-row-${index + 1}.pdf` }));
  await page.route((url) => url.pathname === "/api/documents" && !url.searchParams.get("view"), (route: Route) => route.request().method() === "GET"
    ? route.fulfill({ json: { documents: docs, next_cursor: null, counts: { total: docs.length, ready: docs.length, waiting: 0 }, suggestion: null } }) : route.fallback());
  for (const doc of docs) {
    await page.route(`**/api/documents/${doc.id}`, (route: Route) => route.request().method() === "GET" ? route.fulfill({ json: doc }) : route.fallback());
    await page.route(`**/api/documents/${doc.id}/**`, (route: Route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/notes")) return route.fulfill({ json: { notes: [], next_offset: null } });
      if (path.endsWith("/filing-suggestions")) return route.fulfill({ json: { tags: [], correspondents: [], document_types: [] } });
      return route.fulfill({ status: 404, json: { error: "Document not found" } });
    });
  }
}

test("judge 1 L1: Enter on a Tab-focused row opens that row, and closing returns focus to it, not to the J/K row", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.skip(testInfo.project.name !== "desktop", "Keyboard shortcuts need a hardware keyboard");
  await signIn(page);
  await mockLibrary(page);
  await page.goto("/");
  const title = (n: number) => page.locator(".document-row").filter({ hasText: `r11-row-${n}` }).locator(".document-title-button");
  await expect(title(3)).toBeVisible();
  await page.locator("#main-content").focus();
  await page.keyboard.press("j");
  await page.keyboard.press("j");
  await expect(title(2)).toBeFocused();
  // Tab on to the third row, as a keyboard user would.
  await title(3).focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { level: 2, name: "r11-row-3" })).toBeVisible();
  await dialog.getByRole("button", { name: "Close" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(title(3)).toBeFocused();
  // And with J/K only: Enter opens the highlighted row and Escape returns to it.
  await page.keyboard.press("k");
  await expect(title(2)).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(dialog.getByRole("heading", { level: 2, name: "r11-row-2" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(title(2)).toBeFocused();
});

test("judge 1 L4 / judge 3 L4: on a phone the document title stays clear of the close button", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.skip(testInfo.project.name !== "mobile", "Narrow screens only");
  await signIn(page);
  await mockDocumentWithSuggestions(page);
  await page.goto(`/?document=${FAKE_ID}`);
  const dialog = page.getByRole("dialog");
  await expect(dialog.locator(".detail-title")).toBeVisible();
  const overlap = await dialog.evaluate((panel) => {
    const close = panel.querySelector(".modal-close")!.getBoundingClientRect();
    const title = panel.querySelector(".detail-title")!;
    const box = title.getBoundingClientRect();
    const textRight = box.right - parseFloat(getComputedStyle(title).paddingRight);
    // The close button's focus ring reaches 9px beyond it (3px offset + 6px halo).
    const verticalOverlap = box.top < close.bottom + 9 && box.bottom > close.top - 9;
    return verticalOverlap && textRight > close.left - 9;
  });
  expect(overlap).toBe(false);
});

test("judge 1 L5: Overview empty states use the quiet empty-state text, not a 16px paragraph", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  await page.route(exact("/api/overview"), (route: Route) => route.fulfill({ json: {
    documents: { total: 0, ready: 0, waiting: 0, failed: 0, warnings: 0, needs_action: 0, overdue: 0, untagged: 0, duplicates: 0, bytes: 0 },
    monthly: [], by_type: [], by_source: {}, top_tags: [],
    health: { backup: null, mailboxes: { total: 0, with_errors: 0 }, workflows: { enabled: 0, failed_last_week: 0 }, queues: null },
  } }));
  await page.route(exact("/api/jobs"), (route: Route) => route.fulfill({ json: {
    documents_waiting: { total: 0, items: [] }, documents_failed: { total: 0, items: [] }, purges: [], training: null, workflow_failures: [],
  } }));
  await page.goto("/overview");
  for (const text of ["Nothing is waiting for you.", "Nothing is waiting or failed."]) {
    const line = page.getByText(text, { exact: true });
    await expect(line).toHaveClass(/agent-empty-activity/);
    expect(await line.evaluate((node) => getComputedStyle(node).fontSize)).not.toBe("16px");
  }
});

test("judge 1 L7: People shows the last sign-in date in the app's date format", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  await page.route(exact("/api/people"), (route: Route) => route.request().method() === "GET"
    ? route.fulfill({ json: { admin: true, people: [{ id: 9911, username: "r11-member", name: "", is_active: true, is_admin: false, last_login: "2026-11-20T09:00:00Z", groups: [] }], groups: [] } })
    : route.fallback());
  await page.goto("/people");
  // The same short date as the rest of the app in this locale (en-US: "Nov 20, 2026"), not a numeric 20/11/2026.
  const expected = await page.evaluate(() => new Intl.DateTimeFormat(navigator.language, { day: "numeric", month: "short", year: "numeric" }).format(new Date("2026-11-20T09:00:00Z")));
  expect(expected).toMatch(/Nov/);
  await expect(page.getByText(`last signed in ${expected}`)).toBeVisible();
});

test("judge 1 L7: a waiting upload that is finally sent is announced like a direct upload", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const posts: string[] = [];
  await page.route((url) => url.pathname === "/api/documents", (route: Route) => {
    if (route.request().method() !== "POST") return route.fallback();
    posts.push("post");
    return route.fulfill({ status: 202, json: fakeDocument({ id: "00000000-0000-4000-8000-0000000001b1", title: "r11-waiting", status: "processing" }) });
  });
  // A file kept on this device from an earlier, cut-off upload.
  await page.evaluate(([owner, name]) => new Promise<void>((resolve, reject) => {
    const open = indexedDB.open("ripiano-uploads", 1);
    open.onupgradeneeded = () => open.result.createObjectStore("pending", { keyPath: "id" });
    open.onsuccess = () => {
      const tx = open.result.transaction("pending", "readwrite");
      tx.objectStore("pending").put({ id: "r11-waiting-probe", owner, name, type: "image/png", blob: new Blob(["x"], { type: "image/png" }), addedAt: Date.now(), scanId: "00000000-0000-4000-8000-0000000001c1" });
      tx.oncomplete = () => { open.result.close(); resolve(); };
      tx.onerror = () => reject(tx.error);
    };
  }), [username!, `r11-waiting-${testInfo.project.name}.png`]);
  await page.reload();
  await expect.poll(() => posts.length).toBe(1);
  await expect(page.locator(".upload-done")).toContainText("Added 1 document.");
});

// ---- Worker status (judge 2 M1/L7, judge 3 L3/L7, judge 1 L2/L3): web side of the round-11 API fields ----

const WAIT_IDS = ["00000000-0000-4000-8000-0000000002a1", "00000000-0000-4000-8000-0000000002a2", "00000000-0000-4000-8000-0000000002a3", "00000000-0000-4000-8000-0000000002a4"];

function processingHealth(problem: null | "worker_not_running" | "queue_unavailable", running: boolean) {
  return { pending: 2, processing: 1, waiting_since: "2026-11-20T08:00:00Z", worker: { running, last_seen: "2026-11-20T07:55:00Z" }, problem };
}

async function mockWorkerStatus(page: Page, problem: null | "worker_not_running" | "queue_unavailable", running: boolean, maintenanceRunning = true) {
  const health = processingHealth(problem, running);
  await page.route(exact("/api/overview"), (route: Route) => route.fulfill({ json: {
    documents: { total: 10, ready: 7, waiting: 3, pending: 2, processing: 1, failed: 0, warnings: 0, needs_action: 0, overdue: 0, untagged: 0, duplicates: 0, bytes: 2048 },
    monthly: [], by_type: [], by_source: {}, top_tags: [],
    health: { backup: { status: "complete", at: "2026-11-20T03:00:00Z" }, mailboxes: { total: 0, with_errors: 0 }, workflows: { enabled: 0, failed_last_week: 0 },
      queues: { celery: 2, maintenance: 0 }, processing: health, maintenance_worker: { running: maintenanceRunning, last_seen: "2026-11-20T07:50:00Z" } },
  } }));
  const item = (index: number, title: string, status: string, state: string) =>
    ({ id: WAIT_IDS[index], title, status, state, since: "2026-11-20T08:00:00Z", stalled: state === "stalled", can_retry: state === "stalled", can_cancel: true });
  await page.route(exact("/api/jobs"), (route: Route) => route.fulfill({ json: {
    processing: health,
    documents_waiting: { total: 4, items: [
      item(0, "r11-queued", "pending", "queued"),
      item(1, "r11-no-worker", "pending", "waiting_for_worker"),
      item(2, "r11-no-queue", "pending", "waiting_for_queue"),
      item(3, "r11-interrupted", "processing", "stalled"),
    ] },
    documents_failed: { total: 0, items: [] }, purges: [], training: null, workflow_failures: [],
  } }));
}

test("worker status: with text recognition stopped, Overview and Background jobs say so and never promise a retry by itself", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  await mockWorkerStatus(page, "worker_not_running", false, false);
  await page.goto("/overview");
  const attention = page.locator(".overview-attention");
  await expect(attention.getByRole("heading", { name: "Needs a look" })).toBeVisible();
  await expect(attention).toContainText("Documents have been waiting since");
  await expect(attention).toContainText("text recognition is not running (last seen");
  await expect(attention).toContainText("Start the Ripiano worker container again");
  // The owner is told that backups and scheduled checks are not running either.
  await expect(attention).toContainText("Backups and scheduled checks are not running");
  // The tile counts what Background jobs lists.
  const tile = page.locator(".overview-tile").filter({ hasText: "waiting or being processed" });
  await expect(tile.locator("strong")).toHaveText("3");
  await expect(tile).toContainText("2 queued · 1 being processed");
  const jobs = page.locator(".jobs-card");
  // Said once on the page, in "Needs a look", not again in Background jobs (independent review L1).
  await expect(page.locator(".processing-problem").filter({ hasText: "text recognition is not running" })).toHaveCount(1);
  await expect(jobs.locator(".processing-problem")).toHaveCount(0);
  await expect(jobs.locator("li").filter({ hasText: "r11-queued" })).toContainText("Queued since");
  await expect(jobs.locator("li").filter({ hasText: "r11-no-worker" })).toContainText(": text recognition is not running");
  await expect(jobs.locator("li").filter({ hasText: "r11-no-queue" })).toContainText("for the queue server");
  const interrupted = jobs.locator("li").filter({ hasText: "r11-interrupted" });
  await expect(interrupted).toContainText("it is tried again once text recognition is running again");
  await expect(jobs).not.toContainText("will be tried again by itself");
  await jobs.screenshot({ path: testInfo.outputPath("r11-jobs-worker-down.png") });
});

test("worker status: with the worker running an interrupted document is still tried again by itself, and nothing is flagged", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  await mockWorkerStatus(page, null, true);
  await page.goto("/overview");
  await expect(page.locator(".overview-attention").getByRole("heading", { name: "All calm" })).toBeVisible();
  await expect(page.locator(".processing-problem")).toHaveCount(0);
  await expect(page.locator(".jobs-card li").filter({ hasText: "r11-interrupted" })).toContainText("It was interrupted and will be tried again by itself.");
});

test("worker status: when the queue server cannot be reached, Overview says so", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  await mockWorkerStatus(page, "queue_unavailable", true);
  await page.goto("/overview");
  await expect(page.locator(".overview-attention")).toContainText("the queue server cannot be reached");
  await expect(page.locator(".overview-attention")).not.toContainText("Backups and scheduled checks");
});

test("worker status Italian: the problem and the rows are translated", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page, true);
  await mockWorkerStatus(page, "worker_not_running", false, false);
  await page.goto("/overview");
  const attention = page.locator(".overview-attention");
  await expect(attention).toContainText("il riconoscimento del testo non è attivo");
  await expect(attention).toContainText("I backup e i controlli programmati non sono attivi");
  await expect(page.locator(".jobs-card li").filter({ hasText: "r11-no-queue" })).toContainText("del server delle code");
});

test("judge 3 L7: in the Library a queued document says Waiting, one being processed says Processing", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const docs = [
    fakeDocument({ id: WAIT_IDS[0], title: "r11-pending-row", status: "pending", archive_available: false }),
    fakeDocument({ id: WAIT_IDS[1], title: "r11-processing-row", status: "processing", archive_available: false }),
  ];
  await page.route((url) => url.pathname === "/api/documents" && !url.searchParams.get("view"), (route: Route) => route.request().method() === "GET"
    ? route.fulfill({ json: { documents: docs, next_cursor: null, counts: { total: 2, ready: 0, waiting: 2 }, suggestion: null } }) : route.fallback());
  await page.goto("/");
  await expect(page.locator(".document-row").filter({ hasText: "r11-pending-row" }).locator(".status")).toHaveText("Waiting");
  await expect(page.locator(".document-row").filter({ hasText: "r11-processing-row" }).locator(".status")).toHaveText("Processing");
});

test("round 12: the Library and pending document explain when text recognition has stopped", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  await mockWorkerStatus(page, "worker_not_running", false);
  const waiting = fakeDocument({ id: WAIT_IDS[1], title: "r12-waiting-document", status: "pending", archive_available: false });
  await page.route((url) => url.pathname === "/api/documents" && !url.searchParams.get("view"), (route: Route) => route.request().method() === "GET"
    ? route.fulfill({ json: { documents: [waiting], next_cursor: null, counts: { total: 1, ready: 0, waiting: 1 }, suggestion: null } }) : route.fallback());
  await page.route(exact(`/api/documents/${WAIT_IDS[1]}`), (route: Route) => route.fulfill({ json: waiting }));
  await page.goto("/");
  await expect(page.locator(".processing-problem")).toContainText("text recognition is not running");
  await page.goto(`/?document=${WAIT_IDS[1]}`);
  await expect(page.getByRole("dialog").locator(".processing-problem")).toContainText("text recognition is not running");
});

test("round 12: a member sees a translated instruction to ask the owner about stopped processing", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page, true);
  await mockWorkerStatus(page, "worker_not_running", false);
  await page.route(exact("/api/session"), async (route: Route) => {
    const response = await route.fetch();
    return route.fulfill({ response, json: { ...(await response.json()), owner: false } });
  });
  const waiting = fakeDocument({ id: WAIT_IDS[1], title: "r12-in-attesa", status: "pending", archive_available: false });
  await page.route((url) => url.pathname === "/api/documents" && !url.searchParams.get("view"), (route: Route) => route.request().method() === "GET"
    ? route.fulfill({ json: { documents: [waiting], next_cursor: null, counts: { total: 1, ready: 0, waiting: 1 }, suggestion: null } }) : route.fallback());
  await page.route(exact(`/api/documents/${WAIT_IDS[1]}`), (route: Route) => route.fulfill({ json: waiting }));
  await page.goto("/");
  await expect(page.locator(".processing-problem")).toContainText("Chiedi al proprietario dell'archivio di riavviarlo");
  await expect(page.locator(".processing-problem")).not.toContainText("container");
  await page.goto(`/?document=${WAIT_IDS[1]}`);
  await expect(page.getByRole("dialog").locator(".processing-problem")).toContainText("Chiedi al proprietario dell'archivio di riavviarlo");
  await expect(page.getByRole("dialog").locator(".processing-problem")).not.toContainText("container");
});

test("independent review L2: someone who is not the owner is asked to tell the owner, not to start a container", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  await mockWorkerStatus(page, "worker_not_running", false, false);
  await page.route(exact("/api/session"), async (route: Route) => {
    const response = await route.fetch();
    return route.fulfill({ response, json: { ...(await response.json()), owner: false } });
  });
  await page.goto("/overview");
  const attention = page.locator(".overview-attention");
  await expect(attention).toContainText("Ask the archive owner to start it again");
  await expect(attention).not.toContainText("container");
  // Backups are the owner's: nothing about the maintenance worker.
  await expect(attention).not.toContainText("Backups and scheduled checks");
});

test("independent review M1: the sticker card compares with where the copy is now, not with what it showed earlier", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const state = await mockPaper(page);
  await page.goto(`/?sticker=${STICKER}`);
  const card = page.locator(".sticker-result").filter({ hasText: STICKER });
  await expect(card).toContainText("R11 Studio shelf");
  // Moved elsewhere (in the document dialog, or on another device) while the card is shown.
  state.location = DRAWER;
  const list = card.getByRole("combobox", { name: `New location for paper copy ${STICKER}` });
  const move = card.getByRole("button", { name: `Move paper copy ${STICKER}` });
  // Choosing the place the card showed is a real move now.
  await move.click();
  await expect(page.locator(".location-notice")).toHaveText(`Paper copy ${STICKER} moved to R11 Studio shelf. If its sticker shows the old location, print it again.`);
  expect(state.patches).toEqual([{ path: "move", body: { location_id: SHELF.id } }]);
  // And choosing where it really is says so without sending anything.
  state.location = DRAWER;
  await list.selectOption({ label: "R11 Kitchen drawer" });
  await move.click();
  await expect(page.locator(".location-notice")).toHaveText(`Paper copy ${STICKER} is already there. Choose another location first.`);
  await expect(card).toContainText("R11 Kitchen drawer");
  expect(state.patches).toHaveLength(1);
  // Marked missing elsewhere: Mark missing is refused, and the card shows the copy as missing.
  state.missing = true;
  await page.route(exact(`/api/copies/${COPY_ID}/status`), (route: Route) =>
    route.fulfill({ status: 409, json: { error: "Paper copy already has this status" } }));
  await card.getByRole("button", { name: `Mark missing: paper copy ${STICKER}` }).click();
  await expect(card).toContainText("This paper copy was marked missing.");
  await expect(card.getByRole("button", { name: `Mark found: paper copy ${STICKER}` })).toBeVisible();
});

test("independent review L8: locations that differ only by case or accent keep a stable tree order", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const make = (id: string, path: string[]) => ({ id: `00000000-0000-4000-8000-0000000003${id}`, name: path[path.length - 1], sticker_code: `L-R11X${id}`, parent_id: null, path, description: "" });
  await page.route(exact("/api/locations"), (route: Route) => route.request().method() === "GET"
    ? route.fulfill({ json: { locations: [make("a3", ["R11 Città"]), make("a1", ["R11 Citta", "Box"]), make("a2", ["R11 Citta"])] } }) : route.fallback());
  await page.goto("/paper");
  await expect(page.locator(".location-list .location-path")).toHaveText(["R11 Citta", "R11 Citta / Box", "R11 Città"]);
});
