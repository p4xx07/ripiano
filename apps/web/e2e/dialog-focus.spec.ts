import { expect, test } from "@playwright/test";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

test("add dialog traps keyboard focus and returns it to Add", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const desktopAdd = page.getByRole("button", { name: "Add document", exact: true });
  const add = await desktopAdd.isVisible()
    ? desktopAdd
    : page.getByRole("button", { name: "Add", exact: true });
  await add.focus();
  await add.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Bring a document in." });
  await expect(page.getByRole("button", { name: "Close" })).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(page.getByRole("button", { name: /Browse files/ })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Close" })).toBeFocused();
  expect(await page.getByRole("button", { name: "Close" }).evaluate((element) => getComputedStyle(element).outlineWidth)).toBe("3px");
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(add).toBeFocused();
});
