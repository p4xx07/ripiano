import { expect, test, type Page, type Route } from "@playwright/test";
import { deflateSync } from "node:zlib";

// Round-8 judge regressions owned by the web slice: unsaved edits survive a session that ends mid-edit (J2 M1),
// the unsaved-changes question is modal (J2 M2), a failed "Retry OCR" in the Inbox keeps focus and its Retry
// retries OCR (J2 M3), the Library's Retry OCR button is styled (J1 M1), Find a sticker can use the camera or says
// how to scan without one (J1 M3), plus the low findings (copy history after Move, live regions, 44px error buttons,
// revoked-link reasons, paged agent activity, plain tool names, Workflows wording). States that are hard to reach on
// a shared stack (a failed OCR, a revoked link, a long agent log, a camera) are simulated with page.route or an
// init script; everything else works on the test's own new documents and locations.
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

const FAKE_ID = "00000000-0000-4000-8000-0000000000f8";

/** A failed copy of a real document's JSON, so every field the screens read is present. */
async function failedDocument(page: Page, id: string, title: string) {
  const real = await (await page.request.get(`/api/documents/${id}`)).json();
  return { ...real, id: FAKE_ID, title, original_name: `${title}.pdf`, status: "failed", archive_available: false, error: "The PDF could not be read." };
}

/**
 * Press Save after the session cookie is gone. Another request (the Library refreshing a document that is still
 * processing) may notice the ended session first and show the sign-in screen; the draft is kept either way.
 */
async function saveUnlessSignedOut(page: Page) {
  const save = page.getByRole("dialog").getByRole("button", { name: "Save changes" });
  const signIn = page.getByRole("heading", { name: "Welcome back." });
  await expect(save.or(signIn).first()).toBeVisible();
  await save.click({ timeout: 5000 }).catch(async (cause) => { if (!(await signIn.isVisible())) throw cause; });
}

test("a session that ends mid-edit keeps the draft: signing in again reopens the document with the edits, unsaved", async ({ page, context }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r8-draft-${Date.now()}-${testInfo.project.name}`;
  const id = await uploadReady(page, name);
  await page.goto(`/?document=${id}`);
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("textbox", { name: "Title" }).fill(`${name} renamed`);
  await dialog.getByRole("textbox", { name: "New note" }).fill("Call the bank on Monday");
  // The session ends (expired, or signed out elsewhere); the person then presses Save.
  await context.clearCookies({ name: "sessionid" });
  await saveUnlessSignedOut(page);

  await expect(page.getByRole("heading", { name: "Welcome back." })).toBeVisible();
  // The sign-in screen does not name the document (whoever is at the device may not be its owner).
  await expect(page.getByText("Unsaved changes to a document are kept in this window")).toBeVisible();
  await expect(page.getByText(name)).toHaveCount(0);
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();

  const reopened = page.getByRole("dialog");
  await expect(reopened.getByRole("textbox", { name: "Title" })).toHaveValue(`${name} renamed`);
  await expect(reopened.getByRole("textbox", { name: "New note" })).toHaveValue("Call the bank on Monday");
  const notice = reopened.locator(".draft-restored");
  await expect(notice).toContainText("not saved yet");
  await expect(notice).toBeFocused();
  // Nothing was saved behind the person's back.
  expect((await (await page.request.get(`/api/documents/${id}`)).json()).title).toBe(name);
  await reopened.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect.poll(async () => (await (await page.request.get(`/api/documents/${id}`)).json()).title).toBe(`${name} renamed`);
});

test("a kept draft puts back only what was edited: newer server changes win and are named as conflicts", async ({ page, context }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r8-conflict-${Date.now()}-${testInfo.project.name}`;
  const id = await uploadReady(page, name);
  const sender = await (await page.request.post("/api/correspondents", { headers: await csrf(page), data: { name: `${name}-sender` } })).json();
  await page.goto(`/?document=${id}`);
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("textbox", { name: "Title" }).fill(`${name} mine`);
  await dialog.getByLabel("Document date").fill("2026-03-14");
  // Meanwhile, elsewhere (another device, a workflow): the title and the sender change on the server.
  const patched = await page.request.patch(`/api/documents/${id}`, { headers: await csrf(page), data: { title: `${name} theirs`, correspondent_id: sender.id } });
  expect(patched.ok()).toBe(true);
  await context.clearCookies({ name: "sessionid" });
  await saveUnlessSignedOut(page);
  await expect(page.getByRole("heading", { name: "Welcome back." })).toBeVisible();
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();

  const reopened = page.getByRole("dialog");
  await expect(reopened.getByRole("textbox", { name: "Title" })).toHaveValue(`${name} theirs`); // the newer value
  await expect(reopened.getByLabel("Document date")).toHaveValue("2026-03-14"); // the edit nobody else touched
  await expect(reopened.locator("#detail-correspondent")).toHaveValue(sender.id); // not reverted
  await expect(reopened.locator(".draft-conflicts")).toContainText("Changed by someone else too");
  await expect(reopened.locator(".draft-conflicts")).toContainText("Title");
  await reopened.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect.poll(async () => (await (await page.request.get(`/api/documents/${id}`)).json()).document_date).toBe("2026-03-14");
  const saved = await (await page.request.get(`/api/documents/${id}`)).json();
  expect(saved.title).toBe(`${name} theirs`);
  expect(saved.correspondent?.id).toBe(sender.id);
});

test("signing out explicitly leaves no kept draft, and the sign-in screen can discard one", async ({ page, context }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r8-discard-${Date.now()}-${testInfo.project.name}`;
  const id = await uploadReady(page, name);
  await page.goto(`/?document=${id}`);
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("textbox", { name: "Title" }).fill(`${name} draft`);
  await context.clearCookies({ name: "sessionid" });
  await saveUnlessSignedOut(page);
  await expect(page.getByText("Unsaved changes to a document are kept in this window")).toBeVisible();
  await page.getByRole("button", { name: "Discard them" }).click();
  await expect(page.getByText("Unsaved changes to a document are kept in this window")).toHaveCount(0);
  expect(await page.evaluate(() => sessionStorage.getItem("ripiano.keptDraft"))).toBeNull();
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("the unsaved-changes question is modal: aria-modal, Tab stays inside, the form is inert, Esc keeps editing", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r8-modal-${Date.now()}-${testInfo.project.name}`;
  const id = await uploadReady(page, name);
  await page.goto(`/?document=${id}`);
  const dialog = page.getByRole("dialog");
  const title = dialog.getByRole("textbox", { name: "Title" });
  await title.fill(`${name} edited`);
  await page.keyboard.press("Escape");
  const question = page.getByRole("alertdialog", { name: "You have unsaved changes." });
  await expect(question).toHaveAttribute("aria-modal", "true");
  const keep = question.getByRole("button", { name: "Keep editing" });
  const discard = question.getByRole("button", { name: "Discard changes" });
  await expect(keep).toBeFocused();
  // Round 10 added "Save changes" between the two.
  await page.keyboard.press("Tab");
  await expect(question.getByRole("button", { name: "Save changes" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(discard).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(keep).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(discard).toBeFocused();
  // The document form behind the question cannot be reached.
  expect(await page.evaluate(() => Boolean(document.querySelector(".detail-panel form")?.closest("[inert]")))).toBe(true);
  expect(await page.evaluate(() => Boolean(document.querySelector(".unsaved-confirm")?.closest("[inert]")))).toBe(false);
  await page.keyboard.press("Escape");
  await expect(question).toHaveCount(0);
  await expect(title).toBeFocused();
  await expect(title).toHaveValue(`${name} edited`);
  expect(await page.evaluate(() => document.querySelectorAll(".detail-panel [inert]").length)).toBe(0);
});

test("Inbox: a failed Retry OCR keeps focus on the message, and its Retry retries OCR for that document", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r8-inbox-${Date.now()}-${testInfo.project.name}`;
  const base = await uploadReady(page, name);
  const failed = await failedDocument(page, base, `${name} damaged`);
  const listRequests: string[] = [];
  await page.route((url) => url.pathname === "/api/documents" && url.searchParams.get("view") === "exceptions", (route: Route) => {
    listRequests.push(route.request().url());
    return route.fulfill({ json: { documents: [failed], next_cursor: "next-page" } });
  });
  let retries = 0;
  await page.route(`**/api/documents/${FAKE_ID}/retry`, (route: Route) => {
    retries += 1;
    return retries === 1 ? route.fulfill({ status: 500, contentType: "text/html", body: "<h1>Server error</h1>" }) : route.fulfill({ json: { ok: true } });
  });
  await page.goto("/inbox");
  const row = page.locator(".exception-row").filter({ hasText: `${name} damaged` });
  await row.getByRole("button", { name: "Retry OCR" }).click();
  const alert = page.getByRole("alert");
  await expect(alert).toContainText("The server sent an unexpected reply.");
  await expect(alert).toBeFocused(); // not <body>
  const again = alert.getByRole("button", { name: `Retry OCR for “${name} damaged”` });
  const box = (await again.boundingBox())!;
  expect(box.height).toBeGreaterThanOrEqual(44);
  expect(box.width).toBeGreaterThanOrEqual(44);
  const loadsBefore = listRequests.length;
  await again.click();
  await expect.poll(() => retries).toBe(2);
  await expect(page.getByRole("status").filter({ hasText: "OCR restarted" })).toBeAttached();
  // The message's Retry never loads the list from the next page.
  expect(listRequests.slice(loadsBefore).some((url) => url.includes("cursor="))).toBe(false);
});

test("Library: Retry OCR on a failed row is a styled secondary button, not the browser default", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r8-libretry-${Date.now()}-${testInfo.project.name}`;
  const base = await uploadReady(page, name);
  const failed = await failedDocument(page, base, `${name} damaged`);
  await page.route((url) => url.pathname === "/api/documents" && !url.searchParams.get("view"), async (route: Route) => {
    if (route.request().method() !== "GET") return route.fallback();
    const response = await route.fetch();
    const body = await response.json();
    return route.fulfill({ response, json: { ...body, documents: [failed, ...(body.documents ?? [])] } });
  });
  await page.goto("/");
  const button = page.getByRole("button", { name: `Retry OCR for ${name} damaged.pdf` });
  await expect(button).toBeVisible();
  const style = await button.evaluate((element) => {
    const computed = getComputedStyle(element);
    return { background: computed.backgroundColor, border: computed.borderTopStyle, cursor: computed.cursor };
  });
  expect(style.background).not.toBe("rgb(239, 239, 239)");
  expect(style.border).toBe("solid");
  expect(style.cursor).toBe("pointer");
  if (testInfo.project.name === "mobile") {
    const box = (await button.boundingBox())!;
    expect(box.height).toBeGreaterThanOrEqual(44);
  }
  await page.unrouteAll({ behavior: "ignoreErrors" });
});

const STICKER = { copy: { id: "c8", sticker_code: "R-CAMERA08", location_id: null, location_path: ["Camera shelf"], missing_at: null }, document: { id: FAKE_ID, title: "Camera sticker document" } };

test("Find a sticker reads a QR code with the camera where the browser can, and stops the camera", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  // A stand-in for the browser's QR reader and the rear camera, so the test does not depend on real hardware.
  await page.addInitScript(() => {
    const w = window as unknown as Record<string, unknown>;
    w.__cameraStopped = false;
    w.BarcodeDetector = class {
      static async getSupportedFormats() { return ["qr_code", "ean_13"]; }
      calls = 0;
      async detect() { this.calls += 1; return this.calls < 3 ? [] : [{ rawValue: "https://archive.example.test/?sticker=r-camera08" }]; }
    };
    navigator.mediaDevices.getUserMedia = async () => {
      const canvas = document.createElement("canvas");
      canvas.width = 64; canvas.height = 64;
      canvas.getContext("2d")!.fillRect(0, 0, 64, 64);
      const stream = canvas.captureStream(5);
      for (const track of stream.getTracks()) {
        const stop = track.stop.bind(track);
        track.stop = () => { w.__cameraStopped = true; stop(); };
      }
      return stream;
    };
  });
  await page.route("**/api/stickers/R-CAMERA08", (route: Route) => route.fulfill({ json: STICKER }));
  await signIn(page);
  await page.goto("/paper");
  await expect(page.getByText("Scan the QR code with the camera, or type the code")).toBeVisible();
  await page.getByRole("button", { name: "Scan with camera" }).click();
  await expect(page.locator(".sticker-result")).toContainText("Camera sticker document");
  await expect(page.getByRole("dialog", { name: "Scan a sticker" })).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: "Sticker code" })).toHaveValue("R-CAMERA08");
  expect(await page.evaluate(() => (window as unknown as Record<string, unknown>).__cameraStopped)).toBe(true);
});

test("Find a sticker: a refused camera permission says so clearly", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.addInitScript(() => {
    (window as unknown as Record<string, unknown>).BarcodeDetector = class {
      static async getSupportedFormats() { return ["qr_code"]; }
      async detect() { return []; }
    };
    navigator.mediaDevices.getUserMedia = async () => { throw new DOMException("Permission denied", "NotAllowedError"); };
  });
  await signIn(page);
  await page.goto("/paper");
  await page.getByRole("button", { name: "Scan with camera" }).click();
  const camera = page.getByRole("dialog", { name: "Scan a sticker" });
  await expect(camera.getByRole("alert")).toContainText("Ripiano may not use the camera. Allow camera access for this site");
  await camera.getByRole("button", { name: "Type the code instead" }).click();
  await expect(camera).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Scan with camera" })).toBeFocused();
});

test("Find a sticker without a QR reader (iOS Safari): no camera button, the intro says how to scan instead", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.addInitScript(() => { delete (window as unknown as Record<string, unknown>).BarcodeDetector; });
  await page.route((url) => url.pathname.startsWith("/api/stickers/"), (route: Route) => route.fulfill({ status: 404, json: { error: "Sticker not found" } }));
  await signIn(page);
  await page.goto("/paper");
  await expect(page.getByText("open its QR code with your phone's camera app")).toBeVisible();
  await expect(page.getByRole("button", { name: "Scan with camera" })).toHaveCount(0);
  await expect(page.getByText("Scan a QR code or type")).toHaveCount(0);
  // The dismiss button of the error is a 44px target (J2 L1).
  const box = page.getByRole("textbox", { name: "Sticker code" });
  await box.fill("R-NOPE0008");
  await box.press("Enter");
  const dismiss = page.getByRole("alert").getByRole("button", { name: "Dismiss error" });
  const size = (await dismiss.boundingBox())!;
  expect(size.width).toBeGreaterThanOrEqual(44);
  expect(size.height).toBeGreaterThanOrEqual(44);
});

test("an open copy history shows a Move straight away", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r8-move-${Date.now()}-${testInfo.project.name}`;
  const id = await uploadReady(page, name);
  const headers = await csrf(page);
  const first = await (await page.request.post("/api/locations", { headers, data: { name: `${name}-from` } })).json();
  const second = await (await page.request.post("/api/locations", { headers, data: { name: `${name}-to` } })).json();
  const created = await page.request.post(`/api/documents/${id}/copies`, { headers, data: { location_id: first.id } });
  const sticker = (await created.json()).sticker_code as string;
  await page.goto(`/?document=${id}`);
  const card = page.getByRole("dialog").locator(".copy-card").filter({ hasText: sticker });
  await card.getByRole("button", { name: `History of paper copy ${sticker}` }).click();
  const history = card.getByRole("list", { name: `History of paper copy ${sticker}` });
  await expect(history.getByRole("listitem")).toHaveCount(1);
  await card.getByRole("combobox", { name: `New location for paper copy ${sticker}` }).selectOption({ label: second.path.join(" / ") });
  await card.getByRole("button", { name: `Move paper copy ${sticker}` }).click();
  await expect(history.getByRole("listitem")).toHaveCount(2);
  await expect(history.getByRole("listitem").first()).toContainText(`${name}-to`);
});

test("offline and waiting-upload notices appear inside live regions that are already on the page", async ({ page, context }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  // The offline notice keeps documents already on screen, so wait for the list first.
  if (!(await page.locator(".document-row").count())) await uploadReady(page, `r8-live-${Date.now()}`);
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.locator(".document-row").first()).toBeVisible();
  const regions = page.locator(".notice-region[aria-live='polite']");
  await expect(regions).toHaveCount(2);
  await expect(regions.first()).toBeEmpty();
  await context.setOffline(true);
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(regions.first().locator(".stale-notice")).toContainText("You're offline or Ripiano can't be reached.");
  await context.setOffline(false);
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(regions.first()).toBeEmpty();
});

test("a revoked share link says why instead of showing its expiry date", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r8-revoked-${Date.now()}-${testInfo.project.name}`;
  const id = await uploadReady(page, name);
  const later = new Date(Date.now() + 7 * 86400000).toISOString();
  const now = new Date().toISOString();
  await page.route(`**/api/documents/${id}/shares`, (route: Route) => route.request().method() !== "GET" ? route.fallback() : route.fulfill({ json: { shares: [
    { id: "s1", created_at: now, expires_at: later, revoked_at: now, revoked_reason: "password_changed", active: false },
    { id: "s2", created_at: now, expires_at: later, revoked_at: now, revoked_reason: "account_off", active: false },
    { id: "s3", created_at: now, expires_at: later, revoked_at: now, revoked_reason: "something_new", active: false },
    { id: "s4", created_at: now, expires_at: later, revoked_at: now, revoked_reason: null, active: false },
  ] } }));
  await page.goto(`/?document=${id}`);
  const share = page.getByRole("dialog").getByRole("region", { name: "Share original" });
  await share.getByText("Manage share links").click();
  const rows = share.locator(".share-list li");
  await expect(rows).toHaveCount(4);
  await expect(rows.nth(0)).toContainText("Revoked because your password changed");
  await expect(rows.nth(1)).toContainText("Revoked because the account was turned off");
  await expect(rows.nth(2)).toContainText("Revoked");
  await expect(rows.nth(3)).toContainText("Revoked");
  await expect(share.locator(".share-list")).not.toContainText("Expires");
});

test("Agents activity shows the newest 20 with Show more, and names unknown tools in plain words", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  const start = Date.UTC(2026, 10, 19, 12, 0, 0);
  const events = Array.from({ length: 45 }, (_, index) => ({
    agent: "R8 agent", action: index === 0 ? "read_document_text" : "search_documents", document_id: null, document_title: null,
    outcome: index === 0 ? "denied" : "ok", at: new Date(start - index * 60000).toISOString(),
  }));
  await page.route("**/api/agents/events", (route: Route) => route.fulfill({ json: { events: [...events].reverse() } }));
  await signIn(page);
  await page.goto("/agents");
  const list = page.getByRole("list", { name: "Recent activity" });
  await expect(list.getByRole("listitem")).toHaveCount(20);
  // Newest first, and a tool Ripiano does not offer is described, not shown as a raw identifier.
  await expect(list.getByRole("listitem").first()).toContainText("Asked for an action Ripiano does not offer (“read document text”)");
  await page.getByRole("button", { name: "Show 20 more (25 older)" }).click();
  await expect(list.getByRole("listitem")).toHaveCount(40);
  await expect(list.getByRole("listitem").nth(20)).toBeFocused();
  await page.getByRole("button", { name: "Show 5 more (5 older)" }).click();
  await expect(list.getByRole("listitem")).toHaveCount(45);
  await expect(page.getByRole("button", { name: /^Show \d+ more/ })).toHaveCount(0);
});

test("Workflows intro says which actions run once and that change workflows run on every change", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  await page.goto("/workflows");
  await expect(page.getByText("runs again on every matching change; notes, webhooks and emails are still sent only once per document")).toBeVisible();
  await expect(page.getByText("Each workflow acts once per document")).toHaveCount(0);
});

// Follow-up to J1 M2: a damaged PDF whose readable pages were saved is "ready" with a processing warning, shown as a
// calm notice with "Mark as checked" (not as a failure with Retry OCR). The warning fields are simulated.
async function warnedDocument(page: Page, id: string, title: string, reviewed = false) {
  const real = await (await page.request.get(`/api/documents/${id}`)).json();
  return {
    ...real, id: FAKE_ID, title, original_name: `${title}.pdf`, status: "ready",
    processing_warning: "damaged_pdf", warning: "Some pages of this PDF were damaged; the readable pages were saved and are searchable.",
    processing_warning_reviewed_at: reviewed ? new Date().toISOString() : null,
  };
}

test("Inbox: a partly readable PDF is a warning with Mark as checked, not a failure with Retry OCR", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r8-warn-inbox-${Date.now()}-${testInfo.project.name}`;
  const warned = await warnedDocument(page, await uploadReady(page, name), `${name} partly`);
  let checked = false;
  let patchBody: unknown = null;
  await page.route((url) => url.pathname === "/api/documents" && url.searchParams.get("view") === "exceptions",
    (route: Route) => route.fulfill({ json: { documents: checked ? [] : [warned], next_cursor: null } }));
  await page.route(`**/api/documents/${FAKE_ID}`, (route: Route) => {
    if (route.request().method() !== "PATCH") return route.fallback();
    patchBody = route.request().postDataJSON();
    checked = true;
    return route.fulfill({ json: { ...warned, processing_warning_reviewed_at: new Date().toISOString() } });
  });
  await page.goto("/inbox");
  const row = page.locator(".exception-row").filter({ hasText: `${name} partly` });
  await expect(row.locator(".doc-warning")).toContainText("the readable pages were saved");
  await expect(row.locator(".doc-error")).toHaveCount(0);
  await expect(row.getByRole("button", { name: "Retry OCR" })).toHaveCount(0);
  await row.getByRole("button", { name: "Mark as checked" }).click();
  await expect.poll(() => patchBody).toEqual({ processing_warning_reviewed: true });
  await expect(page.getByRole("status").filter({ hasText: `“${name} partly” marked as checked.` })).toBeAttached();
  await expect(row).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Nothing needs your attention." })).toBeFocused();
});

test("document dialog and Library row show a damaged-PDF warning calmly; Mark as checked quiets it", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r8-warn-doc-${Date.now()}-${testInfo.project.name}`;
  const warned = await warnedDocument(page, await uploadReady(page, name), `${name} partly`);
  let reviewed = false;
  await page.route((url) => url.pathname === "/api/documents" && !url.searchParams.get("view"), async (route: Route) => {
    if (route.request().method() !== "GET") return route.fallback();
    const response = await route.fetch();
    const body = await response.json();
    return route.fulfill({ response, json: { ...body, documents: [reviewed ? { ...warned, processing_warning_reviewed_at: "2026-11-19T12:00:00Z" } : warned, ...(body.documents ?? [])] } });
  });
  await page.route(`**/api/documents/${FAKE_ID}`, (route: Route) => {
    if (route.request().method() === "PATCH") {
      reviewed = true;
      return route.fulfill({ json: { ...warned, processing_warning_reviewed_at: new Date().toISOString() } });
    }
    return route.request().method() === "GET" ? route.fulfill({ json: warned }) : route.fallback();
  });
  await page.goto("/");
  const row = page.locator(".document-row").filter({ hasText: `${name} partly` }).first();
  await expect(row.locator(".doc-warning")).toContainText("the readable pages were saved");
  await expect(row.locator(".status")).toHaveText("Check pages");
  await expect(row.getByRole("button", { name: /^Retry OCR for/ })).toHaveCount(0);
  await expect(row).not.toContainText("Processing failed");

  await page.goto(`/?document=${FAKE_ID}`);
  const dialog = page.getByRole("dialog");
  const notice = dialog.locator(".processing-warning");
  await expect(notice).toContainText("the readable pages were saved");
  // Not presented as a failure: no "Processing failed" error under Files.
  await expect(dialog.locator(".detail-files .inline-error")).toHaveCount(0);
  await notice.getByRole("button", { name: "Mark as checked" }).click();
  await expect(notice).toContainText("(checked)");
  await expect(notice.getByRole("button", { name: "Mark as checked" })).toHaveCount(0);
  await expect(notice).toBeFocused();
  await page.unrouteAll({ behavior: "ignoreErrors" }); // a Library refresh may still be in flight
});

test("Overview counts partly readable files among the things that need a look", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.route("**/api/overview", async (route: Route) => {
    const response = await route.fetch();
    const body = await response.json();
    return route.fulfill({ response, json: { ...body, documents: { ...body.documents, warnings: 2 } } });
  });
  await signIn(page);
  await page.goto("/overview");
  await page.getByRole("button", { name: "2 were only partly readable: check their pages" }).click();
  await expect(page).toHaveURL(/\/inbox$/);
});

test("a skipped workflow run is labelled Skipped and styled neutrally, not as applied", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.route("**/api/workflows", async (route: Route) => {
    if (route.request().method() !== "GET") return route.fallback();
    const response = await route.fetch();
    const body = await response.json();
    const run = { id: "run-r8", workflow: "R8 skipped flow", document: { id: FAKE_ID, title: "R8 skipped document" }, trigger: "updated", status: "skipped", detail: "", created_at: new Date().toISOString() };
    return route.fulfill({ response, json: { ...body, runs: [run, ...(body.runs ?? [])] } });
  });
  await signIn(page);
  await page.goto("/workflows");
  const item = page.getByRole("list", { name: "Recent runs" }).getByRole("listitem").filter({ hasText: "R8 skipped flow" });
  const badge = item.locator(".workflow-run-status");
  await expect(badge).toHaveText("Skipped");
  await expect(badge).toHaveClass(/workflow-run-skipped/);
  await expect(item).not.toContainText("Applied");
});
