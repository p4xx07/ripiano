import { expect, test } from "@playwright/test";

const username = process.env.RIPIANO_E2E_JOB_USERNAME;
const password = process.env.RIPIANO_E2E_JOB_PASSWORD;

type Job = {
  id: string;
  status: "pending" | "failed" | "cancelled";
  can_cancel: boolean;
  can_retry: boolean;
  retry_of: string | null;
  error: string;
  created_at: string;
};

test("backup and NAS copy controls show a queued cancellation and a separate retry", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set a disposable instance-admin account for Backups UI checks");
  const now = new Date().toISOString();
  const backups: (Job & { trigger: string; snapshot_name: string })[] = [{
    id: "11111111-1111-4111-8111-111111111111", status: "pending", can_cancel: true, can_retry: false,
    retry_of: null, error: "", created_at: now, trigger: "manual", snapshot_name: "",
  }];
  const browse: (Job & { document_count: number; folder: string | null })[] = [{
    id: "22222222-2222-4222-8222-222222222222", status: "failed", can_cancel: false, can_retry: true,
    retry_of: null, error: "The mounted folder is unavailable. Check the NAS mount and folder permissions before trying again.", created_at: now, document_count: 0, folder: null,
  }];
  await page.route(/\/api\/(backups|browse-exports)(\/.*)?$/, async (route) => {
    const { pathname } = new URL(route.request().url());
    if (route.request().method() === "GET") {
      await route.fulfill({ json: pathname.endsWith("backups") ? { schedule: "02:00 Europe/Rome", runs: backups } : { runs: browse } });
      return;
    }
    const parts = pathname.split("/");
    const rows = parts[2] === "backups" ? backups : browse;
    const run = rows.find((item) => item.id === parts[3]);
    if (!run) throw new Error(`Unexpected job action: ${pathname}`);
    if (parts[4] === "cancel") {
      run.status = "cancelled";
      run.can_cancel = false;
      run.can_retry = true;
      await route.fulfill({ json: { id: run.id, status: run.status } });
      return;
    }
    if (parts[4] === "retry") {
      run.can_retry = false;
      const retry = { ...run, id: parts[2] === "backups" ? "33333333-3333-4333-8333-333333333333" : "44444444-4444-4444-8444-444444444444", status: "pending" as const, can_cancel: true, retry_of: run.id, error: "" };
      if (parts[2] === "backups") backups.unshift({ ...retry, trigger: "retry", snapshot_name: "" });
      else browse.unshift({ ...retry, document_count: 0, folder: null });
      await route.fulfill({ status: 202, json: { id: retry.id, status: retry.status, retry_of: run.id } });
      return;
    }
    throw new Error(`Unexpected job action: ${pathname}`);
  });

  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "Backups" }).click();
  const backupRow = page.locator(".backup-list .document-row").filter({ hasText: "Manual backup" });
  const browseRow = page.locator(".browse-section .document-row").filter({ hasText: "The mounted folder is unavailable" });
  await expect(backupRow.getByRole("button", { name: /Cancel queued backup/ })).toBeVisible();
  await backupRow.getByRole("button", { name: /Cancel queued backup/ }).click();
  await expect(backupRow.locator(".status")).toHaveText("cancelled");
  await expect(backupRow.getByRole("button", { name: /Retry backup/ })).toBeFocused();
  await expect(browseRow.getByRole("button", { name: /Retry NAS copy/ })).toBeVisible();
  await expect(browseRow.locator(".doc-error")).toHaveCSS("white-space", "normal");
  await page.locator(".browse-section").screenshot({ path: testInfo.outputPath("browse-job-controls.png"), animations: "disabled" });
  await backupRow.getByRole("button", { name: /Retry backup/ }).click();
  const backupRetry = page.locator(".backup-list .document-row").filter({ hasText: "Backup retry" }).locator(".status");
  await expect(backupRetry).toHaveText("pending");
  await expect(backupRetry).toBeFocused();
  await expect(backupRow.getByRole("button", { name: /Retry backup/ })).toHaveCount(0);
  await browseRow.getByRole("button", { name: /Retry NAS copy/ }).click();
  await expect(page.locator(".browse-section .document-row")).toHaveCount(2);
  await expect(browseRow.getByRole("button", { name: /Retry NAS copy/ })).toHaveCount(0);
});
