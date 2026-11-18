import { Client, password } from "./api.mjs";
import fs from "node:fs";
const isoPw = fs.readFileSync("iso.env","utf8").trim().split("=")[1];
const own = new Client(); await own.login("judge3", password());
const iso = new Client(); await iso.login("j3r2-iso", isoPw);
const D = "f9d4facf-2f0f-4a44-932b-87692bf33ac0";
const acc = (await own.req("GET", `/api/documents/${D}/access`)).data;
for (const gr of acc.grants.filter(x=>x.target.name==="j3r2-iso")) console.log("unshare", (await own.req("DELETE", `/api/documents/${D}/access/${gr.id}`)).status);
console.log("after detail", (await iso.req("GET", `/api/documents/${D}`)).status, "original", (await iso.req("GET", `/api/documents/${D}/original`)).status, "shared list", (await iso.req("GET","/api/documents?view=shared")).data.documents.length);
