import fs from 'node:fs';import crypto from 'node:crypto';import {Client,PW,mcp,BASE} from './lib.mjs';
const ids=JSON.parse(fs.readFileSync('ids.json'));const X=JSON.parse(fs.readFileSync('xuser.json'));const o={};
const c=new Client();const lg=await c.login('judge3',PW.JUDGE3_PASSWORD);
// cookie flags on login
o.loginSetCookie=(lg.headers.getSetCookie?.()||[]).map(s=>s.replace(/=[^;]+;/,'=***;'));
const d=ids['three-pages.pdf'].id;
for(const p of ['/original','/archive','/pages/1.png','/export']){const r=await fetch(BASE+'/api/documents/'+d+p,{headers:{Cookie:c.cookie()}});o['hdr'+p]=[r.status,r.headers.get('content-type'),r.headers.get('content-disposition'),r.headers.get('x-content-type-options'),r.headers.get('content-security-policy'),r.headers.get('cache-control')];await r.arrayBuffer();}
// share link
const sl=await c.req('POST','/api/documents/'+d+'/shares',{expires_in_days:1});o.shareCreate=sl.status;
const tok=sl.body.token||sl.body.url?.split('/').pop();
if(tok){const r=await fetch(BASE+'/api/share-links/'+tok);o.shareGet=[r.status,r.headers.get('cache-control'),r.headers.get('content-disposition'),r.headers.get('referrer-policy')];await r.arrayBuffer();
 o.shareRevoke=(await c.req('DELETE','/api/documents/'+d+'/shares/'+sl.body.id)).status;const r2=await fetch(BASE+'/api/share-links/'+tok);o.shareAfterRevoke=r2.status;}
else o.shareBody=JSON.stringify(sl.body).slice(0,200);
// x: agent + token; then password change + deactivate
const x=new Client();await x.login(X.uname,X.upw);
const xg=(await x.req('POST','/api/agents',{name:'xagent2',scopes:['documents:search'],expires_in_days:1})).body;
const xt=(await x.req('POST','/api/account/tokens',{password:X.upw,name:'xt2',expires_in_days:1})).body;
const newpw='Yy-'+crypto.randomBytes(12).toString('hex');
const pc=await x.req('POST','/api/account/password',{current_password:X.upw,new_password:newpw,password:newpw});o.pwChange=[pc.status,JSON.stringify(pc.body).slice(0,120)];
if(pc.status===200){X.upw=newpw;fs.writeFileSync('xuser.json',JSON.stringify(X));}
const tr=await fetch(BASE+'/api/documents',{headers:{Authorization:'Token '+xt.token}});o.tokenAfterPwChange=tr.status;
o.agentAfterPwChange=(await mcp(xg.token,'tools/list')).status;
// deactivate x
const dz=await c.req('PATCH','/api/people/'+X.id,{current_password:PW.JUDGE3_PASSWORD,is_active:false});o.deactivate=dz.status;
o.xSessionAfterDeactivate=(await x.req('GET','/api/documents')).status;
o.xAgentAfterDeactivate=(await mcp(xg.token,'tools/list')).status;
// throttle on x
const codes=[];for(let i=0;i<12;i++){const t=new Client();codes.push((await t.login(X.uname,'wrong'+i)).status);}o.throttle=codes.join(',');
console.log(JSON.stringify(o,null,1));
