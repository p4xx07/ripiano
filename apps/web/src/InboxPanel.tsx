import { useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, Check, Copy, FileText, Inbox, RotateCcw, Trash2 } from "lucide-react";
import { Document, request } from "./api";
import { Button } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/InboxPanel";

export default function InboxPanel({ refreshKey, onOpenDocument }: {
  refreshKey: number;
  onOpenDocument: (document: Document) => void;
}) {
  const m = useMessages(messages);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [confirmResolve, setConfirmResolve] = useState(false);
  const [resolving, setResolving] = useState(false);
  const confirmResolveRef = useRef<HTMLButtonElement>(null);
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
  useEffect(() => {
    if (!moveFocusAfterLoad.current) return;
    moveFocusAfterLoad.current = false;
    contentRef.current?.querySelector<HTMLElement>(".exception-row .document-title-button, .empty-state h2")?.focus();
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
      setNotice(m.copyReviewed);
      await load();
    } catch (cause) {
      moveFocusAfterLoad.current = false;
      setError(cause instanceof Error ? cause.message : m.reviewError);
    } finally {
      setBusyId(null);
    }
  }

  async function trashCopy(document: Document) {
    setBusyId(document.id);
    setError("");
    try {
      await request(`/api/documents/${document.id}/trash`, { method: "POST" });
      moveFocusAfterLoad.current = true;
      setNotice(m.copyTrashed(document.title));
      await load();
    } catch (cause) {
      moveFocusAfterLoad.current = false;
      setError(cause instanceof Error ? cause.message : m.trashError);
    } finally {
      setBusyId(null);
    }
  }

  const isOpenCopy = (document: Document) => Boolean(document.duplicate_of && !document.duplicate_reviewed_at);
  const isSettled = (document: Document) => document.status !== "pending" && document.status !== "processing";
  const openCopies = documents.filter(isOpenCopy);

  /** Keep every original and move every exact copy in the Inbox (all pages) to the Trash. */
  async function resolveAllCopies() {
    setResolving(true);
    setError("");
    try {
      const copies: Document[] = [];
      let cursor: string | null = null;
      for (let page = 0; page < 50; page += 1) {
        const result: { documents: Document[]; next_cursor: string | null } = await request(
          `/api/documents?view=exceptions${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`);
        copies.push(...result.documents.filter((item) => isOpenCopy(item) && isSettled(item)));
        cursor = result.next_cursor;
        if (!cursor) break;
      }
      for (let index = 0; index < copies.length; index += 100) {
        await request("/api/documents/bulk-trash", {
          method: "POST",
          body: JSON.stringify({ action: "trash", document_ids: copies.slice(index, index + 100).map((item) => item.id) }),
        });
      }
      setConfirmResolve(false);
      moveFocusAfterLoad.current = true;
      setNotice(m.copiesTrashed(copies.length));
      await load();
    } catch (cause) {
      moveFocusAfterLoad.current = false;
      setError(cause instanceof Error ? cause.message : m.trashError);
      await load();
    } finally {
      setResolving(false);
    }
  }

  useEffect(() => {
    if (confirmResolve) confirmResolveRef.current?.focus();
  }, [confirmResolve]);

  async function retry(document: Document) {
    setBusyId(document.id);
    setError("");
    try {
      await request(`/api/documents/${document.id}/retry`, { method: "POST" });
      moveFocusAfterLoad.current = true;
      setNotice(m.ocrRestarted);
      await load();
    } catch (cause) {
      moveFocusAfterLoad.current = false;
      setError(cause instanceof Error ? cause.message : m.retryError);
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
    <div className="visually-hidden" role="status" aria-live="polite">{notice}</div>
    {error && <div className="inline-error" role="alert">{error}<button onClick={() => void load(documents.length ? nextCursor : null)}>{m.retry}</button></div>}
    <div ref={contentRef}>
    {loading ? <p>{m.loading}</p> : error && !documents.length ? null : documents.length === 0 ? (
      <div className="empty-state">
        <div className="empty-icon"><Inbox size={32} strokeWidth={1.5} /></div>
        <h2 tabIndex={-1}>{m.emptyTitle}</h2>
        <p>{m.emptyText}</p>
      </div>
    ) : <>
      <h2 className="visually-hidden">{m.listHeading}</h2>
      {openCopies.length > 0 && (
        <div className="inbox-resolve-copies">
          {confirmResolve ? (
            <div role="group" aria-labelledby="inbox-resolve-question" className="inbox-resolve-confirm">
              <p id="inbox-resolve-question">{m.resolveQuestion}</p>
              <Button type="button" variant="danger" ref={confirmResolveRef} disabled={resolving} onClick={() => void resolveAllCopies()}><Trash2 size={16} /> {resolving ? m.resolving : m.resolveConfirm}</Button>
              <Button type="button" variant="secondary" disabled={resolving} onClick={() => setConfirmResolve(false)}>{m.cancel}</Button>
            </div>
          ) : (
            <Button type="button" variant="secondary" disabled={resolving} onClick={() => setConfirmResolve(true)}><Trash2 size={16} /> {m.resolveAll}</Button>
          )}
        </div>
      )}
      <div className="document-list">
        {documents.map((document) => <article className="document-row exception-row" key={document.id}>
          <div className="document-icon">{document.status === "failed" ? <AlertCircle size={21} /> : <FileText size={21} />}</div>
          <div className="document-info">
            <h3><button id={`inbox-title-${document.id}`} className="document-title-button" onClick={() => onOpenDocument(document)}>{document.title}</button></h3>
            {document.status === "failed" && <p className="doc-error">{m.ocrFailed(document.error)}</p>}
            {document.duplicate_of && !document.duplicate_reviewed_at && <p className="inbox-copy-note"><Copy size={13} />{m.exactCopy(document.duplicate_of.title)}</p>}
          </div>
          <div className="exception-actions">
            {document.status === "failed" && <Button type="button" variant="secondary" aria-describedby={`inbox-title-${document.id}`} disabled={busyId === document.id} onClick={() => void retry(document)}><RotateCcw size={16} /> {m.tryOcrAgain}</Button>}
            {document.duplicate_of && !document.duplicate_reviewed_at && <Button type="button" variant="secondary" aria-describedby={`inbox-title-${document.id}`} disabled={busyId === document.id} onClick={() => void keepBoth(document)}><Check size={16} /> {m.keepBoth}</Button>}
            {isOpenCopy(document) && isSettled(document) && <Button type="button" variant="secondary" aria-describedby={`inbox-title-${document.id}`} disabled={busyId === document.id || resolving} onClick={() => void trashCopy(document)}><Trash2 size={16} /> {m.trashCopy}</Button>}
          </div>
        </article>)}
      </div>
      {nextCursor && <Button type="button" variant="secondary" className="load-more" disabled={loadingMore} onClick={() => void load(nextCursor)}>{loadingMore ? m.loadingMore : m.showMore}</Button>}
    </>}
    </div>
  </>;
}
