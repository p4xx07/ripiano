// Run from the repository root against a local stack with a small synthetic owner archive.
// RIPIANO_SHOWCASE_USERNAME and RIPIANO_SHOWCASE_PASSWORD are required.
import { createRequire } from "node:module";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const require = createRequire(new URL("../../apps/web/package.json", import.meta.url));
const { chromium } = require("playwright");

const username = process.env.RIPIANO_SHOWCASE_USERNAME;
const password = process.env.RIPIANO_SHOWCASE_PASSWORD;
if (!username || !password) throw new Error("Set RIPIANO_SHOWCASE_USERNAME and RIPIANO_SHOWCASE_PASSWORD");

const origin = process.env.RIPIANO_SHOWCASE_ORIGIN ?? "http://localhost:18080";
const output = path.resolve("qa-artifacts/20261111-showcase");
const browser = await chromium.launch({ channel: "chrome", headless: true });

async function navigate(page, name) {
  const menu = page.getByRole("button", { name: "Toggle menu" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name, exact: true }).click();
  await page.locator(".sidebar").evaluate(async (element) => {
    if (!element.classList.contains("sidebar-open")) return;
    await new Promise((resolve) => setTimeout(resolve, 250));
  });
}

async function capture(name, viewport, mobile) {
  const directory = path.join(output, name);
  await mkdir(directory, { recursive: true });
  const context = await browser.newContext({ viewport, isMobile: mobile, hasTouch: mobile, deviceScaleFactor: 1, locale: "en-US", timezoneId: mobile ? "America/Los_Angeles" : "Europe/Rome" });
  const page = await context.newPage();
  await page.goto(origin);
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("heading", { name: /Everything in its place/ }).waitFor();
  await page.getByRole("combobox", { name: "Sort documents" }).selectOption("document_newest");
  await page.getByRole("button", { name: "Home insurance policy", exact: true }).waitFor();
  const firstDocument = page.locator(".document-row").first();
  if (!(await firstDocument.innerText()).includes("Dated Oct 1, 2026")) {
    throw new Error("The Library must show the document date used by its sort order");
  }
  await page.waitForTimeout(350);
  await page.screenshot({ path: path.join(directory, "library-full.png"), fullPage: true, animations: "disabled" });

  const add = page.getByRole("button", { name: "Add document", exact: true });
  if (await add.isVisible()) await add.click();
  else await page.getByRole("button", { name: "Add", exact: true }).click();
  await page.getByRole("dialog", { name: "Bring a document in." }).waitFor();
  await page.screenshot({ path: path.join(directory, "add.png"), animations: "disabled" });
  await page.keyboard.press("Escape");

  await navigate(page, "Paper archive");
  await page.getByRole("heading", { name: /Your paper archive/ }).waitFor();
  await page.getByText("Documents binder").first().waitFor();
  await page.locator(".location-list > div").filter({ hasText: "Home / Study / Documents binder" }).getByRole("button", { name: "View contents" }).click();
  await page.getByText("2 paper copies recorded here").waitFor();
  await page.screenshot({ path: path.join(directory, mobile ? "paper-contents-full.png" : "paper-contents.png"), fullPage: mobile, animations: "disabled" });
  await context.close();
}

try {
  await capture("desktop", { width: 1440, height: 900 }, false);
  await capture("mobile", { width: 390, height: 844 }, true);
} finally {
  await browser.close();
}
