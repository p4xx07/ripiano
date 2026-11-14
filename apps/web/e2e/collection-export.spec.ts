import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = path.resolve(process.cwd(), "e2e/fixtures/judge.png");

test("download selected documents as one portable ZIP", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  const prefix = `collection-${Date.now().toString(36)}-${testInfo.project.name}`;
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles(["first", "second"].map((part) => ({
    name: `${prefix}-${part}.png`, mimeType: "image/png", buffer: Buffer.concat([readFileSync(fixture), Buffer.from(`${prefix}-${part}`)]),
  })));
  await page.getByRole("textbox", { name: "Search documents" }).fill(`title:${prefix}`);
  await expect(page.locator(".document-row")).toHaveCount(2);
  await page.getByRole("button", { name: "Select documents" }).click();
  await page.getByRole("checkbox", { name: `Select ${prefix}-first` }).check();
  await page.getByRole("checkbox", { name: `Select ${prefix}-second` }).check();
  await page.getByText("Export selected").click();
  const link = page.getByRole("link", { name: "Download 2 documents" });
  await expect(link).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("collection-export.png"), animations: "disabled", fullPage: true });
  const downloadPromise = page.waitForEvent("download");
  await link.click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("ripiano-documents.zip");
  expect(await download.failure()).toBeNull();
});
