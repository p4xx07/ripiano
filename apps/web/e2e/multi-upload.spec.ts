import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = path.resolve(process.cwd(), "e2e/fixtures/judge.png");

test("a rejected file does not stop the rest of a multi-file upload", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const name = `batch-${Date.now()}-${testInfo.project.name}`;
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles([
    { name: `${name}-first.png`, mimeType: "image/png", buffer: readFileSync(fixture) },
    { name: `${name}-invalid.txt`, mimeType: "text/plain", buffer: Buffer.from("not a document") },
    { name: `${name}-last.png`, mimeType: "image/png", buffer: readFileSync(fixture) },
  ]);

  await expect(page.getByRole("button", { name: `${name}-first`, exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: `${name}-last`, exact: true })).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("1 of 3 files could not be added");
  await expect(page.getByRole("alert")).toContainText(`${name}-invalid.txt`);
  const refreshed = page.waitForResponse((response) => response.url().includes("/api/documents?q=") && response.request().method() === "GET" && response.status() === 200);
  await page.getByRole("button", { name: "Refresh" }).click();
  await refreshed;
  await expect(page.getByRole("alert")).toContainText(`${name}-invalid.txt`);
});
