import { launch, login, shot, FX } from "./lib.mjs";
import fs from "node:fs";
const { browser, page, ctx } = await launch(true);
await login(page);
// offline upload
fs.copyFileSync(`${FX}/judge.png`, "./r4j1-offline.png");
await ctx.setOffline(true);
await page.getByRole("button",{name:/^(Add|Add document)$/}).first().tap();
await page.getByLabel("Choose from photos").setInputFiles("./r4j1-offline.png");
await page.waitForTimeout(3000);
const st = await page.locator("[role=status],[role=alert]").allInnerTexts(); console.log("OFFLINE STATUS:", st.filter(Boolean).join(" || "));
await shot(page,"46-m-offline-upload");
await ctx.setOffline(false);
await page.waitForTimeout(8000);
const st2 = await page.locator("[role=status],[role=alert]").allInnerTexts(); console.log("ONLINE STATUS:", st2.filter(Boolean).join(" || "));
await shot(page,"47-m-back-online");
// reload during queued? check doc exists
const r = await (await page.request.get("/api/documents?q=r4j1-offline")).json().catch(()=>({}));
console.log("search api:", (r.documents||[]).map(d=>`${d.title}:${d.status}`).join(", "));
const r2 = await (await page.request.get("/api/documents?q=r4j1-watched")).json().catch(()=>({}));
console.log("watched:", (r2.documents||[]).map(d=>`${d.title}:${d.status}:${d.source}`).join(", "));
await browser.close();
