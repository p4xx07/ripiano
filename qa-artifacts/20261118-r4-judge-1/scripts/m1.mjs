import { launch, login, shot, FX } from "./lib.mjs";
const { browser, page } = await launch(true);
await page.goto("/"); await shot(page,"30-m-login");
await login(page);
await shot(page,"31-m-home");
const ov = await page.evaluate(()=>({sw:document.documentElement.scrollWidth, cw:document.documentElement.clientWidth}));
console.log("overflow:", JSON.stringify(ov));
// tap targets under 44px
const small = await page.evaluate(()=>[...document.querySelectorAll("button,a,input,select,[role=button]")].filter(e=>{const r=e.getBoundingClientRect(); return r.width>0 && r.height>0 && (r.height<32||r.width<32) && getComputedStyle(e).visibility!=="hidden";}).map(e=>`${(e.getAttribute("aria-label")||e.innerText||e.type||"").trim().slice(0,30)}:${Math.round(e.getBoundingClientRect().width)}x${Math.round(e.getBoundingClientRect().height)}`).slice(0,20));
console.log("small targets:", small.join(", "));
// add via photos
await page.getByRole("button",{name:/^(Add|Add document)$/}).first().tap();
await page.waitForTimeout(600); await shot(page,"32-m-add-sheet");
await page.getByLabel("Choose from photos").setInputFiles(`${FX}/judge.png`);
await page.waitForTimeout(4000); await shot(page,"33-m-after-upload");
const st = await page.locator("[role=status]").allInnerTexts(); console.log("STATUS:", st.filter(Boolean).join(" || "));
// search
const s = page.getByPlaceholder(/Search text/).first(); await s.tap(); await s.fill("mirtillo"); await s.press("Enter"); await page.waitForTimeout(1800);
await shot(page,"34-m-search");
await page.getByRole("button",{name:"Avviso condominio mirtillo",exact:true}).first().tap(); await page.waitForTimeout(1500);
await shot(page,"35-m-detail");
const d = page.getByRole("dialog").first();
const ov2 = await page.evaluate(()=>({sw:document.documentElement.scrollWidth}));
console.log("detail overflow:", JSON.stringify(ov2));
await d.getByText("Paper copies").scrollIntoViewIfNeeded(); await shot(page,"36-m-detail-paper");
// close
const close = d.getByRole("button",{name:/Close|Back/}).first(); console.log("close label:", await close.getAttribute("aria-label")); await close.tap(); await page.waitForTimeout(600);
// menu nav
await page.getByRole("button",{name:"Toggle menu"}).tap(); await page.waitForTimeout(500); await shot(page,"37-m-menu");
await page.getByRole("button",{name:"Paper archive",exact:true}).tap(); await page.waitForTimeout(1000);
await page.locator("main input").first().fill("R-F9YNKLWW"); await page.getByRole("button",{name:"Find",exact:true}).tap(); await page.waitForTimeout(1500);
await shot(page,"38-m-sticker-lookup");
const t = await page.locator("main").innerText(); const i=t.indexOf("Find a sticker"); console.log("LOOKUP:", t.slice(i,i+300).replace(/\n+/g," | "));
const scan = await page.getByRole("button",{name:/Scan/}).count(); console.log("scan buttons:", scan, await page.getByRole("button",{name:/Scan/}).allInnerTexts());
await browser.close();
