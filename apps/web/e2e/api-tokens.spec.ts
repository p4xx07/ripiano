import { expect, request as httpRequest, test } from "@playwright/test";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

test("a personal API token works from a script and stops working when revoked", async ({ page, baseURL }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "Security", exact: true }).click();
  const name = `script-${Date.now()}-${testInfo.project.name}`;
  const form = page.getByRole("form", { name: "New API token" });
  await form.getByLabel("Token name").fill(name);
  await form.getByLabel(/Your password/).fill(password!);
  await form.getByRole("button", { name: "Create token" }).click();
  const token = await page.getByRole("textbox", { name: "New API token" }).inputValue();
  expect(token).toMatch(/^rip_/);

  const script = await httpRequest.newContext({ baseURL, extraHTTPHeaders: { Authorization: `Token ${token}` } });
  const listed = await script.get("/api/documents");
  expect(listed.status()).toBe(200);
  expect((await script.get("/api/account/tokens")).status()).toBe(403);
  const schema = await (await script.get("/api/schema.json")).json();
  expect(Object.keys(schema.paths)).toContain("/api/documents/{document_id}");

  await page.getByRole("button", { name: `Revoke token ${name}` }).click();
  await expect(page.getByRole("button", { name: `Revoke token ${name}` })).toHaveCount(0);
  expect((await script.get("/api/documents")).status()).toBe(401);
  await script.dispose();
});
