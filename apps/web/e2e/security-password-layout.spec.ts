import { expect, test } from "@playwright/test";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

test("Security password fields stay stacked and fill the form", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set isolated stack credentials");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "Security", exact: true }).click();

  const form = page.getByRole("form", { name: "Password" });
  const formBox = await form.boundingBox();
  expect(formBox).not.toBeNull();
  for (const name of ["Current password", "New password", "Repeat new password"]) {
    const input = form.getByRole("textbox", { name, exact: true });
    const label = input.locator("xpath=..");
    await expect(label).toHaveCSS("display", "grid");
    const inputBox = await input.boundingBox();
    expect(inputBox).not.toBeNull();
    expect(inputBox!.width).toBeGreaterThan(formBox!.width * 0.8);
    expect(inputBox!.x).toBeGreaterThanOrEqual(formBox!.x);
  }
  await form.screenshot({ path: testInfo.outputPath("security-password.png"), animations: "disabled" });
});
