import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = readFileSync(path.resolve(process.cwd(), "e2e/fixtures/judge.png"));

test("reserve a code for a digital document, then keep paper with the same code", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set isolated stack credentials");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const upload = page.waitForResponse((item) => item.url().endsWith("/api/documents") && item.request().method() === "POST" && item.status() === 202);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `reserve-${Date.now()}-${testInfo.project.name}.png`, mimeType: "image/png", buffer: fixture });
  const id = (await (await upload).json()).id;
  await page.goto(`/?document=${id}`);
  const dialog = page.getByRole("dialog").filter({ hasText: "Keep it in place." });
  await expect(dialog.getByText("Digital only", { exact: true })).toBeVisible();

  await dialog.getByText("Reserve a code for later (advanced)").click();
  await dialog.getByRole("combobox", { name: /Paper category/ }).selectOption("MED");
  await dialog.getByRole("button", { name: "Reserve code", exact: true }).click();
  await expect(dialog.getByText("Code reserved · digital only")).toBeVisible();
  const reserved = await (await page.request.get(`/api/documents/${id}`)).json();
  const code = reserved.physical_copies[0].sticker_code;
  expect(code).toMatch(/^MED-\d{5}$/);
  expect(reserved.physical_copies[0].reserved_at).toBeTruthy();

  await dialog.getByRole("button", { name: "Keep paper with this code" }).click();
  await expect(dialog.getByRole("link", { name: `Print sticker ${code}` })).toBeVisible();
  const paper = await (await page.request.get(`/api/documents/${id}`)).json();
  expect(paper.physical_copies[0].sticker_code).toBe(code);
  expect(paper.physical_copies[0].reserved_at).toBeNull();
});
