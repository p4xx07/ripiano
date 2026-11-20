import { expect, Page, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = path.resolve(process.cwd(), "e2e/fixtures/judge.png");

async function signIn(page: Page) {
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
}

/** Upload one image and wait until its searchable PDF is ready; returns the new document's ID. */
async function uploadReady(page: Page, name: string) {
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const response = page.waitForResponse((item) => item.url().endsWith("/api/documents") && item.request().method() === "POST" && item.status() === 202);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.png`, mimeType: "image/png", buffer: readFileSync(fixture) });
  const id = (await (await response).json()).id as string;
  await expect.poll(async () => (await (await page.request.get(`/api/documents/${id}`)).json()).status, { timeout: 60000 }).toBe("ready");
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
  return id;
}

test("tapping outside the open phone menu closes it", async ({ page, isMobile }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.skip(!isMobile, "The drawer exists only on narrow screens");
  await signIn(page);
  const menu = page.getByRole("button", { name: "Toggle menu" });
  const sidebar = page.locator("#app-sidebar");
  await menu.click();
  await expect(menu).toHaveAttribute("aria-expanded", "true");
  // The drawer is 244px wide: tap the page beside it.
  const viewport = page.viewportSize()!;
  await page.touchscreen.tap(viewport.width - 40, Math.round(viewport.height / 2));
  await expect(menu).toHaveAttribute("aria-expanded", "false");
  await expect(sidebar).toHaveAttribute("inert", "");
  await expect(page.locator(".sidebar-backdrop")).toHaveCount(0);
  // The tap only closed the menu: nothing behind the scrim was opened.
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("on a phone the first documents and Add are on the first screen", async ({ page, isMobile }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.skip(!isMobile, "Phone layout");
  await signIn(page);
  if (!(await page.locator(".document-row").count())) await uploadReady(page, `first-screen-${Date.now()}-${testInfo.project.name}`);
  for (const size of [{ width: 390, height: 844 }, { width: 375, height: 667 }]) {
    await page.setViewportSize(size);
    await page.evaluate(() => window.scrollTo(0, 0));
    const add = page.getByRole("button", { name: "Add", exact: true });
    await expect(add).toBeVisible();
    await expect(add).toHaveClass(/button-primary/);
    const addBox = (await add.boundingBox())!;
    expect(addBox.y + addBox.height, "Add sits in the top bar").toBeLessThanOrEqual(70);
    expect(addBox.height).toBeGreaterThanOrEqual(44);
    const row = page.locator(".document-row").first();
    await expect(row).toBeVisible();
    const rowBox = (await row.boundingBox())!;
    expect(rowBox.y, `first row at ${size.width}x${size.height}`).toBeLessThan(size.height - 60);
    // Saved searches and search help wait behind Filters on a phone.
    await expect(page.locator(".saved-search-bar")).toHaveCount(0);
    await expect(page.getByText("Precise search")).toBeHidden();
    await expect(page.locator(".library-counts")).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`library-${size.width}x${size.height}.png`) });
  }
  await page.getByRole("button", { name: /^Filters/ }).click();
  await expect(page.getByRole("button", { name: "Save this search" })).toBeVisible();
  await expect(page.getByText("Precise search")).toBeVisible();
  await page.getByRole("button", { name: /^Filters/ }).click();
});

test("the document dialog shows the first page, and a calm placeholder when there is none", async ({ page, isMobile }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `preview-${Date.now()}-${testInfo.project.name}`;
  const id = await uploadReady(page, name);
  await page.getByRole("button", { name, exact: true }).click();
  const dialog = page.getByRole("dialog", { name });
  const preview = dialog.getByRole("region", { name: "Preview" });
  const image = preview.getByRole("img", { name: `First page of “${name}”` });
  await expect(image).toBeVisible();
  await expect.poll(() => image.evaluate((element: HTMLImageElement) => element.complete && element.naturalWidth)).toBeGreaterThan(0);
  expect(await image.getAttribute("src")).toContain(`/api/documents/${id}/pages/1.png`);
  // Close still gets focus first when the dialog opens.
  await expect(dialog.getByRole("button", { name: "Close" }).first()).toBeFocused();
  const titleField = dialog.getByRole("textbox", { name: "Title", exact: true });
  const imageBox = (await image.boundingBox())!;
  const fieldBox = (await titleField.boundingBox())!;
  if (isMobile) {
    // A compact strip above the fields that can be expanded.
    expect(imageBox.y).toBeLessThan(fieldBox.y);
    const toggle = preview.getByRole("button", { name: "Show larger" });
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    const compact = (await preview.locator(".detail-preview-frame").boundingBox())!.height;
    await toggle.click();
    await expect(preview.getByRole("button", { name: "Show smaller" })).toHaveAttribute("aria-expanded", "true");
    // Expanded, the frame no longer clips the page: the whole image fits inside it (a short page stays at the
    // compact height, a tall one grows).
    const frame = (await preview.locator(".detail-preview-frame").boundingBox())!;
    const expandedImage = (await image.boundingBox())!;
    expect(frame.height).toBeGreaterThanOrEqual(compact);
    expect(expandedImage.height).toBeLessThanOrEqual(frame.height + 1);
  } else {
    // Beside the form on a wide screen.
    expect(imageBox.x + imageBox.width).toBeLessThanOrEqual(fieldBox.x);
  }
  await expect(preview.getByRole("link", { name: "Open full size" })).toHaveAttribute("href", `/api/documents/${id}/archive`);
  await page.screenshot({ path: testInfo.outputPath("document-preview.png") });
  await dialog.getByRole("button", { name: "Close" }).first().click();

  // No page image (for example a format without a searchable PDF): a placeholder, never a broken image.
  // The browser keeps the image it already has (the server allows private caching), so the list
  // reports a new version: the dialog then asks for a page the server cannot render.
  await page.route("**/api/documents?*", async (route) => {
    try {
      const response = await route.fetch();
      const body = await response.json();
      for (const item of body.documents) if (item.id === id) item.version_number += 1000;
      await route.fulfill({ response, json: body });
    } catch {
      // The app replaced this list request with a newer one while it was in flight; nothing to answer.
    }
  });
  await page.route(`**/api/documents/${id}/pages/1.png*`, (route) => route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ error: "Page tools need a PDF." }) }));
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await page.getByRole("button", { name, exact: true }).click();
  const reopened = page.getByRole("dialog", { name }).getByRole("region", { name: "Preview" });
  await expect(reopened).toContainText("No preview for this document.");
  await expect(reopened.getByRole("img")).toHaveCount(0);
});

test("offline, the Library keeps the last loaded documents and says so", async ({ page, context }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  if (!(await page.locator(".document-row").count())) await uploadReady(page, `offline-list-${Date.now()}-${testInfo.project.name}`);
  const rows = page.locator(".document-row");
  const before = await rows.count();
  expect(before).toBeGreaterThan(0);
  await context.setOffline(true);
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  const notice = page.locator(".stale-notice");
  await expect(notice).toContainText("You're offline or Ripiano can't be reached.");
  await expect(rows).toHaveCount(before);
  await expect(page.getByRole("heading", { name: /A fresh shelf/ })).toHaveCount(0);
  await expect(page.locator(".summary-card strong").first()).not.toHaveText("0");
  await page.screenshot({ path: testInfo.outputPath("offline-library.png") });
  await context.setOffline(false);
  // Coming back online reloads the list by itself; Refresh does the same on demand.
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(notice).toHaveCount(0);
  await expect(rows).toHaveCount(before);
});

test("a tag can be created from the document dialog and a wrong suggestion dismissed", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await signIn(page);
  const name = `tag-inline-${Date.now()}-${testInfo.project.name}`;
  const id = await uploadReady(page, name);
  const tag = `Inline ${Date.now()} ${testInfo.project.name}`;

  // Simulate a learned suggestion the owner disagrees with (the server finds none for a fresh document).
  // The tag is this test's own: an arbitrary existing tag can be deleted by a spec running in parallel.
  const csrf = { "X-CSRFToken": (await page.context().cookies()).find((cookie) => cookie.name === "csrftoken")?.value ?? "" };
  const wrong = await (await page.request.post("/api/tags", { headers: csrf, data: { name: `Wrong ${Date.now()} ${testInfo.project.name}` } })).json() as { id: string; name: string };
  if (wrong) {
    await page.route(`**/api/documents/${id}/filing-suggestions`, (route) => route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ tags: [{ id: wrong.id, name: wrong.name, example: { id, title: "Earlier bill" }, shared_terms: ["bill"], similarity: 0.4 }], correspondents: [], document_types: [] }),
    }));
  }

  await page.getByRole("button", { name, exact: true }).click();
  const dialog = page.getByRole("dialog", { name });
  if (wrong) {
    await expect(dialog.getByRole("button", { name: `Add tag: ${wrong.name}`, exact: true })).toBeVisible();
    await dialog.getByRole("button", { name: `Reject suggestion “Add tag: ${wrong.name}”` }).click();
    await expect(dialog.getByRole("button", { name: `Add tag: ${wrong.name}`, exact: true })).toHaveCount(0);
  }

  await dialog.getByRole("button", { name: "Create a tag" }).click();
  await dialog.getByRole("textbox", { name: "New tag name" }).fill(tag);
  await dialog.getByRole("button", { name: "Create tag", exact: true }).click();
  const choice = dialog.getByRole("checkbox", { name: tag });
  await expect(choice).toBeChecked();
  await expect(choice).toBeFocused();
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog).toHaveCount(0);
  const saved = await (await page.request.get(`/api/documents/${id}`)).json();
  expect(saved.tags.map((item: { name: string }) => item.name)).toContain(tag);

  if (wrong) {
    // A rejected suggestion is stored on the server (round 5): the real suggestions API no longer offers it.
    await page.unroute(`**/api/documents/${id}/filing-suggestions`);
    const fresh = await (await page.request.get(`/api/documents/${id}/filing-suggestions`)).json();
    expect(fresh.tags.map((item: { id: string }) => item.id)).not.toContain(wrong.id);
    await page.getByRole("button", { name, exact: true }).click();
    await expect(page.getByRole("dialog", { name }).getByRole("button", { name: "Save changes" })).toBeVisible();
    await expect(page.getByRole("dialog", { name }).getByRole("button", { name: `Add tag: ${wrong.name}`, exact: true })).toHaveCount(0);
  }
  await page.request.delete(`/api/tags/${wrong.id}`, { headers: { ...csrf, Referer: page.url() } });
});
