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

test("a missing paper copy keeps its sticker and last known location", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const name = `missing-${Date.now()}-${testInfo.project.name}`;
  const location = `Shelf ${Date.now()} ${testInfo.project.name}`;
  await navigate(page, "Paper archive");
  await page.getByPlaceholder("e.g. Filing cabinet").fill(location);
  await page.getByRole("button", { name: "Add location" }).click();
  await expect(page.getByText(location, { exact: true }).first()).toBeVisible();
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
  let detail = page.getByRole("dialog", { name: "Keep it in place." });
  await detail.locator(".new-copy select").selectOption({ label: location });
  await detail.getByRole("button", { name: "Create sticker" }).click();
  const card = detail.locator(".copy-card").first();
  const code = (await card.locator("strong").textContent())!.trim();
  await card.getByRole("button", { name: "Mark missing" }).click();
  await expect(detail.getByRole("status")).toContainText("marked missing");
  await expect(card).toContainText("Reported missing");
  await expect(card).toContainText(`Last known: ${location}`);
  await expect(card.getByRole("button", { name: "Move" })).toBeDisabled();
  await card.getByRole("button", { name: "History" }).click();
  await expect(card.locator(".copy-history")).toContainText("Marked missing");
  await card.screenshot({ path: testInfo.outputPath("missing-paper-copy.png") });

  await page.goto(`/?sticker=${code}`);
  await expect(page.getByText("This paper copy was reported missing.")).toBeVisible();
  await expect(page.getByText(`Last known: ${location}`)).toBeVisible();
  await page.locator(".sticker-result").screenshot({ path: testInfo.outputPath("missing-sticker-lookup.png") });
  const locationRow = page.locator(".location-list > div").filter({ hasText: location });
  await locationRow.getByRole("button", { name: "View contents" }).click();
  const contents = page.locator(".location-result");
  await expect(contents).toContainText("0 paper copies listed as present");
  await expect(contents).toContainText("1 copy was last recorded here or inside nested locations, then reported missing.");
  await expect(contents.locator(":scope > .location-contents li")).toHaveCount(0);
  const missingItem = contents.locator(".location-missing-contents li");
  await expect(missingItem).toHaveCount(1);
  await expect(missingItem).toContainText(code);
  await expect(missingItem).toContainText(`Last known: ${location}`);
  await contents.screenshot({ path: testInfo.outputPath("missing-location-contents.png") });
  await missingItem.getByRole("button", { name }).click();
  detail = page.getByRole("dialog", { name: "Keep it in place." });
  await detail.locator(".copy-card").first().getByRole("button", { name: "Mark found" }).click();
  await expect(detail.getByRole("status")).toContainText("marked found");
  await expect(detail.locator(".copy-card").first()).not.toContainText("Reported missing");
  await expect(detail.locator(".copy-card").first()).toContainText(location);
  await detail.getByRole("button", { name: "Close" }).click();
  await navigate(page, "Paper archive");
  await page.locator(".location-list > div").filter({ hasText: location }).getByRole("button", { name: "View contents" }).click();
  await expect(page.locator(".location-result")).toContainText("1 paper copy listed as present");
  await expect(page.locator(".location-result .copy-missing-label")).toHaveCount(0);
  await expect(page.locator(".location-result .location-missing-contents li")).toHaveCount(0);
});
