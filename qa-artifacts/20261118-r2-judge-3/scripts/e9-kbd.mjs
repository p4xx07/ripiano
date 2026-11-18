import { start, OUT } from "./pw.mjs";
const { browser, context, page, errors } = await start();
// Keyboard-only: G then letter to Agents? Show shortcut list
await page.keyboard.press("?"); await page.waitForTimeout(500);
const help = page.getByRole("dialog"); console.log("HELP:", (await help.innerText()).replace(/\n/g, " | ").slice(0, 700));
await page.keyboard.press("Escape");
// Tab from top: count tabs to reach Agents nav button
await page.locator("body").click({ position: { x: 5, y: 5 } }).catch(() => {});
await page.keyboard.press("Home");
let found = -1;
for (let i = 0; i < 40; i++) { await page.keyboard.press("Tab"); const t = await page.evaluate(() => document.activeElement?.textContent?.trim()); if (t === "Agents") { found = i + 1; break; } }
console.log("Tabs to Agents:", found);
await page.keyboard.press("Enter"); await page.waitForTimeout(800);
console.log("focus after nav:", await page.evaluate(() => `${document.activeElement?.tagName} ${document.activeElement?.textContent?.slice(0,40)}`));
// Keyboard create agent
const name = page.getByRole("textbox", { name: "Name" });
await name.focus(); await page.keyboard.type("j3r2-kbd-agent");
await page.keyboard.press("Tab"); // first checkbox
const seq = [];
for (let i = 0; i < 12; i++) { const d = await page.evaluate(() => { const a = document.activeElement; return `${a.tagName}:${a.getAttribute("type")||""}:${a.getAttribute("aria-label")||a.labels?.[0]?.textContent||a.textContent}`.slice(0,70); }); seq.push(d); if (d.includes("Read OCR")) await page.keyboard.press("Space"); if (d.startsWith("BUTTON") && /Create|Connect/.test(d)) break; await page.keyboard.press("Tab"); }
console.log("TAB SEQ:", seq.join(" -> "));
const resp = page.waitForResponse(r => r.url().endsWith("/api/agents") && r.request().method() === "POST");
await page.keyboard.press("Enter");
const r = await resp; console.log("created via keyboard", r.status());
await page.waitForTimeout(500);
const fo = await page.evaluate(() => `${document.activeElement?.tagName} ${document.activeElement?.getAttribute("aria-label")||""}`); console.log("focus after create:", fo);
const vis = await page.evaluate(() => { const a = document.activeElement; const s = getComputedStyle(a); return s.outlineStyle + " " + s.outlineWidth + " " + s.boxShadow.slice(0,40); }); console.log("focus style:", vis);
// revoke via keyboard
await page.getByRole("button", { name: "Revoke j3r2-kbd-agent" }).focus(); await page.keyboard.press("Enter"); await page.waitForTimeout(400);
console.log("focus on confirm:", await page.evaluate(() => document.activeElement?.textContent));
await page.screenshot({ path: OUT + "11-keyboard-revoke-confirm-focus.png", mask: [page.locator("input[readonly]")] });
await page.keyboard.press("Enter"); await page.waitForTimeout(800);
console.log("after kbd revoke focus:", await page.evaluate(() => `${document.activeElement?.tagName} ${document.activeElement?.textContent?.slice(0,40)}`));
// Sign out in another tab, then act in this tab
const p2 = await context.newPage(); await p2.goto("/"); await p2.getByRole("button", { name: "Sign out" }).click(); await p2.waitForTimeout(800);
const conf = p2.getByRole("dialog"); if (await conf.count()) { console.log("signout dialog:", (await conf.innerText()).replace(/\n/g," | ").slice(0,200)); }
await page.getByRole("button", { name: "All documents", exact: true }).click(); await page.waitForTimeout(1500);
console.log("other tab after sign-out shows sign-in?", await page.getByRole("button", { name: "Sign in" }).count(), (await page.locator("main").innerText().catch(()=>"")).slice(0,200).replace(/\n/g," | "));
console.log("ERRORS", errors.slice(0, 4));
await browser.close();
