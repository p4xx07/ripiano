import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

test("a document reaches the local fake SMTP server", async ({ page }) => {
  test.skip(!username || !password || process.env.RIPIANO_E2E_MOCK_SMTP !== "1", "Requires isolated stack with fake SMTP");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  const filename = `mailtest-${Date.now()}.png`;
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: filename, mimeType: "image/png", buffer: readFileSync(path.resolve(process.cwd(), "e2e/fixtures/judge.png")) });
  await page.getByRole("textbox", { name: /Search documents/ }).fill(filename);
  await page.getByRole("button", { name: filename.replace(/\.png$/, ""), exact: true }).click();
  const dialog = page.getByRole("dialog").filter({ hasText: "Keep it in place." });
  await dialog.getByRole("button", { name: "Write an email" }).click();
  const form = dialog.getByRole("form", { name: "Email this document" });
  const address = `qa-${Date.now()}@example.test`;
  await form.getByLabel(/^To/).fill(address);
  await form.getByRole("button", { name: "Send email" }).click();
  await expect(dialog.locator(".email-sends")).toContainText(`Sent to ${address}`, { timeout: 30000 });
});
