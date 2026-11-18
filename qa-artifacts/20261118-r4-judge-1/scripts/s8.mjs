import { launch, login, shot, text } from "./lib.mjs";
const { browser, page } = await launch(false);
await login(page);
for (const [nav, name] of [["Inbox","12-inbox"],["Needs action","13-needs-action"],["Paper archive","14-paper-archive"]]) {
  await page.getByRole("button",{name:nav,exact:true}).click(); await page.waitForTimeout(1500);
  await shot(page, name);
  const t = await page.locator("main").innerText(); console.log(`##### ${nav}:\n`, t.slice(0,1800).replace(/\n+/g," | "));
}
await browser.close();
