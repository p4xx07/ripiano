import { useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, Check, Copy, FileText, Inbox, RotateCcw } from "lucide-react";
import { Document, request } from "./api";
import { Button } from "./ui";

export default function InboxPanel({ refreshKey, onOpenDocument }: {
  refreshKey: number;
  onOpenDocument: (document: Document) => void;
}) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const latestRequest = useRef(0);
  const loadingMoreRef = useRef(false);
  const moveFocusAfterLoad = useRef(false);
  const contentRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async (cursor: string | null = null) => {
    if (cursor && loadingMoreRef.current) return;
    if (cursor) {
      loadingMoreRef.current = true;
      setLoadingMore(true);
    }
    const requestNumber = ++latestRequest.current;
    try {
      const result = await request<{ documents: Document[]; next_cursor: string | null }>(
        `/api/documents?view=exceptions${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
      );
      if (requestNumber !== latestRequest.current) return;
      setDocuments((current) => cursor ? [...current, ...result.documents] : result.documents);
      setNextCursor(result.next_cursor);
      setError("");
    } catch (cause) {
      if (requestNumber !== latestRequest.current) return;
      moveFocusAfterLoad.current = false;
      setError(cause instanceof Error ? cause.message : "Could not load Inbox");
    } finally {
      if (cursor) loadingMoreRef.current = false;
      if (requestNumber === latestRequest.current) {
        setLoading(false);
        setLoadingMore(false);
      }
    }
  }, []);

  useEffect(() => { void load(); }, [load, refreshKey]);
  useEffect(() => {
    if (!moveFocusAfterLoad.current) return;
    moveFocusAfterLoad.current = false;
    contentRef.current?.querySelector<HTMLElement>(".exception-row .document-title-button, .empty-state h3")?.focus();
  }, [documents]);

  async function keepBoth(document: Document) {
    setBusyId(document.id);
    setError("");
    try {
      await request(`/api/documents/${document.id}`, {
        method: "PATCH",
        body: JSON.stringify({ duplicate_reviewed: true }),
      });
      moveFocusAfterLoad.current = true;
      setNotice("Copy reviewed. Both documents remain in the Library.");
      await load();
    } catch (cause) {
      moveFocusAfterLoad.current = false;
      setError(cause instanceof Error ? cause.message : "Could not review this copy");
    } finally {
      setBusyId(null);
    }
  }

  async function retry(document: Document) {
    setBusyId(document.id);
    setError("");
    try {
      await request(`/api/documents/${document.id}/retry`, { method: "POST" });
      moveFocusAfterLoad.current = true;
      setNotice("OCR restarted. The original remains safe in the Library.");
      await load();
    } catch (cause) {
      moveFocusAfterLoad.current = false;
      setError(cause instanceof Error ? cause.message : "Could not retry OCR");
    } finally {
      setBusyId(null);
    }
  }

  return <>
    <div className="page-heading">
      <div>
        <div className="eyebrow"><span className="eyebrow-line" /> ONLY WHEN YOU'RE NEEDED</div>
        <h1>Inbox<span className="heading-period">.</span></h1>
        <p>Documents go straight to the Library. Check only processing failures and exact copies here.</p>
      </div>
      <Button type="button" variant="secondary" aria-label="Refresh" title="Refresh Inbox" onClick={() => void load()}><RotateCcw size={16} /> <span className="refresh-label">Refresh</span></Button>
    </div>
    <div className="visually-hidden" role="status" aria-live="polite">{notice}</div>
    {error && <div className="inline-error" role="alert">{error}<button onClick={() => void load(documents.length ? nextCursor : null)}>Retry</button></div>}
    <div ref={contentRef}>
    {loading ? <p>Loading Inbox…</p> : error && !documents.length ? null : documents.length === 0 ? (
      <div className="empty-state">
        <div className="empty-icon"><Inbox size={32} strokeWidth={1.5} /></div>
        <h3 tabIndex={-1}>Nothing needs your attention.</h3>
        <p>New documents stay in the Library automatically. Failed processing or an exact copy will appear here.</p>
      </div>
    ) : <>
      <div className="document-list">
        {documents.map((document) => <article className="document-row exception-row" key={document.id}>
          <div className="document-icon">{document.status === "failed" ? <AlertCircle size={21} /> : <FileText size={21} />}</div>
          <div className="document-info">
            <h3><button className="document-title-button" onClick={() => onOpenDocument(document)}>{document.title}</button></h3>
            {document.status === "failed" && <p className="doc-error">OCR could not finish{document.error ? `: ${document.error}` : "."}</p>}
            {document.duplicate_of && !document.duplicate_reviewed_at && <p><Copy size={13} /> Exact copy of “{document.duplicate_of.title}” · Both originals are saved</p>}
          </div>
          <div className="exception-actions">
            {document.status === "failed" && <Button type="button" variant="secondary" disabled={busyId === document.id} onClick={() => void retry(document)}><RotateCcw size={16} /> Try OCR again</Button>}
            {document.duplicate_of && !document.duplicate_reviewed_at && <Button type="button" variant="secondary" disabled={busyId === document.id} onClick={() => void keepBoth(document)}><Check size={16} /> Keep both</Button>}
          </div>
        </article>)}
      </div>
      {nextCursor && <Button type="button" variant="secondary" className="load-more" disabled={loadingMore} onClick={() => void load(nextCursor)}>{loadingMore ? "Loading…" : "Show more exceptions"}</Button>}
    </>}
    </div>
  </>;
}
