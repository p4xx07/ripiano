import { expect, test } from "@playwright/test";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

test("older documents and follow-ups remain reachable after the first 50", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  const documents = Array.from({ length: 51 }, (_, index) => ({
    id: `fixture-${index}`,
    title: `Paged document ${index + 1}`,
    original_name: `fixture-${index}.pdf`,
    duplicate_of: null,
    source: "web",
    status: "ready",
    archive_available: false,
    error: "",
    created_at: "2026-11-05T09:00:00Z",
    document_date: null,
    action_status: "open",
    action_due_date: null,
    action_note: "Follow up",
    action_completed_at: null,
    tags: [],
    physical_copies: [],
    snippet: "",
  }));
  await page.route("**/api/documents?*", (route) => {
    const offset = Number(new URL(route.request().url()).searchParams.get("offset") ?? 0);
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        documents: documents.slice(offset, offset + 50),
        next_offset: offset + 50 < documents.length ? offset + 50 : null,
        counts: { total: 51, ready: 51, waiting: 0 },
      }),
    });
  });

  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("button", { name: "Show more documents" })).toBeVisible();
  await expect(page.locator(".summary-card").first()).toContainText("51");
  await page.getByRole("button", { name: "Show more documents" }).click();
  await expect(page.locator(".document-list .document-row")).toHaveCount(51);
  await expect(page.getByRole("button", { name: "Paged document 51" })).toBeVisible();

  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "Needs action", exact: true }).click();
  await expect(page.getByRole("button", { name: "Show more follow-ups" })).toBeVisible();
  await page.getByRole("button", { name: "Show more follow-ups" }).click();
  await expect(page.locator(".action-row")).toHaveCount(51);
  await expect(page.getByRole("button", { name: "Paged document 51" })).toBeVisible();
});
