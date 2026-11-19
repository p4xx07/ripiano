import fs from 'node:fs';import crypto from 'node:crypto';
import {Client,PW} from './lib.mjs';
const F='/Users/debotta/dbrepos/ripiano/apps/web/e2e/fixtures/';
const c=new Client();await c.login('judge3',PW.JUDGE3_PASSWORD);
const out={};
async function up(name,buf,fname,headers={}){const fd=new FormData();fd.append('document',new Blob([buf]),fname);const r=await c.req('POST','/api/documents',fd,headers);return {status:r.status,id:r.body.id,err:r.body.error,title:r.body.title,dup:r.body.duplicate_of};}
// upload validation
out.empty=await up('e',Buffer.alloc(0),'empty.pdf');
out.htmlAsPdf=await up('h',Buffer.from('<html><script>alert(1)</script></html>'),'evil.pdf');
out.svg=await up('s',Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>'),'x.png');
out.truncPdf=await up('t',Buffer.from('%PDF-1.4\n garbage no xref'),'trunc.pdf');
out.traversal=await up('p',fs.readFileSync(F+'judge.png'),'../../../etc/j3r4-trav.png');
out.zipAsDocx=await up('z',Buffer.from('PK\x03\x04garbage'),'bad.docx');
// fixtures with web scan id
const ids={};
for(const f of fs.readdirSync(F)){const sid=crypto.randomUUID();const r=await up(f,fs.readFileSync(F+f),'j3r4-'+f,{'X-Ripiano-Scan-ID':sid,'X-Ripiano-Client':'web'});ids[f]={...r,sid};}
out.fixtures=Object.fromEntries(Object.entries(ids).map(([k,v])=>[k,[v.status,v.id,v.err]]));
// lost response retry: re-send same scan id
const f0='three-pages.pdf';const re=await up(f0,fs.readFileSync(F+f0),'j3r4-'+f0,{'X-Ripiano-Scan-ID':ids[f0].sid,'X-Ripiano-Client':'web'});
out.retrySameScan={status:re.status,sameId:re.id===ids[f0].id};
// concurrent duplicate submissions with same scan id
const sid2=crypto.randomUUID();const buf=fs.readFileSync(F+'judge.png');
const rs=await Promise.all([1,2,3,4].map(()=>up('c',buf,'j3r4-concurrent.png',{'X-Ripiano-Scan-ID':sid2,'X-Ripiano-Client':'web'})));
out.concurrent=rs.map(r=>[r.status,r.id,r.err]);
fs.writeFileSync('ids.json',JSON.stringify(ids,null,1));
console.log(JSON.stringify(out,null,1));
