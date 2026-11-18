import { chromium, devices } from "/Users/debotta/dbrepos/ripiano/apps/web/node_modules/@playwright/test/index.mjs";
import fs from "node:fs";
const env = fs.readFileSync("/private/tmp/claude-501/-Users-debotta-dbrepos-ripiano/23569b07-51e7-4ab9-89ce-c4e342f5998a/scratchpad/judges.env","utf8");
export const PW = (env.match(/^JUDGE1_PASSWORD=(.*)$/m)||[])[1]?.trim().replace(/^["']|["']$/g,"");
export const USER = "judge1";
export const BASE = "http://localhost:18080";
export const OUT = "/Users/debotta/dbrepos/ripiano/qa-artifacts/20261118-r4-judge-1";
export const FX = "/Users/debotta/dbrepos/ripiano/apps/web/e2e/fixtures";
export async function launch(mobile=false, locale="en-US") {
  const browser = await chromium.launch({ channel: "chrome" });
  const ctx = await browser.newContext(mobile ? { viewport:{width:390,height:844}, isMobile:true, hasTouch:true, deviceScaleFactor:3, locale, baseURL:BASE } : { viewport:{width:1440,height:900}, locale, baseURL:BASE });
  const page = await ctx.newPage();
  page.on("console", m => { if (m.type()==="error") console.log("CONSOLE ERR:", m.text().slice(0,200)); });
  page.on("pageerror", e => console.log("PAGEERROR:", e.message.slice(0,200)));
  return { browser, ctx, page };
}
export async function login(page) {
  await page.goto("/");
  await page.getByLabel(/Username|Nome utente/).fill(USER);
  await page.getByLabel(/Password/).first().fill(PW);
  await page.getByRole("button", { name: /Sign in|Accedi/ }).click();
  await page.waitForTimeout(2000);
}
export async function shot(page, name, full=false) { await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: full }); }
export async function text(page, n=2500) { return (await page.locator("body").innerText()).slice(0,n); }
