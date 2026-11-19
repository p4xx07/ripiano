import { launch, login, shot, text } from "./lib.mjs";
const { browser, page } = await launch(false);
await login(page);
const search = page.getByPlaceholder(/Search text/).first();
for (const s of ["bolleta","2026-10-14","14/10/2026","date:2026-10"]) { await search.fill(s); await search.press("Enter"); await page.waitForTimeout(1800);
 const t = await page.locator("main").innerText(); const i=t.indexOf("More precise search"); console.log(`### ${s}:`, t.slice(i, i+500).replace(/\n+/g," | ")); }
await shot(page,"10-search-date-empty");
await search.fill(""); await search.press("Enter");
await page.getByRole("button",{name:"Filters"}).click(); await page.waitForTimeout(800);
await shot(page,"11-filters-desktop");
const t = await page.locator("main").innerText(); const i=t.indexOf("Filters"); console.log("FILTERS:", t.slice(i, i+1500).replace(/\n+/g," | "));
await page.getByRole("button",{name:"More precise search"}).click(); await page.waitForTimeout(800);
const t2 = await page.locator("main").innerText(); const j=t2.indexOf("More precise search"); console.log("PRECISE:", t2.slice(j, j+1500).replace(/\n+/g," | "));
await browser.close();
