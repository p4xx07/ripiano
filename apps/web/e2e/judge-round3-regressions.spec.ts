import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const image = readFileSync(path.resolve(process.cwd(), "e2e/fixtures/judge.png"));

// During a local judge run, use the new built PWA at the existing stack's origin so session and CSRF
// behavior remains real. Without this option the journey exercises the deployed image normally.
test.use({ serviceWorkers: "block" });
test.beforeEach(async ({ page }) => {
  const dist = process.env.RIPIANO_E2E_LOCAL_DIST;
  if (!dist) return;
  const origin = new URL(process.env.RIPIANO_E2E_ORIGIN!).origin;
  await page.route("**/*", (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) return route.fallback();
    if (route.request().resourceType() === "document" && !url.pathname.startsWith("/api/"))
      return route.fulfill({ path: path.join(dist, "index.html") });
    if (/^\/assets\/[A-Za-z0-9_-]+\.(js|css)$/.test(url.pathname))
      return route.fulfill({ path: path.join(dist, url.pathname.slice(1)) });
    return route.fallback();
  });
});

async function signIn(page: Page) {
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
}

async function chooseImage(page: Page, name: string) {
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.png`, mimeType: "image/png", buffer: image });
}

test("a file chosen after session expiry waits for its owner and retries after sign-in", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `ended-session-${Date.now()}-${testInfo.project.name}`;
  let firstUpload = true;
  let expired = true;
  const ids: string[] = [];
  await page.route("**/api/session", (route) => route.request().method() === "GET" && expired
    ? route.fulfill({ contentType: "application/json", body: JSON.stringify({ authenticated: false, username: null, setup_required: false, owner: false }) })
    : route.fallback());
  await page.route("**/api/documents", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    ids.push((await route.request().headerValue("x-ripiano-scan-id")) ?? "");
    if (firstUpload) {
      firstUpload = false;
      return route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ error: "Sign in required" }) });
    }
    return route.fallback();
  });
  await chooseImage(page, name);
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  expired = false;
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible({ timeout: 60000 });
  expect(ids).toHaveLength(2);
  expect(ids[0]).toBe(ids[1]);
});

test("Enter creates a sender and type inside the document without closing it", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const suffix = `${Date.now()}-${testInfo.project.name}`;
  const name = `filing-enter-${suffix}`;
  await chooseImage(page, name);
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible({ timeout: 60000 });
  await page.getByRole("button", { name, exact: true }).click();
  const dialog = page.getByRole("dialog").filter({ hasText: "Keep it in place." });
  await dialog.getByRole("button", { name: "More filing options" }).click();
  await dialog.getByRole("button", { name: "Add a sender" }).click();
  await dialog.getByRole("textbox", { name: "New sender name" }).fill(`Sender ${suffix}`);
  await page.keyboard.press("Enter");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel("From")).toContainText(`Sender ${suffix}`);
  await dialog.getByRole("button", { name: "Add a type" }).click();
  await dialog.getByRole("textbox", { name: "New document type name" }).fill(`Type ${suffix}`);
  await page.keyboard.press("Enter");
  await expect(dialog).toBeVisible();
  await expect(dialog.locator("#detail-document-type")).toContainText(`Type ${suffix}`);
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog).toBeHidden();
  await page.getByRole("button", { name, exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "More filing options" }).click();
  await expect(page.getByRole("dialog").getByLabel("From")).toContainText(`Sender ${suffix}`);
  await expect(page.getByRole("dialog").locator("#detail-document-type")).toContainText(`Type ${suffix}`);
});

test("mobile filing, file, and paper actions have touch-sized targets", async ({ page, isMobile }, testInfo) => {
  test.skip(!isMobile || !username || !password, "Use the mobile project with a disposable account");
  await signIn(page);
  const suffix = `${Date.now()}-${testInfo.project.name}`;
  const menu = page.getByRole("button", { name: "Toggle menu" });
  await menu.click();
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name: "Tags & filing" }).click();
  const senders = page.locator(".filing-card").filter({ has: page.getByRole("heading", { name: "Senders & organizations" }) });
  await senders.getByRole("textbox", { name: "New sender name" }).fill(`Mobile sender ${suffix}`);
  await senders.getByRole("button", { name: "Add", exact: true }).click();
  const senderRow = senders.locator(".filing-vocabulary-row").filter({ hasText: `Mobile sender ${suffix}` });
  for (const button of await senderRow.getByRole("button").all()) {
    const box = (await button.boundingBox())!;
    expect(box.width).toBeGreaterThanOrEqual(44);
    expect(box.height).toBeGreaterThanOrEqual(44);
  }

  await menu.click();
  await page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name: "All documents" }).click();
  const name = `mobile-actions-${suffix}`;
  await chooseImage(page, name);
  const row = page.locator(".document-row").filter({ has: page.getByRole("button", { name, exact: true }) });
  await expect(row).toBeVisible({ timeout: 60000 });
  const id = await row.getAttribute("data-document-id");
  expect(id).toBeTruthy();
  const csrf = (await page.context().cookies()).find((cookie) => cookie.name === "csrftoken")?.value;
  const headers = { "X-CSRFToken": csrf ?? "" };
  const location = await page.request.post("/api/locations", { headers, data: { name: `Mobile box ${suffix}` } });
  expect(location.status()).toBe(201);
  const secondLocation = await page.request.post("/api/locations", { headers, data: { name: `Mobile shelf ${suffix}` } });
  expect(secondLocation.status()).toBe(201);
  const copy = await page.request.post(`/api/documents/${id}/copies`, { headers, data: { location_id: (await location.json()).id } });
  expect(copy.status()).toBe(201);
  await page.reload();
  await expect(row).toBeVisible({ timeout: 60000 });
  await row.getByRole("button", { name, exact: true }).click();
  const dialog = page.getByRole("dialog").filter({ hasText: "Keep it in place." });
  for (const control of await dialog.locator(".detail-files a, .copy-actions a, .copy-actions button").all()) {
    const box = (await control.boundingBox())!;
    expect(box.height).toBeGreaterThanOrEqual(44);
  }
  await dialog.getByRole("combobox", { name: /New location for paper copy/ }).selectOption((await secondLocation.json()).id);
  await dialog.getByRole("button", { name: /^Move paper copy / }).click();
  await expect(dialog.getByRole("status")).toContainText("moved");
});

test("search result count is announced", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const count = page.locator(".library-counts");
  await expect(count).toHaveAttribute("role", "status");
  await page.getByRole("textbox", { name: /Search documents by/ }).fill(`no-document-${Date.now()}`);
  await expect(count).toContainText("0 matching documents");
});

test("paper and agent screens fit a 320px viewport", async ({ page, isMobile }, testInfo) => {
  test.skip(!isMobile || !username || !password, "Use the mobile project with a disposable account");
  await signIn(page);
  const csrf = (await page.context().cookies()).find((cookie) => cookie.name === "csrftoken")?.value;
  const location = await page.request.post("/api/locations", {
    headers: { "X-CSRFToken": csrf ?? "" },
    data: { name: `320 viewport location ${Date.now()}-${testInfo.project.name}` },
  });
  expect(location.status()).toBe(201);
  await page.setViewportSize({ width: 320, height: 568 });
  for (const route of ["/paper", "/agents"]) {
    await page.goto(route);
    await expect(page.locator("main")).toBeVisible();
    const { width, scrollWidth } = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth }));
    expect(scrollWidth, `${route} at 320px`).toBeLessThanOrEqual(width + 2);
  }
});

test("owner-only People and Backups layouts fit 320px with representative records", async ({ page, isMobile }) => {
  test.skip(!isMobile || !username || !password, "Use the mobile project with a disposable regular account");
  await signIn(page);
  // Read-only browser fixtures expose the owner layout without giving the test account server privileges.
  await page.route("**/api/session", async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    const response = await route.fetch();
    await route.fulfill({ response, json: { ...(await response.json()), owner: true } });
  });
  await page.route("**/api/people", (route) => route.request().method() === "GET"
    ? route.fulfill({ json: { admin: true, people: [{ id: 1, username: "sample-person-with-a-long-username", name: "Sample person with a long display name for a narrow phone", is_active: true, is_admin: false, last_login: "2026-11-18T10:00:00Z", groups: [1] }], groups: [{ id: 1, name: "Household filing and document review", member_ids: [1] }] } })
    : route.fallback());
  await page.route("**/api/backups", (route) => route.request().method() === "GET"
    ? route.fulfill({ json: { schedule: "10:00", runs: [{ id: "sample-backup", status: "complete", trigger: "manual", snapshot_name: "A completed archive backup with a long descriptive name", error: "", created_at: "2026-11-18T10:00:00Z", can_cancel: false, can_retry: false, retry_of: null }] } })
    : route.fallback());
  await page.route("**/api/browse-exports", (route) => route.request().method() === "GET"
    ? route.fulfill({ json: { runs: [] } })
    : route.fallback());
  await page.evaluate(() => localStorage.setItem("ripiano.language", "it"));
  await page.setViewportSize({ width: 320, height: 568 });
  for (const [route, loaded] of [["/people", ".people-list > li"], ["/backups", ".backup-list .document-row"]] as const) {
    await page.goto(route);
    await expect(page.locator(loaded)).toBeVisible();
    const layout = await page.evaluate(() => {
      const width = innerWidth;
      const offscreen = [...document.querySelectorAll("main *")].filter((element) => {
        const rect = element.getBoundingClientRect();
        if (!rect.width || (rect.right <= width + 2 && rect.left >= -2)) return false;
        for (let parent = element.parentElement; parent && parent.tagName !== "MAIN"; parent = parent.parentElement)
          if (getComputedStyle(parent).overflowX !== "visible") return false;
        return true;
      }).slice(0, 5).map((element) => `${element.tagName}.${String(element.className).slice(0, 32)}`);
      return { width, scrollWidth: document.documentElement.scrollWidth, offscreen };
    });
    expect(layout.scrollWidth, `${route}: ${JSON.stringify(layout)}`).toBeLessThanOrEqual(layout.width + 2);
    expect(layout.offscreen, `${route}: ${JSON.stringify(layout)}`).toEqual([]);
  }
});
