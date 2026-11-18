// Minimal cookie-jar API client for judge 3. Never prints secrets.
import fs from "node:fs";
export const BASE = "http://localhost:18080";
const ENV = "/private/tmp/claude-501/-Users-debotta-dbrepos-ripiano/23569b07-51e7-4ab9-89ce-c4e342f5998a/scratchpad/judges.env";
export function password(n = 3) {
  const line = fs.readFileSync(ENV, "utf8").split("\n").find(l => l.startsWith(`JUDGE${n}_PASSWORD=`));
  return line.slice(line.indexOf("=") + 1).trim();
}
export class Client {
  constructor() { this.jar = {}; this.bearer = null; }
  cookieHeader() { return Object.entries(this.jar).map(([k, v]) => `${k}=${v}`).join("; "); }
  store(res) {
    for (const c of res.headers.getSetCookie?.() || []) {
      const [kv] = c.split(";"); const i = kv.indexOf("=");
      this.jar[kv.slice(0, i)] = kv.slice(i + 1);
    }
  }
  async req(method, path, body, extra = {}) {
    const headers = { ...(extra.headers || {}) };
    if (this.bearer) headers.Authorization = `Bearer ${this.bearer}`;
    else {
      headers.Cookie = this.cookieHeader();
      if (this.jar.csrftoken) headers["X-CSRFToken"] = this.jar.csrftoken;
      headers.Origin = BASE; headers.Referer = BASE + "/";
    }
    let payload = body;
    if (body && !(body instanceof FormData) && typeof body !== "string") { payload = JSON.stringify(body); headers["Content-Type"] = "application/json"; }
    const res = await fetch(BASE + path, { method, headers, body: payload, redirect: "manual" });
    this.store(res);
    const ct = res.headers.get("content-type") || "";
    let data;
    if (extra.raw) data = Buffer.from(await res.arrayBuffer());
    else if (ct.includes("json")) data = await res.json(); else data = await res.text();
    return { status: res.status, data, headers: res.headers };
  }
  async login(username, pw) {
    await this.req("GET", "/api/session");
    if (!this.jar.csrftoken) { await this.req("GET", "/"); }
    return this.req("POST", "/api/session", { username, password: pw });
  }
}
