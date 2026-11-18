import { chromium } from "/Users/debotta/dbrepos/ripiano/apps/web/node_modules/@playwright/test/index.mjs";
import fs from "node:fs";import { PW } from "./lib.mjs";
const SHOT="/Users/debotta/dbrepos/ripiano/qa-artifacts/20261118-r4-judge-3/";
const G=JSON.parse(fs.readFileSync("grants.json"));
const browser=await chromium.launch({channel:"chrome"});
async function session(name,opts){
  const ctx=await browser.newContext(opts);const page=await ctx.newPage();const errs=[];page.on("pageerror",e=>errs.push(String(e)));page.on("console",m=>{if(m.type()==="error")errs.push(m.text().slice(0,150))});
  await page.goto("http://localhost:18080/");
  await page.locator('input[autocomplete=username]').fill("judge3");await page.locator('input[type=password]').fill(PW.JUDGE3_PASSWORD);await page.keyboard.press("Enter");
  await page.waitForTimeout(2500);return {ctx,page,errs};
}
async function nav(page,label){const menu=page.getByRole("button",{name:/Toggle menu|menu/i});if(await menu.first().isVisible().catch(()=>false))await menu.first().click();await page.getByRole("button",{name:label,exact:true}).click();await page.waitForTimeout(1200);}
// DESKTOP agents UI
{const {page,errs,ctx}=await session("d",{viewport:{width:1440,height:900},locale:"en-US"});
 await nav(page,"Agents");
 const name="j3r4-ui-agent-"+G.stamp;
 await page.getByPlaceholder("e.g. Local Mac classifier").fill(name);
 await page.getByLabel("Read OCR text").check();
 const sel=page.locator("select").filter({hasText:/all documents|any|every/i}).first();
 const selects=await page.locator("select").evaluateAll(es=>es.map(e=>[e.getAttribute("aria-label")||e.id,[...e.options].slice(0,4).map(o=>o.text)]));console.log("selects",JSON.stringify(selects).slice(0,500));
 try{await page.getByLabel(/Only documents tagged|Limit to tag|tag/i).first().selectOption({label:G.tA.name});console.log("filter set");}catch(e){console.log("filter select failed",String(e).slice(0,120));}
 await page.getByRole("button",{name:"Create agent token"}).click();await page.waitForTimeout(1000);
 await page.screenshot({path:SHOT+"05-agent-created.png",fullPage:false,mask:[page.getByLabel("New agent token")],maskColor:"#dce8d8"});
 const card=page.locator(".agent-card").filter({hasText:name});console.log("card:",(await card.innerText()).replace(/\n/g," | ").slice(0,300));
 const audit=await page.locator("text=/j3r4-C-|j3r4-B-/").count();console.log("audit rows visible for my agents:",audit);
 await page.screenshot({path:SHOT+"06-agents-audit.png",fullPage:true,mask:[page.getByLabel("New agent token")],maskColor:"#dce8d8"});
 await card.getByRole("button",{name:`Revoke ${name}`}).click();await card.getByRole("button",{name:"Yes, revoke"}).click();await page.waitForTimeout(800);
 console.log("revoked shown:",(await card.innerText()).includes("Revoked"));
 // tokens screen
 await nav(page,"Security");await page.screenshot({path:SHOT+"07-security.png",fullPage:true});
 await nav(page,"Backups");await page.screenshot({path:SHOT+"08-backups.png",fullPage:true});
 console.log("backups text:",(await page.locator("main").innerText()).replace(/\n/g," | ").slice(0,400));
 await nav(page,"People");await page.screenshot({path:SHOT+"09-people.png",fullPage:false});
 // keyboard-only: from fresh library, tab through and record focus order
 await nav(page,"All documents");await page.keyboard.press("/");const f1=await page.evaluate(()=>document.activeElement?.getAttribute("placeholder")||document.activeElement?.tagName);
 await page.keyboard.type("otter");await page.keyboard.press("Enter");await page.waitForTimeout(1500);
 const hits=await page.locator("main").innerText();console.log("slash focus:",f1,"| otter hit three-pages:",hits.includes("j3r4-three-pages"));
 const order=[];await page.keyboard.press("Escape");await page.evaluate(()=>document.activeElement.blur());
 for(let i=0;i<14;i++){await page.keyboard.press("Tab");order.push(await page.evaluate(()=>{const e=document.activeElement;const r=e.getBoundingClientRect();const st=getComputedStyle(e);return (e.getAttribute("aria-label")||e.innerText||e.getAttribute("placeholder")||e.tagName).slice(0,30)+(st.outlineStyle==="none"&&st.boxShadow==="none"?"[NOFOCUSRING]":"")}));}
 console.log("tab order:",order.join(" > "));
 await page.screenshot({path:SHOT+"10-keyboard-focus.png"});
 console.log("desktop errors",errs);await ctx.close();}
// MOBILE Italian
{const {page,errs,ctx}=await session("m",{viewport:{width:390,height:844},isMobile:true,hasTouch:true,deviceScaleFactor:2,locale:"it-IT"});
 await page.screenshot({path:SHOT+"11-mobile-it-library.png"});
 const ov=await page.evaluate(()=>document.documentElement.scrollWidth);console.log("mobile scrollWidth",ov);
 await nav(page,"Agenti");await page.screenshot({path:SHOT+"12-mobile-it-agents.png",fullPage:true});
 const txt=await page.locator("main").innerText();const en=txt.match(/\b(the|and|your|agent token|Revoke|Create)\b/g);console.log("english leftovers on IT agents:",en);
 const small=await page.locator("button:visible, a:visible, input:visible, select:visible").evaluateAll(es=>es.map(e=>{const r=e.getBoundingClientRect();return [(e.getAttribute("aria-label")||e.innerText||e.tagName).slice(0,25),Math.round(r.width),Math.round(r.height)]}).filter(([,w,h])=>w>0&&(h<40||w<40)));console.log("small targets",JSON.stringify(small.slice(0,12)));
 console.log("mobile errors",errs);await ctx.close();}
await browser.close();
