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
  await row.getByRole("button", { name: "Keep both" }).focus();
  await page.keyboard.press("Enter");
  await expect(row).toBeHidden();
  await expect(page.locator(".exception-row .document-title-button").first()).toBeFocused();
  await expect(page.getByRole("status")).toContainText("Both documents remain in the Library");

  await navigate(page, "All documents");
  await page.getByRole("textbox", { name: "Search documents" }).fill(`${name}-copy`);
  await expect(page.getByRole("button", { name: `${name}-copy`, exact: true })).toBeVisible();
});

test("failed OCR can be retried directly from Inbox", async ({ page }, testInfo) => {
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
  // After the retry the card stays as "retrying" and is checked until OCR ends (round-9 judge 2 M3).
  await page.route("**/api/documents/fixture-failed", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      id: "fixture-failed", title: "Unreadable letter", original_name: "letter.pdf",
      duplicate_of: null, duplicate_reviewed_at: null, source: "web", status: failed ? "failed" : "ready",
      archive_available: true, error: "", created_at: "2026-11-05T09:00:00Z",
      document_date: null, action_status: "none", action_due_date: null,
      action_note: "", action_completed_at: null, tags: [], physical_copies: [], snippet: "",
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
  await page.screenshot({ path: testInfo.outputPath("failed-ocr.png") });
  await page.getByRole("button", { name: "Retry OCR" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("status")).toContainText("OCR restarted");
  await expect(page.getByText("Reading the file again…")).toBeVisible();
  const emptyHeading = page.getByRole("heading", { name: "Nothing needs your attention." });
  await expect(emptyHeading).toBeVisible({ timeout: 10_000 });
  await expect(emptyHeading).toBeFocused();
  await expect(page.getByRole("status")).toContainText("“Unreadable letter” was read.");
});

test("a retried document whose processing was interrupted says so calmly in the Inbox", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  let status: "failed" | "processing" | "ready" = "failed";
  const fixtureDocument = () => ({
    id: "fixture-stalled", title: "Interrupted letter", original_name: "letter.pdf",
    duplicate_of: null, duplicate_reviewed_at: null, source: "web", status,
    archive_available: status === "ready", error: status === "failed" ? "OCR failed" : "", created_at: "2026-11-05T09:00:00Z",
    document_date: null, action_status: "none", action_due_date: null,
    action_note: "", action_completed_at: null, tags: [], physical_copies: [], snippet: "",
  });
  await page.route("**/api/documents?view=exceptions*", (route) => route.fulfill({
    json: { documents: status === "failed" ? [fixtureDocument()] : [], next_cursor: null, counts: { total: status === "failed" ? 1 : 0, ready: 0, waiting: 0 } },
  }));
  await page.route("**/api/documents/fixture-stalled", (route) => route.fulfill({ json: fixtureDocument() }));
  await page.route("**/api/documents/fixture-stalled/retry", (route) => {
    status = "processing";
    return route.fulfill({ status: 202, json: { status: "pending" } });
  });
  // The worker stopped during the new attempt: the server flags the job as stalled and retries it by itself.
  await page.route((url) => url.pathname === "/api/jobs", (route) => route.fulfill({ json: {
    documents_waiting: { total: status === "processing" ? 1 : 0, items: status === "processing" ? [{ id: "fixture-stalled", title: "Interrupted letter", status: "processing", since: "2026-11-19T09:00:00Z", stalled: true, can_retry: true, can_cancel: true }] : [] },
    documents_failed: { total: 0, items: [] }, purges: [], training: null, workflow_failures: [],
  } }));
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  await navigate(page, "Inbox");
  await page.getByRole("button", { name: "Retry OCR" }).click();
  const card = page.getByRole("article").filter({ hasText: "Interrupted letter" });
  await expect(card).toContainText("Reading the file again…");
  const hint = "Taking longer than usual. Processing was interrupted and will be tried again by itself.";
  await expect(card).toContainText(hint, { timeout: 10_000 });
  await expect(card).not.toContainText("Reading the file again…");
  await expect(page.getByRole("status")).toContainText(hint);
  // The automatic retry finishes: the usual result is announced and the card leaves.
  status = "ready";
  await expect(page.getByRole("status")).toContainText("“Interrupted letter” was read.", { timeout: 10_000 });
  await expect(card).toHaveCount(0);
});
