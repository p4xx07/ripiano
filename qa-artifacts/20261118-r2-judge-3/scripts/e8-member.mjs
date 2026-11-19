import { start, OUT } from "./pw.mjs";
import { Client, password } from "./api.mjs";
import fs from "node:fs";
const isoPw = fs.readFileSync("iso.env","utf8").trim().split("=")[1];
const { browser, page, errors } = await start({ user: "j3r2-iso", pw: isoPw });
const nav = await page.getByRole("navigation", { name: "Main navigation" }).ariaSnapshot();
console.log(nav.split("\n").filter(l => l.includes("button")).map(l => l.trim()).join(" | "));
await page.getByRole("button", { name: "Sources", exact: true }).click(); await page.waitForTimeout(800);
console.log("SOURCES (member):", (await page.locator("main").innerText()).slice(0, 600).replace(/\n/g, " | "));
// owner turns iso off while iso's page is open
const own = new Client(); await own.login("judge3", password());
const { isoId } = JSON.parse(fs.readFileSync("iso.json"));
const off = await own.req("PATCH", `/api/people/${isoId}`, { is_active: false, current_password: password() }); console.log("turn off", off.status);
await page.getByRole("button", { name: "All documents", exact: true }).click(); await page.waitForTimeout(1500);
console.log("after off, page shows:", (await page.locator("body").innerText()).slice(0, 300).replace(/\n/g, " | "));
await page.screenshot({ path: OUT + "10-member-after-account-turned-off.png" });
const iso2 = new Client(); const lg = await iso2.login("j3r2-iso", isoPw); console.log("login while off", lg.status, lg.data.error);
console.log("ERRORS", errors.slice(0, 5));
await browser.close();
