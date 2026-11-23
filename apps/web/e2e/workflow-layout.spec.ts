import { expect, test } from "@playwright/test";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

test("workflow editor uses page width and keeps the rule understandable", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set isolated stack credentials");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  await page.goto("/workflows");
  await expect(page.getByRole("heading", { name: "Workflows." })).toBeVisible();
  await expect(page.getByRole("form", { name: "Workflow" })).toHaveCount(0);
  await page.getByRole("button", { name: "Tag new documents that mention a word" }).click();
  const form = page.getByRole("form", { name: "Workflow" });
  await expect(form).toBeVisible();
  await form.getByLabel("Name", { exact: true }).fill("Test layout");
  await form.getByLabel("Mention this word or phrase").fill("bollettino");
  await expect(page.locator(".workflow-live-summary")).toContainText("bollettino");
  const width = await page.locator(".workflow-editor").evaluate((node) => node.getBoundingClientRect().width);
  expect(width).toBeGreaterThan(testInfo.project.name === "desktop" ? 650 : 310);
  await page.screenshot({ path: testInfo.outputPath("workflow-editor.png"), fullPage: true, animations: "disabled" });
  await form.getByRole("button", { name: "Cancel" }).click();
  await expect(form).toHaveCount(0);
});
