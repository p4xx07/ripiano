import { launch, login } from "./lib.mjs";
import { client, T } from "./mcp.mjs";
const c = await client(T.tLocal);
console.log("before:", (await c.call("search_documents",{query:"lampone"})).status);
const { browser, page } = await launch(false);
await login(page);
await page.getByRole("button",{name:"Agents",exact:true}).click(); await page.waitForTimeout(1200);
for (const name of ["R4J1b Local","R4J1 Local","R4J1 Cloud"]) {
  const card = page.locator(".agent-card, article, li").filter({hasText: new RegExp(`^${name}\\s`)}).filter({has: page.getByRole("button",{name:"Revoke"})}).first();
  if (!(await card.count())) { console.log("no active card", name); continue; }
  await card.getByRole("button",{name:"Revoke"}).click(); await page.getByRole("button",{name:"Yes, revoke"}).click(); await page.waitForTimeout(1000);
  console.log("revoked", name);
}
await browser.close();
const r = await c.call("search_documents",{query:"lampone"}); console.log("same session after revoke:", r.status, JSON.stringify(r.data).slice(0,150));
const c2 = await client(T.tLocal); console.log("new session:", c2.init.status);
