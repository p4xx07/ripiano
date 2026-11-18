import { launch, login } from "./lib.mjs";
const { browser, page } = await launch(false);
await login(page);
const r = await (await page.request.get("/api/documents?page_size=10")).json();
console.log(JSON.stringify(r.counts), Object.keys(r.documents[0]).join(","));
for (const d of r.documents.slice(0,5)) {
  const det = await (await page.request.get(`/api/documents/${d.id}`)).json();
  console.log("==", d.id, d.title, d.status, "| content:", JSON.stringify((det.content||det.text||"").slice(0,300)), "| keys:", Object.keys(det).join(","));
}
await browser.close();
