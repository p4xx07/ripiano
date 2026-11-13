import { expect, test } from "@playwright/test";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

test("the interface switches to Italian and back, and remembers the choice", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  await page.goto("/");
  await page.getByLabel("Language").selectOption("it");
  await expect(page.getByRole("heading", { name: "Bentornato." })).toBeVisible();
  await page.getByLabel("Nome utente").fill(username!);
  await page.getByLabel("Password").fill("wrong-password");
  await page.getByRole("button", { name: "Accedi" }).click();
  await expect(page.getByRole("alert")).toContainText("Credenziali non valide");
  await page.getByLabel("Lingua").selectOption("en");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const menu = page.getByRole("button", { name: /Toggle menu|Apri o chiudi il menu/ });
  if (await menu.isVisible()) await menu.click();
  await page.getByLabel("Language").selectOption("it");
  await expect(page.locator("html")).toHaveAttribute("lang", "it");
  await expect(page.getByRole("button", { name: "Tutti i documenti" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Cestino" })).toBeVisible();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "it");
  if (await menu.isVisible()) await menu.click();
  await expect(page.getByRole("button", { name: "Cestino" })).toBeVisible();
  await page.getByRole("button", { name: "Da fare", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Da fare/ })).toBeVisible();
  await expect(page.locator(".sidebar")).not.toHaveClass(/sidebar-open/);
  await expect(page.getByRole("heading", { name: "Tutto fatto." })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("italian.png"), animations: "disabled" });

  if (await menu.isVisible()) await menu.click();
  await page.getByLabel("Lingua").selectOption("system");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("heading", { name: /Needs action/ })).toBeVisible();
});
