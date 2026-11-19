import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = readFileSync(path.resolve(process.cwd(), "e2e/fixtures/judge.png"));

test("a workflow sets a title from a pattern and a custom field on new documents", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.setTimeout(180000);
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const suffix = `${Date.now().toString(36)}${testInfo.project.name}`;
  const fieldName = `Checked ${suffix}`;
  const csrf = (await page.context().cookies()).find((cookie) => cookie.name === "csrftoken")?.value ?? "";
  const created = await page.request.post("/api/custom-fields", { headers: { "X-CSRFToken": csrf }, data: { name: fieldName, kind: "text" } });
  expect(created.status()).toBe(201);

  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "Workflows", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Workflows." })).toBeVisible();
  await page.getByRole("button", { name: "Give new documents a title from a pattern" }).click();
  const form = page.getByRole("form", { name: "Workflow" });
  const flowName = `Title ${suffix}`;
  await form.getByLabel("Name", { exact: true }).fill(flowName);
  // Only this test's upload: the e2e account is shared with other specs.
  await form.getByLabel("File name matches").fill(`invoice-${suffix}*`);
  await form.getByLabel(/^Set title/).fill("Invoice {added_date} from {original_filename}");
  await form.getByText("Set custom fields").click();
  await form.getByRole("group", { name: "Set custom fields" }).getByRole("checkbox", { name: fieldName }).check();
  await form.getByLabel(`Value for ${fieldName}`).fill("by workflow");
  await form.getByRole("button", { name: "Create workflow" }).click();
  await expect(page.getByRole("status")).toContainText(`Workflow “${flowName}” saved`);
  const card = page.locator(".mail-card").filter({ hasText: flowName });
  await expect(card).toContainText(`set ${fieldName} to by workflow`);
  await expect(card).toContainText("set title “Invoice {added_date} from {original_filename}”");
  await page.locator(".agent-layout").screenshot({ path: testInfo.outputPath("workflow-assignments.png"), animations: "disabled" });

  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "All documents" }).click();
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const response = page.waitForResponse((item) => item.url().endsWith("/api/documents") && item.request().method() === "POST" && item.status() === 202);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `invoice-${suffix}.png`, mimeType: "image/png", buffer: fixture });
  const id = (await (await response).json()).id;
  await expect.poll(async () => (await (await page.request.get(`/api/documents/${id}`)).json()).title, { timeout: 90000 })
    .toMatch(new RegExp(`^Invoice \\d{4}-\\d{2}-\\d{2} from invoice-${suffix}$`));
  const fields = (await (await page.request.get(`/api/documents/${id}/custom-fields`)).json()).fields;
  expect(fields.find((item: { name: string }) => item.name === fieldName).value).toBe("by workflow");
  const title = (await (await page.request.get(`/api/documents/${id}`)).json()).title as string;

  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "Workflows", exact: true }).click();
  const run = page.locator(".agent-events > div").filter({ hasText: `${flowName} ·` });
  await expect(run).toContainText(`set field ${fieldName} to by workflow`);
  await expect(run).toContainText(`set title ${title}`);
  await run.getByRole("button", { name: title }).click();
  const dialog = page.getByRole("dialog").filter({ hasText: "Keep it in place." });
  await expect(dialog.locator(".document-history")).toContainText(`Workflow`);
  await expect(dialog.locator(".document-history")).toContainText(fieldName);
});
