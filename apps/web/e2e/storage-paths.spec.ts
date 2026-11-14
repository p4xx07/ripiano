import { expect, Page, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = readFileSync(path.resolve(process.cwd(), "e2e/fixtures/judge.png"));

async function navigate(page: Page, name: string) {
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name, exact: true }).click();
}

test("a storage path can be defined and chosen for a document", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.setTimeout(150000);
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  const suffix = `${Date.now()}-${testInfo.project.name}`;
  const pathName = `By sender ${suffix}`;
  await navigate(page, "Tags & filing");
  const form = page.getByRole("form", { name: "New storage path" });
  await form.getByLabel("Storage path name").fill(pathName);
  await form.getByLabel("Folder template").fill("{correspondent}/{year}/{month}");
  await form.getByRole("button", { name: "Add" }).click();
  await expect(page.locator(".storage-paths").getByText(pathName)).toBeVisible();

  await navigate(page, "All documents");
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const response = page.waitForResponse((item) => item.url().endsWith("/api/documents") && item.request().method() === "POST" && item.status() === 202);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  const title = `stored-${suffix}`;
  await (await chooser).setFiles({ name: `${title}.png`, mimeType: "image/png", buffer: Buffer.concat([fixture, Buffer.from(title)]) });
  const id = (await (await response).json()).id;
  await expect.poll(async () => (await (await page.request.get(`/api/documents/${id}`)).json()).status, { timeout: 90000 }).toBe("ready");
  await page.getByRole("textbox", { name: "Search documents" }).fill(`title:${title}`);
  await page.getByRole("button", { name: title, exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Keep it in place." });
  await dialog.getByLabel(/Storage path/).selectOption({ label: pathName });
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog).toBeHidden();
  expect((await (await page.request.get(`/api/documents/${id}`)).json()).storage_path.name).toBe(pathName);

  await navigate(page, "Tags & filing");
  await page.getByRole("button", { name: `Remove storage path ${pathName}` }).click();
  await expect(page.getByRole("button", { name: `Remove storage path ${pathName}` })).toHaveCount(0);
  expect((await (await page.request.get(`/api/documents/${id}`)).json()).storage_path).toBeNull();
});
