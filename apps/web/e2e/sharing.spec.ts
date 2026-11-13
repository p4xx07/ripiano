import { expect, request as httpRequest, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = path.resolve(process.cwd(), "e2e/fixtures/judge.png");

test("selected documents share as one revocable link, and a document can be emailed", async ({ page, baseURL }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.setTimeout(150000);
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  const prefix = `bundle-${Date.now().toString(36)}-${testInfo.project.name}`;
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
  await page.getByText("Share as one link").click();
  await page.getByLabel(/Name of the bundle/).fill(prefix);
  await page.getByRole("button", { name: "Create link for 2 documents" }).click();
  const link = page.getByRole("textbox", { name: "New bundle link" });
  await expect(link).toHaveValue(/\/api\/share-bundles\//);
  const url = new URL(await link.inputValue());
  await page.locator(".bundle-panel").screenshot({ path: testInfo.outputPath("bundle.png"), animations: "disabled" });

  const anonymous = await httpRequest.newContext({ baseURL });
  await expect.poll(async () => (await anonymous.get(url.pathname)).status(), { timeout: 30000 }).toBe(200);
  const zip = await anonymous.get(url.pathname);
  expect(zip.headers()["content-type"]).toBe("application/zip");
  expect((await zip.body()).subarray(0, 2).toString()).toBe("PK");
  await page.getByRole("button", { name: `Revoke bundle ${prefix}` }).click();
  await expect(page.getByRole("button", { name: `Revoke bundle ${prefix}` })).toHaveCount(0);
  expect((await anonymous.get(url.pathname)).status()).toBe(404);
  await anonymous.dispose();

  await page.reload();
  await page.getByRole("textbox", { name: "Search documents" }).fill(`title:${prefix}-first`);
  await page.getByRole("button", { name: `${prefix}-first`, exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Keep it in place." });
  await dialog.getByRole("button", { name: "Write an email" }).click();
  const form = dialog.getByRole("form", { name: "Email this document" });
  await form.getByLabel(/^To/).fill(`friend-${prefix}@ripiano.test`);
  await form.getByLabel(/Message/).fill("Here is the scan.");
  await form.getByRole("button", { name: "Send email" }).click();
  await expect(dialog.locator(".email-sends")).toContainText(`Sent to friend-${prefix}@ripiano.test`, { timeout: 30000 });
});
