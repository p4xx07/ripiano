import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = path.resolve(process.cwd(), "e2e/fixtures/judge.png");

test("a document note can be found, reopened, and deleted", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const name = `note-${Date.now()}-${testInfo.project.name}`;
  const note = `Inspection ${Date.now()} is booked for Tuesday`;
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.png`, mimeType: "image/png", buffer: readFileSync(fixture) });
  await page.getByRole("button", { name, exact: true }).click();
  let dialog = page.getByRole("dialog", { name: "Keep it in place." });
  await dialog.getByRole("textbox", { name: "New note" }).fill(note);
  await dialog.getByRole("button", { name: "Add note" }).click();
  await expect(dialog.locator(".note-list")).toContainText(note);
  await expect(dialog.getByRole("status")).toContainText("Note added.");
  await dialog.getByRole("button", { name: "Close" }).click();

  await page.getByRole("textbox", { name: "Search documents" }).fill(note);
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
  const row = page.locator(".document-row").filter({ has: page.getByRole("button", { name, exact: true }) });
  await expect(row.locator(".document-snippet")).toContainText("Note:");
  await expect(row.locator(".document-snippet")).toContainText(note);
  await page.getByRole("button", { name, exact: true }).click();
  dialog = page.getByRole("dialog", { name: "Keep it in place." });
  await expect(dialog.locator(".note-list")).toContainText(note);
  await dialog.locator(".detail-notes").screenshot({ path: testInfo.outputPath("document-notes.png") });
  await dialog.getByRole("button", { name: /Delete note/ }).click();
  await dialog.getByRole("button", { name: "Confirm delete" }).click();
  await expect(dialog.getByRole("status")).toContainText("Note deleted.");
  await expect(dialog.locator(".note-list")).toHaveCount(0);
  await dialog.getByRole("button", { name: "Close" }).click();
  await expect(page.getByRole("heading", { name: "Nothing found yet" })).toBeVisible();
});
