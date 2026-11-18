import { client, T } from "./mcp.mjs";
const short=(x)=>JSON.stringify(x).slice(0,300);
const l = await client(T.tLocal); const doc="f5c2c6f3-bcbd-47de-a1c7-6a3fdcfa8941";
console.log("add Condominio (guard tag):", short((await l.call("change_document_tags",{document_id:doc, add:["7be38a51-8cc6-4759-a1be-32ba9155c99e"]})).data?.result));
console.log("add Tasse:", short((await l.call("change_document_tags",{document_id:doc, add:["e4d217ee-0c6c-47ae-982e-cfe5921a75e3"]})).data?.result?.structuredContent));
console.log("remove Tasse:", short((await l.call("change_document_tags",{document_id:doc, remove:["e4d217ee-0c6c-47ae-982e-cfe5921a75e3"]})).data?.result?.structuredContent));
