import { chromium } from "/Users/debotta/dbrepos/ripiano/apps/web/node_modules/@playwright/test/index.mjs";
import fs from "node:fs";import { PW } from "./lib.mjs";
const SHOT="/Users/debotta/dbrepos/ripiano/qa-artifacts/20261118-r4-judge-3/";const P=JSON.parse(fs.readFileSync("phys.json"));
const browser=await chromium.launch({channel:"chrome"});
for(const [tag,opts] of [["desktop",{viewport:{width:1440,height:900},locale:"en-US"}],["mobile",{viewport:{width:390,height:844},isMobile:true,hasTouch:true,deviceScaleFactor:2,locale:"en-US"}]]){
 const ctx=await browser.newContext(opts);const page=await ctx.newPage();const errs=[];page.on("pageerror",e=>errs.push(String(e)));
 await page.goto("http://localhost:18080/");await page.locator('input[autocomplete=username]').fill("judge3");await page.locator('input[type=password]').fill(PW.JUDGE3_PASSWORD);await page.keyboard.press("Enter");await page.waitForTimeout(2500);
 const search=page.getByPlaceholder(/Search text/);await search.fill(P.sticker);await search.press("Enter");await page.waitForTimeout(1500);
 await page.screenshot({path:SHOT+`13-${tag}-sticker-search.png`});
 await page.getByText("j3r4-three-pages",{exact:true}).first().click();await page.waitForTimeout(2000);
 await page.screenshot({path:SHOT+`14-${tag}-document.png`,fullPage:false});
 const dlg=await page.getByRole("dialog").count();const ft=await page.evaluate(()=>document.activeElement?.tagName+":"+(document.activeElement?.getAttribute("aria-label")||document.activeElement?.innerText||"").slice(0,30));
 console.log(tag,"dialog open:",dlg,"focus:",ft);
 const body=await page.locator("body").innerText();console.log(tag,"shows shelf/box:",/j3r4 Shelf/.test(body),"sticker:",body.includes(P.sticker));
 await page.keyboard.press("Escape");await page.waitForTimeout(600);
 const ft2=await page.evaluate(()=>document.activeElement?.tagName+":"+(document.activeElement?.innerText||"").slice(0,30));console.log(tag,"focus after Esc:",ft2,"dialogs:",await page.getByRole("dialog").count());
 if(tag==="desktop"){await page.keyboard.press("a");await page.waitForTimeout(600);console.log("a-shortcut dialog:",await page.getByRole("dialog").count(), await page.evaluate(()=>document.activeElement?.innerText?.slice(0,30)));await page.screenshot({path:SHOT+"15-desktop-add-dialog.png"});await page.keyboard.press("Escape");}
 console.log(tag,"errors",errs);await ctx.close();
}
await browser.close();
