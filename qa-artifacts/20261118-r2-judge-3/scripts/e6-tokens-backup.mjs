import { start, OUT } from "./pw.mjs";
import { BASE, password } from "./api.mjs";
const { browser, page, errors } = await start();
await page.getByRole("button", { name: "Security", exact: true }).click();
await page.getByRole("textbox", { name: "Token name" }).fill("j3r2-ui-token");
await page.getByRole("combobox", { name: "Expires after" }).selectOption({ label: "7 days" });
await page.getByRole("textbox", { name: /Your password \(to create/ }).fill("wrong-password-123");
await page.getByRole("button", { name: "Create token" }).click();
await page.waitForTimeout(700);
console.log("wrong pw msg:", await page.locator("[role=alert], [role=status]").allInnerTexts());
await page.getByRole("textbox", { name: /Your password \(to create/ }).fill(password());
const resp = page.waitForResponse(r => r.url().endsWith("/api/account/tokens") && r.request().method() === "POST" && r.status() === 201);
await page.getByRole("button", { name: "Create token" }).click();
const token = (await (await resp).json()).token;
await page.waitForTimeout(600);
console.log("pw field cleared:", await page.getByRole("textbox", { name: /Your password \(to create/ }).inputValue() === "");
const region = page.getByRole("region", { name: "API tokens" });
console.log((await region.ariaSnapshot()).replaceAll(token, "rip_***MASKED***").slice(0, 1500));
await region.screenshot({ path: OUT + "05-api-token-created-masked.png", mask: [page.locator("input[readonly], code, pre"), page.getByText(token)] });
const use = async () => (await fetch(BASE + "/api/documents?q=judge", { headers: { Authorization: "Token " + token } })).status;
console.log("token use", await use());
const revoke = region.getByRole("button", { name: /Revoke/ }).first();
await revoke.click(); await page.waitForTimeout(500);
const conf = region.getByRole("button", { name: /Yes|Confirm|Revoke/ }).first();
if (await conf.count()) { await conf.click(); await page.waitForTimeout(800); }
console.log("after revoke", await use());
// Backups
await page.getByRole("button", { name: "Backups", exact: true }).click();
const bresp = page.waitForResponse(r => r.url().endsWith("/api/backups") && r.request().method() === "POST");
await page.getByRole("button", { name: "Back up now" }).click();
const b = await bresp; const bj = await b.json(); console.log("backup POST", b.status(), bj.status, bj.error || "");
const t0 = Date.now(); let st = "";
for (let i = 0; i < 60; i++) {
  const r = await page.request.get("/api/backups"); const run = (await r.json()).runs.find(x => x.id === (bj.id));
  st = run?.status + " " + (run?.snapshot_name || "") + " " + (run?.error || "");
  if (run && !["pending", "running"].includes(run.status)) break;
  await page.waitForTimeout(3000);
}
console.log("backup final", st, Math.round((Date.now() - t0) / 1000) + "s");
await page.getByRole("button", { name: "Refresh" }).first().click().catch(() => {});
await page.reload(); await page.waitForLoadState("networkidle");
await page.getByRole("button", { name: "Backups", exact: true }).click(); await page.waitForTimeout(1000);
await page.screenshot({ path: OUT + "06-backup-after-manual-run.png" });
// double click race
const [x, y] = await Promise.all([page.request.post("/api/backups", { headers: { "X-CSRFToken": (await page.context().cookies()).find(c => c.name === "csrftoken").value } }), page.request.post("/api/backups", { headers: { "X-CSRFToken": (await page.context().cookies()).find(c => c.name === "csrftoken").value } })]);
console.log("double POST", x.status(), y.status());
console.log("ERRORS", errors);
await browser.close();
