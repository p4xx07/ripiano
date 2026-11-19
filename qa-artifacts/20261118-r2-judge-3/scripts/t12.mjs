import { Client, password } from "./api.mjs";
const show = (label, h) => console.log(label, ["content-security-policy","x-frame-options","x-content-type-options","referrer-policy","cache-control","content-disposition"].map(k => k + "=" + (h.get(k) || "-").slice(0, 90)).join(" | "));
show("/", (await fetch("http://localhost:18080/")).headers);
const c = new Client(); const r = await c.login("judge3", password());
console.log("set-cookie flags:", r.headers.getSetCookie().map(s => s.replace(/=[^;]+/, "=***")).join(" || "));
const o = await c.req("GET", "/api/documents/1a143433-3380-44c5-956e-9d1a83064013/original", null, { raw: true }); show("original", o.headers);
const a = await c.req("GET", "/api/documents/043e3ea3-1dd6-4501-9287-7e40abae65dd/archive", null, { raw: true }); show("archive", a.headers);
show("schema", (await c.req("GET", "/api/schema.json")).headers);
const adm = await fetch("http://localhost:18080/admin/", { redirect: "manual" }); console.log("admin/", adm.status, adm.headers.get("location"));
