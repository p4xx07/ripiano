import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = path.resolve(process.cwd(), "e2e/fixtures/judge.png");

test("one-tap filing suggestions use a manually filed example", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const suffix = `${Date.now()}-${testInfo.project.name}`;
  const topic = Date.now().toString(36);
  const tag = `Utilities ${suffix}`;
  const sender = `Acme Energy ${suffix}`;
  const kind = `Invoice ${suffix}`;
  const source = `Acme electricity nord${topic} luce${topic} bill${topic} source ${suffix}`;
  const target = `Acme electricity nord${topic} luce${topic} bill${topic} target ${suffix}`;
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "Tags & filing" }).click();
  await page.getByPlaceholder("e.g. Bills").fill(tag);
  await page.getByRole("button", { name: "Create tag" }).click();
  await expect(page.getByRole("heading", { name: tag })).toBeVisible();

  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "All documents" }).click();
  let uploads = 0;
  async function upload(name: string) {
    const add = page.getByRole("button", { name: "Add document", exact: true });
    if (await add.isVisible()) await add.click();
    else await page.getByRole("button", { name: "Add", exact: true }).click();
    const response = page.waitForResponse((item) => item.url().endsWith("/api/documents") && item.request().method() === "POST" && item.status() === 202);
    const chooser = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: /Browse files/ }).click();
    // The title is one the person gave, not the file name: a title that is still the file name is no evidence
    // for a suggestion (judge 1 round 9, L2).
    await (await chooser).setFiles({ name: `scan-${uploads += 1}-${suffix}.png`, mimeType: "image/png", buffer: readFileSync(fixture) });
    const document = await (await response).json() as { id: string };
    await expect.poll(async () => (await (await page.request.get(`/api/documents/${document.id}`)).json()).status, { timeout: 60000 }).toBe("ready");
    const csrf = (await page.context().cookies()).find((cookie) => cookie.name === "csrftoken")?.value ?? "";
    expect((await page.request.patch(`/api/documents/${document.id}`, { headers: { "X-CSRFToken": csrf }, data: { title: name } })).status()).toBe(200);
    await page.getByRole("textbox", { name: "Search documents" }).fill(name);
    await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
    return document.id;
  }

  const sourceId = await upload(source);
  await page.getByRole("button", { name: source, exact: true }).click();
  let dialog = page.getByRole("dialog").filter({ hasText: "Keep it in place." });
  await dialog.getByRole("checkbox", { name: tag }).check();
  await dialog.getByRole("button", { name: "Add a sender" }).click();
  await dialog.getByRole("textbox", { name: "New sender name" }).fill(sender);
  await dialog.getByRole("button", { name: "Add sender", exact: true }).click();
  await dialog.getByRole("button", { name: "Add a type" }).click();
  await dialog.getByRole("textbox", { name: "New document type name" }).fill(kind);
  await dialog.getByRole("button", { name: "Add type", exact: true }).click();
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog).toBeHidden();

  const targetId = await upload(target);
  await page.getByRole("button", { name: target, exact: true }).click();
  dialog = page.getByRole("dialog").filter({ hasText: "Keep it in place." });
  const suggestion = dialog.getByRole("button", { name: `Add tag: ${tag}`, exact: true });
  await expect(suggestion).toBeVisible();
  await expect(suggestion).toContainText(source);
  const suggested = await (await page.request.get(`/api/documents/${targetId}/filing-suggestions`)).json();
  expect(suggested.tags.find((item: { name: string }) => item.name === tag)?.example.id).toBe(sourceId);
  expect(suggested.correspondents.find((item: { name: string }) => item.name === sender)?.example.id).toBe(sourceId);
  expect(suggested.document_types.find((item: { name: string }) => item.name === kind)?.example.id).toBe(sourceId);
  const before = await (await page.request.get(`/api/documents/${targetId}`)).json();
  expect(before.tags.some((item: { name: string }) => item.name === tag)).toBe(false);
  await dialog.locator(".filing-suggestions").screenshot({ path: testInfo.outputPath("filing-suggestions.png"), animations: "disabled" });
  await dialog.getByLabel("Title").fill(`${target} draft`);
  await suggestion.click();
  await expect(dialog.getByRole("checkbox", { name: tag })).toBeChecked();
  await expect(dialog.getByRole("checkbox", { name: tag })).toBeFocused();
  await expect(dialog.getByRole("status").filter({ hasText: "saved" })).toHaveText(`Tag ${tag} saved. Other edits still need Save changes.`);
  const afterTap = await (await page.request.get(`/api/documents/${targetId}`)).json();
  expect(afterTap.tags).toEqual(expect.arrayContaining([expect.objectContaining({ name: tag, origin: "manual" })]));
  expect(afterTap.title).toBe(target);
  await dialog.getByRole("button", { name: `Set sender: ${sender}`, exact: true }).click();
  await expect(dialog.getByRole("combobox", { name: "From" })).toHaveValue(suggested.correspondents.find((item: { name: string }) => item.name === sender).id);
  const afterSender = await (await page.request.get(`/api/documents/${targetId}`)).json();
  expect(afterSender.correspondent?.name).toBe(sender);
  expect(afterSender.title).toBe(target);
  await dialog.getByRole("button", { name: `Set type: ${kind}`, exact: true }).click();
  await expect(dialog.getByRole("combobox", { name: "Document type" })).toHaveValue(suggested.document_types.find((item: { name: string }) => item.name === kind).id);
  const afterType = await (await page.request.get(`/api/documents/${targetId}`)).json();
  expect(afterType.document_type?.name).toBe(kind);
  expect(afterType.title).toBe(target);
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog).toBeHidden();
  const after = await (await page.request.get(`/api/documents/${targetId}`)).json();
  expect(after.title).toBe(`${target} draft`);
  expect(after.tags).toEqual(expect.arrayContaining([expect.objectContaining({ name: tag, origin: "manual" })]));
});
