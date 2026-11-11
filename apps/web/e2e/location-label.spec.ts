import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = path.resolve(process.cwd(), "e2e/fixtures/judge.png");

async function navigate(page: Page, name: string) {
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name, exact: true }).click();
}

test("a shelf label finds paper copies inside a nested box", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const parent = `Shelf ${Date.now()} ${testInfo.project.name}`;
  const box = `Box ${Date.now()} ${testInfo.project.name}`;
  const name = `box-label-${Date.now()}-${testInfo.project.name}`;
  await navigate(page, "Paper archive");
  await page.getByPlaceholder("e.g. Filing cabinet").fill(parent);
  await page.getByRole("button", { name: "Add location" }).click();
  await expect(page.locator(".location-path").filter({ hasText: parent })).toBeVisible();
  await page.getByPlaceholder("e.g. Filing cabinet").fill(box);
  await page.getByLabel("Inside").selectOption({ label: parent });
  await page.getByRole("button", { name: "Add location" }).click();
  await expect(page.getByText(`${parent} / ${box}`, { exact: true }).first()).toBeVisible();
  const locations = (await (await page.request.get("/api/locations")).json()).locations as { id: string; name: string; sticker_code: string }[];
  const shelf = locations.find((location) => location.name === parent)!;
  const parentRow = page.locator(".location-list > div").filter({ has: page.getByText(parent, { exact: true }) });
  const popupPromise = page.waitForEvent("popup");
  await parentRow.getByRole("link", { name: "Print label" }).click();
  const label = await popupPromise;
  await expect(label.getByText(shelf.sticker_code, { exact: true })).toBeVisible();
  await label.close();

  await navigate(page, "All documents");
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const upload = page.waitForResponse((response) => response.url().endsWith("/api/documents") && response.request().method() === "POST" && response.status() === 202);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.png`, mimeType: "image/png", buffer: readFileSync(fixture) });
  await upload;
  await page.getByRole("textbox", { name: "Search documents" }).fill(`title:${name}`);
  await page.getByRole("button", { name, exact: true }).click();
  const detail = page.getByRole("dialog", { name: "Keep it in place." });
  await detail.locator(".new-copy select").selectOption({ label: `${parent} / ${box}` });
  await detail.getByRole("button", { name: "Create sticker" }).click();
  await expect(detail.locator(".copy-card")).toContainText(`${parent} / ${box}`);

  await page.goto(`/?location=${shelf.sticker_code}`);
  const result = page.locator(".location-result");
  await expect(result).toContainText(`${parent} / ${box}`);
  await expect(result).toContainText("1 paper copy recorded here or inside nested locations");
  await expect(result.getByRole("button", { name: name })).toBeVisible();
  await result.screenshot({ path: testInfo.outputPath("shelf-contents.png") });
  await result.getByRole("button", { name: name }).click();
  await expect(page.getByRole("dialog", { name: "Keep it in place." })).toBeVisible();
});
