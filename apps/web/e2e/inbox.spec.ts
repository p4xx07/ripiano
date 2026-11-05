import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = path.resolve(process.cwd(), "e2e/fixtures/judge.png");

async function upload(page: Page, name: string) {
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const posted = page.waitForResponse((response) => response.url().endsWith("/api/documents") && response.request().method() === "POST" && response.status() === 202);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.png`, mimeType: "image/png", buffer: readFileSync(fixture) });
  await posted;
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
}

async function navigate(page: Page, name: string) {
  const menu = page.getByRole("button", { name: "Toggle menu" });
  const mobile = await menu.isVisible();
  if (mobile) await menu.click();
  await page.getByRole("button", { name, exact: true }).click();
  if (mobile) await expect.poll(() => page.locator(".sidebar").evaluate((element) => element.getBoundingClientRect().right)).toBeLessThan(1);
}

test("Inbox shows an exact copy and keeping both preserves the document", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const name = `inbox-${Date.now()}-${testInfo.project.name}`;
  await upload(page, `${name}-first`);
  await upload(page, `${name}-copy`);
  await navigate(page, "Inbox");
  const row = page.getByRole("article").filter({ has: page.getByRole("button", { name: `${name}-copy`, exact: true }) });
  await expect(row).toContainText("Exact copy of");
  await page.screenshot({ path: testInfo.outputPath("inbox.png") });
  await row.getByRole("button", { name: "Keep both" }).click();
  await expect(row).toBeHidden();

  await navigate(page, "All documents");
  await page.getByRole("textbox", { name: "Search documents" }).fill(`${name}-copy`);
  await expect(page.getByRole("button", { name: `${name}-copy`, exact: true })).toBeVisible();
});

test("failed OCR can be retried directly from Inbox", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  let failed = true;
  await page.route("**/api/documents?view=exceptions*", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      documents: failed ? [{
        id: "fixture-failed", title: "Unreadable letter", original_name: "letter.pdf",
        duplicate_of: null, duplicate_reviewed_at: null, source: "web", status: "failed",
        archive_available: false, error: "OCR failed", created_at: "2026-11-05T09:00:00Z",
        document_date: null, action_status: "none", action_due_date: null,
        action_note: "", action_completed_at: null, tags: [], physical_copies: [], snippet: "",
      }] : [],
      next_cursor: null,
      counts: { total: failed ? 1 : 0, ready: 0, waiting: 0 },
    }),
  }));
  await page.route("**/api/documents/fixture-failed/retry", (route) => {
    failed = false;
    return route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify({ status: "pending" }) });
  });
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  await navigate(page, "Inbox");
  await expect(page.getByText("OCR could not finish: OCR failed")).toBeVisible();
  await page.getByRole("button", { name: "Try OCR again" }).click();
  await expect(page.getByRole("heading", { name: "Nothing needs your attention." })).toBeVisible();
});
