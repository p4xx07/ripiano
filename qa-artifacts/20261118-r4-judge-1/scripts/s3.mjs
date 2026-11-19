import { launch, login, shot, text, FX } from "./lib.mjs";
const { browser, page } = await launch(false);
await login(page);
const before = await (await page.request.get("/api/documents?page_size=200")).json().catch(()=>null);
console.log("API keys:", before && Object.keys(before));
await page.getByRole("button", { name: "Add document" }).first().click();
await page.getByLabel("Take a photo").setInputFiles(`${FX}/judge.png`);
await page.waitForTimeout(2500);
await shot(page, "04-after-camera-upload");
console.log("AFTER CAMERA:\n", (await text(page, 1800)).split("\n").slice(25,60).join("\n"));
await page.getByRole("button", { name: "Add document" }).first().click();
await page.getByLabel("Browse files").setInputFiles([`${FX}/three-pages.pdf`, `${FX}/outlook-notice.msg`, `${FX}/office-open.odt`]);
const t0 = Date.now();
await page.waitForTimeout(3000);
await shot(page, "05-after-batch-upload");
const live = await page.locator("[role=status],[aria-live]").allInnerTexts(); console.log("LIVE:", live.join(" || ").slice(0,600));
// wait for processing
for (let i=0;i<30;i++){ await page.waitForTimeout(3000); const b = await text(page, 6000); const m=b.match(/(\d+)\nBeing processed/); if (m && m[1]==="0") { console.log("processed after", (Date.now()-t0)/1000,"s"); break;} }
await page.getByRole("button",{name:"Refresh"}).click().catch(()=>{});
await page.waitForTimeout(1500);
await shot(page, "06-after-processing");
console.log((await text(page, 3500)).split("\n").slice(38,80).join("\n"));
await browser.close();
