import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const fixture = path.resolve(process.cwd(), "e2e/fixtures/judge.png");

async function navigate(page: Page, name: string) {
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name, exact: true }).click();
}

test("capture, find, tag, and locate a paper copy", async ({
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

  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const name = `judge-${Date.now()}-${testInfo.project.name}`;
  const upload = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/documents") &&
      response.request().method() === "POST" &&
      response.status() === 202,
  );
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (
    await chooser
  ).setFiles({
    name: `${name}.png`,
    mimeType: "image/png",
    buffer: readFileSync(fixture),
  });
  const documentId = (await (await upload).json()).id;
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible();

  const searchable = page.waitForResponse(
    async (response) =>
      response.url().includes("/api/documents?q=9473") &&
      response.status() === 200 &&
      (await response.json()).documents.some(
        (document: { id: string }) => document.id === documentId,
      ),
    { timeout: 60000 },
  );
  await page.getByRole("textbox", { name: "Search documents" }).fill("9473");
  await searchable;
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
  const matchingRow = page.locator(".document-row").filter({
    has: page.getByRole("button", { name, exact: true }),
  });
  const excerpt = matchingRow.locator(".document-snippet");
  await expect(excerpt).toContainText("Document text:");
  await expect(excerpt).toContainText("9473");
  await matchingRow.screenshot({ path: testInfo.outputPath("search-snippet.png") });
  await page.screenshot({
    path: testInfo.outputPath("archive.png"),
    fullPage: true,
  });

  const tagName = `Judge ${Date.now()}`;
  await navigate(page, "Tags & filing");
  await page.getByPlaceholder("e.g. Bills").fill(tagName);
  await page.getByPlaceholder("invoice, electricity, fattura").fill("9473");
  await page.getByRole("button", { name: "Create tag" }).click();
  await expect(page.getByRole("heading", { name: tagName })).toBeVisible();

  await navigate(page, "Paper archive");
  const locationName = `Judge shelf ${Date.now()}`;
  await page.getByPlaceholder("e.g. Filing cabinet").fill(locationName);
  await page.getByRole("button", { name: "Add location" }).click();
  await expect(
    page.getByText(locationName, { exact: true }).first(),
  ).toBeVisible();

  await navigate(page, "All documents");
  await page.getByRole("textbox", { name: "Search documents" }).fill(tagName);
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
  await page.getByRole("textbox", { name: "Search documents" }).fill("9473");
  await page.getByRole("button", { name, exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Keep it in place." }),
  ).toBeVisible();
  await page.locator(".new-copy select").selectOption({ label: locationName });
  await page.getByRole("button", { name: "Create sticker" }).click();
  await expect(
    page.getByRole("button", { name: "Save changes" }),
  ).toBeEnabled();
  const code = (await page
    .locator(".copy-card strong")
    .first()
    .textContent())!.trim();
  expect(code).toMatch(/^R-[A-Z2-9]{8}$/);
  await page.screenshot({
    path: testInfo.outputPath("paper-copy.png"),
    fullPage: true,
  });

  await page.getByRole("dialog", { name: "Keep it in place." }).getByRole("button", { name: "Close" }).click();
  await page.getByRole("button", { name: /Filters/ }).click();
  const paperFilter = page.getByRole("combobox", { name: "Paper copy" });
  await paperFilter.selectOption("paper");
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("paper-filter.png"), animations: "disabled" });
  await paperFilter.selectOption("virtual");
  await expect(page.getByRole("button", { name, exact: true })).toHaveCount(0);

  await page.goto(`/?sticker=${code}`);
  await expect(page.getByText(code, { exact: true })).toBeVisible();
  await expect(
    page.getByText(locationName, { exact: true }).first(),
  ).toBeVisible();

  await navigate(page, "All documents");
  await page.getByRole("textbox", { name: "Search documents" }).fill("9473");
  await page.getByRole("button", { name, exact: true }).click();
  const detail = page.getByRole("dialog", { name: "Keep it in place." });
  await detail.getByRole("button", { name: "Mark missing" }).click();
  await expect(detail.getByText("Reported missing", { exact: true })).toBeVisible();
  await detail.getByRole("button", { name: "Close" }).click();
  const missingRow = page.locator(".document-row").filter({ has: page.getByRole("button", { name, exact: true }) });
  await expect(missingRow.getByText("Paper copy reported missing")).toBeVisible();
  await expect(missingRow.getByText(locationName, { exact: true })).toHaveCount(0);
  await missingRow.screenshot({ path: testInfo.outputPath("missing-paper-copy.png"), animations: "disabled" });
  await page.getByRole("button", { name: /Filters/ }).click();
  const missingFilterResponse = page.waitForResponse((response) =>
    response.request().method() === "GET" &&
    response.status() === 200 &&
    new URL(response.url()).searchParams.get("copy_status") === "missing",
  );
  await page.getByRole("combobox", { name: "Paper copy" }).selectOption("missing");
  expect((await (await missingFilterResponse).json()).documents.some((document: { id: string }) => document.id === documentId)).toBe(true);
  await expect(missingRow).toBeVisible();
});
