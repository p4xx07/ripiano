import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const owner = { username: process.env.RIPIANO_E2E_USERNAME, password: process.env.RIPIANO_E2E_PASSWORD };
// The second disposable account (also used by the two-step sign-in journey, which leaves it with 2FA off).
const reader = { username: process.env.RIPIANO_E2E_2FA_USERNAME, password: process.env.RIPIANO_E2E_2FA_PASSWORD };
const fixture = path.resolve(process.cwd(), "e2e/fixtures/judge.png");

async function signIn(page: Page, account: { username?: string; password?: string }) {
  await page.getByLabel("Username").fill(account.username!);
  await page.getByLabel("Password").fill(account.password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
}

async function openNav(page: Page, name: string) {
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name, exact: true }).click();
}

test("share one document with another person, who can edit its details but nothing else", async ({ page }, testInfo) => {
  test.skip(!owner.username || !owner.password || !reader.username || !reader.password, "Set the RIPIANO_E2E_* and RIPIANO_E2E_2FA_* accounts");
  test.skip(testInfo.project.name !== "desktop", "The second account is shared, so this runs once");
  test.setTimeout(120000);
  await page.goto("/");
  await signIn(page, owner);

  const name = `shared-${Date.now()}`;
  await page.getByRole("button", { name: "Add document", exact: true }).click();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.png`, mimeType: "image/png", buffer: readFileSync(fixture) });
  await page.getByRole("button", { name, exact: true }).click();
  let dialog = page.getByRole("dialog", { name: "Keep it in place." });
  await dialog.getByText("Manage access").click();
  await dialog.getByLabel("Person or group").selectOption({ label: reader.username! });
  await dialog.locator(".access-panel .share-controls").getByLabel("Access").selectOption("edit");
  await dialog.getByRole("button", { name: "Share", exact: true }).click();
  await expect(dialog.locator(".access-panel").getByRole("status")).toContainText("can now view and edit details");
  await expect(dialog.getByLabel(`Access for ${reader.username}`, { exact: true })).toHaveValue("edit");
  await dialog.locator(".access-panel").screenshot({ path: testInfo.outputPath("document-access.png") });
  await dialog.getByRole("button", { name: "Close" }).click();
  await page.locator("button[title=\"Sign out\"]").click();

  await signIn(page, reader);
  // The reader's own Library stays theirs; the document is under Shared with me.
  await expect(page.getByRole("button", { name, exact: true })).toHaveCount(0);
  await openNav(page, "Shared with me");
  await expect(page.getByRole("heading", { name: /Shared with me/ })).toBeVisible();
  await page.getByRole("textbox", { name: "Search shared documents" }).fill(name);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.locator(".document-row")).toHaveCount(1);
  await expect(page.locator(".document-row")).toContainText(`Shared by ${owner.username} · Can edit details`);
  await page.getByRole("button", { name, exact: true }).click();
  dialog = page.getByRole("dialog", { name });
  await expect(dialog.getByText(`Shared by ${owner.username}`)).toBeVisible();
  await expect(dialog.getByText("Manage access")).toHaveCount(0);
  await expect(dialog.getByText("Move to Trash")).toHaveCount(0);
  const download = await page.request.get(await dialog.getByRole("link", { name: "Download original" }).getAttribute("href") as string);
  expect(Buffer.from(await download.body())).toEqual(readFileSync(fixture));
  await dialog.getByLabel("Title").fill(`${name} reviewed`);
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog.getByRole("status")).toContainText("Changes saved.");
  await dialog.getByRole("textbox", { name: "New note" }).fill("Checked the amounts");
  await dialog.getByRole("button", { name: "Add note" }).click();
  await expect(dialog.locator(".note-list")).toContainText("Checked the amounts");
  await dialog.screenshot({ path: testInfo.outputPath("shared-document.png") });
  await dialog.getByRole("button", { name: "Close" }).click();
  await page.locator("button[title=\"Sign out\"]").click();

  // The owner sees the reader's change and note, then removes access.
  await signIn(page, owner);
  await page.getByRole("textbox", { name: "Search documents" }).fill(`${name} reviewed`);
  await page.getByRole("button", { name: `${name} reviewed`, exact: true }).click();
  dialog = page.getByRole("dialog", { name: "Keep it in place." });
  await expect(dialog.locator(".note-list")).toContainText(`${reader.username}`);
  await dialog.getByText("Manage access").click();
  await dialog.getByRole("button", { name: `Remove access for ${reader.username}` }).click();
  await expect(dialog.locator(".access-panel")).toContainText("Only you can open this document.");
  await dialog.getByRole("button", { name: "Close" }).click();
  await page.locator("button[title=\"Sign out\"]").click();

  await signIn(page, reader);
  await openNav(page, "Shared with me");
  await page.getByRole("textbox", { name: "Search shared documents" }).fill(name);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByRole("heading", { name: "No matches." })).toBeVisible();
});
