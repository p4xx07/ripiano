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

test("a sender rule with 'any of these words' files a document that uses one of them", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.setTimeout(150000);
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  const suffix = `${Date.now().toString(36)}${testInfo.project.name}`;
  const senderName = `Utility ${suffix}`;
  const word = `gasco${suffix}`;
  await navigate(page, "Tags & filing");
  const card = page.locator(".filing-card").filter({ has: page.getByRole("heading", { name: "Senders & organizations" }) });
  await card.getByRole("textbox", { name: "New sender name" }).fill(senderName);
  await card.getByRole("button", { name: "Add", exact: true }).click();
  const row = card.locator(".filing-vocabulary-list li").filter({ has: page.getByText(senderName, { exact: true }) });
  await row.getByRole("button", { name: "Add matching phrase" }).click();
  await row.getByRole("textbox", { name: `Matching phrase for ${senderName}` }).fill(`electrico${suffix} ${word}`);
  await row.getByRole("combobox", { name: `How the phrase for ${senderName} matches` }).selectOption("any");
  await row.getByRole("button", { name: "Add", exact: true }).click();
  await expect(row.locator(".rule-chip")).toContainText("Any of these words:");

  await navigate(page, "All documents");
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const upload = page.waitForResponse((response) => response.url().endsWith("/api/documents") && response.request().method() === "POST" && response.status() === 202);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `bill from ${word} november.png`, mimeType: "image/png", buffer: fixture });
  const id = (await (await upload).json()).id;
  await expect.poll(async () => {
    const document = await (await page.request.get(`/api/documents/${id}`)).json();
    return document.status === "ready" ? `${document.correspondent?.name}:${document.correspondent_origin}` : document.status;
  }, { timeout: 120000 }).toBe(`${senderName}:rule`);
});
