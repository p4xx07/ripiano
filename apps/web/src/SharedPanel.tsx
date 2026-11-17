import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { FileText, RotateCcw, Search, Users } from "lucide-react";
import { Document, formatDate, request } from "./api";
import { Button } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/SharedPanel";

type Chip = { key: string; label: string; kind: string; owner: string; params: Record<string, string> };

export default function SharedPanel({ refreshKey, onOpenDocument }: {
  refreshKey: number;
  onOpenDocument: (document: Document) => void;
}) {
  const m = useMessages(messages);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [applied, setApplied] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const latestRequest = useRef(0);
  const [shared, setShared] = useState<Chip[]>([]);
  const [chip, setChip] = useState<Chip | null>(null);
  useEffect(() => {
    type Item = { id: string; name: string; owner: { name: string }; query?: string; tag_id?: string | null; correspondent_id?: string | null;
      document_type_id?: string | null; date_from?: string | null; date_to?: string | null };
    request<{ tags: Item[]; correspondents: Item[]; document_types: Item[]; saved_views: Item[] }>("/api/shared-filing").then((all) => {
      const pick = (item: Item) => Object.fromEntries(Object.entries({ q: item.query, tag_id: item.tag_id, correspondent_id: item.correspondent_id,
        document_type_id: item.document_type_id, date_from: item.date_from, date_to: item.date_to }).filter(([, value]) => value)) as Record<string, string>;
      setShared([
        ...all.saved_views.map((item) => ({ key: `v${item.id}`, label: item.name, kind: m.kindSavedView, owner: item.owner.name, params: pick(item) })),
        ...all.tags.map((item) => ({ key: `t${item.id}`, label: item.name, kind: m.kindTag, owner: item.owner.name, params: { tag_id: item.id } })),
        ...all.correspondents.map((item) => ({ key: `c${item.id}`, label: item.name, kind: m.kindSender, owner: item.owner.name, params: { correspondent_id: item.id } })),
        ...all.document_types.map((item) => ({ key: `d${item.id}`, label: item.name, kind: m.kindType, owner: item.owner.name, params: { document_type_id: item.id } })),
      ]);
    }).catch(() => setShared([]));
  }, [refreshKey, m]);

  const load = useCallback(async (search: string, cursor: string | null = null, filter: Chip | null = null) => {
    const requestNumber = ++latestRequest.current;
    if (cursor) setLoadingMore(true);
    try {
      const params = new URLSearchParams({ view: "shared", ...(filter?.params ?? {}) });
      if (search) params.set("q", [filter?.params.q, search].filter(Boolean).join(" "));
      if (cursor) params.set("cursor", cursor);
      const result = await request<{ documents: Document[]; next_cursor: string | null }>(`/api/documents?${params}`);
      if (requestNumber !== latestRequest.current) return;
      setDocuments((current) => cursor ? [...current, ...result.documents] : result.documents);
      setNextCursor(result.next_cursor);
      setError("");
    } catch (cause) {
      if (requestNumber !== latestRequest.current) return;
      setError(cause instanceof Error ? cause.message : m.loadError);
    } finally {
      if (requestNumber === latestRequest.current) {
        setLoading(false);
        setLoadingMore(false);
      }
    }
  }, [m]);

  useEffect(() => { void load(applied, null, chip); }, [load, applied, refreshKey, chip]);

  function search(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setApplied(query.trim());
  }

  return <>
    <div className="page-heading">
      <div>
        <div className="eyebrow"><span className="eyebrow-line" /> {m.eyebrow}</div>
        <h1>{m.heading}<span className="heading-period">.</span></h1>
        <p>{m.intro}</p>
      </div>
      <Button type="button" variant="secondary" aria-label={m.refresh} title={m.refreshTitle} onClick={() => void load(applied, null, chip)}><RotateCcw size={16} /> <span className="refresh-label">{m.refresh}</span></Button>
    </div>
    <form className="shared-search" role="search" onSubmit={search}>
      <Search size={17} aria-hidden="true" />
      <input aria-label={m.searchLabel} placeholder={m.searchLabel} value={query} maxLength={200} onChange={(event) => setQuery(event.target.value)} />
      <Button type="submit" variant="secondary">{m.search}</Button>
    </form>
    {shared.length > 0 && <div className="shared-chips" role="group" aria-label={m.filtersLabel}>
      {shared.map((item) => <button type="button" key={item.key} className={`saved-search-chip shared-chip ${chip?.key === item.key ? "active" : ""}`} aria-pressed={chip?.key === item.key}
        title={m.chipTitle(item.kind, item.owner)} onClick={() => { setLoading(true); setChip((current) => current?.key === item.key ? null : item); }}>
        <small>{item.kind}</small> {item.label}
      </button>)}
    </div>}
    {error && <div className="inline-error" role="alert">{error}<button type="button" onClick={() => void load(applied, null, chip)}>{m.retry}</button></div>}
    {loading ? <p>{m.loading}</p> : error && !documents.length ? null : documents.length === 0 ? (
      <div className="empty-state">
        <div className="empty-icon"><Users size={32} strokeWidth={1.5} /></div>
        <h2>{applied ? m.noMatches : m.nothingShared}</h2>
        <p>{applied ? m.tryOtherWords : m.emptyHint}</p>
      </div>
    ) : <>
      <h2 className="visually-hidden">{m.listHeading}</h2>
      <div className="document-list">
        {documents.map((document) => <article className="document-row" key={document.id}>
          <div className="document-icon"><FileText size={21} /></div>
          <div className="document-info">
            <h3><button className="document-title-button" onClick={() => onOpenDocument(document)}>{document.title}</button></h3>
            <div className="document-meta">
              {m.sharedBy(document.shared_by ?? "")} · {document.access === "edit" ? m.canEdit : m.canView}
              {document.document_date ? ` · ${formatDate(`${document.document_date}T00:00:00`)}` : ""}
            </div>
            {document.snippet && <p>{document.snippet}</p>}
          </div>
        </article>)}
      </div>
      {nextCursor !== null && <Button type="button" variant="secondary" className="load-more" disabled={loadingMore} onClick={() => void load(applied, nextCursor, chip)}>{loadingMore ? m.loadingMore : m.showMore}</Button>}
    </>}
  </>;
}
