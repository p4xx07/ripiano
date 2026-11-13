import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixtures = [
  { file: "office-legacy.doc", mime: "application/msword", word: "marmellata" },
  { file: "office-open.odt", mime: "application/vnd.oasis.opendocument.text", word: "girasole" },
  { file: "email-notice.eml", mime: "message/rfc822", word: "lampone", title: "Avviso TARI 2026 lampone" },
  { file: "outlook-notice.msg", mime: "application/vnd.ms-outlook", word: "mirtillo", title: "Avviso condominio mirtillo" },
];

test("older Word, OpenDocument, and email files become searchable with originals intact", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.setTimeout(240000);
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  for (const fixture of fixtures) {
    const original = readFileSync(path.resolve(process.cwd(), "e2e/fixtures", fixture.file));
    const name = `${testInfo.project.name}-${Date.now()}-${fixture.file}`;
    const add = page.getByRole("button", { name: "Add document", exact: true });
    if (await add.isVisible()) await add.click();
    else await page.getByRole("button", { name: "Add", exact: true }).click();
    await expect(page.getByText(/emails \(\.eml, \.msg\), and Word, Excel, PowerPoint, OpenDocument, or RTF/)).toBeVisible();
    const upload = page.waitForResponse((response) => response.url().endsWith("/api/documents") && response.request().method() === "POST" && response.status() === 202);
    const chooser = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: /Browse files/ }).click();
    await (await chooser).setFiles({ name, mimeType: fixture.mime, buffer: original });
    const created = await (await upload).json();
    if (fixture.title) expect(created.title).toBe(fixture.title);
    await expect.poll(async () => (await (await page.request.get(`/api/documents/${created.id}`)).json()).status, { timeout: 120000 }).toBe("ready");

    expect(await (await page.request.get(`/api/documents/${created.id}/original`)).body()).toEqual(original);
    const archive = await page.request.get(`/api/documents/${created.id}/archive`);
    expect((await archive.body()).subarray(0, 5).toString()).toBe("%PDF-");
    const found = await (await page.request.get(`/api/documents?q=${fixture.word}`)).json();
    expect(found.documents.map((item: { id: string }) => item.id)).toContain(created.id);
  }
});
