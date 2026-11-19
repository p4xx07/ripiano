import { expect, test, type Page } from "@playwright/test";
import { deflateSync } from "node:zlib";

// Round-6 judge regressions owned by the web slice: Move keeps the shown location (J2 H1), unsaved edits are
// not thrown away silently (J1 M2) and saving is confirmed (J1 L1), touch targets (J1 M3), focus after
// async actions (J2 M1, J1 L4, J2 L4), distinct control names (J2 M2), sticker creation is announced
// (J2 L1), the `g p` shortcut (J1 L4) and Italian install metadata and search help (J2 L2/L3).
// Every test works on its own new document and location; nothing shared is changed.
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

async function navigate(page: Page, name: string) {
  const menu = page.getByRole("button", { name: "Toggle menu" });
  const mobile = await menu.isVisible();
  if (mobile) await menu.click();
  await page.getByRole("button", { name, exact: true }).click();
  if (mobile) await expect.poll(() => page.locator(".sidebar").evaluate((element) => element.getBoundingClientRect().right)).toBeLessThan(1);
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

async function createLocation(page: Page, name: string): Promise<{ id: string; path: string[] }> {
  const response = await page.request.post("/api/locations", { headers: await csrf(page), data: { name } });
  expect(response.status()).toBe(201);
  return response.json();
}

async function openDocument(page: Page, id: string) {
  await page.goto(`/?document=${id}`);
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("textbox", { name: "Title" })).toBeVisible();
  return dialog;
}

const activeTag = (page: Page) => page.evaluate(() => document.activeElement?.tagName ?? "");

test("Move without changing the list keeps the copy's location, and a real move keeps focus", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r6-move-${Date.now()}-${testInfo.project.name}`;
  const id = await uploadReady(page, name);
  const first = await createLocation(page, `${name}-shelf`);
  const second = await createLocation(page, `${name}-box`);
  const created = await page.request.post(`/api/documents/${id}/copies`, { headers: await csrf(page), data: { location_id: first.id } });
  expect(created.status()).toBe(201);
  const copy = await created.json() as { id: string; sticker_code: string };
  const dialog = await openDocument(page, id);
  const card = dialog.locator(".copy-card").filter({ hasText: copy.sticker_code });
  const list = card.getByRole("combobox", { name: `New location for paper copy ${copy.sticker_code}` });
  await expect(list).toHaveValue(first.id);
  // The Move button names its copy (J2 M2), and pressing it untouched changes nothing (J2 H1).
  const move = card.getByRole("button", { name: `Move paper copy ${copy.sticker_code}` });
  await move.click();
  await expect(dialog.getByRole("status").filter({ hasText: "is already there" })).toBeVisible();
  const location = async () => ((await (await page.request.get(`/api/documents/${id}/copies`)).json()).copies as { id: string; location_id: string | null }[])
    .find((item) => item.id === copy.id)?.location_id;
  expect(await location()).toBe(first.id);
  await expect(card).toContainText(`${name}-shelf`);
  // A real move: the button keeps focus (J2 M1) and the notice suggests reprinting the sticker (J1 L6).
  await list.selectOption(second.id);
  await move.focus();
  await page.keyboard.press("Enter");
  await expect(dialog.getByRole("status").filter({ hasText: "moved" })).toContainText("print it again");
  await expect.poll(location).toBe(second.id);
  await expect(move).toBeFocused();
  await expect(list).toHaveValue(second.id);
  // Pressing Move again does not clear the new location either.
  await move.click();
  await expect(dialog.getByRole("status").filter({ hasText: "is already there" })).toBeVisible();
  expect(await location()).toBe(second.id);
});

test("creating a sticker is announced", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r6-sticker-${Date.now()}-${testInfo.project.name}`;
  const id = await uploadReady(page, name);
  const shelf = await createLocation(page, `${name}-shelf`);
  const dialog = await openDocument(page, id);
  await dialog.getByRole("combobox", { name: "Location for the new paper copy" }).selectOption(shelf.id);
  const create = dialog.getByRole("button", { name: "Create sticker" });
  await create.click();
  await expect(dialog.getByRole("status").filter({ hasText: "created for" })).toContainText(`${name}-shelf`);
  await expect(create).toBeFocused();
});

test("closing with unsaved edits asks first; Save is confirmed on screen", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r6-unsaved-${Date.now()}-${testInfo.project.name}`;
  const id = await uploadReady(page, name);
  const title = async () => (await (await page.request.get(`/api/documents/${id}`)).json()).title as string;
  const before = await title();
  let dialog = await openDocument(page, id);
  // Nothing changed: Close closes at once.
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  dialog = await openDocument(page, id);
  const titleField = dialog.getByRole("textbox", { name: "Title" });
  await titleField.fill(`${before} edited`);
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  await expect(dialog.getByText("You have unsaved changes.")).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Keep editing" })).toBeFocused();
  await dialog.getByRole("button", { name: "Keep editing" }).click();
  await expect(dialog.getByText("You have unsaved changes.")).toHaveCount(0);
  await expect(titleField).toHaveValue(`${before} edited`);
  // Esc asks too, and Esc again answers "keep editing".
  await titleField.focus();
  await page.keyboard.press("Escape");
  await expect(dialog.getByRole("button", { name: "Keep editing" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog.getByText("You have unsaved changes.")).toHaveCount(0);
  await expect(titleField).toBeFocused();
  await page.keyboard.press("Escape");
  await dialog.getByRole("button", { name: "Discard changes" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(await title()).toBe(before);

  // Saving closes the dialog and says so where it can be seen.
  dialog = await openDocument(page, id);
  await dialog.getByRole("textbox", { name: "Title" }).fill(`${name} saved`);
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator(".saved-notice")).toBeVisible();
  await expect(page.locator(".saved-notice")).toContainText(`Saved “${name} saved”.`);
  expect(await title()).toBe(`${name} saved`);
});

test("document dialog controls are at least 44px tall on touch screens", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.skip(testInfo.project.name !== "mobile", "Touch-target sizes apply to coarse pointers");
  await signIn(page);
  const name = `r6-touch-${Date.now()}-${testInfo.project.name}`;
  const id = await uploadReady(page, name);
  const shelf = await createLocation(page, `${name}-shelf`);
  expect((await page.request.post(`/api/documents/${id}/copies`, { headers: await csrf(page), data: { location_id: shelf.id } })).status()).toBe(201);
  const dialog = await openDocument(page, id);
  await expect(dialog.locator(".copy-card")).toHaveCount(1);
  const small = await dialog.evaluate((root) => {
    const selector = "input:not([type=checkbox]):not([type=radio]):not([type=hidden]):not([type=file]), select, .button, .tag-choice";
    return Array.from(root.querySelectorAll<HTMLElement>(selector))
      .filter((element) => element.getClientRects().length > 0 && !element.closest(".visually-hidden"))
      .map((element) => ({ label: element.getAttribute("aria-label") ?? element.textContent?.trim().slice(0, 40) ?? element.tagName, height: element.getBoundingClientRect().height }))
      .filter((item) => item.height < 44 - 0.5);
  });
  expect(small).toEqual([]);
});

test("focus stays put after OCR, notes, clear search and a failed sign-in", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  // A failed sign-in (an account that does not exist, so no real account is rate-limited) keeps focus on the
  // button and marks both fields invalid (J2 L4).
  await page.goto("/");
  await page.getByLabel("Username").fill(`r6-nobody-${Date.now()}`);
  await page.getByLabel("Password").fill("not-the-password");
  const signInButton = page.getByRole("button", { name: "Sign in" });
  await signInButton.click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(signInButton).toBeFocused();
  await expect(page.getByLabel("Username")).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByLabel("Password")).toHaveAttribute("aria-invalid", "true");

  await signIn(page);
  await expect(page.getByLabel("Username")).toHaveCount(0);
  const name = `r6-focus-${Date.now()}-${testInfo.project.name}`;
  // Clear search returns focus to the search field (J1 L4).
  const search = page.getByRole("textbox", { name: /Search documents by text/ });
  await search.fill(name);
  await page.getByRole("button", { name: "Clear search" }).click();
  await expect(search).toBeFocused();
  await expect(search).toHaveValue("");

  const id = await uploadReady(page, name);
  const dialog = await openDocument(page, id);
  // Add note: the keyboard stays in the note field (J2 M1).
  const note = dialog.getByRole("textbox", { name: "New note" });
  await note.fill(`${name} note`);
  await dialog.getByRole("button", { name: "Add note" }).click();
  await expect(dialog.getByRole("status").filter({ hasText: "Note added." })).toBeVisible();
  await expect(note).toBeFocused();
  // Retry OCR: the button stays (marked unavailable while OCR runs) and keeps focus.
  const ocr = dialog.getByRole("button", { name: "Retry OCR" });
  await ocr.focus();
  await page.keyboard.press("Enter");
  await expect(dialog.getByRole("status").filter({ hasText: "OCR queued" })).toBeVisible();
  await expect(ocr).toBeFocused();
  expect(await activeTag(page)).toBe("BUTTON");
  await expect.poll(async () => (await (await page.request.get(`/api/documents/${id}`)).json()).status, { timeout: 90000 }).toBe("ready");
  await expect(ocr).not.toHaveAttribute("aria-disabled", "true");
});

test("paper archive controls name their location, and g then p opens it", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r6-labels-${Date.now()}-${testInfo.project.name}`;
  await createLocation(page, `${name}-shelf`);
  if (testInfo.project.name === "desktop") {
    await page.keyboard.press("g");
    await page.keyboard.press("p");
  } else {
    await navigate(page, "Paper archive");
  }
  await expect(page).toHaveURL(/\/paper$/);
  await expect(page.getByRole("button", { name: `View contents of ${name}-shelf`, exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: `Print label for ${name}-shelf`, exact: true })).toBeVisible();
  if (testInfo.project.name === "desktop") {
    await page.keyboard.press("?");
    await expect(page.getByRole("dialog")).toContainText("Go to Paper archive");
  }
});

test("Italian: install metadata and search help are in Italian", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  await page.evaluate(() => localStorage.setItem("ripiano.language", "it"));
  try {
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("lang", "it");
    const href = await page.locator('link[rel="manifest"]').getAttribute("href");
    expect(href).toMatch(/-it\.webmanifest$/);
    const manifest = await (await page.request.get(href!)).json();
    expect(manifest.lang).toBe("it");
    expect(manifest.description).toBe("I tuoi documenti, al loro posto.");
    const help = page.locator("details.search-syntax");
    if (testInfo.project.name === "mobile") await page.getByRole("button", { name: /^Filtri/ }).click();
    await help.locator("summary").click();
    await expect(help).toContainText("is:untagged (senza etichette)");
    await expect(help).toContainText("is:tagged (con almeno un'etichetta)");
    // Switching back to English swaps the manifest too.
    await page.evaluate(() => localStorage.setItem("ripiano.language", "en"));
    await page.reload();
    await expect(page.locator('link[rel="manifest"]')).toHaveAttribute("href", /(?<!-it)\.webmanifest$/);
  } finally {
    await page.evaluate(() => localStorage.removeItem("ripiano.language"));
  }
});

test("agent activity names the document and labels refusals", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  // The rows are answered here, so the check does not depend on this account's real agent history.
  await page.route("**/api/agents/events", (route) => route.fulfill({ json: { events: [
    { agent: "r6-agent", action: "add_tag", document_id: "00000000-0000-0000-0000-000000000001", document_title: "r6 Electricity bill", outcome: "denied", at: "2026-11-18T10:00:00Z" },
    { agent: "r6-agent", action: "search_documents", document_id: null, outcome: "ok", at: "2026-11-18T09:00:00Z" },
  ] } }));
  await navigate(page, "Agents");
  const rows = page.getByRole("list", { name: "Recent activity" }).getByRole("listitem");
  await expect(rows.first()).toContainText("on “r6 Electricity bill”");
  await expect(rows.first()).toContainText("refused");
  await expect(rows.nth(1)).toContainText("done");
  await expect(rows.nth(1)).not.toContainText("on “");
});

test("Back with unsaved edits returns to the document and asks first", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r6-back-${Date.now()}-${testInfo.project.name}`;
  const id = await uploadReady(page, name);
  // Open the document inside the app, so Back has a Library entry to go to.
  await page.evaluate((documentId) => {
    window.history.pushState(null, "", `/?document=${documentId}`);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, id);
  const dialog = page.getByRole("dialog");
  const titleField = dialog.getByRole("textbox", { name: "Title" });
  await expect(titleField).toBeVisible();
  await titleField.fill(`${name} edited`);
  await page.goBack();
  await expect(dialog.getByText("You have unsaved changes.")).toBeVisible();
  await expect(titleField).toHaveValue(`${name} edited`);
  await expect.poll(() => new URL(page.url()).searchParams.get("document")).toBe(id);
  await dialog.getByRole("button", { name: "Discard changes" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect.poll(() => new URL(page.url()).searchParams.get("document")).toBeNull();
});
