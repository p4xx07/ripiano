import { Client, password } from "./api.mjs";
import fs from "node:fs"; import net from "node:net"; import crypto from "node:crypto";
const c = new Client(); await c.login("judge3", password());
const FX = "/Users/debotta/dbrepos/ripiano/apps/web/e2e/fixtures/";
const count = async () => { let n = 0, cur = ""; for (;;) { const r = await c.req("GET", "/api/documents?q=j3r2-partial" + (cur ? "&cursor=" + cur : "")); n += r.data.documents.length; if (!r.data.next_cursor) break; cur = r.data.next_cursor; } return n; };
const before = await count();
// partial upload: send half of the multipart body then reset
const file = fs.readFileSync(FX + "three-pages.pdf");
const boundary = "----j3r2" + Date.now();
const head = Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="document"; filename="j3r2-partial.pdf"\r\nContent-Type: application/pdf\r\n\r\n`);
const tail = Buffer.from(`\r\n--${boundary}--\r\n`);
const body = Buffer.concat([head, file, tail]);
await new Promise(res => {
  const s = net.connect(18080, "localhost", () => {
    s.write(`POST /api/documents HTTP/1.1\r\nHost: localhost:18080\r\nCookie: ${c.cookieHeader()}\r\nX-CSRFToken: ${c.jar.csrftoken}\r\nOrigin: http://localhost:18080\r\nReferer: http://localhost:18080/\r\nContent-Type: multipart/form-data; boundary=${boundary}\r\nContent-Length: ${body.length}\r\n\r\n`);
    s.write(body.subarray(0, Math.floor(body.length / 2)));
    setTimeout(() => { s.destroy(); res(); }, 800);
  });
  s.on("error", () => res());
});
await new Promise(r => setTimeout(r, 3000));
console.log("partial upload: docs before", before, "after", await count());
// truncated-but-complete: declared length matches, but file content truncated (corrupt PDF)
const fd = new FormData(); fd.append("document", new Blob([file.subarray(0, Math.floor(file.length / 3))]), "j3r2-truncated.pdf");
const tr = await c.req("POST", "/api/documents", fd); console.log("truncated pdf upload", tr.status, tr.data.status || tr.data.error);
// Batch then cancel queued, then retry; original hash preserved across reprocess
const ids = [];
for (const f of ["asn-batch-desktop.pdf", "barcode-batch-desktop.pdf", "office-slides.pptx", "office-open.odt", "office-legacy.doc"]) { const f2 = new FormData(); f2.append("document", new Blob([fs.readFileSync(FX + f)]), "j3r2-cancel-" + f); const r = await c.req("POST", "/api/documents", f2); ids.push([f, r.data.id]); }
const cancels = [];
for (const [f, id] of ids.reverse()) { const r = await c.req("POST", `/api/documents/${id}/cancel-processing`); cancels.push(`${f}:${r.status}${r.data.error ? " " + r.data.error : ""}`); }
console.log("cancel results:", cancels);
const cancelled = ids.filter(([f, id]) => cancels.find(x => x.startsWith(f + ":200")));
await new Promise(r => setTimeout(r, 2000));
for (const [f, id] of cancelled) { const d = await c.req("GET", `/api/documents/${id}`); console.log("cancelled state", f, d.data.status, d.data.error); }
for (const [f, id] of cancelled) { const r = await c.req("POST", `/api/documents/${id}/retry`); console.log("retry", f, r.status, r.data.status || r.data.error); }
await new Promise(r => setTimeout(r, 20000));
for (const [f, id] of ids) { const d = await c.req("GET", `/api/documents/${id}`); console.log("final", f, d.data.status, d.data.title, (d.data.error||"").slice(0,60)); }
// reprocess preserves original bytes
const target = ids.find(([f]) => f === "office-open.odt")[1];
const h1 = crypto.createHash("sha256").update((await c.req("GET", `/api/documents/${target}/original`, null, { raw: true })).data).digest("hex");
const rp = await c.req("POST", `/api/documents/${target}/reprocess`); console.log("reprocess", rp.status, rp.data.status || rp.data.error);
const rp2 = await c.req("POST", `/api/documents/${target}/reprocess`); console.log("reprocess again while busy", rp2.status, rp2.data.error);
await new Promise(r => setTimeout(r, 15000));
const h2 = crypto.createHash("sha256").update((await c.req("GET", `/api/documents/${target}/original`, null, { raw: true })).data).digest("hex");
const fxh = crypto.createHash("sha256").update(fs.readFileSync(FX + "office-open.odt")).digest("hex");
console.log("original sha same before/after reprocess:", h1 === h2, "matches fixture:", h1 === fxh, (await c.req("GET", `/api/documents/${target}`)).data.status);
// failed doc retry (polyglot)
const pr = await c.req("POST", `/api/documents/28f4426e-3317-4bb2-ae28-3a6d9e48aad1/retry`); console.log("retry failed polyglot", pr.status, pr.data.status || pr.data.error);
await new Promise(r => setTimeout(r, 8000));
console.log("polyglot after retry", (await c.req("GET", `/api/documents/28f4426e-3317-4bb2-ae28-3a6d9e48aad1`)).data.status);
const jobs = await c.req("GET", "/api/jobs"); console.log("jobs", JSON.stringify(jobs.data).slice(0, 500));
