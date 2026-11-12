import { useState } from "react";
import { Copy, Link2, ShieldOff } from "lucide-react";
import { request } from "./api";
import { Button, Field } from "./ui";

type Share = { id: string; created_at: string; expires_at: string; revoked_at: string | null; active: boolean };
type CreatedShare = Share & { url: string };

export default function ShareLinksPanel({ documentId }: { documentId: string }) {
  const [opened, setOpened] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [shares, setShares] = useState<Share[]>([]);
  const [days, setDays] = useState(7);
  const [created, setCreated] = useState<CreatedShare | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    try {
      const result = await request<{ shares: Share[] }>(`/api/documents/${documentId}/shares`);
      setShares(result.shares);
      setLoaded(true);
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load share links");
    }
  }

  async function create() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await request<CreatedShare>(`/api/documents/${documentId}/shares`, {
        method: "POST", body: JSON.stringify({ expires_in_days: days }),
      });
      setCreated(result);
      await load();
      setNotice("Link created. Copy it now; Ripiano only shows it once.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create a share link");
    } finally {
      setBusy(false);
    }
  }

  async function revoke(id: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await request(`/api/documents/${documentId}/shares/${id}`, { method: "DELETE" });
      if (created?.id === id) setCreated(null);
      await load();
      setNotice("Link revoked. It can no longer download the file.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not revoke the link");
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    if (!created) return;
    try {
      await navigator.clipboard.writeText(created.url);
      setNotice("Link copied.");
    } catch {
      setError("Copy failed. Select the link in the field and copy it manually.");
    }
  }

  return <section className="share-panel" aria-labelledby="share-heading">
    <h3 id="share-heading"><Link2 size={17} /> Share original</h3>
    <p>Anyone holding a link can download the original without signing in. The link expires automatically, and you can revoke it sooner. Moving this document to Trash revokes its links.</p>
    <details open={opened} onToggle={(event) => {
      const next = event.currentTarget.open;
      setOpened(next);
      if (next && !loaded) void load();
    }}>
      <summary>Manage share links</summary>
      <div className="share-body">
        {error && <p className="inline-error" role="alert">{error}</p>}
        {notice && <p className="bulk-notice" role="status">{notice}</p>}
        <div className="share-controls">
          <Field label="Link expires after">
            <select value={days} onChange={(event) => setDays(Number(event.target.value))} disabled={busy}>
              <option value={1}>1 day</option><option value={7}>7 days</option><option value={30}>30 days</option>
            </select>
          </Field>
          <Button type="button" disabled={busy} onClick={() => void create()}>Create link</Button>
        </div>
        {created && <div className="share-created">
          <Field label="New share link — shown only once">
            <input readOnly value={created.url} onFocus={(event) => event.currentTarget.select()} />
          </Field>
          <Button type="button" variant="secondary" onClick={() => void copy()}><Copy size={16} /> Copy link</Button>
        </div>}
        {!loaded && <p>Loading links…</p>}
        {loaded && !shares.length && <p>No links created for this document.</p>}
        {shares.length > 0 && <ul className="share-list">
          {shares.map((share) => <li key={share.id}>
            <span>{share.active ? "Active" : share.revoked_at ? "Revoked" : "Expired"} · <time dateTime={share.expires_at}>Expires {new Date(share.expires_at).toLocaleString()}</time></span>
            {share.active && <button type="button" disabled={busy} onClick={() => void revoke(share.id)}><ShieldOff size={15} /> Revoke</button>}
          </li>)}
        </ul>}
      </div>
    </details>
  </section>;
}
