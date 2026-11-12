import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = path.resolve(process.cwd(), "e2e/fixtures/office-letter.docx");

test("a Word document becomes searchable while its original stays intact", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const name = `office-${Date.now()}-${testInfo.project.name}`;
  const original = readFileSync(fixture);
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const upload = page.waitForResponse((response) => response.url().endsWith("/api/documents") && response.request().method() === "POST" && response.status() === 202);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.docx`, mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", buffer: original });
  const id = (await (await upload).json()).id;
  await expect.poll(async () => (await (await page.request.get(`/api/documents/${id}`)).json()).status, { timeout: 75000 }).toBe("ready");

  const originalResponse = await page.request.get(`/api/documents/${id}/original`);
  expect(originalResponse.status()).toBe(200);
  expect(await originalResponse.body()).toEqual(original);
  const archiveResponse = await page.request.get(`/api/documents/${id}/archive`);
  expect(archiveResponse.status()).toBe(200);
  expect((await archiveResponse.body()).subarray(0, 5).toString()).toBe("%PDF-");

  const searchable = page.waitForResponse(async (response) =>
    response.url().includes("/api/documents?q=") && response.status() === 200 &&
    (await response.json()).documents.some((document: { id: string }) => document.id === id),
    { timeout: 15000 },
  );
  await page.getByRole("textbox", { name: "Search documents" }).fill("text:Ripiano");
  await searchable;
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("office-search.png"), animations: "disabled", fullPage: true });
  await page.getByRole("button", { name, exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Keep it in place." });
  await expect(dialog.getByRole("link", { name: "Download original" })).toBeVisible();
  await expect(dialog.getByRole("link", { name: "Open searchable PDF" })).toBeVisible();
  await dialog.locator(".detail-files").first().screenshot({ path: testInfo.outputPath("office-document.png"), animations: "disabled" });
});

test("Excel and PowerPoint files become searchable PDFs", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const prefix = `office-pair-${Date.now()}-${testInfo.project.name}`;
  const cases = [
    { name: `${prefix}-sheet.xlsx`, mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", fixture: "office-sheet.xlsx", term: "Excel" },
    { name: `${prefix}-slides.pptx`, mimeType: "application/vnd.openxmlformats-officedocument.presentationml.presentation", fixture: "office-slides.pptx", term: "PowerPoint" },
  ];
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles(cases.map(({ name, mimeType, fixture: source }) => ({
    name, mimeType, buffer: readFileSync(path.resolve(process.cwd(), "e2e/fixtures", source)),
  })));

  const query = `title:${prefix}`;
  const list = async () => (await (await page.request.get(`/api/documents?q=${encodeURIComponent(query)}`)).json()).documents as { id: string; original_name: string }[];
  await expect.poll(async () => (await list()).length, { timeout: 30000 }).toBe(2);
  for (const item of cases) {
    const document = (await list()).find((candidate) => candidate.original_name === item.name);
    expect(document).toBeDefined();
    const id = document!.id;
    await expect.poll(async () => (await (await page.request.get(`/api/documents/${id}`)).json()).status, { timeout: 75000 }).toBe("ready");
    expect(await (await page.request.get(`/api/documents/${id}/original`)).body()).toEqual(readFileSync(path.resolve(process.cwd(), "e2e/fixtures", item.fixture)));
    expect((await (await page.request.get(`/api/documents/${id}/archive`)).body()).subarray(0, 5).toString()).toBe("%PDF-");
    const matches = await (await page.request.get(`/api/documents?q=${encodeURIComponent(`text:${item.term} title:${prefix}`)}`)).json();
    expect(matches.documents.some((candidate: { id: string }) => candidate.id === id)).toBe(true);
  }
});
