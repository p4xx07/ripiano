import { launch, login, shot, text } from "./lib.mjs";
const { browser, page } = await launch(false);
await login(page);
await page.getByRole("button", { name: "Avviso condominio mirtillo", exact: true }).first().click();
await page.waitForTimeout(2000);
const d = page.getByRole("dialog").first();
console.log((await d.innerText()).replace(/\n+/g," | ").slice(0,5000));
await shot(page,"15-detail-outlook-suggestions");
await browser.close();
