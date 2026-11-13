import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = readFileSync(path.resolve(process.cwd(), "e2e/fixtures/judge.png"));

test("a document lists similar documents found locally", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.setTimeout(150000);
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  const topic = `${Date.now().toString(36)}${testInfo.project.name}`;
  const names = [`Condominio girasole${topic} rendiconto${topic} spese${topic} quarto`, `Condominio girasole${topic} rendiconto${topic} spese${topic} quinto`];
  const ids: string[] = [];
  for (const name of names) {
    const add = page.getByRole("button", { name: "Add document", exact: true });
    if (await add.isVisible()) await add.click();
    else await page.getByRole("button", { name: "Add", exact: true }).click();
    const response = page.waitForResponse((item) => item.url().endsWith("/api/documents") && item.request().method() === "POST" && item.status() === 202);
    const chooser = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: /Browse files/ }).click();
    await (await chooser).setFiles({ name: `${name}.png`, mimeType: "image/png", buffer: Buffer.concat([fixture, Buffer.from(name)]) });
    const id = (await (await response).json()).id;
    await expect.poll(async () => (await (await page.request.get(`/api/documents/${id}`)).json()).status, { timeout: 90000 }).toBe("ready");
    ids.push(id);
  }
  await page.getByRole("textbox", { name: "Search documents" }).fill(`girasole${topic}`);
  await page.getByRole("button", { name: names[0], exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Keep it in place." });
  await dialog.getByRole("button", { name: "Find similar documents" }).click();
  const list = dialog.locator(".similar-list");
  await expect(list).toContainText(names[1]);
  await expect(list).toContainText(`girasole${topic}`);
  await dialog.locator(".similar-panel").screenshot({ path: testInfo.outputPath("similar.png"), animations: "disabled" });
  await list.getByRole("button", { name: names[1] }).click();
  await expect(page.getByRole("dialog", { name: "Keep it in place." })).toBeVisible();
});
