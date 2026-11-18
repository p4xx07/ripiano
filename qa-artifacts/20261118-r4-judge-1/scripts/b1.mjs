import { launch, login, shot } from "./lib.mjs";
const { browser, page } = await launch(false);
await login(page);
for (const [nav,name] of [["Backups","44-backups"],["Sources","45-sources"]]) {
 await page.getByRole("button",{name:nav,exact:true}).click(); await page.waitForTimeout(1500); await shot(page,name);
 console.log(`#### ${nav}:`, (await page.locator("main").innerText()).replace(/\n+/g," | ").slice(0,2200));
}
await browser.close();
