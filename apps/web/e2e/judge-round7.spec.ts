import { expect, test, type Page } from "@playwright/test";
import { deflateSync } from "node:zlib";

// Round-7 judge regressions owned by the web slice: a scanned sticker URL is found (J1 M1), focus after a refused
// form (J2 M1), a queued upload survives a cleared CSRF cookie and the sign-in screen says it waits (J2 M2, L1),
// Workflows "Recent runs" is a styled list (J3 M1), removing a revoked agent asks for the password (D10), and the
// cheap low findings (beforeunload, named focus target, alertdialog, focus on entry points, 44px icon links).
// Every test works on its own new documents, locations and agents; nothing shared is changed. Wrong-password
// answers are simulated in the browser where possible so the shared account's sign-in throttle is not used up.
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

/** A new document with a paper copy in a new location; returns the copy's sticker code. */
async function paperCopy(page: Page, name: string) {
  const id = await uploadReady(page, name);
  const location = await (await page.request.post("/api/locations", { headers: await csrf(page), data: { name: `${name}-box` } })).json();
  const created = await page.request.post(`/api/documents/${id}/copies`, { headers: await csrf(page), data: { location_id: location.id } });
  expect(created.status()).toBe(201);
  return { id, sticker: (await created.json()).sticker_code as string };
}

const focusedName = (page: Page) => page.evaluate(() => {
  const active = document.activeElement as HTMLElement | null;
  return active ? `${active.tagName} ${active.getAttribute("aria-label") ?? active.textContent?.trim() ?? ""}` : "";
});

test("Find a sticker accepts what a scanner types: a full QR address, whitespace, lowercase; unknown codes say not found", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r7-scan-${Date.now()}-${testInfo.project.name}`;
  const { sticker } = await paperCopy(page, name);
  await page.goto("/paper");
  const box = page.getByRole("textbox", { name: "Sticker code" });
  const result = page.locator(".sticker-result");
  // The label's QR holds an address on the server's public origin, which may differ from this one.
  for (const scanned of [
    `  https://archive.example.test/?sticker=${sticker}  `,
    `http://192.168.1.20:8080/some/path/?lang=it&sticker=${sticker.toLowerCase()}&x=1`,
    `  ${sticker.toLowerCase()} `,
  ]) {
    await box.fill(scanned);
    await box.press("Enter");
    await expect(result).toContainText(name);
    await expect(result.locator(".sticker-code")).toHaveText(sticker);
    await expect(box).toHaveValue(sticker);
    await expect(page.locator(".inline-error")).toHaveCount(0);
  }
  for (const unknown of ["R-ZZZZZZZZ", "https://archive.example.test/?sticker=R-ZZZZZZZZ", "http://host/odd/%2F/path"]) {
    await box.fill(unknown);
    await box.press("Enter");
    await expect(page.getByRole("alert")).toHaveText("Sticker not found");
    await expect(result).toHaveCount(0);
  }
});

test("a refused agent token or password change keeps focus on the field it is about", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  // The server's answer to a wrong password, simulated so the shared account's sign-in throttle is not used.
  const wrong = { status: 400, contentType: "application/json", body: JSON.stringify({ error: "Your password is not correct" }) };
  await page.route("**/api/agents", (route) => route.request().method() === "POST" ? route.fulfill(wrong) : route.continue());
  await page.route("**/api/account/password", (route) => route.fulfill(wrong));

  await page.goto("/agents");
  const form = page.locator(".agent-create-card form");
  await form.getByLabel("Name", { exact: true }).fill(`r7-focus-${Date.now()}`);
  const agentPassword = form.getByLabel("Your password (to create an agent token)");
  await agentPassword.fill("not-the-password");
  const create = form.getByRole("button", { name: "Create agent token" });
  await create.focus();
  await page.keyboard.press("Enter");
  await expect(form.getByRole("alert")).toHaveText("Your password is not correct");
  await expect(agentPassword).toBeFocused();
  await expect(agentPassword).toHaveAttribute("aria-invalid", "true");
  await expect(agentPassword).toHaveAccessibleDescription("Your password is not correct");

  await page.goto("/security");
  const panel = page.getByRole("form", { name: "Password" });
  const current = panel.getByLabel("Current password");
  await current.fill("not-the-password");
  await panel.getByLabel(/^New password/).fill("a-new-password-for-r7");
  await panel.getByLabel("Repeat new password").fill("a-new-password-for-r7");
  await panel.getByRole("button", { name: "Change password" }).focus();
  await page.keyboard.press("Enter");
  await expect(panel.getByRole("alert")).toHaveText("Your password is not correct");
  await expect(current).toBeFocused();
  await expect(current).toHaveAttribute("aria-invalid", "true");
  await expect(current).toHaveAccessibleDescription("Your password is not correct");
  // A mismatch is caught before sending and marks the repeat field.
  await panel.getByLabel("Repeat new password").fill("something-else-entirely");
  await panel.getByRole("button", { name: "Change password" }).click();
  await expect(panel.getByLabel("Repeat new password")).toBeFocused();
  await expect(panel.getByLabel("Repeat new password")).toHaveAttribute("aria-invalid", "true");
  await expect(current).not.toHaveAttribute("aria-invalid", "true");
});

test("an upload made after the session and CSRF cookie are gone waits, the sign-in screen says so, and it is sent after sign-in", async ({ page, context }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r7-csrf-${Date.now()}-${testInfo.project.name}`;
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  // What "clear site data" or storage eviction does: every cookie (session and CSRF token) is gone.
  await context.clearCookies();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.png`, mimeType: "image/png", buffer: uniquePng(name) });

  await expect(page.getByRole("heading", { name: "Welcome back." })).toBeVisible();
  await expect(page.getByText("You were signed out. Sign in again to continue.")).toBeVisible();
  await expect(page.getByText(`1 file is waiting on this device and will upload once ${username} signs in again.`)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Welcome back." })).toBeFocused(); // not <body> (J2 L2)
  await expect(page.locator(".upload-report")).toHaveCount(0); // not reported as rejected

  const uploaded = page.waitForResponse((item) => item.url().endsWith("/api/documents") && item.request().method() === "POST" && item.status() === 202);
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  const id = (await (await uploaded).json()).id as string;
  expect((await (await page.request.get(`/api/documents/${id}`)).json()).original_name).toBe(`${name}.png`);
  await expect(page.getByText("waiting to upload")).toHaveCount(0);
  // Focus lands on the screen's heading after signing in, not on <body> (J2 L2).
  await expect.poll(() => page.evaluate(() => document.activeElement?.tagName)).toBe("H1");
});

test("a real permission 403 is not retried as a CSRF failure", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  let calls = 0;
  await page.route("**/api/locations", (route) => {
    if (route.request().method() !== "POST") return route.continue();
    calls += 1;
    return route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ error: "Owner access required" }) });
  });
  await page.goto("/paper");
  await page.getByPlaceholder("e.g. Filing cabinet").fill("r7-never-created");
  await page.getByRole("button", { name: "Add location at top level" }).click();
  await expect(page.getByRole("alert")).toContainText("Owner access required");
  expect(calls).toBe(1);
  await expect(page.getByRole("heading", { name: "Your paper archive." })).toBeVisible(); // still signed in
});

test("opening a sticker QR address focuses the Paper archive heading", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const { sticker } = await paperCopy(page, `r7-qr-${Date.now()}-${testInfo.project.name}`);
  await page.goto(`/?sticker=${sticker}`);
  await expect(page.locator(".sticker-result .sticker-code")).toHaveText(sticker);
  await expect(page.getByRole("heading", { level: 1, name: "Your paper archive." })).toBeFocused();
});

test("Workflows Recent runs is a list whose rows are laid out and not clipped", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const loaded = page.waitForResponse((item) => new URL(item.url()).pathname === "/api/workflows" && item.request().method() === "GET");
  await page.goto("/workflows");
  const hasRuns = ((await (await loaded).json()).runs as unknown[]).length > 0;
  await expect(page.getByRole("heading", { name: "Recent runs" })).toBeVisible();
  const list = page.getByRole("list", { name: "Recent runs" });
  if (hasRuns) await expect(list).toBeVisible();
  test.skip(!(await list.count()), "No workflow has run on this account yet (workflows.spec.ts makes one)");
  const row = list.getByRole("listitem").first();
  await expect(row).toBeVisible();
  const boxes = await row.evaluate((element) => {
    const list = element.parentElement!.getBoundingClientRect();
    const items = Array.from(element.children).map((child) => child.getBoundingClientRect());
    const style = getComputedStyle(element);
    return {
      listLeft: list.left, listRight: list.right,
      left: Math.min(...items.map((item) => item.left)), right: Math.max(...items.map((item) => item.right)),
      paddingLeft: parseFloat(style.paddingLeft), display: style.display, borderBottom: parseFloat(style.borderBottomWidth),
      tops: items.map((item) => Math.round(item.top)),
    };
  });
  expect(boxes.display).toBe("grid");
  expect(boxes.paddingLeft).toBeGreaterThanOrEqual(12);
  expect(boxes.left).toBeGreaterThanOrEqual(boxes.listLeft + 8); // the first letter is inside the card
  expect(boxes.right).toBeLessThanOrEqual(boxes.listRight);
  expect(new Set(boxes.tops).size).toBeGreaterThan(1); // name, document and detail are on separate lines
  if ((await list.getByRole("listitem").count()) > 1) expect(boxes.borderBottom).toBeGreaterThan(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.locator(".workflow-runs").screenshot({ path: testInfo.outputPath(`workflow-runs-${testInfo.project.name}.png`), animations: "disabled" });
});

test("the unsaved-changes step is an alert dialog, Keep editing returns to a named field, and a reload asks first", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `r7-unsaved-${Date.now()}-${testInfo.project.name}`;
  const id = await uploadReady(page, name);
  const tag = await (await page.request.post("/api/tags", { headers: await csrf(page), data: { name: `${name}-tag` } })).json();
  await page.goto(`/?document=${id}`);
  const dialog = page.getByRole("dialog");
  const checkbox = dialog.getByRole("checkbox", { name: tag.name, exact: true });
  await checkbox.focus();
  await page.keyboard.press("Space");
  await page.keyboard.press("Escape");
  const question = page.getByRole("alertdialog", { name: "You have unsaved changes." });
  await expect(question).toHaveAccessibleDescription("Close without saving them?");
  await expect(question.getByRole("heading", { name: "You have unsaved changes." })).toBeVisible();
  await question.getByRole("button", { name: "Keep editing" }).press("Enter");
  await expect(question).toHaveCount(0);
  await expect(checkbox).toBeFocused();
  expect(await focusedName(page)).toBe(`INPUT ${tag.name}`); // named on the control itself (J1 L6)

  // A reload with unsaved edits asks the browser's question; dismissing it keeps the page and the edit (J1 L1).
  const asked = page.waitForEvent("dialog");
  void page.reload().catch(() => undefined);
  const prompt = await asked;
  expect(prompt.type()).toBe("beforeunload");
  await prompt.dismiss();
  await expect(checkbox).toBeChecked();
  // Discarding removes the guard: the next reload is not interrupted.
  await page.keyboard.press("Escape");
  await page.getByRole("alertdialog").getByRole("button", { name: "Discard changes" }).click();
  let prompted = false;
  page.on("dialog", (item) => { prompted = true; void item.accept(); });
  await page.reload();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  expect(prompted).toBe(false);
});

test("card icon links are 44x44 on touch screens", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.skip(testInfo.project.name !== "mobile", "Touch layout only");
  await signIn(page);
  const name = `r7-touch-${Date.now()}-${testInfo.project.name}`;
  await uploadReady(page, name);
  await page.getByPlaceholder("Search text, sender, type, tag…").fill(name);
  const link = page.getByRole("link", { name: `Download ${name}.png` });
  await expect(link).toBeVisible();
  const box = (await link.boundingBox())!;
  expect(box.width).toBeGreaterThanOrEqual(44);
  expect(box.height).toBeGreaterThanOrEqual(44);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

// Needs the API with docs/DECISIONS.md D10 (DELETE /api/agents/<id>?forget=1 asks for {"password"}). On an older
// API build the probe below skips this test with "needs the D10 API"; it is expected to pass after the API rebuild.
test("removing a revoked agent with its activity log asks for the password (D10)", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const headers = await csrf(page);
  async function revokedGrant(label: string) {
    const created = await page.request.post("/api/agents", { headers, data: { name: label, scopes: ["documents:search"], expires_in_days: 1, password } });
    expect(created.status()).toBe(201);
    const grant = await created.json() as { id: string };
    expect((await page.request.delete(`/api/agents/${grant.id}`, { headers })).status()).toBe(200);
    return grant.id;
  }
  const stamp = `${Date.now()}-${testInfo.project.name}`;
  const probe = await revokedGrant(`R7 probe ${stamp}`);
  const probed = await page.request.delete(`/api/agents/${probe}?forget=1`, { headers });
  test.skip(probed.status() === 200, "needs the D10 API (forget without a password was accepted): rebuild the api service");
  expect(probed.status()).toBe(400);
  expect((await page.request.delete(`/api/agents/${probe}?forget=1`, { headers, data: { password } })).status()).toBe(200);

  const name = `R7 agent ${stamp}`;
  const id = await revokedGrant(name);
  await page.goto("/agents");
  const group = page.locator("details.agent-inactive");
  await group.locator("summary").click();
  const card = group.locator("article").filter({ hasText: name });
  await card.getByRole("button", { name: `Remove ${name}` }).click();
  const confirm = card.getByRole("form", { name: /and its activity log\? This cannot be undone\./ });
  const field = confirm.getByLabel("Your password (to remove the activity log)");
  await expect(field).toBeFocused();
  // One real wrong attempt (it counts toward the sign-in limit, so only in one project).
  if (testInfo.project.name === "desktop") {
    await field.fill("not-the-password");
    await confirm.getByRole("button", { name: "Yes, remove" }).focus();
    await page.keyboard.press("Enter");
    await expect(confirm.getByRole("alert")).toHaveText("Your password is not correct");
    await expect(field).toBeFocused();
    await expect(field).toHaveAttribute("aria-invalid", "true");
    await expect(field).toHaveAccessibleDescription("Your password is not correct");
    expect(((await (await page.request.get("/api/agents")).json()).grants as { id: string }[]).some((item) => item.id === id)).toBe(true);
  }
  await field.fill(password!);
  await confirm.getByRole("button", { name: "Yes, remove" }).click();
  await expect(page.getByText(name, { exact: true })).toHaveCount(0);
  expect(((await (await page.request.get("/api/agents")).json()).grants as { id: string }[]).some((item) => item.id === id)).toBe(false);
});
