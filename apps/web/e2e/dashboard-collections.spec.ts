import { expect, test } from "@playwright/test";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

test("personal dashboard keeps live collections and opens them in Library", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set isolated stack credentials");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  await page.getByRole("button", { name: "Open your dashboard" }).click();
  await expect(page.getByRole("heading", { name: "Your dashboard" })).toBeVisible();
  const name = `QA bills ${Date.now()}`;
  await page.getByLabel("Collection name").fill(name);
  await page.getByLabel("Search words (optional)").fill("TARI OR bollo");
  await page.getByRole("button", { name: "Add collection" }).click();
  const card = page.locator(".dashboard-collection").filter({ has: page.getByRole("button", { name, exact: true }) });
  await expect(card).toBeVisible();
  await expect(card.getByText(/document/)).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("dashboard-collections.png"), fullPage: true, animations: "disabled" });
  await card.getByRole("button", { name: `Remove ${name} from dashboard` }).click();
  await expect(card).toHaveCount(0);
  await page.getByLabel("Or add a saved search").selectOption({ label: name });
  await page.getByRole("button", { name: "Add to dashboard" }).click();
  await expect(card).toBeVisible();
  await page.getByLabel("Open this dashboard first on this device").check();
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Your dashboard" })).toBeVisible();
  await card.getByRole("button", { name: "Open all in Library" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  await expect(page.getByRole("textbox", { name: /Search documents/ })).toHaveValue("TARI OR bollo");
  if (testInfo.project.name === "mobile") await page.getByRole("button", { name: "Filters" }).click();
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: `Delete saved search ${name}` }).click();
  await expect(page.getByRole("button", { name, exact: true })).toHaveCount(0);
});

test("People form fields have separated labels and styled inputs", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set isolated stack credentials");
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();
  await page.goto("/people");
  const label = page.locator(".people-form .detail-label").first();
  const input = label.locator("input");
  await expect(label).toBeVisible();
  await expect(input).toBeVisible();
  const metrics = await label.evaluate((node) => {
    const field = node.querySelector("input");
    return { display: getComputedStyle(node).display, borderRadius: field ? getComputedStyle(field).borderRadius : "" };
  });
  expect(metrics.display).toBe("grid");
  expect(metrics.borderRadius).not.toBe("0px");
  await page.screenshot({ path: testInfo.outputPath("people-fixed.png"), fullPage: true, animations: "disabled" });
});
