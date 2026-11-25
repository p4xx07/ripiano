import { expect, test, type Page } from "@playwright/test";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

async function navigate(page: Page, name: string) {
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name, exact: true }).click();
}

test("missing starter tags are added in one click, and a second click adds nothing", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  await navigate(page, "Tags & filing");
  const add = page.getByRole("button", { name: "Add missing starter tags" });
  await expect(page.locator(".starter-tags")).toContainText("Rename or delete any of them.");
  await add.click();
  await expect(page.getByRole("status").filter({ hasText: /starter tag/ })).toHaveText(/starter tags? added\.|All starter tags are already here\./);
  for (const name of ["Home", "Utilities", "Finance and taxes", "Health", "Vehicles", "Personal", "Events and travel", "Warranties"]) {
    await expect(page.locator(".tag-card h3").getByText(name, { exact: true })).toBeVisible();
  }
  await add.click();
  await expect(page.getByRole("status").filter({ hasText: /starter tag/ })).toHaveText("All starter tags are already here.");
  await page.screenshot({ path: testInfo.outputPath("starter-tags.png"), animations: "disabled" });
});
