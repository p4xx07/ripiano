import { Client } from "./api.mjs";
import fs from "node:fs";
const isoPw = fs.readFileSync("iso.env","utf8").trim().split("=")[1];
const iso = new Client(); console.log((await iso.login("j3r2-iso", isoPw)).status);
const tags = (await iso.req("GET","/api/tags")).data; const tg = (tags.tags||tags).find(t=>t.name==="j3r2-iso-tag");
const acc = await iso.req("GET", `/api/object-access/tag/${tg.id}`); console.log(JSON.stringify(acc.data).slice(0,300));
for (const g of acc.data.grants||[]) console.log("del", (await iso.req("DELETE", `/api/object-access/tag/${tg.id}/${g.id}`)).status);
console.log("tag delete", (await iso.req("DELETE", `/api/tags/${tg.id}`)).status);
