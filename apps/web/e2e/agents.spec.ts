import { expect, test } from "@playwright/test";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;

test("create a limited agent and revoke its access", async ({
  page,
}, testInfo) => {
  test.skip(
    !username || !password,
    "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD",
  );
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("heading", { name: /Everything in its place/ }),
  ).toBeVisible();
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "Agents", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Agents." })).toBeVisible();

  const name = `Judge agent ${Date.now()} ${testInfo.project.name}`;
  await page.getByPlaceholder("e.g. Local Mac classifier").fill(name);
  await expect(page.getByLabel("Find document titles and tags")).toBeChecked();
  await expect(page.getByLabel("Read OCR text")).not.toBeChecked();
  await expect(page.getByLabel("Add or remove tags")).not.toBeChecked();
  await expect(page.getByLabel("Set sender and document type")).not.toBeChecked();
  await page.getByLabel("Set sender and document type").check();
  await page.getByRole("button", { name: "Create agent token" }).click();
  await expect(page.getByText("Copy this token now")).toBeVisible();
  const token = await page.getByLabel("New agent token").inputValue();
  expect(token).toMatch(/^rpa_/);
  const card = page.locator(".agent-card").filter({ hasText: name });
  await expect(card).toContainText("Find document titles and tags");
  await expect(card).toContainText("Set sender and document type");
  await expect(card).not.toContainText("Read OCR text");
  await page.screenshot({
    path: testInfo.outputPath("agents.png"),
    fullPage: true,
    mask: [page.getByLabel("New agent token")],
    maskColor: "#dce8d8",
  });
  await card.getByRole("button", { name: "Revoke" }).click();
  await expect(card).toContainText("Revoked");
  await expect(page.getByLabel("New agent token")).toHaveCount(0);
});
