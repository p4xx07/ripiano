import { launch, login, shot, text } from "./lib.mjs";
const { browser, page, ctx } = await launch(false);
await login(page);
await page.getByRole("button", { name: "Avviso condominio mirtillo", exact: true }).first().click();
await page.waitForTimeout(1500);
const d = page.getByRole("dialog").first();
const ps = d.getByText("Print sticker").first();
console.log("print el:", await ps.evaluate(e => { const a=e.closest("a,button"); return a ? a.outerHTML.slice(0,300) : e.outerHTML.slice(0,300); }));
const href = await ps.evaluate(e => e.closest("a")?.href);
if (href) { const p2 = await ctx.newPage(); await p2.goto(href); await p2.waitForTimeout(1500); await p2.screenshot({path:"/Users/debotta/dbrepos/ripiano/qa-artifacts/20261118-r4-judge-1/18-print-label.png"}); console.log("LABEL:", (await p2.locator("body").innerText()).slice(0,300).replace(/\n+/g," | ")); await p2.close(); }
const mv = d.locator("select").filter({ has: page.locator("option[value='']", {hasText:/^No location$/}) }).first();
console.log("move selects:", await d.locator("select").count());
const sels = d.locator("select"); const n = await sels.count(); let target;
for (let i=0;i<n;i++){ const v = await sels.nth(i).inputValue(); const opts = await sels.nth(i).locator("option").allInnerTexts(); if (opts.includes("No location")) target = sels.nth(i); }
await target.selectOption({label:"Studio scaffale / Armadio ingresso"});
await d.getByRole("button",{name:"Move",exact:true}).click(); await page.waitForTimeout(1200);
const st = await page.locator("[role=status]").allInnerTexts(); console.log("STATUS:", st.filter(Boolean).join(" || "));
await d.getByRole("button",{name:/History/}).first().click(); await page.waitForTimeout(1000);
const pc = await d.innerText(); const k = pc.indexOf("Paper copies"); console.log("PAPER:", pc.slice(k,k+600).replace(/\n+/g," | "));
await page.keyboard.press("Escape"); await page.waitForTimeout(500);
await page.getByRole("button",{name:"Paper archive",exact:true}).click(); await page.waitForTimeout(1000);
const inp = page.locator("main input").first(); await inp.fill("r-f9ynklww");
await page.getByRole("button",{name:"Find",exact:true}).click(); await page.waitForTimeout(1500);
await shot(page,"19-sticker-lookup");
const t = await page.locator("main").innerText(); const i=t.indexOf("Find a sticker"); console.log("LOOKUP:", t.slice(i,i+700).replace(/\n+/g," | "));
await browser.close();
