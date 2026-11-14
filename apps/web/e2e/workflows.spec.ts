import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = readFileSync(path.resolve(process.cwd(), "e2e/fixtures/judge.png"));

test("a workflow tags matching new documents and records what it did", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.setTimeout(180000);
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const suffix = `${Date.now()}-${testInfo.project.name}`;
  const word = `pelican${Date.now().toString(36)}${testInfo.project.name}`;
  const tag = `Workflow tag ${suffix}`;
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "Tags & filing" }).click();
  await page.getByPlaceholder("e.g. Bills").fill(tag);
  await page.getByRole("button", { name: "Create tag" }).click();
  await expect(page.getByRole("heading", { name: tag })).toBeVisible();

  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "Workflows", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Workflows." })).toBeVisible();
  await page.getByRole("button", { name: "Tag new documents that mention a word" }).click();
  const form = page.getByRole("form", { name: "Workflow" });
  await form.getByLabel("Name", { exact: true }).fill(`Tag ${suffix}`);
  await form.getByLabel("Mention this word or phrase").fill(word);
  await form.getByRole("group", { name: "Add tags" }).getByRole("checkbox", { name: tag }).check();
  await form.getByRole("button", { name: "Create workflow" }).click();
  await expect(page.getByRole("status")).toContainText(`Workflow “Tag ${suffix}” saved`);
  const card = page.locator(".mail-card").filter({ hasText: `Tag ${suffix}` });
  await expect(card).toContainText(`When a document is added, if it mentions “${word}”: add ${tag}.`);
  await page.locator(".agent-layout").screenshot({ path: testInfo.outputPath("workflows.png"), animations: "disabled" });

  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "All documents" }).click();
  async function upload(name: string) {
    const add = page.getByRole("button", { name: "Add document", exact: true });
    if (await add.isVisible()) await add.click();
    else await page.getByRole("button", { name: "Add", exact: true }).click();
    const response = page.waitForResponse((item) => item.url().endsWith("/api/documents") && item.request().method() === "POST" && item.status() === 202);
    const chooser = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: /Browse files/ }).click();
    await (await chooser).setFiles({ name: `${name}.png`, mimeType: "image/png", buffer: fixture });
    const id = (await (await response).json()).id;
    await expect.poll(async () => (await (await page.request.get(`/api/documents/${id}`)).json()).status, { timeout: 90000 }).toBe("ready");
    return id;
  }
  const matching = await upload(`receipt ${word} ${suffix}`);
  const other = await upload(`unrelated ${suffix}`);
  await expect.poll(async () => (await (await page.request.get(`/api/documents/${matching}`)).json()).tags
    .map((item: { name: string; origin: string }) => `${item.name}:${item.origin}`), { timeout: 30000 }).toContain(`${tag}:source`);
  expect((await (await page.request.get(`/api/documents/${other}`)).json()).tags.map((item: { name: string }) => item.name)).not.toContain(tag);

  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "Workflows", exact: true }).click();
  const run = page.locator(".agent-events > div").filter({ hasText: `receipt ${word}` });
  await expect(run).toContainText(`added tag ${tag}`);
  await run.getByRole("button", { name: `receipt ${word} ${suffix}` }).click();
  await expect(page.getByRole("dialog", { name: "Keep it in place." })).toBeVisible();
});
