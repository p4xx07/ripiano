import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = readFileSync(path.resolve(process.cwd(), "e2e/fixtures/judge.png"));

// Judge 3 (M3): an upload made without a connection is kept on the device and sent when the connection returns.
test("an upload made offline waits on the device and is sent when the connection returns", async ({ page, context }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const name = `offline ${Date.now()}-${testInfo.project.name}`;
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  await context.setOffline(true);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.png`, mimeType: "image/png", buffer: fixture });
  await expect(page.getByText("1 file is waiting to upload")).toBeVisible();
  await expect(page.locator(".upload-report")).toHaveCount(0); // not reported as rejected

  const uploaded = page.waitForResponse((item) => item.url().endsWith("/api/documents") && item.request().method() === "POST" && item.status() === 202);
  await context.setOffline(false);
  await page.evaluate(() => window.dispatchEvent(new Event("online")));
  await uploaded;
  await expect(page.getByText("1 file is waiting to upload")).toHaveCount(0);
  await page.reload();
  await expect(page.getByText("waiting to upload")).toHaveCount(0); // nothing left behind on the device
});
