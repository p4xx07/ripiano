import { launch, login, shot } from "./lib.mjs";
const { browser, page } = await launch(true, "it-IT");
await page.goto("/"); await page.waitForTimeout(800);
console.log("login IT:", (await page.locator("body").innerText()).slice(0,200).replace(/\n+/g," | "));
await login(page);
const en = /\b(the|your|and|with|Add|Search|Ready|documents?|Select|Filters|Paper|Save|Changes|Find|Move|Revoke|Created|Expires|Sources|Optional|Nothing)\b/;
async function scan(label){ const t = await page.locator("body").innerText(); const lines = t.split("\n").map(s=>s.trim()).filter(s=>s && en.test(s) && !/^(j1|r2j1|j1r3|office|three-pages|judge|R4J1|J1R3|R2|Local|Cloud|Avviso|Bolletta|Fattura|Preventivo|asn-|barcode-|tag-barcode)/.test(s)); console.log(`## ${label} EN-ish lines:`, lines.slice(0,15).join(" ‖ ")); }
await shot(page,"41-it-m-home"); await scan("home");
await page.getByRole("button",{name:/^Aggiungi/}).first().tap(); await page.waitForTimeout(500); await scan("add"); await shot(page,"42-it-m-add"); await page.keyboard.press("Escape");
await page.getByRole("button",{name:"Avviso condominio mirtillo",exact:true}).first().tap(); await page.waitForTimeout(1500); await scan("detail"); await page.getByRole("dialog").getByRole("button",{name:/Chiudi/}).first().tap(); await page.waitForTimeout(500);
const menu = page.getByRole("button",{name:/menu/i}).first(); 
for (const nav of ["Archivio cartaceo","Agenti","Fonti","Backup","Posta in arrivo"]) { await menu.tap().catch(()=>{}); await page.waitForTimeout(400); const b = page.getByRole("button",{name:nav,exact:true}); if (await b.count()) { await b.first().tap(); await page.waitForTimeout(1200); await scan(nav);} else console.log("no nav", nav, (await page.getByRole("navigation").first().innerText()).replace(/\n+/g,", ")); }
await shot(page,"43-it-m-inbox");
await browser.close();
