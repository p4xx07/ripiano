import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = path.resolve(process.cwd(), "e2e/fixtures/judge.png");

async function navigate(page: Page, name: string) {
  const menu = page.getByRole("button", { name: "Toggle menu" });
  const mobile = await menu.isVisible();
  if (mobile) await menu.click();
  await page.getByRole("button", { name, exact: true }).click();
  if (mobile) await expect.poll(() => page.locator(".sidebar").evaluate((element) => element.getBoundingClientRect().right)).toBeLessThan(1);
}

test("matching phrases file a new document without an Inbox step", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const suffix = `${Date.now()}-${testInfo.project.name}`;
  const documentName = `auto-file-${suffix}`;
  const senderName = `Sender ${suffix}`;
  const typeName = `Notice ${suffix}`;
  await navigate(page, "Tags & filing");
  for (const [heading, inputName, label] of [
    ["Senders & organizations", "New sender name", senderName],
    ["Document types", "New type name", typeName],
  ]) {
    const card = page.locator(".filing-card").filter({ has: page.getByRole("heading", { name: heading }) });
    await card.getByRole("textbox", { name: inputName }).fill(label);
    await card.getByRole("button", { name: "Add", exact: true }).click();
    const row = card.locator(".filing-vocabulary-list li").filter({ has: page.getByText(label, { exact: true }) });
    await expect(row).toBeVisible();
    await row.getByRole("button", { name: "Add matching phrase" }).click();
    await row.getByRole("textbox", { name: `Matching phrase for ${label}` }).fill(documentName);
    await row.getByRole("button", { name: "Add", exact: true }).click();
    await expect(row.getByText(documentName, { exact: true })).toBeVisible();
  }
  await page.screenshot({ path: testInfo.outputPath("matching-phrases.png") });

  await navigate(page, "All documents");
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${documentName}.png`, mimeType: "image/png", buffer: readFileSync(fixture) });
  const row = page.locator(".document-row").filter({ has: page.getByRole("button", { name: documentName, exact: true }) });
  await expect(row).toBeVisible();
  await expect(row).toContainText(`From: ${senderName}`, { timeout: 60000 });
  await expect(row).toContainText(`Type: ${typeName}`);
  await row.getByRole("button", { name: documentName, exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Keep it in place." });
  await expect(dialog.getByLabel("From")).toContainText(senderName);
  await expect(dialog.getByLabel("Document type")).toContainText(typeName);
  await expect(dialog.getByText("Added by matching phrase · change it if needed")).toHaveCount(2);
  await page.screenshot({ path: testInfo.outputPath("automatic-filing.png") });
  const saved = page.waitForResponse((response) => response.url().includes("/api/documents/") && response.request().method() === "PATCH" && response.status() === 200);
  await dialog.getByLabel("Title").fill(`${documentName} reviewed`);
  await dialog.getByRole("button", { name: "Save changes" }).click();
  const updated = await (await saved).json();
  expect(updated.correspondent_origin).toBe("rule");
  expect(updated.document_type_origin).toBe("rule");
  expect(updated.tags.some((tag: { origin: string }) => tag.origin === "rule")).toBe(true);
});
