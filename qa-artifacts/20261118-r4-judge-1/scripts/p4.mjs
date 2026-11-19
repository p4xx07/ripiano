import { launch, login } from "./lib.mjs";
const { browser, page } = await launch(false);
await login(page);
await page.getByRole("button",{name:"Agents",exact:true}).click(); await page.waitForTimeout(1200);
console.log(await page.getByRole("button",{name:/Revoke/}).evaluateAll(bs=>bs.map(b=>b.getAttribute("aria-label")+"|"+b.innerText)));
await browser.close();
