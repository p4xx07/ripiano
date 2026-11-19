import { chromium } from "/Users/debotta/dbrepos/ripiano/apps/web/node_modules/@playwright/test/index.mjs";
import fs from "node:fs";
import { Client, PW } from "/private/tmp/claude-501/-Users-debotta-dbrepos-ripiano/23569b07-51e7-4ab9-89ce-c4e342f5998a/scratchpad/j3r4/lib.mjs";
const SHOT="/Users/debotta/dbrepos/ripiano/qa-artifacts/20261118-r4-judge-3/";
const stamp=Date.now()%1000000;
const png=fs.readFileSync("/Users/debotta/dbrepos/ripiano/apps/web/e2e/fixtures/judge.png");
const browser=await chromium.launch({channel:"chrome"});
console.log("chrome",browser.version());
const ctx=await browser.newContext({viewport:{width:1440,height:900},locale:"en-US"});
const page=await ctx.newPage();
const errs=[];page.on("pageerror",e=>errs.push(String(e)));
await page.goto("http://localhost:18080/");
await page.getByLabel("Username").fill("judge3");await page.getByLabel("Password").fill(PW.JUDGE3_PASSWORD);
await page.getByRole("button",{name:/sign in/i}).click();
await page.waitForTimeout(2500);
await page.screenshot({path:SHOT+"01-desktop-library.png"});
async function addFile(name){
  await page.getByRole("button",{name:/^add/i}).first().click();
  await page.locator('input[type=file]').nth(2).setInputFiles({name,mimeType:"image/png",buffer:png});
}
// 1. offline upload
await ctx.setOffline(true);
await addFile(`j3r4-offline-${stamp}.png`);
await page.waitForTimeout(2000);
await page.screenshot({path:SHOT+"02-offline-waiting.png"});
const banner=await page.locator("text=/waiting/i").first().textContent().catch(()=>null);
console.log("offline banner:",banner);
await ctx.setOffline(false);
await page.waitForTimeout(8000);
await page.screenshot({path:SHOT+"03-back-online.png"});
// 2. lost response: server gets request, browser sees network failure
let lost=0;
await page.route("**/api/documents",async route=>{ if(route.request().method()==="POST"&&lost===0){lost++;const r=await route.fetch();console.log("server answered",r.status(),"- dropping response");await route.abort("failed");} else await route.continue();});
await addFile(`j3r4-lost-${stamp}.png`);
await page.waitForTimeout(2000);
const banner2=await page.locator("text=/waiting/i").first().textContent().catch(()=>null);
console.log("after lost response banner:",banner2);
await page.screenshot({path:SHOT+"04-lost-response-waiting.png"});
await ctx.setOffline(true);await page.waitForTimeout(500);await ctx.setOffline(false);
await page.waitForTimeout(8000);
const c=new Client();await c.login("judge3",PW.JUDGE3_PASSWORD);
for(const n of ["offline","lost"]){const r=await c.req("GET","/api/documents?q="+encodeURIComponent(`j3r4-${n}-${stamp}`));console.log(n,"copies:",(r.body.documents||[]).filter(d=>d.title.includes(`${stamp}`)).map(d=>d.title+"/"+d.status));}
const waitingLeft=await page.evaluate(()=>new Promise(res=>{const q=indexedDB.open("ripiano-uploads",1);q.onsuccess=()=>{const t=q.result.transaction("pending").objectStore("pending").getAll();t.onsuccess=()=>res(t.result.length)};q.onerror=()=>res(-1);}));
console.log("idb pending left",waitingLeft,"pageerrors",errs);
await browser.close();
