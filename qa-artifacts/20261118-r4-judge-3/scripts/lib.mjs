import fs from 'node:fs';
export const BASE='http://localhost:18080';
const env=fs.readFileSync('/private/tmp/claude-501/-Users-debotta-dbrepos-ripiano/23569b07-51e7-4ab9-89ce-c4e342f5998a/scratchpad/judges.env','utf8');
export const PW=Object.fromEntries(env.split('\n').filter(l=>l.includes('=')).map(l=>[l.split('=')[0].trim(),l.slice(l.indexOf('=')+1).trim()]));
export class Client{
  constructor(){this.jar={};}
  cookie(){return Object.entries(this.jar).map(([k,v])=>k+'='+v).join('; ');}
  store(r){const sc=r.headers.getSetCookie?.()||[];for(const c of sc){const [kv]=c.split(';');const i=kv.indexOf('=');this.jar[kv.slice(0,i)]=kv.slice(i+1);}}
  async req(method,path,body,extra={}){
    const h={Cookie:this.cookie(),Origin:BASE,Referer:BASE+'/',...extra};
    if(this.jar.csrftoken)h['X-CSRFToken']=this.jar.csrftoken;
    let b=body;
    if(body&&!(body instanceof FormData)&&typeof body!=='string'){b=JSON.stringify(body);h['Content-Type']='application/json';}
    const r=await fetch(BASE+path,{method,headers:h,body:b,redirect:'manual'});
    this.store(r);
    const t=await r.text();let j;try{j=JSON.parse(t)}catch{j=t.slice(0,300)}
    return {status:r.status,body:j,headers:r.headers};
  }
  async login(u,p){await this.req('GET','/api/session');return this.req('POST','/api/session',{username:u,password:p});}
}
export async function mcp(token,method,params={},extra={}){
  const r=await fetch(BASE+'/mcp',{method:'POST',headers:{'Content-Type':'application/json',Accept:'application/json, text/event-stream',...(token?{Authorization:'Bearer '+token}:{}),...extra},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params})});
  const t=await r.text();let j;try{j=JSON.parse(t)}catch{j=t.slice(0,300)}
  return {status:r.status,body:j};
}
