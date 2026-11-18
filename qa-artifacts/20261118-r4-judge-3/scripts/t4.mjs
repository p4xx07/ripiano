import fs from 'node:fs';import {Client,PW,mcp,BASE} from './lib.mjs';
const c=new Client();await c.login('judge3',PW.JUDGE3_PASSWORD);
const ids=JSON.parse(fs.readFileSync('ids.json'));const o={};
const stamp=Date.now()%100000;
const tA=(await c.req('POST','/api/tags',{name:'j3r4-agentA-'+stamp,color:'#336699'})).body;
const tB=(await c.req('POST','/api/tags',{name:'j3r4-agentB-'+stamp,color:'#993366'})).body;
const tX=(await c.req('POST','/api/tags',{name:'j3r4-free-'+stamp,color:'#669933'})).body;
const dA=ids['three-pages.pdf'].id, dB=ids['judge.png'].id, dN=ids['office-letter.docx'].id;
o.tagA=(await c.req('POST','/api/documents/bulk-tags',{document_ids:[dA],tag_id:tA.id,action:'add'})).status;
o.tagB=(await c.req('POST','/api/documents/bulk-tags',{document_ids:[dB],tag_id:tB.id,action:'add'})).status;
const g=async(name,scopes,filter)=>(await c.req('POST','/api/agents',{name:name+'-'+stamp,scopes,filter_tag_id:filter,expires_in_days:1})).body;
const A=await g('j3r4-A',['documents:search','documents:text','documents:tag'],tA.id);
const B=await g('j3r4-B',['documents:search'],tB.id);
const C=await g('j3r4-C',['documents:search','documents:tag','documents:filing'],null);
o.grants=[A,B,C].map(x=>[x.name,x.scopes,x.filter_tag_name,!!x.token]);
const tools=async t=>((await mcp(t,'tools/list')).body.result?.tools||[]).map(x=>x.name);
o.toolsA=await tools(A.token);o.toolsB=await tools(B.token);o.toolsC=await tools(C.token);
const call=async(t,name,args)=>{const r=await mcp(t,'tools/call',{name,arguments:args});return r.body.result?.structuredContent??r.body;};
o.A_search=(await call(A.token,'search_documents',{query:''})).documents?.map(d=>d.title);
o.B_search=(await call(B.token,'search_documents',{query:''})).documents?.map(d=>d.title);
o.C_searchCount=(await call(C.token,'search_documents',{query:''})).documents?.length;
o.B_text_denied=await call(B.token,'get_document_text',{document_id:dB});
o.A_text_otherdoc=await call(A.token,'get_document_text',{document_id:dB});
o.A_text_own=JSON.stringify(await call(A.token,'get_document_text',{document_id:dA})).slice(0,160);
// cross-agent manipulation: C (no filter) tries to add tag A to doc N (would widen A's view) and remove tag B from dB (narrow B)
o.C_addTagA=await call(C.token,'change_document_tags',{document_id:dN,add:[tA.id]});
o.C_removeTagB=await call(C.token,'change_document_tags',{document_id:dB,remove:[tB.id]});
// A tries to add tag B to its own doc (would widen B's view to dA)
o.A_addTagB=await call(A.token,'change_document_tags',{document_id:dA,add:[tB.id]});
// A adds free tag ok
o.A_addFree=await call(A.token,'change_document_tags',{document_id:dA,add:[tX.id]});
// A removes its own filter tag from doc -> loses doc
o.A_removeOwn=await call(A.token,'change_document_tags',{document_id:dA,remove:[tA.id]});
o.A_afterRemove=(await call(A.token,'search_documents',{query:''})).documents?.length;
// restore via human
o.restore=(await c.req('POST','/api/documents/bulk-tags',{document_ids:[dA],tag_id:tA.id,action:'add'})).body;
o.A_afterRestore=(await call(A.token,'search_documents',{query:''})).documents?.length;
// search text leakage: B search by text phrase
o.B_textQuery=(await call(B.token,'search_documents',{query:'the'})).documents?.length;
// bad token / expired / wrong prefix
o.noAuth=(await mcp(null,'tools/list')).status;
o.apiTokenOnMcp=(await mcp('rip_xxxxx','tools/list')).status;
o.evilOrigin=(await mcp(A.token,'tools/list',{}, {Origin:'https://evil.example'})).status;
// revoke A
o.revoke=(await c.req('DELETE','/api/agents/'+A.id)).body;
o.A_afterRevoke=(await mcp(A.token,'tools/list')).status;
o.A_callAfterRevoke=(await mcp(A.token,'tools/call',{name:'search_documents',arguments:{query:''}})).status;
o.B_stillWorks=(await call(B.token,'search_documents',{query:''})).documents?.length;
// after A revoked, C can now add tag A? (revoked grant no longer guarded)
o.C_addTagA_afterRevoke=await call(C.token,'change_document_tags',{document_id:dN,add:[tA.id]});
const ev=(await c.req('GET','/api/agents/events')).body.events.filter(e=>e.agent.endsWith(String(stamp))).slice(0,30);
o.audit=ev.map(e=>`${e.agent}|${e.action}|${e.outcome}|${e.document_id?'doc':''}`);
fs.writeFileSync('grants.json',JSON.stringify({A:{id:A.id},B:{id:B.id,token:B.token},C:{id:C.id,token:C.token},tA,tB,tX,stamp}));
console.log(JSON.stringify(o,null,1));
