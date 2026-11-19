import { FormEvent, useEffect, useState } from "react";
import { ArrowRight, Link2, Search, X } from "lucide-react";
import { Document, request } from "./api";
import { Button } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/DocumentLinks";

type RelatedDocument = { id: string; title: string; created_at: string };

export default function DocumentLinks({ documentId, onOpenDocument }: { documentId: string; onOpenDocument: (id: string) => void }) {
  const m = useMessages(messages);
  const [links, setLinks] = useState<RelatedDocument[]>([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Document[]>([]);
  const [busy, setBusy] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [removeId, setRemoveId] = useState<string | null>(null);

  useEffect(() => {
    void request<{ links: RelatedDocument[] }>(`/api/documents/${documentId}/links`)
      .then((result) => setLinks(result.links))
      .catch((cause) => setError(cause instanceof Error ? cause.message : m.loadError));
  }, [documentId, m]);

  async function search(event: FormEvent) {
    event.preventDefault();
    if (query.trim().length < 2) return;
    setBusy(true);
    setError("");
    setSearched(false);
    try {
      const result = await request<{ documents: Document[] }>(`/api/documents?q=${encodeURIComponent(query.trim())}`);
      setResults(result.documents.filter((item) => item.id !== documentId));
      setSearched(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.searchError);
    } finally {
      setBusy(false);
    }
  }

  async function add(target: Document) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await request(`/api/documents/${documentId}/links`, { method: "POST", body: JSON.stringify({ document_id: target.id }) });
      const result = await request<{ links: RelatedDocument[] }>(`/api/documents/${documentId}/links`);
      setLinks(result.links);
      setResults([]);
      setQuery("");
      setSearched(false);
      setNotice(m.linked(target.title));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.linkError);
    } finally {
      setBusy(false);
    }
  }

  async function remove(target: RelatedDocument) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await request(`/api/documents/${documentId}/links/${target.id}`, { method: "DELETE" });
      setLinks((current) => current.filter((item) => item.id !== target.id));
      setRemoveId(null);
      setNotice(m.unlinked(target.title));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.unlinkError);
    } finally {
      setBusy(false);
    }
  }

  return <section className="document-links" aria-labelledby="document-links-heading">
    <h3 id="document-links-heading"><Link2 size={17} /> {m.heading}</h3>
    <p>{m.intro}</p>
    {error && <div className="inline-error" role="alert">{error}</div>}
    {notice && <p className="bulk-notice" role="status">{notice}</p>}
    {links.length ? <ul className="related-list">{links.map((item) => <li key={item.id}>
      <button type="button" className="related-open" onClick={() => onOpenDocument(item.id)}>{item.title} <ArrowRight size={16} /></button>
      {removeId === item.id ? <span className="related-remove"><button type="button" disabled={busy} onClick={() => void remove(item)}>{m.confirmUnlink}</button><button type="button" disabled={busy} onClick={() => setRemoveId(null)}>{m.cancel}</button></span> : <button type="button" aria-label={m.unlinkLabel(item.title)} disabled={busy} onClick={() => setRemoveId(item.id)}><X size={16} /></button>}
    </li>)}</ul> : <p>{m.empty}</p>}
    <form className="related-search" onSubmit={(event) => void search(event)}>
      <label htmlFor={`related-query-${documentId}`}>{m.findLabel}</label>
      <div><input id={`related-query-${documentId}`} value={query} onChange={(event) => { setQuery(event.target.value); setSearched(false); setResults([]); }} placeholder={m.searchPlaceholder} /><Button disabled={busy || query.trim().length < 2}><Search size={16} /> {m.search}</Button></div>
    </form>
    {searched && !results.length && <p>{m.noResults}</p>}
    {results.length > 0 && <ul className="related-results">{results.filter((item) => !links.some((link) => link.id === item.id)).slice(0, 10).map((item) => <li key={item.id}><span>{item.title}</span><Button type="button" variant="secondary" disabled={busy} onClick={() => void add(item)}>{m.link}</Button></li>)}</ul>}
  </section>;
}
