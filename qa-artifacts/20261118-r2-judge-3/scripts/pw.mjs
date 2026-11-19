import { chromium } from "@playwright/test";
import { password } from "./api.mjs";
export const OUT = "/Users/debotta/dbrepos/ripiano/qa-artifacts/20261118-r2-judge-3/";
export async function start({ mobile = false, locale = "en-US", user = "judge3", pw = password() } = {}) {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const context = await browser.newContext(mobile ? { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2, locale, baseURL: "http://localhost:18080" } : { viewport: { width: 1440, height: 900 }, locale, baseURL: "http://localhost:18080" });
  const page = await context.newPage();
  const errors = [];
  page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", e => errors.push("PAGEERROR " + e.message));
  await page.goto("/");
  if (user) {
    await page.getByLabel(/Username|Nome utente/).fill(user);
    await page.getByLabel(/^Password/).first().fill(pw);
    await page.getByRole("button", { name: /Sign in|Accedi/ }).click();
    await page.waitForLoadState("networkidle");
  }
  return { browser, context, page, errors };
}
