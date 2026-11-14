import { useCallback, useEffect, useRef, useState } from "react";
import { Check, ClipboardList, FileText, RotateCcw } from "lucide-react";
import { Document, formatDate, request } from "./api";
import { Button } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/ActionPanel";

export default function ActionPanel({ refreshKey, onOpenDocument }: {
  refreshKey: number;
  onOpenDocument: (document: Document) => void;
}) {
  const m = useMessages(messages);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const latestRequest = useRef(0);
  const loadingMoreRef = useRef(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (cursor: string | null = null) => {
    if (cursor && loadingMoreRef.current) return;
    if (cursor) {
      loadingMoreRef.current = true;
      setLoadingMore(true);
    }
    const requestNumber = ++latestRequest.current;
    try {
      const result = await request<{ documents: Document[]; next_cursor: string | null }>(`/api/documents?view=actions${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`);
      if (requestNumber !== latestRequest.current) return;
      setDocuments((current) => cursor ? [...current, ...result.documents] : result.documents);
      setNextCursor(result.next_cursor);
      setError("");
    } catch (cause) {
      if (requestNumber !== latestRequest.current) return;
      setError(cause instanceof Error ? cause.message : m.loadError);
    } finally {
      if (cursor) loadingMoreRef.current = false;
      if (requestNumber === latestRequest.current) {
        setLoading(false);
        setLoadingMore(false);
      }
    }
  }, [m]);

  useEffect(() => { void load(); }, [load, refreshKey]);

  async function markDone(document: Document) {
    setBusyId(document.id);
    try {
      await request(`/api/documents/${document.id}`, {
        method: "PATCH",
        body: JSON.stringify({ action_status: "done" }),
      });
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.completeError);
    } finally {
      setBusyId(null);
    }
  }

  return <>
    <div className="page-heading">
      <div>
        <div className="eyebrow"><span className="eyebrow-line" /> {m.eyebrow}</div>
        <h1>{m.heading}<span className="heading-period">.</span></h1>
        <p>{m.intro}</p>
      </div>
      <Button type="button" variant="secondary" aria-label={m.refresh} title={m.refreshTitle} onClick={() => void load()}><RotateCcw size={16} /> <span className="refresh-label">{m.refresh}</span></Button>
    </div>
    {error && <div className="inline-error" role="alert">{error}<button onClick={() => void load(documents.length ? nextCursor : null)}>{m.retry}</button></div>}
    {loading ? <p>{m.loading}</p> : error && !documents.length ? null : documents.length === 0 ? (
      <div className="empty-state">
        <div className="empty-icon"><ClipboardList size={32} strokeWidth={1.5} /></div>
        <h3>{m.emptyTitle}</h3>
        <p>{m.emptyText}</p>
      </div>
    ) : <>
    <div className="document-list">
      {documents.map((document) => <article className="document-row action-row" key={document.id}>
        <div className="document-icon"><FileText size={21} /></div>
        <div className="document-info">
          <h3><button className="document-title-button" onClick={() => onOpenDocument(document)}>{document.title}</button></h3>
          <div className="document-meta">{document.action_due_date ? m.due(formatDate(`${document.action_due_date}T00:00:00`)) : m.noDueDate}</div>
          {document.action_note && <p title={document.action_note}>{document.action_note}</p>}
        </div>
        <Button type="button" variant="secondary" className="action-done" disabled={busyId === document.id} onClick={() => void markDone(document)}>
          <Check size={17} /> {m.done}
        </Button>
      </article>)}
    </div>
    {nextCursor !== null && <Button type="button" variant="secondary" className="load-more" disabled={loadingMore} onClick={() => void load(nextCursor)}>{loadingMore ? m.loadingMore : m.showMore}</Button>}
    </>}
  </>;
}
