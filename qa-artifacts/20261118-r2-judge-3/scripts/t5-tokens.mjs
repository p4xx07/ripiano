import { Client, password } from "./api.mjs";
import fs from "node:fs";
let isoPw = fs.readFileSync("iso.env","utf8").trim().split("=")[1];
const { isoId, isoDoc } = JSON.parse(fs.readFileSync("iso.json"));
const own = new Client(); await own.login("judge3", password());
const iso = new Client(); await iso.login("j3r2-iso", isoPw);
const out = {};
out.noPw = (await iso.req("POST","/api/account/tokens",{name:"t"})).data.error;
const t = await iso.req("POST","/api/account/tokens",{name:"j3r2-tok", expires_in_days: 1, password: isoPw});
out.create = t.status + " prefix=" + t.data.prefix + " listHasToken=" + JSON.stringify((await iso.req("GET","/api/account/tokens")).data).includes(t.data.token);
const T = new Client(); T.bearer = null;
const tok = async (m, p, b) => { const h = { Authorization: "Token " + t.data.token }; let body=b; if (b && !(b instanceof FormData)) { body = JSON.stringify(b); h["Content-Type"]="application/json"; } const r = await fetch("http://localhost:18080"+p,{method:m,headers:h,body}); let d; try{d=await r.json()}catch{d={}}; return r.status + (d.error?" "+d.error:""); };
for (const [k,m,p,b] of [["docs","GET","/api/documents"],["tokens","GET","/api/account/tokens"],["mintToken","POST","/api/account/tokens",{name:"x",password:isoPw}],["session","GET","/api/session"],["logout","DELETE","/api/session"],["security","GET","/api/account/security"],["pwchange","POST","/api/account/password",{}],["people","GET","/api/people"],["agents","GET","/api/agents"],["shareLink","POST",`/api/documents/${isoDoc}/shares`,{days:3}],["access","POST",`/api/documents/${isoDoc}/access`,{user_id:1}],["accessGET","GET",`/api/documents/${isoDoc}/access`],["email","POST",`/api/documents/${isoDoc}/email`,{}],["bundles","POST","/api/share-bundles",{}],["mail","GET","/api/mail"],["sources","GET","/api/sources"],["workflows","GET","/api/workflows"],["exportDoc","GET",`/api/documents/${isoDoc}/export`],["patchDoc","PATCH",`/api/documents/${isoDoc}`,{title:"tok-renamed"}],["schema","GET","/api/schema.json"]]) out["tok_"+k] = await tok(m,p,b);
// upload via token (no CSRF)
const fd = new FormData(); fd.append("document", new Blob([fs.readFileSync("/Users/debotta/dbrepos/ripiano/apps/web/e2e/fixtures/judge.png")]), "tok-upload.png");
out.tok_upload = await tok("POST","/api/documents",fd);
// object-access (tag share) via token
const tg = await iso.req("POST","/api/tags",{name:"j3r2-iso-tag"});
out.tok_objectAccessShareTag = await tok("POST", `/api/object-access/tag/${tg.data.id}`, {user_id: 1, level: "view"});
out.badPrefix = await (async()=>{const r=await fetch("http://localhost:18080/api/documents",{headers:{Authorization:"Token rip_"+"A".repeat(43)}});return r.status})();
// revoke via UI endpoint, then use
const tokId = t.data.id;
// Password reset by admin revokes token: create second token first
const t2 = await iso.req("POST","/api/account/tokens",{name:"j3r2-tok2", expires_in_days: 1, password: isoPw});
out.revoke = (await iso.req("DELETE", `/api/account/tokens/${tokId}`)).status;
out.afterRevoke = await tok("GET","/api/documents");
// admin resets iso password
const newPw = isoPw + "Z9";
const reset = await own.req("PATCH", `/api/people/${isoId}`, {password: newPw, current_password: password()});
out.adminReset = reset.status;
fs.writeFileSync("iso.env", "ISO_PASSWORD="+newPw+"\n");
const r2 = await fetch("http://localhost:18080/api/documents",{headers:{Authorization:"Token "+t2.data.token}}); out.tok2AfterPwReset = r2.status;
out.isoOldSessionAfterReset = (await iso.req("GET","/api/session")).data.authenticated;
console.log(JSON.stringify(out,null,1));
