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
  await expect(panel).toContainText("Automatic filing stays off unless you choose it");
  const automatic = panel.getByRole("checkbox", { name: /File new documents automatically when very confident/ });
  await expect(automatic).not.toBeChecked();
  await automatic.click();
  await expect(automatic).toBeChecked();
  await expect.poll(async () => (await (await page.request.get("/api/filing-model")).json()).auto_apply).toBe(true);
  await panel.screenshot({ path: testInfo.outputPath("auto-filing-enabled.png"), animations: "disabled" });
  await page.reload();
  await page.getByRole("button", { name: "Tags & filing", exact: true }).click();
  const reopened = page.getByRole("region", { name: "Learned suggestions" });
  await expect(reopened.getByRole("checkbox", { name: /File new documents automatically when very confident/ })).toBeChecked();
  await reopened.getByRole("checkbox", { name: /File new documents automatically when very confident/ }).click();
  await expect.poll(async () => (await (await page.request.get("/api/filing-model")).json()).auto_apply).toBe(false);
  await reopened.getByRole("button", { name: "Learn now" }).click();
  await expect(reopened.getByText("Learning started")).toBeVisible();
  await expect(reopened.getByText(/^Last learned /)).toBeVisible({ timeout: 150000 });
  await expect(reopened.getByText("Senders", { exact: true })).toBeVisible();
  await expect(reopened.getByRole("button", { name: "Learn now" })).toBeEnabled();
  await reopened.screenshot({ path: testInfo.outputPath("learning.png") });
});

test("automatic filing control remains usable on mobile", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.skip(testInfo.project.name !== "mobile", "Mobile layout check");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: "Toggle menu" }).click();
  await page.getByRole("button", { name: "Tags & filing", exact: true }).click();
  await expect.poll(() => page.locator(".sidebar").evaluate((element) => element.getBoundingClientRect().right)).toBeLessThan(1);
  const panel = page.getByRole("region", { name: "Learned suggestions" });
  const automatic = panel.getByRole("checkbox", { name: /File new documents automatically when very confident/ });
  await expect(automatic).not.toBeChecked();
  await automatic.click();
  await expect(automatic).toBeChecked();
  await panel.screenshot({ path: testInfo.outputPath("auto-filing-mobile.png"), animations: "disabled" });
  await automatic.click();
  await expect(automatic).not.toBeChecked();
});
