import { expect, test } from "@playwright/test";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

test("learned suggestions can be relearned on demand and explain how reliable they are", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.skip(testInfo.project.name !== "desktop", "One model per account, so this runs once");
  test.setTimeout(180000);
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  await page.getByRole("button", { name: "Tags & filing", exact: true }).click();
  const panel = page.getByRole("region", { name: "Learned suggestions" });
  await expect(panel).toContainText("never files anything without you");
  await panel.getByRole("button", { name: "Learn now" }).click();
  await expect(panel.getByText("Learning started")).toBeVisible();
  await expect(panel.getByText(/^Last learned /)).toBeVisible({ timeout: 150000 });
  await expect(panel.getByText("Senders", { exact: true })).toBeVisible();
  await expect(panel.getByRole("button", { name: "Learn now" })).toBeEnabled();
  await panel.screenshot({ path: testInfo.outputPath("learning.png") });
});
