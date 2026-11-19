import { launch, login, shot, text } from "./lib.mjs";
const { browser, page } = await launch(false);
await login(page);
const search = page.getByRole("searchbox").or(page.getByPlaceholder(/Search text/)).first();
async function q(s, name){ await search.fill(s); await search.press("Enter"); await page.waitForTimeout(1800);
  const items = await page.locator("main").innerText(); const idx = items.indexOf("Select documents");
  console.log(`### "${s}":`, items.slice(idx, idx+700).replace(/\n+/g," | ")); if(name) await shot(page,name); }
await q("9473","08-search-ocr-phrase");
await q("judge 9473");
await q("Acquedotto Mirto","09-search-sender");
await q("tag:Condominio");
await q("Condominio");
await q("ottobre");
await q("bolleta");
await q("2026-10-14");
await q("lampone");
await browser.close();
