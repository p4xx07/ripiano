import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = path.resolve(process.cwd(), "e2e/fixtures/judge.png");

async function navigate(page: Page, name: string) {
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name, exact: true }).click();
}

test("a document can need action without filing, then be completed", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const name = `action-${Date.now()}-${testInfo.project.name}`;
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.png`, mimeType: "image/png", buffer: readFileSync(fixture) });
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible();

  await page.getByRole("button", { name, exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Keep it in place." });
  await dialog.getByLabel("Follow-up").selectOption("open");
  await dialog.getByLabel("Due date").fill("2027-01-15");
  await dialog.getByLabel("What needs doing?").fill("Pay this invoice");
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog).toBeHidden();

  await navigate(page, "Needs action");
  const row = page.getByRole("article").filter({ has: page.getByRole("button", { name, exact: true }) });
  await expect(row).toContainText("Pay this invoice");
  await expect(row).toContainText(/Due (?:15 Jan|Jan 15),? 2027/);
  await row.getByRole("button", { name: "Done" }).click();
  await expect(page.getByRole("button", { name, exact: true })).toBeHidden();
});
