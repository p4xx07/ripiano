import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

async function navigate(page: Page, name: string) {
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name, exact: true }).click();
}

test("a printed tag code files a scanned document", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.setTimeout(150000);
  const code = `ARCHIVE-BILLS-${testInfo.project.name.toUpperCase()}`;
  const tagName = `Barcode bills ${Date.now()} ${testInfo.project.name}`;
  const documentName = `barcode-invoice-${Date.now()}-${testInfo.project.name}`;
  const fixture = readFileSync(path.resolve(process.cwd(), `e2e/fixtures/tag-barcode-${testInfo.project.name}.pdf`));

  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  await navigate(page, "Tags & filing");
  await page.getByPlaceholder("e.g. Bills").fill(tagName);
  await page.getByPlaceholder("e.g. ARCHIVE-BILLS").fill(code);
  await page.getByRole("button", { name: "Create tag" }).click();
  const tagCard = page.locator(".tag-card").filter({ has: page.getByRole("heading", { name: tagName }) });
  await expect(tagCard).toContainText(`Barcode: ${code}`);
  const labelUrl = await tagCard.getByRole("link", { name: "Print label" }).getAttribute("href");
  expect(labelUrl).toBeTruthy();
  const label = await page.request.get(labelUrl!);
  expect(label.status()).toBe(200);
  expect(await label.text()).toContain(code);
  await tagCard.screenshot({ path: testInfo.outputPath("tag-barcode.png"), animations: "disabled" });
  await tagCard.getByRole("button", { name: "Change code" }).click();
  await expect(tagCard.getByRole("textbox", { name: `Barcode for ${tagName}` })).toHaveValue(code);
  await tagCard.screenshot({ path: testInfo.outputPath("edit-tag-barcode.png"), animations: "disabled" });
  await tagCard.getByRole("button", { name: `Cancel barcode edit for ${tagName}` }).click();

  await navigate(page, "All documents");
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const upload = page.waitForResponse((response) => response.url().endsWith("/api/documents") && response.request().method() === "POST" && response.status() === 202);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${documentName}.pdf`, mimeType: "application/pdf", buffer: fixture });
  const documentId = (await (await upload).json()).id;
  await expect.poll(async () => {
    const document = await (await page.request.get(`/api/documents/${documentId}`)).json();
    return `${document.status}:${document.tags.find((tag: { name: string }) => tag.name === tagName)?.origin ?? "none"}`;
  }, { timeout: 120000 }).toBe("ready:source");
  await page.getByRole("textbox", { name: "Search documents" }).fill(`title:${documentName}`);
  await page.getByRole("button", { name: "Refresh" }).click();
  const row = page.locator(".document-row").filter({ has: page.getByRole("button", { name: documentName, exact: true }) });
  await expect(row).toContainText(tagName);
  await row.screenshot({ path: testInfo.outputPath("tagged-by-barcode.png"), animations: "disabled" });
});
