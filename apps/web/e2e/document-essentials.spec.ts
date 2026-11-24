import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = readFileSync(path.resolve(process.cwd(), "e2e/fixtures/judge.png"));

test("document opens with essentials and keeps manual filing available", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set isolated stack credentials");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const name = `essentials-${Date.now()}-${testInfo.project.name}`;
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const response = page.waitForResponse((item) => item.url().endsWith("/api/documents") && item.request().method() === "POST" && item.status() === 202);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.png`, mimeType: "image/png", buffer: fixture });
  const id = (await (await response).json()).id;
  await page.goto(`/?document=${id}`);
  const dialog = page.getByRole("dialog").filter({ hasText: "Keep it in place." });
  await expect(dialog.getByLabel("Title")).toBeVisible();
  await expect(dialog.getByLabel("Document date")).toBeVisible();
  await expect(dialog.getByText("Digital only", { exact: true })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "More filing options" })).toHaveAttribute("aria-expanded", "false");
  await expect(dialog.getByLabel("Archive number (ASN)")).toHaveCount(0);
  await expect(dialog.getByRole("button", { name: "Save changes" })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("document-essentials.png"), animations: "disabled" });

  await dialog.getByRole("button", { name: "Add task" }).click();
  await dialog.getByLabel("Due date").fill("2027-02-03");
  await dialog.getByLabel("What needs doing?").fill("Review this");
  await dialog.getByRole("button", { name: "More filing options" }).click();
  await expect(dialog.getByLabel("Archive number (ASN)")).toBeVisible();
  await expect(dialog.getByLabel("From")).toBeVisible();
  await dialog.getByRole("button", { name: "More filing options" }).click();
  await expect(dialog.getByLabel("From")).toHaveCount(0);
  await dialog.getByRole("button", { name: "Keep paper copy" }).click();
  await expect(dialog.getByLabel("Paper category")).toBeFocused();
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog).toBeHidden();
  const saved = await (await page.request.get(`/api/documents/${id}`)).json();
  expect(saved.action_status).toBe("open");
  expect(saved.action_note).toBe("Review this");
});
