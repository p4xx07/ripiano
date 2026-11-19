import fs from 'node:fs';import {Client,PW} from './lib.mjs';
const c=new Client();await c.login('judge3',PW.JUDGE3_PASSWORD);
const b=await c.req('POST','/api/backups',{});console.log('backup start',b.status,b.body);
const b2=await c.req('POST','/api/backups',{});console.log('second click',b2.status,b2.body);
const id=b.body.id||b2.body.id;
for(let i=0;i<40;i++){await new Promise(r=>setTimeout(r,3000));const runs=(await c.req('GET','/api/backups')).body.runs;const run=runs.find(r=>r.id===id);if(i%5==0||!['pending','running'].includes(run.status))console.log(i,run.status,run.snapshot_name,run.error);if(!['pending','running'].includes(run.status))break;}
const ids=JSON.parse(fs.readFileSync('ids.json'));
const fail='7e1f7a60-d4f7-47ab-912b-f89fdf8ada95';
console.log('retry failed',(await c.req('POST','/api/documents/'+fail+'/retry')).status);
const st={};for(const [f,v] of Object.entries(ids)){const r=await c.req('GET','/api/documents/'+v.id);st[f]=r.body.status+'/'+(r.body.error||'').slice(0,40);}console.log(st);
