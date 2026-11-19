import { launch, login, shot } from "./lib.mjs";
const { browser, page } = await launch(false);
await login(page);
await page.getByRole("button",{name:"Agents",exact:true}).click(); await page.waitForTimeout(1200);
const card = page.locator("main").locator("article, li, .card, div").filter({hasText:/^R4J1b Cloud/}).filter({has: page.getByRole("button",{name:"Revoke"})}).last();
await card.getByRole("button",{name:"Revoke"}).click(); await page.waitForTimeout(800);
const t0 = await page.locator("main").innerText(); const i0=t0.indexOf("R4J1b Cloud"); console.log("CONFIRM STEP:", t0.slice(i0,i0+300).replace(/\n+/g," | ")); await shot(page,"22a-revoke-confirm"); await page.getByRole("button",{name:"Yes, revoke"}).click();
const dlg = page.getByRole("dialog"); if (await dlg.count()) { console.log("CONFIRM:", (await dlg.first().innerText()).replace(/\n+/g," | ")); await dlg.getByRole("button",{name:/Revoke/}).last().click(); }
await page.waitForTimeout(1200);
const t = await page.locator("main").innerText(); const i=t.indexOf("R4J1b Cloud"); console.log("CARD:", t.slice(i,i+150).replace(/\n+/g," | "));
const j=t.indexOf("Recent activity"); console.log("AUDIT:", t.slice(j,j+900).replace(/\n+/g," | "));
await shot(page,"22-agent-revoked-audit");
await browser.close();
