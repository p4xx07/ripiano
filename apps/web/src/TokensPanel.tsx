import { FormEvent, useCallback, useEffect, useState } from "react";
import { Check, Copy, KeySquare } from "lucide-react";
import { request } from "./api";
import { Button, Field } from "./ui";

type Token = { id: string; name: string; prefix: string; created_at: string; expires_at: string; last_used_at: string | null; active: boolean };

export default function TokensPanel() {
  const [tokens, setTokens] = useState<Token[]>([]);
  const [name, setName] = useState("");
  const [days, setDays] = useState(90);
  const [password, setPassword] = useState("");
  const [created, setCreated] = useState("");
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setTokens((await request<{ tokens: Token[] }>("/api/account/tokens")).tokens);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load API tokens");
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setCopied(false);
    try {
      const result = await request<Token & { token: string }>("/api/account/tokens", {
        method: "POST", body: JSON.stringify({ name, expires_in_days: days, password }),
      });
      setCreated(result.token);
      setName("");
      setPassword("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create the token");
    } finally {
      setBusy(false);
    }
  }

  async function revoke(token: Token) {
    setBusy(true);
    try {
      await request(`/api/account/tokens/${token.id}`, { method: "DELETE" });
      if (created.startsWith(token.prefix)) setCreated("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not revoke the token");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="tokens-panel" aria-labelledby="tokens-heading">
      <div className="section-heading agent-activity-heading">
        <div>
          <h2 id="tokens-heading">API tokens</h2>
          <p>For your own scripts. A token acts with your access, but cannot change sign-in or security settings. <a href="/api/schema.json" target="_blank" rel="noreferrer">API reference (OpenAPI)</a></p>
        </div>
      </div>
      {error && <div className="inline-error" role="alert">{error}</div>}
      {created && (
        <div className="agent-token-card">
          <div className="agent-token-head"><KeySquare size={19} aria-hidden="true" /><strong>Copy this token now</strong></div>
          <p>It will not be shown again. Send it as <code>Authorization: Token …</code>.</p>
          <div className="agent-token-row">
            <input aria-label="New API token" readOnly value={created} onFocus={(event) => event.target.select()} />
            <Button type="button" variant="secondary" onClick={() => void navigator.clipboard.writeText(created).then(() => setCopied(true)).catch(() => setError("Copy is unavailable here. Select and copy the token."))}>
              {copied ? <Check size={16} aria-hidden="true" /> : <Copy size={16} aria-hidden="true" />} {copied ? "Copied" : "Copy"}
            </Button>
          </div>
        </div>
      )}
      {tokens.length > 0 && (
        <div className="agent-list">
          {tokens.map((token) => (
            <article className="agent-card mail-card" key={token.id}>
              <div className="agent-card-body">
                <strong>{token.name}{token.active ? "" : " · Expired"}</strong>
                <span><code>{token.prefix}…</code> · expires {new Date(token.expires_at).toLocaleDateString()} · {token.last_used_at ? `last used ${new Date(token.last_used_at).toLocaleString()}` : "never used"}</span>
              </div>
              <div className="mail-actions">
                <Button type="button" variant="secondary" disabled={busy} aria-label={`Revoke token ${token.name}`} onClick={() => void revoke(token)}>Revoke</Button>
              </div>
            </article>
          ))}
        </div>
      )}
      <form className="tokens-form" onSubmit={create} aria-label="New API token">
        <Field label="Token name" className="detail-label"><input value={name} onChange={(event) => setName(event.target.value)} maxLength={100} required placeholder="e.g. Backup script" /></Field>
        <Field label="Expires after" className="detail-label">
          <select value={days} onChange={(event) => setDays(Number(event.target.value))}>
            {[7, 30, 90, 180, 365].map((value) => <option key={value} value={value}>{value} days</option>)}
          </select>
        </Field>
        <Field label="Your password (to create a token)" className="detail-label"><input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></Field>
        <Button disabled={busy}>Create token</Button>
      </form>
    </section>
  );
}
