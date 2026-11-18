import fs from 'node:fs';import {Client,PW,BASE} from './lib.mjs';
const c=new Client();await c.login('judge3',PW.JUDGE3_PASSWORD);const ids=JSON.parse(fs.readFileSync('ids.json'));const X=JSON.parse(fs.readFileSync('xuser.json'));const o={};
const s=Date.now()%100000;
const L1=(await c.req('POST','/api/locations',{name:'j3r4 Shelf '+s})).body;const L2=(await c.req('POST','/api/locations',{name:'j3r4 Box '+s,parent_id:L1.id})).body;
const d=ids['three-pages.pdf'].id;
const cp=await c.req('POST','/api/documents/'+d+'/copies',{location_id:L2.id});o.copy=[cp.status,cp.body.sticker_code];
const sticker=cp.body.sticker_code;
o.lookup=(await c.req('GET','/api/stickers/'+encodeURIComponent(sticker))).body?.document?.title||JSON.stringify((await c.req('GET','/api/stickers/'+encodeURIComponent(sticker))).body).slice(0,120);
const mv=await c.req('PATCH','/api/copies/'+cp.body.id,{location_id:L1.id,note:'moved'});o.move=mv.status;
const lab=await fetch(BASE+'/api/copies/'+cp.body.id+'/label',{headers:{Cookie:c.cookie()}});o.label=[lab.status,lab.headers.get('content-type')];await lab.arrayBuffer();
o.hist=((await c.req('GET','/api/copies/'+cp.body.id+'/history')).body.movements||[]).length;
o.searchSticker=((await c.req('GET','/api/documents?q='+encodeURIComponent(sticker))).body.documents||[]).map(x=>x.title);
// cross account sticker lookup: reactivate x? x is deactivated; use x via reactivation
await c.req('PATCH','/api/people/'+X.id,{current_password:PW.JUDGE3_PASSWORD,is_active:true});
const x=new Client();await x.login(X.uname,X.upw);o.xSticker=(await x.req('GET','/api/stickers/'+encodeURIComponent(sticker))).status;o.xLoc=(await x.req('GET','/api/locations/'+L1.id)).status;o.xLabel=(await x.req('GET','/api/copies/'+cp.body.id+'/label')).status;
await c.req('PATCH','/api/people/'+X.id,{current_password:PW.JUDGE3_PASSWORD,is_active:false});
fs.writeFileSync('phys.json',JSON.stringify({sticker,copy:cp.body.id,L1:L1.id}));
console.log(JSON.stringify(o,null,1));
