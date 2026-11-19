import { launch, login, shot } from "./lib.mjs";
const { browser, page } = await launch(false);
await login(page);
const f = async () => page.evaluate(()=>{const e=document.activeElement; return `${e.tagName}[${(e.getAttribute("aria-label")||e.innerText||e.placeholder||"").trim().slice(0,40)}]`;});
await page.keyboard.press("Tab"); console.log("tab1:", await f());
await page.keyboard.press("Enter"); await page.waitForTimeout(300); console.log("after skip:", await f());
await page.keyboard.press("/"); await page.waitForTimeout(200); console.log("after /:", await f());
await page.keyboard.type("lampone"); await page.keyboard.press("Enter"); await page.waitForTimeout(1500);
// tab to first result
let steps=0; for (; steps<25; steps++){ await page.keyboard.press("Tab"); const a = await f(); if (a.includes("Avviso TARI")) break; }
console.log("tabs to first result:", steps+1, await f());
const vis = await page.evaluate(()=>{const e=document.activeElement; const cs=getComputedStyle(e); return `outline=${cs.outlineStyle} ${cs.outlineWidth} ${cs.outlineColor} shadow=${cs.boxShadow.slice(0,60)}`;}); console.log("focus style:", vis);
await shot(page,"40-kbd-focus-result");
await page.keyboard.press("Enter"); await page.waitForTimeout(1200); console.log("in dialog focus:", await f());
let trap=[]; for (let i=0;i<60;i++){ await page.keyboard.press("Tab"); trap.push(await page.evaluate(()=>!!document.activeElement.closest("[role=dialog]"))); }
console.log("focus stayed in dialog for 60 tabs:", trap.every(Boolean));
await page.keyboard.press("Escape"); await page.waitForTimeout(500); console.log("after Esc focus:", await f(), "dialogs:", await page.getByRole("dialog").count());
// shortcut help?
await page.keyboard.press("?"); await page.waitForTimeout(500); console.log("? dialog:", await page.getByRole("dialog").count() ? (await page.getByRole("dialog").first().innerText()).slice(0,300).replace(/\n+/g," | ") : "none");
await page.keyboard.press("Escape");
await page.keyboard.press("a"); await page.waitForTimeout(500); console.log("'a' opens:", await page.getByRole("dialog").count() ? (await page.getByRole("dialog").first().innerText()).slice(0,60).replace(/\n+/g," | ") : "none");
await page.keyboard.press("Escape");
// axe-like quick checks: images without alt, buttons without names, inputs without labels
const a11y = await page.evaluate(()=>{ const r={}; r.imgNoAlt=[...document.images].filter(i=>!i.hasAttribute("alt")).length; r.btnNoName=[...document.querySelectorAll("button,a[href]")].filter(b=>!(b.getAttribute("aria-label")||b.innerText.trim()||b.title||b.getAttribute("aria-labelledby"))).map(b=>b.outerHTML.slice(0,80)); r.inputNoLabel=[...document.querySelectorAll("input:not([type=hidden]),select,textarea")].filter(i=>!(i.labels?.length||i.getAttribute("aria-label")||i.getAttribute("aria-labelledby"))).map(i=>i.outerHTML.slice(0,100)); r.lang=document.documentElement.lang; r.h1=[...document.querySelectorAll("h1")].map(h=>h.innerText); return r;});
console.log(JSON.stringify(a11y));
await browser.close();
