import { launch, login, shot } from "./lib.mjs";
const { browser, page } = await launch(false);
await login(page);
for (let i=0;i<8;i++){ const r2 = await (await page.request.get("/api/documents?q=r4j1-watched")).json(); const l=(r2.documents||[]).map(d=>`${d.title}:${d.status}:${d.source}`); if (l.length){ console.log("watched:", l.join(", "), "after", i*10,"s"); break;} await page.waitForTimeout(10000); }
await page.getByRole("button",{name:"Sources",exact:true}).click(); await page.waitForTimeout(1200);
const t = await page.locator("main").innerText(); const i=t.indexOf("Connected storage"); console.log(t.slice(i,i+500).replace(/\n+/g," | "));
await shot(page,"48-source-card");
await browser.close();
