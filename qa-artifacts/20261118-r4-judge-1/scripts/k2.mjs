import { launch, login } from "./lib.mjs";
const { browser, page } = await launch(false);
await login(page);
const f = async () => page.evaluate(()=>{const e=document.activeElement; return `${e.tagName}.${e.className}[${(e.getAttribute("aria-label")||e.innerText||"").trim().slice(0,30)}]`;});
async function trial(label, prep) {
  await prep(); await page.keyboard.press("Enter"); await page.waitForTimeout(1200);
  await page.keyboard.press("Escape"); await page.waitForTimeout(600); console.log(label, "->", await f());
}
await trial("tab-no-search", async()=>{ await page.locator("h1").click(); for(let i=0;i<40;i++){ await page.keyboard.press("Tab"); if ((await f()).includes("document-title-button")) break; } console.log(" focused", await f()); });
await trial("click-then-close-button", async()=>{ await page.getByRole("button",{name:"three-pages",exact:true}).first().focus(); });
const s = page.getByPlaceholder(/Search text/).first(); await s.fill("lampone"); await s.press("Enter"); await page.waitForTimeout(1500);
await trial("search+j", async()=>{ await page.locator("h1").click(); await page.keyboard.press("j"); console.log(" focused", await f()); });
await trial("search+focus", async()=>{ await page.getByRole("button",{name:"Avviso TARI 2026 lampone",exact:true}).first().focus(); });
await browser.close();
