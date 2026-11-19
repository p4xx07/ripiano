import { client, T } from "./mcp.mjs";
const short=(x)=>JSON.stringify(x).slice(0,400);
const c = await client(T.tCloud); console.log("cloud riunione:", short((await c.call("search_documents",{query:"riunione"})).data?.result?.structuredContent));
const l = await client(T.tLocal);
const tools = (await l.list()).data.result.tools; console.log("change_document_tags schema:", JSON.stringify(tools.find(t=>t.name==="change_document_tags").inputSchema).slice(0,400));
console.log("list_tags:", short((await l.call("list_tags",{})).data?.result?.structuredContent));
const r = await fetch("http://localhost:18080/mcp",{method:"POST",headers:{"Content-Type":"application/json",Accept:"application/json, text/event-stream"},body:JSON.stringify({jsonrpc:"2.0",id:1,method:"initialize",params:{protocolVersion:"2025-06-18",capabilities:{},clientInfo:{name:"x",version:"1"}}})});
console.log("no-token:", r.status);
const r2 = await fetch("http://localhost:18080/mcp",{method:"POST",headers:{"Content-Type":"application/json",Accept:"application/json, text/event-stream",Authorization:"Bearer bogus"+T.tLocal.slice(5)},body:"{}"}); console.log("bad token:", r2.status);
