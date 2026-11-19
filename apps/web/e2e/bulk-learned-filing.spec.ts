import { expect, test } from "@playwright/test";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const targetPrefix = process.env.RIPIANO_E2E_BACKFILL_PREFIX;

test("selected existing documents can use the local model without enabling automatic intake", async ({ page }, testInfo) => {
  test.skip(!username || !password || !targetPrefix, "Set disposable account and backfill fixture variables");
  const title = `${targetPrefix}-${testInfo.project.name}`;
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  await page.getByRole("textbox", { name: "Search documents" }).fill(`title:"${title}"`);
  const row = page.locator(".document-row").filter({ has: page.getByRole("button", { name: title, exact: true }) });
  await expect(row).toBeVisible();
  await expect(row).not.toContainText("From: Council");
  await page.getByRole("button", { name: "Select documents" }).click();
  await row.getByRole("checkbox", { name: `Select ${title}` }).check();
  await page.getByText("File with local model", { exact: true }).click();
  const action = page.waitForResponse((response) => response.url().endsWith("/api/documents/bulk-learned-filing") && response.request().method() === "POST");
  await page.getByRole("button", { name: "File 1 selected" }).click();
  const result = await (await action).json();
  expect(result.updated).toBe(1);
  expect(result.assignments).toBeGreaterThanOrEqual(1);
  await expect(row).toContainText("From: Council");
  await expect(page.locator(".bulk-notice")).toContainText("The local model added");
  expect((await (await page.request.get("/api/filing-model")).json()).auto_apply).toBe(false);
  if (testInfo.project.name === "desktop") {
    await page.locator("main").screenshot({ path: testInfo.outputPath("selected-local-filing.png"), animations: "disabled" });
  } else {
    await page.screenshot({ path: testInfo.outputPath("selected-local-filing.png"), animations: "disabled", fullPage: true });
  }
});
