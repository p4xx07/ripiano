// Capture the README screenshots. Run from apps/web so Playwright resolves:
//   cd apps/web && RIPIANO_DEMO_PASSWORD=... node ../../qa-artifacts/20261119-readme/shots.mjs http://localhost:18080 demo-readme ../../qa-artifacts/20261119-readme
import { createRequire } from "node:module";

const { chromium } = createRequire(`${process.cwd()}/`)("@playwright/test");
const [origin, username, out] = process.argv.slice(2);
const browser = await chromium.launch({ channel: "chrome" });

async function signIn(options) {
  const context = await browser.newContext({ locale: "en-US", colorScheme: "light", ...options });
  const page = await context.newPage();
  await page.goto(`${origin}/`);
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(process.env.RIPIANO_DEMO_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.locator(".library-list .document-row").nth(5).waitFor();
  await page.waitForLoadState("networkidle");
  return { context, page };
}

async function settle(page) {
  await page.evaluate(() => document.activeElement?.blur?.());
  await page.mouse.move(0, 0);
  await page.waitForFunction(() => [...document.images].every((image) => image.complete));
  await page.waitForTimeout(500);
}

// 1. Desktop Library, scrolled so the search bar and the document list fill the view.
{
  const { context, page } = await signIn({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await page.getByRole("heading", { name: "Your documents" }).evaluate((heading) => heading.scrollIntoView({ block: "start" }));
  await page.evaluate(() => window.scrollBy(0, -24));
  await settle(page);
  await page.screenshot({ path: `${out}/desktop-library.png`, animations: "disabled" });

  // 2. A document open: first-page preview beside its filing details.
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.getByRole("button", { name: "Electricity bill October 2026", exact: true }).click();
  await page.getByRole("img", { name: /First page of/ }).waitFor();
  await settle(page);
  await page.screenshot({ path: `${out}/desktop-document.png`, animations: "disabled" });
  await context.close();
}

// 3. Phone Library (PWA in a mobile browser).
{
  const { context, page } = await signIn({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true });
  await settle(page);
  await page.screenshot({ path: `${out}/mobile-library.png`, animations: "disabled" });
  await context.close();
}

await browser.close();
console.log("shots done");
