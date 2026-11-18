import { start, OUT } from "./pw.mjs";
import fs from "node:fs";
const FX = "/Users/debotta/dbrepos/ripiano/apps/web/e2e/fixtures/";
const { browser, context, page, errors } = await start();
const countDocs = async () => { const r = await page.request.get("/api/overview"); const j = await r.json(); return j.documents ?? j.totals?.documents ?? JSON.stringify(j).slice(0,80); };
const openAdd = async () => { await page.getByRole("button", { name: "Add document", exact: true }).click(); await page.waitForTimeout(400); };
await openAdd();
console.log((await page.getByRole("dialog").ariaSnapshot()).slice(0, 1500));
// 1. Mixed valid/invalid batch
let chooser = page.waitForEvent("filechooser");
await page.getByRole("button", { name: /Browse files/ }).click();
await (await chooser).setFiles([{ name: "j3r2-fake.pdf", mimeType: "application/pdf", buffer: fs.readFileSync("bad/fake.pdf") }, { name: "j3r2-empty.pdf", mimeType: "application/pdf", buffer: Buffer.alloc(0) }, { name: "j3r2-valid-tag-barcode.pdf", mimeType: "application/pdf", buffer: fs.readFileSync(FX + "tag-barcode-desktop.pdf") }]);
await page.waitForTimeout(3000);
console.log("REPORT:", (await page.locator("body").innerText()).split("\n").filter(l => /j3r2|upload|reject|waiting|Use PDF|empty/i.test(l)).slice(0, 15));
await page.screenshot({ path: OUT + "07-mixed-batch-report.png" });
await page.keyboard.press("Escape");
// 2. Offline upload
await page.reload(); await page.waitForLoadState("networkidle");
await openAdd();
await context.setOffline(true);
chooser = page.waitForEvent("filechooser");
await page.getByRole("button", { name: /Browse files/ }).click();
await (await chooser).setFiles({ name: "j3r2-offline-judge.png", mimeType: "image/png", buffer: fs.readFileSync(FX + "judge.png") });
await page.waitForTimeout(1500);
console.log("OFFLINE:", (await page.locator("body").innerText()).split("\n").filter(l => /waiting|offline|connection|j3r2/i.test(l)).slice(0, 8));
await page.screenshot({ path: OUT + "08-offline-upload-waiting.png" });
// reload while offline? Simulate closing the app: go online after a fresh page load
await context.setOffline(false);
const up = page.waitForResponse(r => r.url().endsWith("/api/documents") && r.request().method() === "POST", { timeout: 30000 }).catch(() => null);
await page.evaluate(() => window.dispatchEvent(new Event("online")));
const ur = await up; console.log("OFFLINE resend:", ur && ur.status());
await page.waitForTimeout(1500);
console.log("after online:", (await page.locator("body").innerText()).split("\n").filter(l => /waiting/i.test(l)).slice(0, 4));
// 3. Lost response: server receives, client sees network failure
await page.keyboard.press("Escape");
let lost = 0;
await page.route("**/api/documents", async route => {
  if (route.request().method() === "POST" && lost === 0) { lost++; await route.fetch(); await route.abort("connectionreset"); return; }
  await route.continue();
});
await openAdd();
chooser = page.waitForEvent("filechooser");
await page.getByRole("button", { name: /Browse files/ }).click();
const lostName = `j3r2-lost-${Date.now()}.pdf`;
await (await chooser).setFiles({ name: lostName, mimeType: "application/pdf", buffer: fs.readFileSync(FX + "three-pages.pdf") });
await page.waitForTimeout(2000);
console.log("LOST:", (await page.locator("body").innerText()).split("\n").filter(l => /waiting|could not|fail|retry|j3r2-lost/i.test(l)).slice(0, 8));
await page.screenshot({ path: OUT + "09-lost-response-queued.png" });
await page.evaluate(() => window.dispatchEvent(new Event("online")));
await page.waitForTimeout(5000);
await page.unroute("**/api/documents");
const list = await (await page.request.get("/api/documents?q=" + encodeURIComponent(lostName.replace(".pdf","")))).json();
console.log("LOST copies stored:", list.documents?.length, list.documents?.map(d => d.title + " dup=" + !!d.duplicate_of));
const pend = await page.evaluate(async () => new Promise(res => { const r = indexedDB.open("ripiano-uploads", 1); r.onsuccess = () => { const tx = r.result.transaction("pending", "readonly"); const g = tx.objectStore("pending").getAll(); g.onsuccess = () => res(g.result.map(x => x.name)); }; r.onerror = () => res("err"); }));
console.log("IndexedDB pending:", pend);
console.log("ERRORS", errors);
await browser.close();
