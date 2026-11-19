import { Client, password } from "./api.mjs";
import fs from "node:fs";
const c = new Client(); await c.login("judge3", password());
const FX = "/Users/debotta/dbrepos/ripiano/apps/web/e2e/fixtures/";
async function up(path, name) {
  const fd = new FormData();
  fd.append("document", new Blob([fs.readFileSync(path)]), name);
  const r = await c.req("POST", "/api/documents", fd);
  return [r.status, typeof r.data === "object" ? (r.data.error || r.data.id + " " + r.data.status + " " + r.data.original_name) : String(r.data).slice(0,120)];
}
const out = {};
for (const [f, n] of [["bad/fake.pdf","fake.pdf"],["bad/evil.pdf.exe","evil.pdf.exe"],["bad/empty.pdf","empty.pdf"],["bad/page.png","page.png"],["bad/img.svg","img.svg"],["bad/polyglot.pdf","polyglot.pdf"],["bad/big.pdf","big.pdf"],["bad/anim.gif","anim.gif"],["bad/fake.pdf","../../../etc/j3r2-traversal.pdf"]]) {
  out[n] = await up(f, n);
}
// path traversal with a valid pdf
out["traversal-valid"] = await up(FX+"three-pages.pdf", "../../j3r2-trav/three-pages.pdf");
out["html-name"] = await up(FX+"judge.png", "<img src=x onerror=alert(1)>j3r2.png");
for (const f of ["three-pages.pdf","judge.png","office-letter.docx","email-notice.eml","outlook-notice.msg","office-sheet.xlsx"]) out["fx:"+f] = await up(FX+f, f);
// CSRF: POST without X-CSRFToken
const fd = new FormData(); fd.append("document", new Blob([fs.readFileSync(FX+"judge.png")]), "csrf.png");
const r = await fetch("http://localhost:18080/api/documents", {method:"POST", headers:{Cookie:c.cookieHeader()}, body:fd});
out["csrf-missing"] = [r.status, (await r.text()).slice(0,100)];
const r2 = await fetch("http://localhost:18080/api/documents", {method:"POST", headers:{Cookie:c.cookieHeader(), "X-CSRFToken": c.jar.csrftoken, Origin:"http://evil.example", Referer:"http://evil.example/"}, body:fd});
out["csrf-evil-origin"] = [r2.status, (await r2.text()).slice(0,100)];
console.log(JSON.stringify(out, null, 1));
