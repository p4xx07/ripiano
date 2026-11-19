import { useEffect, useState } from "react";
import { Check, Copy, Link2 } from "lucide-react";
import { request } from "./api";
import { Button, Field } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/BundlePanel";

type Bundle = { id: string; title: string; documents: { id: string; title: string }[]; expires_at: string; downloads: number; active: boolean; status: "building" | "ready" | "failed" };

export default function BundlePanel({ selectedIds }: { selectedIds: string[] }) {
  const m = useMessages(messages);
  const [bundles, setBundles] = useState<Bundle[] | null>(null);
  const [title, setTitle] = useState("");
  const [days, setDays] = useState(7);
  const [url, setUrl] = useState("");
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // A link belongs to the selection it was made for.
  useEffect(() => { setUrl(""); setCopied(false); }, [selectedIds.join(",")]);
  useEffect(() => {
    if (!bundles?.some((item) => item.active && item.status === "building")) return;
    const timer = window.setTimeout(() => void load(), 2000);
    return () => window.clearTimeout(timer);
  }, [bundles]);

  async function load() {
    try {
      setBundles((await request<{ bundles: Bundle[] }>("/api/share-bundles")).bundles);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.loadError);
    }
  }

  async function create() {
    setBusy(true);
    setError("");
    setCopied(false);
    try {
      const result = await request<Bundle & { url: string }>("/api/share-bundles", {
        method: "POST", body: JSON.stringify({ document_ids: selectedIds, title, expires_in_days: days }),
      });
      setUrl(result.url);
      setTitle("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.createError);
    } finally {
      setBusy(false);
    }
  }

  async function revoke(bundle: Bundle) {
    setBusy(true);
    setError("");
    try {
      await request(`/api/share-bundles/${bundle.id}`, { method: "DELETE" });
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.revokeError);
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="bulk-filing-details" onToggle={(event) => { if (event.currentTarget.open && bundles === null) void load(); }}>
      <summary>{m.summary}</summary>
      <div className="bulk-filing bundle-panel">
        <p>{m.intro}</p>
        {error && <p className="inline-error" role="alert">{error}</p>}
        <Field label={m.name} hint={m.optional} className="detail-label"><input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={200} placeholder={m.namePlaceholder} /></Field>
        <Field label={m.expiresAfter} className="detail-label">
          <select value={days} onChange={(event) => setDays(Number(event.target.value))}>
            {[1, 3, 7, 14, 30].map((value) => <option key={value} value={value}>{m.days(value)}</option>)}
          </select>
        </Field>
        <Button type="button" variant="secondary" disabled={busy || !selectedIds.length || selectedIds.length > 50} onClick={() => void create()}>
          <Link2 size={16} aria-hidden="true" /> {m.createLink(selectedIds.length)}
        </Button>
        {url && (
          <div className="agent-token-row" role="status">
            <input aria-label={m.newLink} readOnly value={url} onFocus={(event) => event.target.select()} />
            <Button type="button" variant="secondary" onClick={() => void navigator.clipboard.writeText(url).then(() => setCopied(true)).catch(() => setError(m.copyUnavailable))}>
              {copied ? <Check size={16} aria-hidden="true" /> : <Copy size={16} aria-hidden="true" />} {copied ? m.copied : m.copy}
            </Button>
          </div>
        )}
        {url && <small>{m.copyNow}</small>}
        {selectedIds.length > 50 && <p className="inline-error">{m.tooMany}</p>}
        {bundles && bundles.some((item) => item.active) && (
          <ul className="bundle-list">
            {bundles.filter((item) => item.active).map((item) => (
              <li key={item.id}>
                <span>
                  <strong>{item.title}</strong> · {item.status === "building" ? m.preparing : item.status === "failed" ? m.failed : m.downloaded(item.downloads)} · {m.expires(new Date(item.expires_at).toLocaleDateString())}
                  <small className="bundle-documents">{item.documents.map((document) => document.title).join(", ")}</small>
                </span>
                <Button type="button" variant="secondary" disabled={busy} onClick={() => void revoke(item)} aria-label={m.revokeLabel(item.title)}>{m.revoke}</Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </details>
  );
}
