import { expect, test } from "@playwright/test";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

test("search and Add shortcuts respect typing and dialogs", async ({ page, isMobile }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  if (isMobile) await page.getByRole("button", { name: "Toggle menu" }).click();
  await page.getByRole("button", { name: "Tags & filing" }).click();
  await expect(page.getByRole("heading", { name: /Tags that do the work/ })).toBeVisible();

  await page.keyboard.press("/");
  const search = page.getByRole("textbox", { name: /Search documents by text/ });
  await expect(search).toBeFocused();
  await page.keyboard.type("n");
  await expect(search).toHaveValue("n");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await search.clear();
  await page.keyboard.press("/");
  await expect(search).toHaveValue("/");
  await search.clear();
  await page.getByRole("heading", { name: /Everything in its place/ }).click();
  await page.keyboard.press("n");
  const add = page.getByRole("dialog", { name: "Bring a document in." });
  await expect(add).toBeVisible();
  await page.keyboard.press("/");
  await expect(add).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(add).toHaveCount(0);
});
