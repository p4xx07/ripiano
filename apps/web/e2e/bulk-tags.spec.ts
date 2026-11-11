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

test("select documents and apply a manual tag together", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const suffix = `${Date.now()}-${testInfo.project.name}`;
  const tagName = `Bulk filing ${suffix}`;
  await navigate(page, "Tags & filing");
  await page.getByPlaceholder("e.g. Bills").fill(tagName);
  await page.getByRole("button", { name: "Create tag" }).click();
  await expect(page.getByRole("heading", { name: tagName })).toBeVisible();
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
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
