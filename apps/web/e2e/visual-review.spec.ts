import { expect, test, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

async function navigate(page: Page, name: string) {
  const menu = page.getByRole("button", { name: "Toggle menu" });
  const mobile = await menu.isVisible();
  if (mobile) await menu.click();
  await page.getByRole("button", { name, exact: true }).click();
  if (mobile) await expect.poll(() => page.locator(".sidebar").evaluate((element) => element.getBoundingClientRect().right)).toBeLessThan(1);
}

test("review the main archive surfaces", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  const output = path.resolve(process.cwd(), "../../qa-artifacts/65d544b/visual", testInfo.project.name);
  mkdirSync(output, { recursive: true });
  async function shot(name: string) { await page.screenshot({ path: path.join(output, `${name}.png`) }); }

  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  const loaded = page.waitForResponse((response) => response.url().includes("/api/documents?q=") && response.status() === 200);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  await loaded;
  await shot("library");

  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Bring a document in." })).toBeVisible();
  await shot("add-dialog");
  await page.keyboard.press("Escape");

  await page.getByRole("textbox", { name: "Search documents" }).fill("zzzzzzzzzzzzzzzzzzzz");
  await expect(page.getByRole("heading", { name: "Nothing found yet" })).toBeVisible();
  await shot("search-empty");

  await page.route("**/api/documents?q=brokenvisualreview", (route) => route.fulfill({
    status: 503,
    contentType: "application/json",
    body: JSON.stringify({ error: "Archive temporarily unavailable" }),
  }));
  await page.getByRole("textbox", { name: "Search documents" }).fill("brokenvisualreview");
  await expect(page.getByRole("alert")).toContainText("Archive temporarily unavailable");
  await expect(page.getByRole("heading", { name: "Nothing found yet" })).toBeHidden();
  await shot("search-error");
  await page.getByRole("textbox", { name: "Search documents" }).fill("");
  await expect(page.locator(".document-row .document-title-button").first()).toBeVisible();
  await page.locator(".document-row .document-title-button").first().click();
  await expect(page.getByRole("dialog", { name: "Keep it in place." })).toBeVisible();
  await shot("document-detail");
  await page.keyboard.press("Escape");

  await navigate(page, "Needs action");
  await expect(page.getByRole("heading", { name: /Needs action/ })).toBeVisible();
  await expect(page.getByText("Loading follow-ups…")).toBeHidden();
  await shot("actions");

  await navigate(page, "Tags & filing");
  await shot("tags");
  await navigate(page, "Paper archive");
  await shot("paper-archive");
  await navigate(page, "Agents");
  await shot("agents");
  await navigate(page, "Backups");
  await shot("backups");
});
