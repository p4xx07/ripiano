import { chromium } from "@playwright/test";
const out = process.argv[2];
const browser = await chromium.launch({ channel: "chrome" });
async function shoot(name, options) {
  const context = await browser.newContext({ locale: "en-US", colorScheme: "light", ...options });
  const page = await context.newPage();
  await page.goto("http://localhost:18091/");
  await page.getByLabel("Username").fill("giulia");
  await page.getByLabel("Password").fill(process.env.SHOWCASE_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("heading", { name: /Everything in its place/ }).waitFor();
  await page.locator(".library-list .document-row").nth(5).waitFor();
  await page.waitForLoadState("networkidle");
  await page.mouse.move(0, 0);
  await page.screenshot({ path: `${out}/${name}-library.png`, animations: "disabled" });
  if (!options.isMobile) {
    await page.getByRole("button", { name: "Bolletta luce ottobre 2026", exact: true }).click();
    const preview = page.getByRole("img", { name: /First page of/ });
    await preview.waitFor();
    await page.waitForFunction(() => [...document.images].every((image) => image.complete));
    await page.evaluate(() => (document.activeElement)?.blur?.());
    await page.mouse.move(0, 0);
    await page.waitForTimeout(400);
    await page.screenshot({ path: `${out}/${name}-document.png`, animations: "disabled" });
  }
  await context.close();
}
await shoot("desktop", { viewport: { width: 1440, height: 900 } });
await shoot("mobile", { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
await browser.close();
console.log("shots done");
