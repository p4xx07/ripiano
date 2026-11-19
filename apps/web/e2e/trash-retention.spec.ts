import { expect, test } from "@playwright/test";

function credentials(project: string) {
  const suffix = project.toUpperCase();
  return {
    username: process.env[`RIPIANO_E2E_RETENTION_${suffix}_USERNAME`],
    password: process.env[`RIPIANO_E2E_RETENTION_${suffix}_PASSWORD`],
  };
}

test("review, enable, persist, and disable automatic Trash cleanup", async ({ page }, testInfo) => {
  const { username, password } = credentials(testInfo.project.name);
  test.skip(!username || !password, "Set a separate retention QA account for each browser project");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "Trash", exact: true }).click();
  const panel = page.locator(".trash-retention");
  await expect(panel.getByRole("spinbutton", { name: /Delete after/ })).toBeEnabled();
  if (await panel.getByRole("button", { name: "Turn off" }).isVisible()) {
    await panel.getByRole("button", { name: "Turn off" }).click();
  }
  await expect(panel).toContainText("Off · Documents stay in Trash");
  await panel.getByRole("spinbutton", { name: /Delete after/ }).fill("30");
  await panel.getByRole("button", { name: "Review and enable" }).click();
  const confirmation = page.getByRole("dialog", { name: "Enable automatic cleanup?" });
  await expect(confirmation).toContainText("0 documents are eligible now");
  await expect(confirmation).toContainText("Older backups may retain copies");
  await page.screenshot({ path: testInfo.outputPath("retention-confirmation.png"), animations: "disabled" });
  await confirmation.getByRole("button", { name: "Confirm automatic cleanup" }).click();
  await expect(panel).toContainText("On · Documents left in Trash for 30 days");
  await expect(page.locator(".section-heading")).toContainText("Automatic cleanup is on after 30 days");
  await page.reload();
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "Trash", exact: true }).click();
  await expect(panel).toContainText("On · Documents left in Trash for 30 days");
  await panel.getByRole("button", { name: "Turn off" }).click();
  await expect(panel).toContainText("Off · Documents stay in Trash");
  await expect(page.locator(".section-heading")).toContainText("Nothing is erased automatically");
  await page.screenshot({ path: testInfo.outputPath("retention-off.png"), animations: "disabled" });
});
