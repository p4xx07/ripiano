import { expect, test } from "@playwright/test";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

test("create and reorganize nested tags", async ({ page, isMobile }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  if (isMobile) await page.getByRole("button", { name: "Toggle menu" }).click();
  await page.getByRole("button", { name: "Tags & filing" }).click();
  const suffix = `${Date.now()}-${testInfo.project.name}`;
  const parentName = `Home ${suffix}`;
  const childName = `Policies ${suffix}`;
  const name = page.getByPlaceholder("e.g. Bills");

  await name.fill(parentName);
  await page.getByRole("button", { name: "Create tag" }).click();
  await expect(page.getByRole("heading", { name: parentName })).toBeVisible();
  await name.fill(childName);
  await page.getByRole("combobox", { name: "Parent tag" }).selectOption({ label: parentName });
  await page.getByRole("button", { name: "Create tag" }).click();
  const parent = page.locator(".tag-card").filter({ has: page.getByRole("heading", { name: parentName }) });
  const child = page.locator(".tag-card").filter({ has: page.getByRole("heading", { name: childName }) });
  await expect(child.locator(".tag-path")).toHaveText(`${parentName} / ${childName}`);
  await child.getByRole("button", { name: `Move ${childName}` }).click();
  expect(await child.evaluate((element) => element.scrollWidth - element.clientWidth)).toBeLessThanOrEqual(1);
  await page.screenshot({ path: testInfo.outputPath("move-tag.png") });
  await child.getByRole("combobox", { name: `Parent for ${childName}` }).selectOption("");
  await expect(child.locator(".tag-path")).toHaveCount(0);
  await child.getByRole("button", { name: `Move ${childName}` }).click();
  await child.getByRole("combobox", { name: `Parent for ${childName}` }).selectOption({ label: parentName });
  await expect(child.locator(".tag-path")).toHaveText(`${parentName} / ${childName}`);
  await page.screenshot({ path: testInfo.outputPath("nested-tags.png") });

  page.once("dialog", (dialog) => void dialog.accept());
  await parent.getByRole("button", { name: `Delete ${parentName}` }).click();
  await expect(page.getByRole("alert")).toContainText("Move or delete child tags first");
  page.once("dialog", (dialog) => void dialog.accept());
  await child.getByRole("button", { name: `Delete ${childName}` }).click();
  await expect(child).toHaveCount(0);
  page.once("dialog", (dialog) => void dialog.accept());
  await parent.getByRole("button", { name: `Delete ${parentName}` }).click();
  await expect(parent).toHaveCount(0);
});
