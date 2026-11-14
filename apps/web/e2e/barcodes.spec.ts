import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const username = process.env.RIPIANO_E2E_USERNAME;
const password = process.env.RIPIANO_E2E_PASSWORD;
const asnFor = { desktop: 900001, mobile: 900002 } as Record<string, number>;

test("a separator sheet splits a scan and an ASN barcode numbers the part", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.setTimeout(240000);
  const asn = asnFor[testInfo.project.name];
  const original = readFileSync(path.resolve(process.cwd(), `e2e/fixtures/barcode-batch-${testInfo.project.name}.pdf`));
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  // Free this project's ASN from an earlier run so the barcode can claim it.
  const previous = await (await page.request.get(`/api/documents?q=asn:${asn}`)).json();
  for (const item of previous.documents) {
    const csrf = (await page.context().cookies()).find((cookie) => cookie.name === "csrftoken")?.value ?? "";
    await page.request.patch(`/api/documents/${item.id}`, { data: { asn: null }, headers: { "X-CSRFToken": csrf } });
  }

  const name = `batch-${Date.now()}-${testInfo.project.name}`;
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const upload = page.waitForResponse((response) => response.url().endsWith("/api/documents") && response.request().method() === "POST" && response.status() === 202);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.pdf`, mimeType: "application/pdf", buffer: original });
  const source = await (await upload).json();
  await expect.poll(async () => (await (await page.request.get(`/api/documents/${source.id}`)).json()).is_split_source, { timeout: 120000 }).toBe(true);

  const partTitle = `${name} (2/2)`;
  await expect.poll(async () => {
    const found = await (await page.request.get(`/api/documents?q=${encodeURIComponent(`title:"${name}"`)}`)).json();
    return found.documents.map((item: { title: string; status: string }) => `${item.title}:${item.status}`).sort();
  }, { timeout: 150000 }).toEqual([`${name} (1/2):ready`, `${partTitle}:ready`]);
  const numbered = await (await page.request.get(`/api/documents?q=asn:${asn}`)).json();
  expect(numbered.documents.map((item: { title: string }) => item.title)).toEqual([partTitle]);
  expect(await (await page.request.get(`/api/documents/${source.id}/original`)).body()).toEqual(original);

  const searched = page.waitForResponse(async (response) => response.url().includes(`q=asn%3A${asn}`) && response.status() === 200
    && (await response.json()).documents.length === 1);
  await page.getByRole("textbox", { name: "Search documents" }).fill(`asn:${asn}`);
  await searched;
  await page.getByRole("button", { name: partTitle, exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Keep it in place." });
  await expect(dialog.getByLabel(/Archive number \(ASN\)/)).toHaveValue(String(asn));
  await dialog.getByRole("button", { name: /Open full scan/ }).click();
  await expect(page.getByRole("dialog", { name: "Keep it in place." })).toContainText("This full scan was split by barcodes");
});

test("ASN barcodes start separate documents without separator sheets", async ({ page }, testInfo) => {
  test.skip(!username || !password, "Set RIPIANO_E2E_USERNAME and RIPIANO_E2E_PASSWORD");
  test.setTimeout(240000);
  const [firstAsn, secondAsn] = testInfo.project.name === "mobile" ? [900021, 900022] : [900011, 900012];
  const original = readFileSync(path.resolve(process.cwd(), `e2e/fixtures/asn-batch-${testInfo.project.name}.pdf`));
  await page.goto("/");
  await page.getByLabel("Username").fill(username!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Everything in its place/ })).toBeVisible();

  const csrf = (await page.context().cookies()).find((cookie) => cookie.name === "csrftoken")?.value ?? "";
  for (const asn of [firstAsn, secondAsn]) {
    const previous = await (await page.request.get(`/api/documents?q=asn:${asn}`)).json();
    for (const item of previous.documents) {
      await page.request.patch(`/api/documents/${item.id}`, { data: { asn: null }, headers: { "X-CSRFToken": csrf } });
    }
  }

  const name = `asn-scan-${Date.now()}-${testInfo.project.name}`;
  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  const upload = page.waitForResponse((response) => response.url().endsWith("/api/documents") && response.request().method() === "POST" && response.status() === 202);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /Browse files/ }).click();
  await (await chooser).setFiles({ name: `${name}.pdf`, mimeType: "application/pdf", buffer: original });
  const source = await (await upload).json();
  await expect.poll(async () => (await (await page.request.get(`/api/documents/${source.id}`)).json()).is_split_source, { timeout: 120000 }).toBe(true);
  await expect.poll(async () => {
    const found = await (await page.request.get(`/api/documents?q=${encodeURIComponent(`title:"${name}"`)}`)).json();
    return found.documents.map((item: { title: string; status: string }) => `${item.title}:${item.status}`).sort();
  }, { timeout: 150000 }).toEqual([`${name} (1/2):ready`, `${name} (2/2):ready`]);
  const first = await (await page.request.get(`/api/documents?q=asn:${firstAsn}`)).json();
  const second = await (await page.request.get(`/api/documents?q=asn:${secondAsn}`)).json();
  expect(first.documents.map((item: { title: string }) => item.title)).toEqual([`${name} (1/2)`]);
  expect(second.documents.map((item: { title: string }) => item.title)).toEqual([`${name} (2/2)`]);
  expect(await (await page.request.get(`/api/documents/${source.id}/original`)).body()).toEqual(original);

  const searched = page.waitForResponse(async (response) => response.url().includes(`q=asn%3A${secondAsn}`) && response.status() === 200
    && (await response.json()).documents.length === 1);
  await page.getByRole("textbox", { name: "Search documents" }).fill(`asn:${secondAsn}`);
  await searched;
  await page.getByRole("button", { name: `${name} (2/2)`, exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Keep it in place." });
  await expect(dialog.getByLabel(/Archive number \(ASN\)/)).toHaveValue(String(secondAsn));
  await expect(dialog.getByRole("button", { name: /Open full scan/ })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("asn-only-split.png"), animations: "disabled" });
  await dialog.getByRole("button", { name: /Open full scan/ }).click();
  await expect(page.getByRole("dialog", { name: "Keep it in place." })).toContainText("This full scan was split by barcodes");
});
