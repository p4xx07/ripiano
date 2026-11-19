import fs from 'node:fs';import crypto from 'node:crypto';import {Client,PW,BASE} from './lib.mjs';
const c=new Client();await c.login('judge3',PW.JUDGE3_PASSWORD);const o={};
const F='/Users/debotta/dbrepos/ripiano/apps/web/e2e/fixtures/three-pages.pdf';const buf=fs.readFileSync(F);
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const fd=new FormData();fd.append('document',new Blob([buf]),'j3r4-cancel.pdf');const u=await c.req('POST','/api/documents',fd);const id=u.body.id;
const cx=await c.req('POST','/api/documents/'+id+'/cancel-processing');o.cancel=[cx.status,JSON.stringify(cx.body).slice(0,150)];
await new Promise(r=>setTimeout(r,2000));let d=(await c.req('GET','/api/documents/'+id)).body;o.afterCancel=[d.status,d.error];
const rt=await c.req('POST','/api/documents/'+id+'/retry');o.retry=[rt.status,JSON.stringify(rt.body).slice(0,100)];
for(let i=0;i<30;i++){await new Promise(r=>setTimeout(r,2000));d=(await c.req('GET','/api/documents/'+id)).body;if(!['pending','processing'].includes(d.status))break;}
o.afterRetry=[d.status,d.error];
const rp=await c.req('POST','/api/documents/'+id+'/reprocess');o.reprocess=rp.status;
for(let i=0;i<30;i++){await new Promise(r=>setTimeout(r,2000));d=(await c.req('GET','/api/documents/'+id)).body;if(!['pending','processing'].includes(d.status))break;}
o.afterReprocess=d.status;
const orig=Buffer.from(await (await fetch(BASE+'/api/documents/'+id+'/original',{headers:{Cookie:c.cookie()}})).arrayBuffer());o.originalIntact=sha(orig)===sha(buf);
const jobs=await c.req('GET','/api/jobs');o.jobsKeys=Object.keys(jobs.body);o.jobsStatus=jobs.status;
// retry of failed trunc
d=(await c.req('GET','/api/documents/7e1f7a60-d4f7-47ab-912b-f89fdf8ada95')).body;o.truncAfterRetry=[d.status,d.error?.slice(0,80)];
// search checks
for(const q of ['otter','tag:'+JSON.parse(fs.readFileSync('grants.json')).tA.name,'lampone','mirtillo']){const r=await c.req('GET','/api/documents?q='+encodeURIComponent(q));o['q:'+q.slice(0,20)]=[r.status,(r.body.documents||[]).filter(x=>x.title.startsWith('j3r4')||/lampone|mirtillo/i.test(x.title)).map(x=>x.title).slice(0,4),r.body.error];}
// trashed doc hidden from agent C
console.log(JSON.stringify(o,null,1));
