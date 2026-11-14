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

test("select documents and file tags, sender, and type together", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const suffix = `${Date.now()}-${testInfo.project.name}`;
  const tagName = `Bulk filing ${suffix}`;
  const senderName = `Bulk sender ${suffix}`;
  const typeName = `Bulk type ${suffix}`;
  await navigate(page, "Tags & filing");
  await page.getByPlaceholder("e.g. Bills").fill(tagName);
  await page.getByRole("button", { name: "Create tag" }).click();
  await expect(page.getByRole("heading", { name: tagName })).toBeVisible();
  const senders = page.locator(".filing-card").filter({ has: page.getByRole("heading", { name: "Senders & organizations" }) });
  await senders.getByRole("textbox", { name: "New sender name" }).fill(senderName);
  await senders.getByRole("button", { name: "Add", exact: true }).click();
  await expect(senders.getByText(senderName, { exact: true })).toBeVisible();
  const types = page.locator(".filing-card").filter({ has: page.getByRole("heading", { name: "Document types" }) });
  await types.getByRole("textbox", { name: "New type name" }).fill(typeName);
  await types.getByRole("button", { name: "Add", exact: true }).click();
  await expect(types.getByText(typeName, { exact: true })).toBeVisible();
  await navigate(page, "All documents");

  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles(["first", "second"].map((part) => ({
    name: `bulk-${suffix}-${part}.png`, mimeType: "image/png", buffer: readFileSync(fixture),
  })));

  const titles = ["first", "second"].map((part) => `bulk-${suffix}-${part}`);
  const search = page.getByRole("textbox", { name: "Search documents" });
  await search.fill(`bulk-${suffix}`);
  await expect(page.locator(".document-row")).toHaveCount(2);
  const rows = titles.map((title) => page.locator(".document-row").filter({ has: page.getByRole("button", { name: title, exact: true }) }));
  for (const row of rows) await expect(row).toBeVisible();
  await page.getByRole("button", { name: "Select documents" }).click();
  for (const title of titles) await page.getByRole("checkbox", { name: `Select ${title}` }).check();
  await expect(page.getByText("2 selected")).toBeVisible();
  await page.getByRole("combobox", { name: "Tag for selected documents" }).selectOption({ label: tagName });
  await page.getByRole("button", { name: "Add tag", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: `Added ${tagName} to 2 documents.` })).toBeVisible();
  for (const row of rows) await expect(row).toContainText(tagName);
  await page.screenshot({ path: testInfo.outputPath("bulk-tags.png") });

  for (const title of titles) await page.getByRole("checkbox", { name: `Select ${title}` }).check();
  await page.getByRole("button", { name: "Remove tag", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: `Removed ${tagName} from 2 documents.` })).toBeVisible();
  for (const row of rows) await expect(row).not.toContainText(tagName);
  await page.getByText("Change sender or document type").click();
  for (const title of titles) await page.getByRole("checkbox", { name: `Select ${title}` }).check();
  await page.getByRole("combobox", { name: "Sender for selected documents" }).selectOption({ label: senderName });
  await page.getByRole("button", { name: "Set sender" }).click();
  await expect(page.getByRole("status").filter({ hasText: `Set sender to ${senderName} for 2 documents.` })).toBeVisible();
  for (const row of rows) await expect(row).toContainText(`From: ${senderName}`);
  for (const title of titles) await page.getByRole("checkbox", { name: `Select ${title}` }).check();
  await page.getByRole("combobox", { name: "Document type for selected documents" }).selectOption({ label: typeName });
  await page.getByRole("button", { name: "Set type" }).click();
  await expect(page.getByRole("status").filter({ hasText: `Set document type to ${typeName} for 2 documents.` })).toBeVisible();
  for (const row of rows) await expect(row).toContainText(`Type: ${typeName}`);
  await page.screenshot({ path: testInfo.outputPath("bulk-filing.png") });
  for (const title of titles) await page.getByRole("checkbox", { name: `Select ${title}` }).check();
  await page.getByRole("combobox", { name: "Sender for selected documents" }).selectOption("none");
  await page.getByRole("button", { name: "Set sender" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Cleared sender for 2 documents." })).toBeVisible();
  for (const row of rows) await expect(row).not.toContainText(`From: ${senderName}`);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
