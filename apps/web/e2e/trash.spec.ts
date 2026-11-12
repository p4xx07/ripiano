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

test("move a filed document to Trash and restore it", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const name = `trash-${Date.now()}-${testInfo.project.name}`;
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const upload = page.waitForResponse((response) => response.url().endsWith("/api/documents") && response.request().method() === "POST" && response.status() === 202);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.png`, mimeType: "image/png", buffer: readFileSync(fixture) });
  const id = (await (await upload).json()).id;
  await expect.poll(async () => (await (await page.request.get(`/api/documents/${id}`)).json()).status, { timeout: 60000 }).toBe("ready");
  await page.getByRole("textbox", { name: "Search documents" }).fill(`title:${name}`);
  await page.getByRole("button", { name, exact: true }).click();
  const detail = page.getByRole("dialog", { name: "Keep it in place." });
  await detail.getByRole("button", { name: "Move to Trash", exact: true }).click();
  await expect(detail.getByText(`Move “${name}” to Trash?`)).toBeVisible();
  await detail.getByRole("button", { name: "Confirm move" }).click();
  await expect(detail).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Nothing found yet" })).toBeVisible();
  expect((await (await page.request.get(`/api/documents/${id}`)).status())).toBe(404);

  await navigate(page, "Trash");
  await expect(page.getByRole("heading", { name: "Trash." })).toBeVisible();
  await expect(page.locator(".sidebar")).not.toHaveClass(/sidebar-open/);
  const row = page.locator(".document-row").filter({ hasText: name });
  await expect(row).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("trash-page.png"), fullPage: true, animations: "disabled" });
  await row.screenshot({ path: testInfo.outputPath("trashed-document.png") });
  await row.getByRole("button", { name: "Restore" }).click();
  await expect(page.getByRole("status")).toContainText(`“${name}” is back in the Library.`);
  await expect(row).toHaveCount(0);
  await navigate(page, "All documents");
  await page.getByRole("textbox", { name: "Search documents" }).fill(`title:${name}`);
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
});

test("move selected documents to Trash and restore them together", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const prefix = `bulk-trash-${Date.now()}-${testInfo.project.name}`;
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles(["first", "second"].map((part) => ({
    name: `${prefix}-${part}.png`, mimeType: "image/png", buffer: readFileSync(fixture),
  })));
  await page.getByRole("textbox", { name: "Search documents" }).fill(`title:${prefix}`);
  await expect(page.locator(".document-row")).toHaveCount(2);
  const list = await (await page.request.get(`/api/documents?q=${encodeURIComponent(`title:${prefix}`)}`)).json();
  const ids: string[] = list.documents.map((document: { id: string }) => document.id);
  await Promise.all(ids.map(async (id) => {
    await expect.poll(async () => (await (await page.request.get(`/api/documents/${id}`)).json()).status, { timeout: 60000 }).toBe("ready");
  }));
  const originals = await Promise.all(ids.map(async (id) => (await page.request.get(`/api/documents/${id}/original`)).body()));

  await page.getByRole("button", { name: "Select documents" }).click();
  for (const part of ["first", "second"]) await page.getByRole("checkbox", { name: `Select ${prefix}-${part}` }).check();
  await page.getByText("Move to Trash", { exact: true }).click();
  await page.getByRole("button", { name: "Confirm move of 2" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Moved 2 documents to Trash." })).toBeVisible();
  await expect(page.locator(".document-row")).toHaveCount(0);
  for (const id of ids) expect((await page.request.get(`/api/documents/${id}`)).status()).toBe(404);

  await navigate(page, "Trash");
  const rows = page.locator(".document-row").filter({ hasText: prefix });
  await expect(rows).toHaveCount(2);
  await page.getByRole("button", { name: "Select documents" }).click();
  for (const part of ["first", "second"]) await page.getByRole("checkbox", { name: `Select ${prefix}-${part}` }).check();
  await page.getByRole("button", { name: "Restore selected" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Restored 2 documents to the Library." })).toBeVisible();
  await expect(rows).toHaveCount(0);
  for (const [index, id] of ids.entries()) {
    expect((await page.request.get(`/api/documents/${id}`)).status()).toBe(200);
    expect(await (await page.request.get(`/api/documents/${id}/original`)).body()).toEqual(originals[index]);
  }
});
