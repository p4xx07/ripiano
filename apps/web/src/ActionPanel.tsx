import { useCallback, useEffect, useRef, useState } from "react";
import { Check, ClipboardList, FileText } from "lucide-react";
import { Document, formatDate, request } from "./api";
import { Button } from "./ui";

export default function ActionPanel({ refreshKey, onOpenDocument }: {
  refreshKey: number;
  onOpenDocument: (document: Document) => void;
}) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const latestRequest = useRef(0);
  const loadingMoreRef = useRef(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (offset = 0) => {
    if (offset && loadingMoreRef.current) return;
    if (offset) {
      loadingMoreRef.current = true;
      setLoadingMore(true);
    }
    const requestNumber = ++latestRequest.current;
    try {
      const result = await request<{ documents: Document[]; next_offset: number | null }>(`/api/documents?view=actions&offset=${offset}`);
      if (requestNumber !== latestRequest.current) return;
      setDocuments((current) => offset ? [...current, ...result.documents] : result.documents);
      setNextOffset(result.next_offset);
      setError("");
    } catch (cause) {
      if (requestNumber !== latestRequest.current) return;
      setError(cause instanceof Error ? cause.message : "Could not load follow-ups");
    } finally {
      if (offset) loadingMoreRef.current = false;
      if (requestNumber === latestRequest.current) {
        setLoading(false);
        setLoadingMore(false);
      }
    }
  }, []);

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
      setError(cause instanceof Error ? cause.message : "Could not complete follow-up");
    } finally {
      setBusyId(null);
    }
  }

  return <>
    <div className="page-heading">
      <div>
        <div className="eyebrow"><span className="eyebrow-line" /> WHEN SOMETHING NEEDS YOU</div>
        <h1>Needs action<span className="heading-period">.</span></h1>
        <p>Only documents with something left to do appear here.</p>
      </div>
    </div>
    {error && <div className="inline-error" role="alert">{error}<button onClick={() => void load(documents.length ? nextOffset ?? 0 : 0)}>Retry</button></div>}
    {loading ? <p>Loading follow-ups…</p> : error && !documents.length ? null : documents.length === 0 ? (
      <div className="empty-state">
        <div className="empty-icon"><ClipboardList size={32} strokeWidth={1.5} /></div>
        <h3>All clear.</h3>
        <p>Mark a document as needing action when there is something to do. Filing stays optional.</p>
      </div>
    ) : <>
    <div className="document-list">
      {documents.map((document) => <article className="document-row action-row" key={document.id}>
        <div className="document-icon"><FileText size={21} /></div>
        <div className="document-info">
          <h3><button className="document-title-button" onClick={() => onOpenDocument(document)}>{document.title}</button></h3>
          <div className="document-meta">{document.action_due_date ? `Due ${formatDate(`${document.action_due_date}T00:00:00`)}` : "No due date"}</div>
          {document.action_note && <p title={document.action_note}>{document.action_note}</p>}
        </div>
        <Button type="button" variant="secondary" className="action-done" disabled={busyId === document.id} onClick={() => void markDone(document)}>
          <Check size={17} /> Done
        </Button>
      </article>)}
    </div>
    {nextOffset !== null && <Button type="button" variant="secondary" className="load-more" disabled={loadingMore} onClick={() => void load(nextOffset)}>{loadingMore ? "Loading…" : "Show more follow-ups"}</Button>}
    </>}
  </>;
}
