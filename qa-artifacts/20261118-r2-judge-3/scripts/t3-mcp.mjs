import { Client, password, BASE } from "./api.mjs";
import fs from "node:fs";
const c = new Client(); await c.login("judge3", password());
const mask = t => t ? t.slice(0,8)+"…" : t;
async function mcp(token, method, params = {}, extra = {}) {
  const headers = { "Content-Type": "application/json", Accept: "application/json, text/event-stream", ...(extra.headers||{}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const r = await fetch(BASE + "/mcp", { method: "POST", headers, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }) });
  const txt = await r.text(); let j; try { j = JSON.parse(txt) } catch { j = txt.slice(0,200) }
  return { status: r.status, body: j, www: r.headers.get("www-authenticate") };
}
const call = (t, name, args) => mcp(t, "tools/call", { name, arguments: args });
const tool = r => r.body?.result?.structuredContent ?? r.body?.result ?? r.body;
// tags
async function tag(name) { const r = await c.req("POST", "/api/tags", { name }); if (r.status === 201 || r.status===200) return r.data.id; const l = await c.req("GET","/api/tags"); return (l.data.tags||l.data).find(t=>t.name===name).id; }
const tA = await tag("j3r2-agentA"), tB = await tag("j3r2-agentB");
const [docA, docB, docN] = ["84b97330-3561-4164-a00f-62c8dfbac450","84e97c96-5d1a-4e0b-84c0-dfbfe80018c1","f9d4facf-2f0f-4a44-932b-87692bf33ac0"];
console.log("bulk A", (await c.req("POST","/api/documents/bulk-tags",{document_ids:[docA],tag_id:tA,action:"add"})).status);
console.log("bulk B", (await c.req("POST","/api/documents/bulk-tags",{document_ids:[docB],tag_id:tB,action:"add"})).status);
const gA = await c.req("POST","/api/agents",{name:"j3r2-reader-A", scopes:["documents:search","documents:text"], filter_tag_id:tA, expires_in_days:3});
const gB = await c.req("POST","/api/agents",{name:"j3r2-cloud-B", scopes:["documents:search","documents:tag"], filter_tag_id:tB, expires_in_days:3});
const gC = await c.req("POST","/api/agents",{name:"j3r2-filer-C", scopes:["documents:filing"], expires_in_days:1});
console.log("grants", gA.status, gB.status, gC.status, mask(gA.data.token));
const A = gA.data.token, B = gB.data.token, C = gC.data.token;
const out = {};
out.noauth = await mcp(null, "tools/list");
out.badtoken = await mcp("rpa_nottherealtoken", "tools/list");
out.apitokenAsBearer = await mcp("rip_whatever", "tools/list");
out.init = await mcp(A, "initialize", {protocolVersion:"2025-06-18", capabilities:{}, clientInfo:{name:"j3",version:"1"}});
for (const [k,t] of [["A",A],["B",B],["C",C]]) out["list"+k] = (await mcp(t,"tools/list")).body?.result?.tools?.map(x=>x.name) ?? (await mcp(t,"tools/list"));
out.A_search_all = tool(await call(A,"search_documents",{query:""})).documents?.map(d=>d.title);
out.A_search_text = tool(await call(A,"search_documents",{query:"TARI"})).documents?.map(d=>d.title);
out.A_text_own = JSON.stringify(tool(await call(A,"get_document_text",{document_id:docA}))).slice(0,200);
out.A_text_outside = tool(await call(A,"get_document_text",{document_id:docB}));
out.A_text_other_untagged = tool(await call(A,"get_document_text",{document_id:docN}));
out.A_tag_denied = tool(await call(A,"change_document_tags",{document_id:docA, add:[tB]}));
out.A_semantic = tool(await call(A,"semantic_search",{query:"rifiuti"}));
out.B_search_all = tool(await call(B,"search_documents",{query:""})).documents?.map(d=>d.title);
out.B_search_text_phrase = tool(await call(B,"search_documents",{query:"condominio"})).documents?.map(d=>d.title);
out.B_text_denied = tool(await call(B,"get_document_text",{document_id:docB}));
out.B_listtags_count = tool(await call(B,"list_tags",{})).tags?.length;
out.B_tag_outside = tool(await call(B,"change_document_tags",{document_id:docA, add:[tB]}));
out.B_tag_add_A_to_own = tool(await call(B,"change_document_tags",{document_id:docB, add:[tA]}));
out.A_sees_B_doc_now = tool(await call(A,"search_documents",{query:""})).documents?.map(d=>d.title);
out.B_remove_A = tool(await call(B,"change_document_tags",{document_id:docB, remove:[tA]}));
out.B_badargs = tool(await call(B,"change_document_tags",{document_id:"../../etc", add:"x"}));
out.C_filing = tool(await call(C,"list_filing_options",{})).correspondents?.length;
out.C_search_denied = tool(await call(C,"search_documents",{query:""}));
out.C_unknown = tool(await call(C,"delete_everything",{}));
// cross-origin request with valid token
out.A_evil_origin = (await mcp(A,"tools/list",{}, {headers:{Origin:"http://evil.example"}})).status;
out.A_evil_host = (await mcp(A,"tools/list",{}, {headers:{Host:"evil.example"}})).status;
// revoke B
console.log("revoke B", (await c.req("DELETE", `/api/agents/${gB.data.id}`)).status);
const rv = await mcp(B,"tools/list"); out.B_after_revoke = [rv.status, rv.www && rv.www.slice(0,80)];
out.B_after_revoke_call = (await call(B,"search_documents",{query:""})).status;
out.A_still = (await mcp(A,"tools/list")).body?.result?.tools?.length;
const ev = await c.req("GET","/api/agents/events");
out.events = ev.data.events.filter(e=>e.agent.startsWith("j3r2")).slice(0,25).map(e=>`${e.agent}|${e.action}|${e.outcome}|${e.document_id?e.document_id.slice(0,8):"-"}`);
const list = await c.req("GET","/api/agents");
out.grants = list.data.grants.filter(g=>g.name.startsWith("j3r2")).map(g=>`${g.name} revoked=${!!g.revoked_at} last=${!!g.last_used_at} json_has_token=${"token" in g}`);
// history of docB shows agent?
const h = await c.req("GET", `/api/documents/${docB}/history`); out.histB = JSON.stringify(h.data).slice(0,400);
fs.writeFileSync("grants.json", JSON.stringify({A, C, gA: gA.data.id, gC: gC.data.id, tA, tB}));
console.log(JSON.stringify(out, null, 1));
