import { launch, login, shot, text } from "./lib.mjs";
const { browser, page } = await launch(false);
await login(page);
await page.getByRole("button",{name:"Agents",exact:true}).click(); await page.waitForTimeout(1500);
await shot(page,"20-agents", true);
console.log((await page.locator("main").innerText()).replace(/\n+/g," | ").slice(0,5000));
const inputs = await page.locator("main input, main select, main textarea").evaluateAll(els=>els.map(e=>`${e.tagName}:${e.type}:${e.name}:${e.getAttribute("aria-label")||e.labels?.[0]?.innerText||""}`));
console.log(inputs.join("\n"));
await browser.close();
