import { expect, test, type Page } from "@playwright/test";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

async function navigate(page: Page, name: string) {
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name, exact: true }).click();
}

test("locations reset Inside after adding, then rename, move, and delete", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const stamp = `${Date.now()} ${testInfo.project.name}`;
  const shelf = `Shelf ${stamp}`;
  const box = `Box ${stamp}`;
  const cabinet = `Cabinet ${stamp}`;
  const renamed = `Blue box ${stamp}`;
  const row = (path: string) => page.locator(".location-list > div").filter({ has: page.getByText(path, { exact: true }) });

  await navigate(page, "Paper archive");
  const nameInput = page.getByPlaceholder("e.g. Filing cabinet");
  const inside = page.locator(".tag-create-card").getByLabel("Inside");

  await nameInput.fill(shelf);
  await page.getByRole("button", { name: "Add location at top level" }).click();
  await expect(page.getByRole("status").filter({ hasText: `Added “${shelf}” at the top level.` })).toBeVisible();

  await nameInput.fill(box);
  await inside.selectOption({ label: shelf });
  await page.getByRole("button", { name: `Add location inside ${shelf}` }).click();
  await expect(page.getByRole("status").filter({ hasText: `Added “${box}” inside ${shelf}.` })).toBeVisible();
  await expect(row(`${shelf} / ${box}`)).toBeVisible();

  // The parent resets after creating, so the next location is top level unless chosen again.
  await expect(inside).toHaveValue("");
  await nameInput.fill(cabinet);
  await page.getByRole("button", { name: "Add location at top level" }).click();
  await expect(row(cabinet)).toBeVisible();
  await expect(page.getByText(`${shelf} / ${cabinet}`, { exact: true })).toHaveCount(0);

  // Rename with the keyboard.
  await row(`${shelf} / ${box}`).getByRole("button", { name: `Edit ${shelf} / ${box}` }).click();
  const editor = page.getByRole("form", { name: `Edit ${shelf} / ${box}` });
  await expect(editor.getByLabel("Name", { exact: true })).toBeFocused();
  await editor.getByLabel("Name", { exact: true }).fill(renamed);
  await editor.getByLabel("Name", { exact: true }).press("Enter");
  await expect(page.getByRole("status").filter({ hasText: `The location is now ${shelf} / ${renamed}.` })).toBeVisible();
  await expect(row(`${shelf} / ${renamed}`)).toBeVisible();

  // A location cannot be moved inside itself, so it is not offered as a parent.
  await row(shelf).getByRole("button", { name: `Edit ${shelf}` }).click();
  const shelfEditor = page.getByRole("form", { name: `Edit ${shelf}` });
  await expect(shelfEditor.getByLabel("Inside").locator("option", { hasText: renamed })).toHaveCount(0);
  await shelfEditor.getByRole("button", { name: "Cancel" }).click();

  // Move the box into the cabinet.
  await row(`${shelf} / ${renamed}`).getByRole("button", { name: /^Edit / }).click();
  const moveEditor = page.getByRole("form", { name: `Edit ${shelf} / ${renamed}` });
  await moveEditor.getByLabel("Inside").selectOption({ label: cabinet });
  await moveEditor.getByRole("button", { name: "Save" }).click();
  await expect(row(`${cabinet} / ${renamed}`)).toBeVisible();

  // Deleting a location that still contains another one is refused with a clear message.
  await row(cabinet).getByRole("button", { name: `Edit ${cabinet}` }).click();
  await page.getByRole("form", { name: `Edit ${cabinet}` }).getByRole("button", { name: "Delete location" }).click();
  await expect(page.getByRole("alert")).toContainText("still contains other locations");
  await page.getByRole("form", { name: `Edit ${cabinet}` }).getByRole("button", { name: "Cancel" }).click();

  // Delete the empty box after confirming, then the now-empty cabinet and shelf.
  for (const path of [`${cabinet} / ${renamed}`, cabinet, shelf]) {
    page.once("dialog", (dialog) => {
      expect(dialog.message()).toContain(path);
      void dialog.accept();
    });
    await row(path).getByRole("button", { name: `Edit ${path}` }).click();
    await page.getByRole("form", { name: `Edit ${path}` }).getByRole("button", { name: "Delete location" }).click();
    await expect(page.getByRole("status").filter({ hasText: `Deleted “${path}”.` })).toBeVisible();
    await expect(row(path)).toHaveCount(0);
  }
});
