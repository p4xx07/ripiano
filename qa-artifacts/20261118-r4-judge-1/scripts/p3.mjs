import { launch, login } from "./lib.mjs";
import { client } from "./mcp.mjs";
const { browser, page } = await launch(false);
await login(page);
await page.getByRole("button",{name:"Agents",exact:true}).click(); await page.waitForTimeout(1200);
// new agent for session test
await page.getByLabel("Name").fill("R4J1e Session");
await page.getByRole("button",{name:"Create agent token"}).click(); await page.waitForTimeout(1500);
const vals = await page.locator("main input, main code, main textarea").evaluateAll(els=>els.map(e=>e.value||e.textContent||""));
const tok = vals.find(v => /^[A-Za-z0-9_\-\.]{30,}$/.test(v.trim()))?.trim();
const c = await client(tok); console.log("session before:", (await c.call("search_documents",{query:"lampone"})).status);
async function revoke(name){
  const b = page.getByRole("button",{name:`Revoke ${name}`,exact:true});
  if (!(await b.count())) { console.log("no active card", name); return; }
  await b.click(); await page.waitForTimeout(300); await page.getByRole("button",{name:"Yes, revoke"}).click(); await page.waitForTimeout(1000); console.log("revoked",name);
}
for (const n of ["R4J1e Session","R4J1d Session","R4J1c Session","R4J1b Local","R4J1 Local","R4J1 Cloud"]) await revoke(n);
const t = await page.locator("main").innerText(); for (const n of ["R4J1e Session","R4J1d Session","R4J1c Session","R4J1b Local","R4J1 Local","R4J1 Cloud"]) { const i=t.indexOf(n+"\n"); console.log(n, "=>", t.slice(i+n.length, i+n.length+30).replace(/\n+/g," ")); }
const r = await c.call("search_documents",{query:"lampone"}); console.log("same session after revoke:", r.status, JSON.stringify(r.data).slice(0,120));
await browser.close();
