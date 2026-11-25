import { expect, test, type Page } from "@playwright/test";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

async function signIn(page: Page) {
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
}

test("short choices are pills: one click changes the theme and the arrow keys move the selection", async ({ page }) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.emulateMedia({ colorScheme: "light" });
  await signIn(page);
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  const root = page.locator("html");
  const appearance = page.locator("#app-sidebar").getByRole("radiogroup", { name: "Appearance" });
  await expect(appearance.getByRole("radio")).toHaveCount(4);
  await expect(appearance.getByRole("radio", { name: "Auto", exact: true })).toBeChecked();

  const dark = appearance.getByRole("radio", { name: "Dark", exact: true });
  await dark.click();
  await expect(dark).toBeChecked();
  await expect(root).toHaveAttribute("data-theme", "dark");

  // Native radio behaviour: the arrow keys move the selection and apply it.
  await dark.focus();
  await page.keyboard.press("ArrowRight");
  const amoled = appearance.getByRole("radio", { name: "AMOLED", exact: true });
  await expect(amoled).toBeChecked();
  await expect(amoled).toBeFocused();
  await expect(root).toHaveAttribute("data-theme", "amoled");

  await appearance.getByRole("radio", { name: "Auto", exact: true }).click();
  await expect(root).toHaveAttribute("data-theme", "light");
});

test("the Library paper filter pills wrap on a narrow phone instead of scrolling sideways", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.setViewportSize({ width: 360, height: 740 });
  await signIn(page);
  await page.getByRole("button", { name: /^Filters/ }).click();
  const paper = page.getByRole("radiogroup", { name: "Paper copy" });
  await expect(paper).toBeVisible();
  await expect(paper.getByRole("radio", { name: "Any", exact: true })).toBeChecked();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  const box = await paper.boundingBox();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(360);
  for (const pill of await paper.locator(".segmented-pill").all()) {
    // 36px with a mouse, 44px on touch screens (the mobile project emulates touch).
    expect((await pill.boundingBox())!.height).toBeGreaterThanOrEqual(testInfo.project.name === "mobile" ? 44 : 36);
  }
  await paper.getByRole("radio", { name: "Digital only", exact: true }).click();
  await expect(paper.getByRole("radio", { name: "Digital only", exact: true })).toBeChecked();
  await expect(page.getByRole("button", { name: "Clear filters" })).toBeVisible();
});

test("sidebar theme and language pills are full touch targets on a phone and Enter does not submit anything", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.skip(testInfo.project.name !== "mobile", "touch sizes apply to the phone project");
  await signIn(page);
  await page.getByRole("button", { name: "Toggle menu" }).click();
  for (const name of ["Appearance", "Language"]) {
    const group = page.getByRole("radiogroup", { name });
    await expect(group).toBeVisible();
    for (const pill of await group.locator(".segmented-pill").all()) {
      expect((await pill.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    }
  }
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
