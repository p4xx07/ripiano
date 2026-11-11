import { expect, test } from "@playwright/test";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

test("appearance follows the device and keeps the selected AMOLED palette", async ({ page, isMobile }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/");
  const root = page.locator("html");
  await expect(root).toHaveAttribute("data-theme", "dark");
  await page.getByRole("combobox", { name: "Appearance" }).waitFor();
  await page.emulateMedia({ colorScheme: "light" });
  await expect(root).toHaveAttribute("data-theme", "light");

  await page.getByRole("combobox", { name: "Appearance" }).selectOption("amoled");
  await expect(root).toHaveAttribute("data-theme", "amoled");
  await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute("content", "#000000");
  await expect(page.locator('link[rel="manifest"]')).toHaveAttribute("href", "/manifest-amoled.webmanifest");
  const background = await root.evaluate((element) =>
    getComputedStyle(element).getPropertyValue("--color-canvas").trim());
  expect(background).toBe("#000000");
  const manifest = await page.evaluate(async () => (await fetch("/manifest-amoled.webmanifest")).json());
  expect(manifest.background_color).toBe("#000000");
  expect(manifest.id).toBe("/");

  await page.reload();
  await expect(root).toHaveAttribute("data-theme", "amoled");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  if (isMobile) await page.getByRole("button", { name: "Toggle menu" }).click();
  await expect(page.getByRole("combobox", { name: "Appearance" })).toHaveValue("amoled");
  if (isMobile) {
    await page.getByRole("button", { name: "Dismiss navigation" }).click();
    await expect(page.locator(".sidebar")).not.toHaveClass(/sidebar-open/);
  }
});
