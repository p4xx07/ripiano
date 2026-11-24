import { expect, test, type Page } from "@playwright/test";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

async function navigate(page: Page, name: string) {
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name, exact: true }).click();
}

test("a full location path is created in one step and reused", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  await navigate(page, "Paper archive");
  const shelf = `Shelf ${Date.now()} ${testInfo.project.name}`;
  const fullPath = `${shelf} / Top / Row / Box`;
  const name = page.getByPlaceholder("e.g. Filing cabinet");
  await name.fill(fullPath);
  await page.getByRole("button", { name: "Add location at top level" }).click();
  await expect(page.getByRole("status")).toContainText(`Location ready: ${fullPath}`);
  await expect(page.locator(".location-path").getByText(fullPath, { exact: true })).toBeVisible();

  await name.fill(`${shelf.toLowerCase()} / top / row / box`);
  await page.getByRole("button", { name: "Add location at top level" }).click();
  await expect(page.getByRole("status")).toContainText(`Location ready: ${fullPath}`);
  await expect(page.locator(".location-path").getByText(fullPath, { exact: true })).toHaveCount(1);
  await page.screenshot({ path: testInfo.outputPath("location-path.png"), animations: "disabled" });
});
