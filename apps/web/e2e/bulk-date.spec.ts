import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = path.resolve(process.cwd(), "e2e/fixtures/judge.png");

test("set and clear the document date for a selected batch", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const prefix = `bulk-date-${Date.now()}-${testInfo.project.name}`;
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
  expect(ids).toHaveLength(2);

  await page.getByRole("button", { name: "Select documents" }).click();
  for (const part of ["first", "second"]) await page.getByRole("checkbox", { name: `Select ${prefix}-${part}` }).check();
  await page.getByText("Change document date").click();
  await page.getByLabel("Document date for selected documents").fill("2025-04-15");
  await page.getByRole("button", { name: "Set date" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Set document date to 2025-04-15 for 2 documents." })).toBeVisible();
  for (const id of ids) {
    expect((await (await page.request.get(`/api/documents/${id}`)).json()).document_date).toBe("2025-04-15");
  }
  await page.screenshot({ path: testInfo.outputPath("bulk-date.png"), animations: "disabled" });

  for (const part of ["first", "second"]) await page.getByRole("checkbox", { name: `Select ${prefix}-${part}` }).check();
  await page.getByRole("button", { name: "Clear date" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Cleared document date for 2 documents." })).toBeVisible();
  for (const id of ids) {
    expect((await (await page.request.get(`/api/documents/${id}`)).json()).document_date).toBeNull();
  }
});
