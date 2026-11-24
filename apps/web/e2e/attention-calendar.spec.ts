import { expect, test, type Page } from "@playwright/test";
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

test("a proposed payment date becomes an editable task and calendar entries stay local", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set isolated stack credentials");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const name = `attention-${Date.now()}-${testInfo.project.name}`;
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const uploaded = page.waitForResponse((response) => response.url().endsWith("/api/documents") && response.request().method() === "POST" && response.status() === 202);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.png`, mimeType: "image/png", buffer: fixture });
  const id = (await (await uploaded).json()).id as string;
  const due = "2027-01-15";
  const event = "2027-03-14";
  let suggestion: { kind: "payment" | "event"; date: string } = { kind: "payment", date: due };
  await page.route("**/api/documents/*/attention-suggestion", (route) => route.fulfill({ json: { suggestion } }));
  // This test isolates the UI. Backend OCR and date detection are exercised by test_attention_suggestions.py.
  await page.route(`**/api/documents/${id}`, async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({ response, json: { ...body, status: "ready" } });
  });
  await page.goto(`/?document=${id}`);
  const dialog = page.getByRole("dialog").filter({ hasText: "Keep it in place." });
  await expect(dialog.getByText("Possible payment deadline")).toBeVisible();
  await dialog.screenshot({ path: testInfo.outputPath("payment-suggestion.png"), animations: "disabled" });
  await dialog.getByRole("button", { name: "Use as task" }).click();
  await expect(dialog.getByLabel("Due date")).toHaveValue(due);
  await expect(dialog.getByLabel("What needs doing?")).toHaveValue("Pay this document");
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog).toBeHidden();
  const saved = await (await page.request.get(`/api/documents/${id}`)).json();
  expect(saved.action_status).toBe("open");
  expect(saved.action_due_date).toBe(due);

  await navigate(page, "Needs action");
  const row = page.locator(".action-row").filter({ hasText: name });
  await expect(row).toBeVisible();
  const download = page.waitForEvent("download");
  await row.getByRole("button", { name: "Add to calendar" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe(`ripiano-${due}.ics`);
  expect(readFileSync((await file.path())!, "utf-8")).toContain("DTSTART;VALUE=DATE:20270115");

  suggestion = { kind: "event", date: event };
  await page.goto(`/?document=${id}`);
  const eventDialog = page.getByRole("dialog").filter({ hasText: "Keep it in place." });
  await expect(eventDialog.getByText("Possible event date")).toBeVisible();
  await eventDialog.screenshot({ path: testInfo.outputPath("event-suggestion.png"), animations: "disabled" });
  const eventDownload = page.waitForEvent("download");
  await eventDialog.getByRole("button", { name: "Add to calendar" }).first().click();
  const eventFile = await eventDownload;
  expect(readFileSync((await eventFile.path())!, "utf-8")).toContain("DTSTART;VALUE=DATE:20270314");
});
