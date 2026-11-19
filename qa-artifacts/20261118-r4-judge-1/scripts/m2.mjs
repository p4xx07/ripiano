import { launch, login } from "./lib.mjs";
const { browser, page } = await launch(true);
await login(page);
const info = await page.getByRole("button",{name:"Avviso condominio mirtillo",exact:true}).first().evaluate(b => { const out=[]; let e=b; for (let i=0;i<4&&e;i++){ const cs=getComputedStyle(e); out.push(`${e.tagName}.${e.className} ov=${cs.overflow} to=${cs.textOverflow} ws=${cs.whiteSpace} w=${Math.round(e.getBoundingClientRect().width)} sw=${e.scrollWidth}`); e=e.parentElement;} return out; });
console.log(info.join("\n"));
await browser.close();
