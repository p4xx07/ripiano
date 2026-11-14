import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = path.resolve(process.cwd(), "e2e/fixtures/judge.png");

test("a searchable PDF can be rebuilt from its preserved original", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const name = `reprocess-${Date.now()}-${testInfo.project.name}`;
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const upload = page.waitForResponse((response) => response.url().endsWith("/api/documents") && response.request().method() === "POST" && response.status() === 202);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.png`, mimeType: "image/png", buffer: readFileSync(fixture) });
  const id = (await (await upload).json()).id;
  await expect.poll(async () => (await (await page.request.get(`/api/documents/${id}`)).json()).status, { timeout: 60000 }).toBe("ready");
  const originalBefore = await (await page.request.get(`/api/documents/${id}/original`)).body();
  await page.getByRole("textbox", { name: "Search documents" }).fill(`title:${name}`);
  await page.getByRole("button", { name, exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Keep it in place." });
  const files = dialog.locator(".detail-files").first();
  await expect(files.getByRole("link", { name: "Open searchable PDF" })).toBeVisible();
  await files.getByRole("button", { name: "Run OCR again" }).click();
  await expect(files.getByRole("status")).toContainText("OCR queued from the preserved original.");
  await expect(files.getByRole("link", { name: "Download original" })).toBeVisible();
  await expect.poll(async () => (await (await page.request.get(`/api/documents/${id}`)).json()).status, { timeout: 60000 }).toBe("ready");
  await expect(files.getByRole("status")).toContainText("Searchable PDF is ready.");
  await expect(files.getByRole("link", { name: "Open searchable PDF" })).toBeVisible();
  expect(await (await page.request.get(`/api/documents/${id}/original`)).body()).toEqual(originalBefore);
  await files.screenshot({ path: testInfo.outputPath("reprocess.png") });
  await dialog.getByRole("button", { name: "Close" }).click();
  await page.getByRole("textbox", { name: "Search documents" }).fill(`text:9473 title:${name}`);
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
});
