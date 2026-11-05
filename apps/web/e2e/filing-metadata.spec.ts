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

test("sender and document type can be managed, assigned, and found", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const suffix = `${Date.now()}-${testInfo.project.name}`;
  const senderName = `Town office ${suffix}`;
  const renamedSender = `City office ${suffix}`;
  const typeName = `Permit notice ${suffix}`;
  await navigate(page, "Tags & filing");
  const senders = page.locator(".filing-card").filter({ has: page.getByRole("heading", { name: "Senders & organizations" }) });
  await senders.getByRole("textbox", { name: "New sender name" }).fill(senderName);
  await senders.getByRole("button", { name: "Add", exact: true }).click();
  await expect(senders.getByText(senderName, { exact: true })).toBeVisible();
  await senders.getByRole("button", { name: `Rename ${senderName}` }).focus();
  await page.keyboard.press("Enter");
  const renameInput = senders.getByRole("textbox", { name: `Rename ${senderName}` });
  await expect(renameInput).toBeFocused();
  await renameInput.fill(renamedSender);
  await page.keyboard.press("Enter");
  await expect(senders.getByText(renamedSender, { exact: true })).toBeVisible();
  await expect(senders.getByRole("button", { name: `Rename ${renamedSender}` })).toBeFocused();
  await expect(senders.getByRole("status")).toContainText("renamed");
  await senders.getByRole("button", { name: `Rename ${renamedSender}` }).click();
  await expect(senders.getByRole("textbox", { name: `Rename ${renamedSender}` })).toBeFocused();
  await senders.getByRole("button", { name: "Cancel rename" }).click();
  await expect(senders.getByRole("button", { name: `Rename ${renamedSender}` })).toBeFocused();
  await expect(senders.getByRole("status")).toContainText("cancelled");
  const senderFilter = senders.getByRole("textbox", { name: "Filter senders & organizations" });
  await senderFilter.fill(`missing-${suffix}`);
  await expect(senders.getByText("No matches. Try another name.")).toBeVisible();
  await senderFilter.fill(renamedSender);
  await expect(senders.getByText(renamedSender, { exact: true })).toBeVisible();
  await senderFilter.clear();

  const disposableSender = `Discard ${suffix}`;
  await senders.getByRole("textbox", { name: "New sender name" }).fill(disposableSender);
  await senders.getByRole("button", { name: "Add", exact: true }).click();
  await expect(senders.getByText(disposableSender, { exact: true })).toBeVisible();
  page.once("dialog", (dialog) => void dialog.accept());
  await senders.getByRole("button", { name: `Delete ${disposableSender}` }).focus();
  await page.keyboard.press("Enter");
  await expect(senders.getByText(disposableSender, { exact: true })).toBeHidden();
  await expect(senderFilter).toBeFocused();
  await expect(senders.getByRole("status")).toContainText("deleted");

  const types = page.locator(".filing-card").filter({ has: page.getByRole("heading", { name: "Document types" }) });
  await types.getByRole("textbox", { name: "New type name" }).fill(typeName);
  await types.getByRole("button", { name: "Add", exact: true }).click();
  await expect(types.getByText(typeName, { exact: true })).toBeVisible();
  await types.getByRole("textbox", { name: "Filter document types" }).fill(typeName);
  await expect(types.locator(".filing-vocabulary-list li")).toHaveCount(1);
  await page.screenshot({ path: testInfo.outputPath("filing-vocabularies.png") });

  await navigate(page, "All documents");
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const name = `filing-${suffix}`;
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.png`, mimeType: "image/png", buffer: readFileSync(fixture) });
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
  await page.getByRole("button", { name, exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Keep it in place." });
  await dialog.getByLabel("From").selectOption({ label: renamedSender });
  await dialog.getByLabel("Document type").selectOption({ label: typeName });
  await page.screenshot({ path: testInfo.outputPath("document-filing.png") });
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog).toBeHidden();

  const search = page.getByRole("textbox", { name: "Search documents" });
  const senderResults = page.waitForResponse((response) => response.url().includes(`q=${encodeURIComponent(renamedSender)}`) && response.status() === 200);
  await search.fill(renamedSender);
  const senderPayload = await (await senderResults).json();
  expect(senderPayload.documents).toHaveLength(1);
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
  const typeResults = page.waitForResponse((response) => response.url().includes(`q=${encodeURIComponent(typeName)}`) && response.status() === 200);
  await search.fill(typeName);
  const typePayload = await (await typeResults).json();
  expect(typePayload.documents).toHaveLength(1);
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
  await expect(page.locator(".document-row")).toHaveCount(1);
  await page.screenshot({ path: testInfo.outputPath("filing-metadata.png") });

  const inlineSender = `Library sender ${suffix}`;
  await page.getByRole("button", { name, exact: true }).click();
  const reopened = page.getByRole("dialog", { name: "Keep it in place." });
  await reopened.getByRole("button", { name: "Add a sender" }).click();
  await reopened.getByRole("textbox", { name: "New sender name" }).fill(inlineSender);
  await reopened.getByRole("button", { name: "Add sender", exact: true }).click();
  await expect(reopened.getByLabel("From")).toHaveValue(/.+/);
  await reopened.getByRole("button", { name: "Save changes" }).click();
  await expect(reopened).toBeHidden();
  const inlineResults = page.waitForResponse((response) => response.url().includes(`q=${encodeURIComponent(inlineSender)}`) && response.status() === 200);
  await search.fill(inlineSender);
  await expect(search).toHaveValue(inlineSender);
  expect((await (await inlineResults).json()).documents).toHaveLength(1);
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
});
