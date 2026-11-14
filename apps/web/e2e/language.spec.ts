import { expect, test } from "@playwright/test";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

test("English is the default on an Italian device; device language remains opt-in", async ({ browser }) => {
  const context = await browser.newContext({ locale: "it-IT" });
  try {
    const page = await context.newPage();
    await page.goto(process.env.RIPIANO_E2E_ORIGIN ?? "http://localhost:8080");
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    await expect(page.getByLabel("Language")).toHaveValue("en");
    await page.getByLabel("Language").selectOption("system");
    await expect(page.locator("html")).toHaveAttribute("lang", "it");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("lang", "it");
  } finally {
    await context.close();
  }
});

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
  const closeNavigation = page.getByRole("button", { name: "Chiudi la navigazione" });
  if (await menu.isVisible()) await menu.click();
  await page.getByLabel("Language").selectOption("it");
  await expect(page.locator("html")).toHaveAttribute("lang", "it");
  await expect(page.getByRole("button", { name: "Tutti i documenti" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Cestino" })).toBeVisible();
  if (await closeNavigation.isVisible()) await closeNavigation.click();
  await expect(page.getByRole("heading", { name: "Tutto al suo posto." })).toBeVisible();
  await expect(page.getByRole("heading", { name: "I tuoi documenti" })).toBeVisible();
  await page.getByRole("button", { name: "Filtri" }).click();
  await page.getByLabel("Copia cartacea").selectOption("virtual");
  await expect(page.getByRole("button", { name: "Cancella filtri" })).toBeVisible();
  await page.getByRole("button", { name: "Cancella filtri" }).click();
  await page.screenshot({ path: testInfo.outputPath("library-filters-italian.png"), fullPage: true, animations: "disabled" });
  await page.getByRole("button", { name: "Filtri" }).click();
  const add = page.getByRole("button", { name: "Aggiungi documento", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Aggiungi", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Aggiungi un documento." })).toBeVisible();
  await expect(page.getByRole("button", { name: /Scegli dalle foto/ })).toBeVisible();
  await page.getByRole("dialog", { name: "Aggiungi un documento." }).getByRole("button", { name: "Chiudi", exact: true }).click();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: testInfo.outputPath("library-italian.png"), fullPage: true, animations: "disabled" });
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
