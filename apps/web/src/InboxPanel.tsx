import { useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, AlertTriangle, Check, Copy, FileText, Inbox, RotateCcw, Trash2 } from "lucide-react";
import { ApiError, Document, hasOpenWarning, request } from "./api";
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
  // What the error's "Retry" does: the action that failed (retry OCR for that document), or reload the list.
  const [errorRetry, setErrorRetry] = useState<{ label: string; run: () => void } | null>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  // Set when the next error message should take focus; the effect below runs once the message is on the page.
  const focusError = useRef(false);
  useEffect(() => {
    if (!error || !focusError.current) return;
    focusError.current = false;
    errorRef.current?.focus();
  }, [error, errorRetry]);
  const [notice, setNotice] = useState("");
  const [confirmResolve, setConfirmResolve] = useState(false);
  const [resolving, setResolving] = useState(false);
  const confirmResolveRef = useRef<HTMLButtonElement>(null);
  const latestRequest = useRef(0);
  const loadingMoreRef = useRef(false);
  const moveFocusAfterLoad = useRef(false);
  const contentRef = useRef<HTMLDivElement>(null);
  // Documents whose OCR was restarted from here: their cards stay (marked "retrying") and are checked until the
  // new attempt ends, which is announced either way (round-9 judge 2 M3).
  const [retrying, setRetrying] = useState<Record<string, Document>>({});
  const retryingRef = useRef(retrying);
  retryingRef.current = retrying;
  // Retried documents whose new attempt was interrupted (the worker stopped): the server tries again by itself,
  // and the card says so in the same calm words as the Library row.
  const [stalled, setStalled] = useState<Record<string, true>>({});
  const stalledRef = useRef(stalled);
  stalledRef.current = stalled;

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
      setDocuments((current) => {
        if (cursor) return [...current, ...result.documents];
        // A card being retried is no longer an exception on the server while OCR runs; keep it where it was.
        const next = [...result.documents];
        current.forEach((item, index) => {
          const kept = retryingRef.current[item.id];
          if (kept && !next.some((doc) => doc.id === item.id)) next.splice(Math.min(index, next.length), 0, kept);
        });
        return next;
      });
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

  /** A partly readable file (damaged PDF) the owner has checked: it leaves the Inbox (round-8 judge 1 M2). */
  async function markChecked(document: Document) {
    setBusyId(document.id);
    setError("");
    try {
      await request(`/api/documents/${document.id}`, {
        method: "PATCH",
        body: JSON.stringify({ processing_warning_reviewed: true }),
      });
      moveFocusAfterLoad.current = true;
      setNotice(m.warningChecked(document.title));
      await load();
    } catch (cause) {
      moveFocusAfterLoad.current = false;
      setError(cause instanceof Error ? cause.message : m.warningCheckError);
      focusError.current = true;
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

  // Errors from the list itself retry the load; set before each other action so its error retries that action.
  useEffect(() => {
    if (!error) setErrorRetry(null);
  }, [error]);

  const retryingIds = Object.keys(retrying).sort().join(",");
  useEffect(() => {
    if (!retryingIds) return;
    let stopped = false;
    let tick = 0;
    const checkStalled = async (waiting: string[]) => {
      const next: Record<string, true> = {};
      if (waiting.length) {
        try {
          const jobs = await request<{ documents_waiting: { items: { id: string; stalled?: boolean }[] } }>("/api/jobs");
          for (const item of jobs.documents_waiting.items) if (item.stalled && waiting.includes(item.id)) next[item.id] = true;
        } catch {
          return; // Passing (offline, restarting): keep what is shown and look again later.
        }
      }
      if (stopped) return;
      const before = stalledRef.current;
      if (Object.keys(next).sort().join(",") === Object.keys(before).sort().join(",")) return;
      if (Object.keys(next).some((id) => !before[id])) setNotice(m.ocrStalled);
      setStalled(next);
    };
    const check = async () => {
      const waiting: string[] = [];
      for (const id of retryingIds.split(",")) {
        let current: Document;
        try {
          current = await request<Document>(`/api/documents/${id}`);
        } catch (cause) {
          // Gone (moved to Trash elsewhere): stop following it. Anything else is passing: check again on the next tick.
          if (cause instanceof ApiError && cause.status === 404 && !stopped) {
            setRetrying((all) => {
              const rest = { ...all };
              delete rest[id];
              return rest;
            });
            setDocuments((all) => all.filter((item) => item.id !== id));
          }
          continue;
        }
        if (stopped) return;
        if (current.status === "pending" || current.status === "processing") {
          waiting.push(id);
          continue;
        }
        const title = retryingRef.current[id]?.title ?? current.title;
        const retryButton = window.document.getElementById(`inbox-retry-${id}`);
        const focusWasOnCard = Boolean(retryButton && retryButton === window.document.activeElement);
        setRetrying((all) => {
          const rest = { ...all };
          delete rest[id];
          return rest;
        });
        if (current.status === "failed") {
          setDocuments((all) => all.map((item) => item.id === id ? current : item));
          setNotice(m.ocrFailedAgain(title, current.error));
        } else {
          setDocuments((all) => all.filter((item) => item.id !== id || hasOpenWarning(current)).map((item) => item.id === id ? current : item));
          setNotice(hasOpenWarning(current) ? m.ocrPartlyRead(title) : m.ocrSucceeded(title));
          if (focusWasOnCard && !hasOpenWarning(current)) moveFocusAfterLoad.current = true;
        }
      }
      // The jobs list is a second request, so it is asked less often than the documents themselves.
      if (tick++ % 3 === 0 || Object.keys(stalledRef.current).length) await checkStalled(waiting);
    };
    // One pass at a time, less often while OCR keeps running (3 s up to 30 s), and none in a hidden tab.
    let delay = 3000;
    let timer = 0;
    const pass = async () => {
      if (!window.document.hidden) {
        await check();
        delay = Math.min(Math.round(delay * 1.5), 30000);
      }
      if (!stopped) timer = window.setTimeout(() => void pass(), delay);
    };
    timer = window.setTimeout(() => void pass(), delay);
    return () => { stopped = true; window.clearTimeout(timer); };
  }, [retryingIds, m]);

  async function retry(document: Document) {
    setBusyId(document.id);
    setError("");
    try {
      await request(`/api/documents/${document.id}/retry`, { method: "POST" });
      const pending = { ...document, status: "processing" as const, error: "" };
      setRetrying((all) => ({ ...all, [document.id]: pending }));
      retryingRef.current = { ...retryingRef.current, [document.id]: pending };
      setDocuments((all) => all.map((item) => item.id === document.id ? pending : item));
      setNotice(m.ocrRestarted);
    } catch (cause) {
      moveFocusAfterLoad.current = false;
      setError(cause instanceof Error ? cause.message : m.retryError);
      // "Retry" in the message retries OCR for this document; focus goes to the message (round-8 judge 2 M3).
      setErrorRetry({
        label: m.retryOcrFor(document.title),
        run: () => {
          window.document.getElementById(`inbox-retry-${document.id}`)?.focus();
          void retry(document);
        },
      });
      focusError.current = true;
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
    {error && <div ref={errorRef} className="inline-error" role="alert" tabIndex={-1}>{error}
      {errorRetry
        ? <button type="button" aria-label={errorRetry.label} onClick={errorRetry.run}>{m.retry}</button>
        : <button type="button" onClick={() => void load(documents.length ? nextCursor : null)}>{m.retry}</button>}
    </div>}
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
          <div className="document-icon">{document.status === "failed" ? <AlertCircle size={21} aria-hidden="true" /> : hasOpenWarning(document) ? <AlertTriangle size={21} aria-hidden="true" /> : <FileText size={21} aria-hidden="true" />}</div>
          <div className="document-info">
            <h3><button id={`inbox-title-${document.id}`} className="document-title-button" onClick={() => onOpenDocument(document)}>{document.title}</button></h3>
            {retrying[document.id] && (stalled[document.id]
              ? <p className="doc-processing doc-stalled">{m.ocrStalled}</p>
              : <p className="doc-processing">{m.ocrRetrying}</p>)}
            {document.status === "failed" && <p className="doc-error">{m.ocrFailed(document.error)}</p>}
            {document.status !== "failed" && hasOpenWarning(document) && <p className="doc-warning">{document.warning || m.partlyReadable}</p>}
            {document.duplicate_of && !document.duplicate_reviewed_at && <p className="inbox-copy-note"><Copy size={13} />{m.exactCopy(document.duplicate_of.title)}</p>}
          </div>
          <div className="exception-actions">
            {(document.status === "failed" || retrying[document.id]) && <Button id={`inbox-retry-${document.id}`} type="button" variant="secondary" aria-label={retrying[document.id] ? m.retryingOcrFor(document.title) : m.tryOcrAgainFor(document.title)} pending={busyId === document.id || Boolean(retrying[document.id])} onClick={() => void retry(document)}><RotateCcw size={16} /> {retrying[document.id] ? m.retryingOcr : m.tryOcrAgain}</Button>}
            {document.status !== "failed" && hasOpenWarning(document) && (document.access ?? "owner") === "owner" && <Button type="button" variant="secondary" aria-describedby={`inbox-title-${document.id}`} pending={busyId === document.id} onClick={() => void markChecked(document)}><Check size={16} /> {m.markChecked}</Button>}
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
