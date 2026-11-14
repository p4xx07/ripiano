import { useEffect, useState } from "react";
import { Check, Copy, Link2 } from "lucide-react";
import { request } from "./api";
import { Button, Field } from "./ui";

type Bundle = { id: string; title: string; documents: { id: string; title: string }[]; expires_at: string; downloads: number; active: boolean; status: "building" | "ready" | "failed" };

export default function BundlePanel({ selectedIds }: { selectedIds: string[] }) {
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
      setError(cause instanceof Error ? cause.message : "Could not load shared bundles");
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
      setError(cause instanceof Error ? cause.message : "Could not create the link");
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
      setError(cause instanceof Error ? cause.message : "Could not revoke the link");
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="bulk-filing-details" onToggle={(event) => { if (event.currentTarget.open && bundles === null) void load(); }}>
      <summary>Share as one link</summary>
      <div className="bulk-filing bundle-panel">
        <p>Anyone with the link can download the selected originals as one ZIP until it expires or you revoke it. Documents you move to Trash drop out.</p>
        {error && <p className="inline-error" role="alert">{error}</p>}
        <Field label="Name of the bundle" hint="Optional" className="detail-label"><input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={200} placeholder="e.g. Documents for the accountant" /></Field>
        <Field label="Expires after" className="detail-label">
          <select value={days} onChange={(event) => setDays(Number(event.target.value))}>
            {[1, 3, 7, 14, 30].map((value) => <option key={value} value={value}>{value} day{value === 1 ? "" : "s"}</option>)}
          </select>
        </Field>
        <Button type="button" variant="secondary" disabled={busy || !selectedIds.length || selectedIds.length > 50} onClick={() => void create()}>
          <Link2 size={16} aria-hidden="true" /> Create link for {selectedIds.length} {selectedIds.length === 1 ? "document" : "documents"}
        </Button>
        {url && (
          <div className="agent-token-row" role="status">
            <input aria-label="New bundle link" readOnly value={url} onFocus={(event) => event.target.select()} />
            <Button type="button" variant="secondary" onClick={() => void navigator.clipboard.writeText(url).then(() => setCopied(true)).catch(() => setError("Copy is unavailable here. Select and copy the link."))}>
              {copied ? <Check size={16} aria-hidden="true" /> : <Copy size={16} aria-hidden="true" />} {copied ? "Copied" : "Copy"}
            </Button>
          </div>
        )}
        {url && <small>Copy it now. Ripiano shows each link only once. The download works once the bundle is ready below.</small>}
        {selectedIds.length > 50 && <p className="inline-error">Choose 50 or fewer documents for one link.</p>}
        {bundles && bundles.some((item) => item.active) && (
          <ul className="bundle-list">
            {bundles.filter((item) => item.active).map((item) => (
              <li key={item.id}>
                <span>
                  <strong>{item.title}</strong> · {item.status === "building" ? "Preparing…" : item.status === "failed" ? "Could not be prepared: a file changed or is missing" : `downloaded ${item.downloads}×`} · expires {new Date(item.expires_at).toLocaleDateString()}
                  <small className="bundle-documents">{item.documents.map((document) => document.title).join(", ")}</small>
                </span>
                <Button type="button" variant="secondary" disabled={busy} onClick={() => void revoke(item)} aria-label={`Revoke bundle ${item.title}`}>Revoke</Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </details>
  );
}
