import { launch, login, shot } from "./lib.mjs";
const { browser, page } = await launch(false);
await login(page);
await page.getByRole("button",{name:"Inbox",exact:true}).click(); await page.waitForTimeout(1200);
await page.getByRole("button",{name:"Try OCR again"}).first().click(); await page.waitForTimeout(1000);
console.log("retry status:", (await page.locator("[role=status],[role=alert]").allInnerTexts()).filter(Boolean).join(" || "));
await page.waitForTimeout(12000); await page.getByRole("button",{name:"Refresh"}).click(); await page.waitForTimeout(1500);
const t = await page.locator("main").innerText(); const i=t.indexOf("j1r3-damaged"); console.log("damaged now:", t.slice(i,i+250).replace(/\n+/g," | "));
await shot(page,"49-retry-ocr");
await page.getByRole("button",{name:"Backups",exact:true}).click(); await page.waitForTimeout(1000);
const t0=Date.now(); await page.getByRole("button",{name:"Back up now"}).click();
for (let k=0;k<20;k++){ await page.waitForTimeout(3000); const b=await page.locator("main").innerText(); const j=b.indexOf("Recent snapshots"); const first=b.slice(j,j+200).replace(/\n+/g," | "); if (/complete|failed/.test(first.split("|").slice(2,6).join("|")) && !first.includes("164038")) { console.log("backup:", first, ((Date.now()-t0)/1000)+"s"); break; } if(k==19) console.log("backup pending:", first); }
console.log("status:", (await page.locator("[role=status],[role=alert]").allInnerTexts()).filter(Boolean).join(" || "));
await shot(page,"50-backup-now");
await browser.close();
