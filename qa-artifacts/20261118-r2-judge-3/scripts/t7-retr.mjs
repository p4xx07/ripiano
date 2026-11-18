import { Client, password } from "./api.mjs";
const c = new Client(); await c.login("judge3", password());
const txt = async id => { const d = (await c.req("GET", `/api/documents/${id}`)).data; return Object.entries(d).filter(([k,v]) => typeof v === "string" && v.length > 40 && /text|content/.test(k)).map(([k,v]) => k+": "+v.slice(0,160).replace(/\n/g," ")); };
console.log("png:", await txt("724c8e86-c969-46fa-92e3-9ed0edd64ab3"));
console.log("3p:", await txt("043e3ea3-1dd6-4501-9287-7e40abae65dd"));
const d = (await c.req("GET", `/api/documents/84b97330-3561-4164-a00f-62c8dfbac450`)).data; console.log(Object.keys(d).join(","));
for (const q of ["tributi", "\"Comune di Esempio\"", "sender:\"Comune di Esempio\"", "tag:j3r2-agentA", "date:2026-11", "date:2026-11-10", "lampone -mirtillo", "tag:j3r2-agentA OR tag:j3r2-agentB", "text:mirtillo", "is:failed"]) {
  const r = await c.req("GET", "/api/documents?q=" + encodeURIComponent(q)); console.log(q.padEnd(40), r.status, r.data.error || (r.data.documents || []).slice(0,6).map(x => x.title).join(" ; "));
}
