import { launch, login, shot, OUT, BASE } from "./lib.mjs";
const { browser, page } = await launch(false);
await login(page);
await page.getByRole("button",{name:"Agents",exact:true}).click(); await page.waitForTimeout(1200);
async function create(name, perms, access) {
  await page.getByLabel("Name").fill(name);
  for (const p of ["Find document titles and tags","Read OCR text","Add or remove tags","Set sender and document type"]) {
    const cb = page.getByLabel(p, {exact:true}); if ((await cb.isChecked()) !== perms.includes(p)) await cb.click();
  }
  await page.getByLabel("Document access").selectOption({label: access});
  await page.getByRole("button",{name:/Create|Connect|Add agent/}).first().click(); await page.waitForTimeout(1500);
  const body = await page.locator("main").innerText();
  const vals = await page.locator("main input, main code, main textarea").evaluateAll(els=>els.map(e=>e.value||e.textContent||""));
  const tok = vals.find(v => /^[A-Za-z0-9_\-\.]{30,}$/.test(v.trim()))?.trim();
  const i = body.indexOf(name); console.log("AFTER CREATE:", body.slice(Math.max(0,body.indexOf("Connected agents")-600), body.indexOf("Connected agents")+50).replace(/\n+/g," | ").replace(tok||"@@@","<TOKEN>"));
  return tok;
}
const tLocal = await create("R4J1b Local", ["Find document titles and tags","Read OCR text","Add or remove tags"], "All your documents");
await page.screenshot({ path: `${OUT}/21-agent-token-masked.png`, mask: [page.locator("main input[readonly], main code, main textarea")] });
const tCloud = await create("R4J1b Cloud", ["Find document titles and tags"], "Only “Condominio” documents");
import fs from "node:fs";
fs.writeFileSync("/private/tmp/claude-501/-Users-debotta-dbrepos-ripiano/23569b07-51e7-4ab9-89ce-c4e342f5998a/scratchpad/j1/.tokens.json", JSON.stringify({tLocal, tCloud}), {mode:0o600});
console.log("tokens captured:", !!tLocal, tLocal?.length, !!tCloud, tCloud?.length);
await browser.close();
