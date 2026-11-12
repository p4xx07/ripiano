import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_BROWSE_USERNAME;
const password = process.env.RIPIANO_E2E_BROWSE_PASSWORD;
const fixture = path.resolve(process.cwd(), "e2e/fixtures/judge.png");

test("build a readable NAS copy from the Backups screen", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set dedicated NAS browse E2E credentials");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const name = `browse-${Date.now()}-${testInfo.project.name}`;
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const upload = page.waitForResponse((response) => response.url().endsWith("/api/documents") && response.request().method() === "POST" && response.status() === 202);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.png`, mimeType: "image/png", buffer: readFileSync(fixture) });
  const id = (await (await upload).json()).id;
  await expect.poll(async () => (await (await page.request.get(`/api/documents/${id}`)).json()).status, { timeout: 60000 }).toBe("ready");

  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "Backups" }).click();
  await expect(page.getByRole("heading", { name: "Browse on your NAS" })).toBeVisible();
  const started = page.waitForResponse((response) => response.url().endsWith("/api/browse-exports") && response.request().method() === "POST" && response.status() === 202);
  await page.getByRole("button", { name: "Build browse copy" }).click();
  const runId = (await (await started).json()).id;
  await expect.poll(async () => {
    const runs = (await (await page.request.get("/api/browse-exports")).json()).runs as { id: string; status: string; folder: string | null; document_count: number }[];
    return runs.find((run) => run.id === runId)?.status;
  }, { timeout: 60000 }).toBe("complete");
  const runs = (await (await page.request.get("/api/browse-exports")).json()).runs as { id: string; folder: string | null; document_count: number }[];
  const run = runs.find((item) => item.id === runId);
  expect(run?.folder).toMatch(/^browse\/owners\/\d+\/complete\//);
  expect(run?.document_count).toBeGreaterThanOrEqual(1);
  await page.reload();
  const menuAfterReload = page.getByRole("button", { name: "Toggle menu" });
  if (await menuAfterReload.isVisible()) await menuAfterReload.click();
  await page.getByRole("button", { name: "Backups" }).click();
  await expect(page.getByText(`${run!.document_count} ${run!.document_count === 1 ? "document" : "documents"} ready on NAS`).first()).toBeVisible();
  await page.locator(".browse-section").screenshot({ path: testInfo.outputPath("nas-browse.png"), animations: "disabled" });
});
