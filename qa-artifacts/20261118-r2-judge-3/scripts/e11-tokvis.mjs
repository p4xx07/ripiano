import { start, OUT } from "./pw.mjs";
const { browser, page } = await start({ mobile: true });
const menu = page.getByRole("button", { name: /Menu/i }).first();
if (await menu.isVisible().catch(() => false)) await menu.click();
await page.getByRole("button", { name: "Agents", exact: true }).click(); await page.waitForTimeout(800);
await page.getByRole("textbox", { name: "Name" }).fill("j3r2-vis-agent");
const resp = page.waitForResponse(r => r.url().endsWith("/api/agents") && r.request().method() === "POST");
await page.getByRole("button", { name: /Create agent token/ }).tap();
const g = await (await resp).json(); await page.waitForTimeout(800);
const box = page.getByRole("textbox", { name: "New agent token" });
const inView = await box.evaluate(e => { const b = e.getBoundingClientRect(); return { top: Math.round(b.top), vh: innerHeight, visible: b.top >= 0 && b.bottom <= innerHeight }; });
console.log("token box after create:", inView, "scrollY", await page.evaluate(() => scrollY));
await page.screenshot({ path: OUT + "19-mobile-after-create-token-offscreen.png" });
// revoke via API for cleanup
const csrf = (await page.context().cookies()).find(c => c.name === "csrftoken").value;
console.log("cleanup revoke", (await page.request.delete(`/api/agents/${g.id}`, { headers: { "X-CSRFToken": csrf } })).status());
// desktop too
await browser.close();
