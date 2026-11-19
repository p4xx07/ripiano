import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = path.resolve(process.cwd(), "e2e/fixtures/judge.png");

test("rebuild OCR for selected documents and preserve both originals", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const prefix = `bulk-ocr-${Date.now()}-${testInfo.project.name}`;
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles(["first", "second"].map((part) => ({
    name: `${prefix}-${part}.png`, mimeType: "image/png", buffer: readFileSync(fixture),
  })));
  const search = page.getByRole("textbox", { name: "Search documents" });
  await search.fill(`title:${prefix}`);
  await expect(page.locator(".document-row")).toHaveCount(2);
  const list = await (await page.request.get(`/api/documents?q=${encodeURIComponent(`title:${prefix}`)}`)).json();
  const ids: string[] = list.documents.map((document: { id: string }) => document.id);
  expect(ids).toHaveLength(2);
  await Promise.all(ids.map(async (id) => {
    await expect.poll(async () => (await (await page.request.get(`/api/documents/${id}`)).json()).status, { timeout: 60000 }).toBe("ready");
  }));
  const originals = await Promise.all(ids.map(async (id) => (await page.request.get(`/api/documents/${id}/original`)).body()));

  await page.getByRole("button", { name: "Select documents" }).click();
  for (const part of ["first", "second"]) {
    await page.getByRole("checkbox", { name: `Select ${prefix}-${part}` }).check();
  }
  await page.getByText("OCR actions").click();
  await page.getByRole("button", { name: "Rebuild searchable PDFs" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Started OCR for 2 documents." })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("bulk-ocr.png") });
  await Promise.all(ids.map(async (id) => {
    await expect.poll(async () => (await (await page.request.get(`/api/documents/${id}`)).json()).status, { timeout: 60000 }).toBe("ready");
  }));
  for (const [index, id] of ids.entries()) {
    expect(await (await page.request.get(`/api/documents/${id}/original`)).body()).toEqual(originals[index]);
  }
});
