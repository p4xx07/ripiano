import fs from "node:fs";
let T = {}; try { T = JSON.parse(fs.readFileSync(new URL("./.tokens.json", import.meta.url))); } catch {}
const URL_ = "http://localhost:18080/mcp";
async function rpc(tok, sess, body) {
  const h = {"Content-Type":"application/json", Accept:"application/json, text/event-stream", Authorization:`Bearer ${tok}`};
  if (sess) { h["Mcp-Session-Id"]=sess; h["MCP-Protocol-Version"]="2025-06-18"; }
  const r = await fetch(URL_, {method:"POST", headers:h, body: JSON.stringify(body)});
  const txt = await r.text(); let data=null;
  const m = txt.match(/^data: (.*)$/m); try { data = JSON.parse(m?m[1]:txt);} catch { data = txt.slice(0,200); }
  return { status:r.status, sess: r.headers.get("mcp-session-id"), data };
}
export async function client(tok) {
  const init = await rpc(tok, null, {jsonrpc:"2.0", id:1, method:"initialize", params:{protocolVersion:"2025-06-18", capabilities:{}, clientInfo:{name:"judge-client",version:"1"}}});
  if (init.status!==200) return { init };
  const s = init.sess; await rpc(tok, s, {jsonrpc:"2.0", method:"notifications/initialized"});
  let id=10;
  return { init, list: () => rpc(tok,s,{jsonrpc:"2.0",id:id++,method:"tools/list"}), call: (name,args) => rpc(tok,s,{jsonrpc:"2.0",id:id++,method:"tools/call",params:{name,arguments:args}}) };
}
export { T };
const mode = process.argv[1].endsWith("mcp.mjs") ? process.argv[2] : null;
const short = (x)=>JSON.stringify(x).slice(0,700);
if (mode==="probe") {
  for (const [k,tok] of Object.entries(T)) {
    const c = await client(tok); console.log(`== ${k} init`, c.init.status);
    if (!c.list) { console.log(short(c.init.data)); continue; }
    const l = await c.list(); console.log("tools:", l.data?.result?.tools?.map(t=>t.name).join(","));
    const s1 = await c.call("search_documents", {query:"mirtillo"}); console.log("search mirtillo:", short(s1.data));
    const s2 = await c.call("search_documents", {query:"9473"}); console.log("search 9473 (OCR only):", short(s2.data));
    const s3 = await c.call("search_documents", {query:"lampone"}); console.log("search lampone (Tasse doc):", short(s3.data));
    const g = await c.call("get_document_text", {document_id:"b3677ee0-6a5e-4ab8-8a58-4f376ad417f6"}); console.log("get_text:", short(g.data));
  }
}
if (mode==="after") {
  for (const [k,tok] of Object.entries(T)) { const c = await client(tok); console.log(`== ${k} init`, c.init.status, short(c.init.data).slice(0,200)); if (c.list){ const s=await c.call("search_documents",{query:"mirtillo"}); console.log(short(s.data).slice(0,200)); } }
}
