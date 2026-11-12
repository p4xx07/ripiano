import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = readFileSync(path.resolve(process.cwd(), "e2e/fixtures/three-pages.pdf"));

test("page edits become a new version and the previous file stays available", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.setTimeout(240000);
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const name = `pages-${Date.now()}-${testInfo.project.name}`;
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const upload = page.waitForResponse((response) => response.url().endsWith("/api/documents") && response.request().method() === "POST" && response.status() === 202);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.pdf`, mimeType: "application/pdf", buffer: fixture });
  const id = (await (await upload).json()).id;
  const ready = async () => (await (await page.request.get(`/api/documents/${id}`)).json()).status;
  await expect.poll(ready, { timeout: 120000 }).toBe("ready");

  await page.getByRole("textbox", { name: "Search documents" }).fill(name);
  await page.getByRole("button", { name, exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Keep it in place." });
  await dialog.getByRole("button", { name: "Open pages & versions" }).click();
  const panel = dialog.locator(".pages-panel");
  await expect(panel.getByRole("img", { name: "Page 3" })).toBeVisible();
  await panel.getByRole("button", { name: "Remove page 2" }).click();
  await panel.getByRole("button", { name: "Rotate page 1 right" }).click();
  await panel.getByRole("button", { name: "Move page 3 earlier" }).click();
  await panel.getByRole("button", { name: "Move page 3 earlier" }).click();
  await panel.screenshot({ path: testInfo.outputPath("pages-editing.png"), animations: "disabled" });
  await panel.getByRole("button", { name: "Save as new version" }).click();
  await expect(panel.getByRole("status")).toContainText("Saved as a new version");
  await expect.poll(ready, { timeout: 120000 }).toBe("ready");

  const versions = await (await page.request.get(`/api/documents/${id}/versions`)).json();
  expect(versions.current.number).toBe(2);
  expect(versions.current.note).toBe("Edited pages: removed 1 page, rotated 1 page, reordered pages");
  const previous = await page.request.get(`/api/documents/${id}/versions/${versions.versions[0].id}/download`);
  expect(await previous.body()).toEqual(fixture);
  expect((await (await page.request.get(`/api/documents/${id}/pages`)).json()).count).toBe(2);
  const text = (await (await page.request.get(`/api/documents?q=${encodeURIComponent(`text:heron title:"${name}"`)}`)).json()).documents;
  expect(text).toEqual([]);

  await expect(panel.getByText("Version 1", { exact: true })).toBeVisible();
  await panel.getByRole("checkbox", { name: /New document after page/ }).first().check();
  await panel.getByRole("button", { name: "Split into 2 documents" }).click();
  await expect(panel.getByRole("status")).toContainText("Created 2 new documents");
  await expect(panel.getByRole("button", { name: `Open “${name} (2/2)”` })).toBeVisible();
  await panel.screenshot({ path: testInfo.outputPath("pages-versions.png"), animations: "disabled" });
});
