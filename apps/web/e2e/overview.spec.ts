import { expect, test } from "@playwright/test";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

test("the overview shows archive totals, a monthly chart, and what needs attention", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Overview." })).toBeVisible();
  const api = await (await page.request.get("/api/overview")).json();
  const total = await page.evaluate((value) => value.toLocaleString(), api.documents.total as number);
  await expect(page.locator(".overview-tile").first()).toContainText(total);
  await expect(page.getByRole("img", { name: /Documents added per month/ })).toBeVisible();
  await expect(page.getByRole("table", { name: "Documents added per month" })).toHaveCount(1);
  await expect(page.getByRole("heading", { name: "Document types" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("overview.png"), fullPage: true, animations: "disabled" });
});
