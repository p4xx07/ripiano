import { useCallback, useEffect, useState } from "react";
import { ArrowDownToLine, ArrowLeft, ArrowRight, History, Layers, RotateCcw, RotateCw, Scissors, Trash2, Undo2, Upload } from "lucide-react";
import { ApiError, formatDateTime, request, type Document } from "./api";
import { Button } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/PagesPanel";

type PageInfo = { count: number; source: "original" | "searchable"; signed: boolean; version_number: number };
type Version = { id: string; number: number; note: string; original_name: string; size: number; created_at: string };
type Versions = { current: { number: number; note: string; original_name: string; size: number; created_at: string }; versions: Version[] };
type PageState = { index: number; rotation: number; removed: boolean };
type Summary = { id: string; title: string; revoked_shares?: number };

function size(bytes: number) {
  return bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export default function PagesPanel({ documentId, ready, editable, onChanged, onOpenDocument }: {
  documentId: string;
  ready: boolean;
  editable: boolean;
  onChanged: () => void;
  onOpenDocument: (id: string) => void;
}) {
  const m = useMessages(messages);
  const [opened, setOpened] = useState(false);
  const [info, setInfo] = useState<PageInfo | null>(null);
  const [versions, setVersions] = useState<Versions | null>(null);
  const [pages, setPages] = useState<PageState[]>([]);
  const [splitAfter, setSplitAfter] = useState<number[]>([]);
  const [acceptSignature, setAcceptSignature] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [created, setCreated] = useState<Summary[]>([]);
  const [moved, setMoved] = useState("");
  const [sourceQuery, setSourceQuery] = useState("");
  const [sourceResults, setSourceResults] = useState<Document[]>([]);
  const [sourceChoice, setSourceChoice] = useState<Document | null>(null);
  const [sourceError, setSourceError] = useState("");
  const [sourceSearching, setSourceSearching] = useState(false);
  const [sourceHasMore, setSourceHasMore] = useState(false);
  const [sourceRevision, setSourceRevision] = useState(0);

  const load = useCallback(async (includePages = true) => {
    try {
      const history = await request<Versions>(`/api/documents/${documentId}/versions`);
      setVersions(history);
      if (ready && includePages) {
        const pageInfo = await request<PageInfo>(`/api/documents/${documentId}/pages`);
        setInfo(pageInfo);
        setPages(Array.from({ length: pageInfo.count }, (_, index) => ({ index, rotation: 0, removed: false })));
        setSplitAfter([]);
      } else if (!includePages) {
        setInfo(null);
        setPages([]);
      }
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.loadError);
    }
  }, [documentId, ready]);

  // Load when opened, and again once a document that was still processing becomes ready.
  useEffect(() => {
    if (opened) void load();
  }, [opened, load]);

  useEffect(() => {
    if (!opened || sourceQuery.trim().length < 2) {
      setSourceResults([]);
      setSourceError("");
      setSourceSearching(false);
      setSourceHasMore(false);
      return;
    }
    let cancelled = false;
    setSourceResults([]);
    setSourceSearching(true);
    setSourceHasMore(false);
    const timer = window.setTimeout(() => {
      void request<{ documents: Document[]; next_cursor: string | null }>(`/api/documents?${new URLSearchParams({ q: sourceQuery.trim() })}`)
        .then((result) => {
          if (cancelled) return;
          setSourceResults(result.documents.filter((item) => item.id !== documentId && item.status === "ready" && !item.is_split_source));
          setSourceError("");
          setSourceSearching(false);
          setSourceHasMore(Boolean(result.next_cursor));
        })
        .catch((cause) => {
          if (cancelled) return;
          setSourceResults([]);
          setSourceError(cause instanceof Error ? cause.message : m.searchError);
          setSourceSearching(false);
        });
    }, 250);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [documentId, opened, sourceQuery, sourceRevision]);

  async function run(action: () => Promise<string>) {
    setBusy(true);
    setError("");
    setNotice("");
    setMoved("");
    try {
      setNotice(await action());
    } catch (cause) {
      if (cause instanceof ApiError && (cause.data.code === "stale" || cause.data.code === "source_stale")) {
        onChanged();
        await load(cause.data.code === "source_stale");
      }
      setError(cause instanceof Error ? cause.message : m.genericError);
    } finally {
      setBusy(false);
    }
  }

  function update(position: number, change: Partial<PageState>) {
    setPages((value) => value.map((item, index) => (index === position ? { ...item, ...change } : item)));
  }

  function move(position: number, offset: number) {
    setMoved(m.moved(pages[position].index + 1, offset < 0));
    setPages((value) => {
      const next = [...value];
      const target = position + offset;
      if (target < 0 || target >= next.length) return value;
      [next[position], next[target]] = [next[target], next[position]];
      return next;
    });
    setSplitAfter([]);
  }

  const kept = pages.filter((item) => !item.removed);
  const changed = pages.some((item, position) => item.removed || item.rotation || item.index !== position);
  const groups = (() => {
    const result: number[][] = [[]];
    pages.forEach((item, position) => {
      if (!item.removed) result[result.length - 1].push(item.index);
      if (splitAfter.includes(position) && result[result.length - 1].length) result.push([]);
    });
    return result.filter((group) => group.length);
  })();
  const needsConsent = Boolean(info?.signed) && !acceptSignature;
  const rotations = Object.fromEntries(pages.filter((item) => item.rotation && !item.removed).map((item) => [String(item.index), item.rotation]));
  const sharesNote = (result: Summary) => result.revoked_shares ? m.sharesRevoked(result.revoked_shares) : "";

  function saveVersion() {
    void run(async () => {
      const result = await request<Summary>(`/api/documents/${documentId}/pages`, {
        method: "POST",
        body: JSON.stringify({ order: kept.map((item) => item.index), rotate: rotations, accept_signature_loss: acceptSignature, version_number: info?.version_number }),
      });
      onChanged();
      await load(false);
      return m.savedVersion(sharesNote(result));
    });
  }

  function split() {
    void run(async () => {
      const result = await request<{ documents: Summary[] }>(`/api/documents/${documentId}/split`, {
        method: "POST", body: JSON.stringify({ groups, rotate: rotations }),
      });
      setCreated(result.documents);
      setSplitAfter([]);
      return m.splitDone(result.documents.length);
    });
  }

  function restore(version: Version) {
    void run(async () => {
      const result = await request<Summary>(`/api/documents/${documentId}/versions/${version.id}/restore`, {
        method: "POST", body: JSON.stringify({ version_number: versions?.current.number }),
      });
      onChanged();
      await load(false);
      return m.restored(version.number, sharesNote(result));
    });
  }

  function uploadVersion(file: File) {
    void run(async () => {
      const form = new FormData();
      form.append("file", file);
      if (versions) form.append("version_number", String(versions.current.number));
      const result = await request<Summary>(`/api/documents/${documentId}/versions`, { method: "POST", body: form });
      onChanged();
      await load(false);
      return m.uploaded(sharesNote(result));
    });
  }

  function useExistingDocument() {
    if (!sourceChoice) return;
    const chosen = sourceChoice;
    void run(async () => {
      let result: Summary;
      try {
        result = await request<Summary>(`/api/documents/${documentId}/versions/from-document`, {
          method: "POST",
          body: JSON.stringify({ source_document_id: chosen.id, source_version_number: chosen.version_number, version_number: versions?.current.number }),
        });
      } catch (cause) {
        if (cause instanceof ApiError && cause.data.code === "source_stale") {
          setSourceChoice(null);
          setSourceRevision((value) => value + 1);
        }
        throw cause;
      }
      setSourceChoice(null);
      setSourceQuery("");
      onChanged();
      await load(false);
      return m.usedExisting(chosen.title, sharesNote(result));
    });
  }

  if (!opened) {
    return (
      <section className="pages-section" aria-labelledby="pages-heading">
        <h3 id="pages-heading"><Layers size={17} aria-hidden="true" /> {m.heading}</h3>
        <p>{m.intro}</p>
        <Button type="button" variant="secondary" onClick={() => setOpened(true)}>{m.open}</Button>
      </section>
    );
  }

  return (
    <section className="pages-section pages-panel" aria-labelledby="pages-heading">
      <h3 id="pages-heading"><Layers size={17} aria-hidden="true" /> {m.heading}</h3>
      {error && <div className="inline-error" role="alert">{error}</div>}
      {notice && <p className="bulk-notice" role="status">{notice}</p>}
      {created.length > 0 && (
        <div className="pages-created">
          {created.map((item) => <button type="button" key={item.id} onClick={() => onOpenDocument(item.id)}>{m.openCreated(item.title)}</button>)}
        </div>
      )}
      {!ready && <p>{editable ? m.notReadyEditable : m.notReady}</p>}
      {info && (
        <>
          <p>
            {m.pageCount(info.count)}
            {info.source === "searchable" && m.usesSearchable}
          </p>
          {info.signed && (
            <div className="mail-warning pages-signed" role="note">
              <p>{m.signedWarning}</p>
              <label><input type="checkbox" checked={acceptSignature} onChange={(event) => setAcceptSignature(event.target.checked)} /> {m.acceptSignature}</label>
            </div>
          )}
          <ol className="pages-grid">
            {pages.map((item, position) => (
              <li key={item.index} className={item.removed ? "removed" : undefined}>
                <div className="page-thumb">
                  <img src={`/api/documents/${documentId}/pages/${item.index + 1}.png?v=${info.version_number}`} alt={m.pageAlt(item.index + 1)}
                    style={{ transform: `rotate(${item.rotation}deg)` }} loading="lazy" />
                </div>
                <strong>{m.pageLabel(item.index + 1, item.removed)}</strong>
                <div className="page-actions">
                  <button type="button" aria-label={m.rotateLeft(item.index + 1)} onClick={() => update(position, { rotation: (item.rotation + 270) % 360 })}><RotateCcw size={16} aria-hidden="true" /></button>
                  <button type="button" aria-label={m.rotateRight(item.index + 1)} onClick={() => update(position, { rotation: (item.rotation + 90) % 360 })}><RotateCw size={16} aria-hidden="true" /></button>
                  <button type="button" aria-label={m.moveEarlier(item.index + 1)} aria-disabled={position === 0} onClick={() => position > 0 && move(position, -1)}><ArrowLeft size={16} aria-hidden="true" /></button>
                  <button type="button" aria-label={m.moveLater(item.index + 1)} aria-disabled={position === pages.length - 1} onClick={() => position < pages.length - 1 && move(position, 1)}><ArrowRight size={16} aria-hidden="true" /></button>
                  <button type="button" aria-label={m.removePage(item.index + 1)} aria-pressed={item.removed}
                    onClick={() => update(position, { removed: !item.removed })}>{item.removed ? <Undo2 size={16} aria-hidden="true" /> : <Trash2 size={16} aria-hidden="true" />}</button>
                </div>
                {position < pages.length - 1 && (
                  <label className="page-split">
                    <input type="checkbox" checked={splitAfter.includes(position)} onChange={() => setSplitAfter((value) => value.includes(position) ? value.filter((entry) => entry !== position) : [...value, position])} />
                    {m.splitAfter(item.index + 1)}
                  </label>
                )}
              </li>
            ))}
          </ol>
          {moved && !notice && <p className="visually-hidden" role="status">{moved}</p>}
          <div className="pages-footer">
            <Button type="button" disabled={busy || !changed || kept.length === 0 || needsConsent} onClick={saveVersion}>{m.saveVersion}</Button>
            <Button type="button" variant="secondary" disabled={busy || groups.length < 2} onClick={split}>
              <Scissors size={16} aria-hidden="true" /> {groups.length < 2 ? m.splitInto : m.splitIntoCount(groups.length)}
            </Button>
            {(changed || splitAfter.length > 0) && <Button type="button" variant="secondary" disabled={busy} onClick={() => void load()}>{m.undo}</Button>}
          </div>
          {kept.length === 0 && <p className="mail-warning">{m.keepOne}</p>}
        </>
      )}
      {versions && (
        <div className="pages-versions">
          <h4><History size={16} aria-hidden="true" /> {m.versions}</h4>
          <ul>
            <li>
              <strong>{m.currentVersion(versions.current.number)}</strong>
              <span>{versions.current.note} · {formatDateTime(versions.current.created_at)} · {size(versions.current.size)}</span>
            </li>
            {versions.versions.map((version) => (
              <li key={version.id}>
                <strong>{m.version(version.number)}</strong>
                <span>{version.note} · {formatDateTime(version.created_at)} · {size(version.size)}</span>
                <div className="page-actions">
                  <a href={`/api/documents/${documentId}/versions/${version.id}/download`}><ArrowDownToLine size={16} aria-hidden="true" /> {m.download}</a>
                  <button type="button" disabled={busy || !editable} onClick={() => restore(version)}>{m.makeCurrent}</button>
                </div>
              </li>
            ))}
          </ul>
          <label className={`pages-upload button button-secondary${busy || !editable ? " is-disabled" : ""}`}>
            <Upload size={16} aria-hidden="true" /> {m.uploadVersion}
            <input className="visually-hidden" type="file" accept="application/pdf,image/jpeg,image/png,.eml,.msg,.docx,.xlsx,.pptx,.doc,.xls,.ppt,.odt,.ods,.odp,.rtf"
              disabled={busy || !editable} onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ""; if (file) uploadVersion(file); }} />
          </label>
          <div className="pages-source-picker">
            <h5>{m.useExistingHeading}</h5>
            <p>{m.useExistingIntro}</p>
            <label htmlFor="pages-source-search">{m.searchReady}</label>
            <input id="pages-source-search" type="search" value={sourceQuery} disabled={busy || !editable}
              placeholder={m.searchPlaceholder} onChange={(event) => { setSourceQuery(event.target.value); setSourceChoice(null); }} />
            {sourceError && <p className="inline-error" role="alert">{sourceError}</p>}
            {sourceSearching && <p role="status">{m.searching}</p>}
            {sourceQuery.trim().length >= 2 && !sourceSearching && !sourceError && sourceResults.length === 0 && <p>{m.noneFound(sourceHasMore)}</p>}
            {sourceResults.length > 0 && (
              <fieldset disabled={busy || !editable}>
                <legend>{m.chooseSource}</legend>
                {sourceResults.map((item) => (
                  <label key={item.id} className="pages-source-option">
                    <input type="radio" name={`source-${documentId}`} checked={sourceChoice?.id === item.id} onChange={() => setSourceChoice(item)} />
                    <span><strong>{item.title}</strong><small>{m.sourceVersion(item.original_name, item.version_number)}</small></span>
                  </label>
                ))}
              </fieldset>
            )}
            {sourceHasMore && !sourceSearching && sourceResults.length > 0 && <p>{m.firstFifty}</p>}
            <Button type="button" variant="secondary" disabled={busy || !editable || !sourceChoice} onClick={useExistingDocument}>{m.useAsVersion}</Button>
          </div>
        </div>
      )}
    </section>
  );
}
