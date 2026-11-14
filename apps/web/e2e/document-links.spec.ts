import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = path.resolve(process.cwd(), "e2e/fixtures/judge.png");

async function upload(page: Page, name: string) {
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.png`, mimeType: "image/png", buffer: readFileSync(fixture) });
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
}

test("related documents link from either side and can be unlinked", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  const first = `policy-${Date.now()}-${testInfo.project.name}`;
  const second = `renewal-${Date.now()}-${testInfo.project.name}`;
  await upload(page, first);
  await upload(page, second);
  await page.getByRole("button", { name: first, exact: true }).click();
  let dialog = page.getByRole("dialog", { name: "Keep it in place." });
  const links = dialog.locator(".document-links");
  await links.getByRole("textbox", { name: "Find a document to link" }).fill(second);
  await links.getByRole("button", { name: "Search" }).click();
  await expect(links.locator(".related-results")).toContainText(second);
  await links.getByRole("button", { name: "Link", exact: true }).click();
  await expect(links.locator(".related-list")).toContainText(second);
  await links.screenshot({ path: testInfo.outputPath("related-documents.png") });
  await links.getByRole("button", { name: second, exact: true }).click();
  dialog = page.getByRole("dialog", { name: "Keep it in place." });
  await expect(dialog.locator(".document-links .related-list")).toContainText(first);
  await dialog.getByRole("button", { name: `Unlink ${first}` }).click();
  await dialog.getByRole("button", { name: "Confirm unlink" }).click();
  await expect(dialog.locator(".document-links")).toContainText("No related documents yet.");
});
