import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = path.resolve(process.cwd(), "e2e/fixtures/judge.png");

test("overview opens documents without tags in the Library", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const title = `Untagged ${Date.now()} ${testInfo.project.name}`;
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const uploaded = page.waitForResponse((response) => response.url().endsWith("/api/documents") && response.request().method() === "POST" && response.status() === 202);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${title}.png`, mimeType: "image/png", buffer: readFileSync(fixture) });
  const document = await (await uploaded).json() as { id: string };

  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Overview." })).toBeVisible();
  await page.getByRole("button", { name: /without tags · View in Library/ }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  await expect(page.getByRole("textbox", { name: /Search documents by text/ })).toHaveValue("is:untagged");
  await expect(page.getByRole("button", { name: title, exact: true })).toBeVisible();
  const filtered = await (await page.request.get("/api/documents?q=is%3Auntagged")).json();
  expect(filtered.documents.some((item: { id: string }) => item.id === document.id)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("untagged-library.png"), animations: "disabled" });
});
