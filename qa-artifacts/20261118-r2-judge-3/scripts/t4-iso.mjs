import { Client, password } from "./api.mjs";
import fs from "node:fs";
const isoPw = fs.readFileSync("iso.env","utf8").trim().split("=")[1];
const own = new Client(); await own.login("judge3", password());
const iso = new Client(); console.log("iso login", (await iso.login("j3r2-iso", isoPw)).status);
const g = JSON.parse(fs.readFileSync("grants.json"));
const D = "f9d4facf-2f0f-4a44-932b-87692bf33ac0"; // office-letter.docx owned by judge3
const out = {};
const probe = async (label, m, p, b) => { const r = await iso.req(m, p, b); out[label] = r.status + (r.data?.error ? " " + r.data.error : ""); };
const paths = [["detail","GET",`/api/documents/${D}`],["original","GET",`/api/documents/${D}/original`],["archive","GET",`/api/documents/${D}/archive`],["history","GET",`/api/documents/${D}/history`],["notes","GET",`/api/documents/${D}/notes`],["page1","GET",`/api/documents/${D}/pages/1.png`],["export","GET",`/api/documents/${D}/export`],["versions","GET",`/api/documents/${D}/versions`],["similar","GET",`/api/documents/${D}/similar`],["copies","GET",`/api/documents/${D}/copies`],["links","GET",`/api/documents/${D}/links`],["patch","PATCH",`/api/documents/${D}`,{title:"pwned"}],["trash","POST",`/api/documents/${D}/trash`],["purge","POST",`/api/documents/${D}/purge`],["reprocess","POST",`/api/documents/${D}/reprocess`],["share","POST",`/api/documents/${D}/shares`,{days:7}],["access","POST",`/api/documents/${D}/access`,{user_id:1,level:"edit"}],["tagpatch","PATCH",`/api/tags/${g.tA}`,{name:"pwned"}],["bulktag","POST","/api/documents/bulk-tags",{document_ids:[D],tag_id:g.tA,action:"add"}],["merge","POST","/api/documents/merge",{document_ids:[D]}],["versionFromDoc","POST",`/api/documents/${D}/versions/from-document`,{source_id:D}],["exportBulk","POST","/api/documents/export",{document_ids:[D]}],["agents","GET","/api/agents"],["agentsCreate","POST","/api/agents",{name:"x",scopes:["documents:search"]}],["backups","GET","/api/backups"],["backupCreate","POST","/api/backups",{}],["jobs","GET","/api/jobs"],["overview","GET","/api/overview"],["semanticSettings","GET","/api/semantic-settings"],["sources","GET","/api/sources"]];
for (const p of paths) await probe(...p);
const ppl = await iso.req("GET","/api/people"); out.peopleKeys = Object.keys(ppl.data.people[0]||{}).join(",") + " n=" + ppl.data.people.length;
const s = await iso.req("GET", "/api/documents?q=office-letter"); out.searchOwn = s.data.documents?.length;
const sv = await iso.req("GET", "/api/documents?view=shared"); out.sharedBefore = sv.data.documents?.length;
// MCP: try judge3 grant A against iso? n/a. Version from other's doc: iso uploads own doc then tries from-document with judge3 doc as source
const fd = new FormData(); fd.append("document", new Blob([fs.readFileSync("/Users/debotta/dbrepos/ripiano/apps/web/e2e/fixtures/judge.png")]), "iso-judge.png");
const up = await iso.req("POST","/api/documents", fd); const isoDoc = up.data.id; out.isoUpload = up.status;
out.isoDocFromOwner = (await own.req("GET", `/api/documents/${isoDoc}`)).status; // admin can't read member doc?
const vf = await iso.req("POST", `/api/documents/${isoDoc}/versions/from-document`, {source_id: D, document_id: D, source_document_id: D}); out.versionSteal = vf.status + " " + JSON.stringify(vf.data).slice(0,150);
const lk = await iso.req("POST", `/api/documents/${isoDoc}/links`, {target_id: D}); out.linkToForeign = lk.status + " " + JSON.stringify(lk.data).slice(0,120);
const mg = await iso.req("POST", `/api/documents/merge`, {document_ids: [isoDoc, D]}); out.mergeForeign = mg.status + " " + JSON.stringify(mg.data).slice(0,120);
// share view-only
const people = (await own.req("GET","/api/people")).data.people; const isoId = people.find(p=>p.username==="j3r2-iso").id;
const sh = await own.req("POST", `/api/documents/${D}/access`, {user_id: isoId, level: "view"}); out.shareView = sh.status;
out.sharedAfter = (await iso.req("GET","/api/documents?view=shared")).data.documents?.map(d=>d.title+"/"+d.access);
for (const p of [["v_detail","GET",`/api/documents/${D}`],["v_original","GET",`/api/documents/${D}/original`],["v_history","GET",`/api/documents/${D}/history`],["v_patch","PATCH",`/api/documents/${D}`,{title:"pwned"}],["v_trash","POST",`/api/documents/${D}/trash`],["v_note","POST",`/api/documents/${D}/notes`,{body:"iso note"}],["v_share","POST",`/api/documents/${D}/shares`,{days:7}],["v_reshare","POST",`/api/documents/${D}/access`,{user_id:isoId,level:"edit"}],["v_versionsteal","POST",`/api/documents/${isoDoc}/versions/from-document`,{source_id:D}],["v_customfield","GET",`/api/documents/${D}/custom-fields`],["v_email","POST",`/api/documents/${D}/email`,{to:"x@example.com"}]]) await probe(...p);
const vs = await iso.req("POST", `/api/documents/${isoDoc}/versions/from-document`, {source_document_id: D}); out.v_versionsteal2 = vs.status + " " + JSON.stringify(vs.data).slice(0,150);
// revoke share
const acc = (await own.req("GET", `/api/documents/${D}/access`)).data; out.accList = JSON.stringify(acc).slice(0,200);
const gid = (acc.grants||acc.access||[]).find(x=>x.user?.id===isoId || x.user_id===isoId)?.id;
out.unshare = (await own.req("DELETE", `/api/documents/${D}/access/${gid}`)).status;
out.after_unshare_detail = (await iso.req("GET", `/api/documents/${D}`)).status;
out.after_unshare_original = (await iso.req("GET", `/api/documents/${D}/original`)).status;
fs.writeFileSync("iso.json", JSON.stringify({isoId, isoDoc}));
console.log(JSON.stringify(out, null, 1));
