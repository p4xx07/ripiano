import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { FileText, RotateCcw, Search, Users } from "lucide-react";
import { Document, formatDate, request } from "./api";
import { Button } from "./ui";

export default function SharedPanel({ refreshKey, onOpenDocument }: {
  refreshKey: number;
  onOpenDocument: (document: Document) => void;
}) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [applied, setApplied] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const latestRequest = useRef(0);

  const load = useCallback(async (search: string, cursor: string | null = null) => {
    const requestNumber = ++latestRequest.current;
    if (cursor) setLoadingMore(true);
    try {
      const params = new URLSearchParams({ view: "shared" });
      if (search) params.set("q", search);
      if (cursor) params.set("cursor", cursor);
      const result = await request<{ documents: Document[]; next_cursor: string | null }>(`/api/documents?${params}`);
      if (requestNumber !== latestRequest.current) return;
      setDocuments((current) => cursor ? [...current, ...result.documents] : result.documents);
      setNextCursor(result.next_cursor);
      setError("");
    } catch (cause) {
      if (requestNumber !== latestRequest.current) return;
      setError(cause instanceof Error ? cause.message : "Could not load shared documents");
    } finally {
      if (requestNumber === latestRequest.current) {
        setLoading(false);
        setLoadingMore(false);
      }
    }
  }, []);

  useEffect(() => { void load(applied); }, [load, applied, refreshKey]);

  function search(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setApplied(query.trim());
  }

  return <>
    <div className="page-heading">
      <div>
        <div className="eyebrow"><span className="eyebrow-line" /> FROM OTHER PEOPLE HERE</div>
        <h1>Shared with me<span className="heading-period">.</span></h1>
        <p>Documents other people on this Ripiano chose to share with you or your groups.</p>
      </div>
      <Button type="button" variant="secondary" aria-label="Refresh" title="Refresh shared documents" onClick={() => void load(applied)}><RotateCcw size={16} /> <span className="refresh-label">Refresh</span></Button>
    </div>
    <form className="shared-search" role="search" onSubmit={search}>
      <Search size={17} aria-hidden="true" />
      <input aria-label="Search shared documents" placeholder="Search shared documents" value={query} maxLength={200} onChange={(event) => setQuery(event.target.value)} />
      <Button type="submit" variant="secondary">Search</Button>
    </form>
    {error && <div className="inline-error" role="alert">{error}<button type="button" onClick={() => void load(applied)}>Retry</button></div>}
    {loading ? <p>Loading shared documents…</p> : error && !documents.length ? null : documents.length === 0 ? (
      <div className="empty-state">
        <div className="empty-icon"><Users size={32} strokeWidth={1.5} /></div>
        <h3>{applied ? "No matches." : "Nothing shared yet."}</h3>
        <p>{applied ? "Try other words." : "When someone shares a document with you, it appears here."}</p>
      </div>
    ) : <>
      <div className="document-list">
        {documents.map((document) => <article className="document-row" key={document.id}>
          <div className="document-icon"><FileText size={21} /></div>
          <div className="document-info">
            <h3><button className="document-title-button" onClick={() => onOpenDocument(document)}>{document.title}</button></h3>
            <div className="document-meta">
              Shared by {document.shared_by} · {document.access === "edit" ? "Can edit details" : "Can view"}
              {document.document_date ? ` · ${formatDate(`${document.document_date}T00:00:00`)}` : ""}
            </div>
            {document.snippet && <p>{document.snippet}</p>}
          </div>
        </article>)}
      </div>
      {nextCursor !== null && <Button type="button" variant="secondary" className="load-more" disabled={loadingMore} onClick={() => void load(applied, nextCursor)}>{loadingMore ? "Loading…" : "Show more"}</Button>}
    </>}
  </>;
}
