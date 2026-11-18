import { launch, login } from "./lib.mjs";
const { browser, page } = await launch(false);
await login(page);
const f = async () => page.evaluate(()=>{const e=document.activeElement; return `${e.tagName}.${e.className}[${(e.getAttribute("aria-label")||e.innerText||"").trim().slice(0,30)}]`;});
for (const [label, act] of [["wait10s", async()=>page.waitForTimeout(10000)], ["tab60", async()=>{for(let i=0;i<60;i++) await page.keyboard.press("Tab");}], ["tab5", async()=>{for(let i=0;i<5;i++) await page.keyboard.press("Tab");}]]) {
  await page.getByRole("button",{name:"three-pages",exact:true}).first().focus(); await page.keyboard.press("Enter"); await page.waitForTimeout(1000);
  await act(); console.log(label, "focus before Esc:", await f());
  await page.keyboard.press("Escape"); await page.waitForTimeout(600); console.log(label, "->", await f());
}
await browser.close();
