import { useCallback, useEffect, useState } from "react";
import { ArrowDownToLine, ArrowLeft, ArrowRight, History, Layers, RotateCcw, RotateCw, Scissors, Trash2, Undo2, Upload } from "lucide-react";
import { request } from "./api";
import { Button } from "./ui";

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

  const load = useCallback(async () => {
    try {
      const history = await request<Versions>(`/api/documents/${documentId}/versions`);
      setVersions(history);
      if (ready) {
        const pageInfo = await request<PageInfo>(`/api/documents/${documentId}/pages`);
        setInfo(pageInfo);
        setPages(Array.from({ length: pageInfo.count }, (_, index) => ({ index, rotation: 0, removed: false })));
        setSplitAfter([]);
      }
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load pages");
    }
  }, [documentId, ready]);

  // Load when opened, and again once a document that was still processing becomes ready.
  useEffect(() => {
    if (opened) void load();
  }, [opened, load]);

  async function run(action: () => Promise<string>) {
    setBusy(true);
    setError("");
    setNotice("");
    setMoved("");
    try {
      setNotice(await action());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "That did not work");
      if (cause instanceof Error && cause.message.startsWith("This document changed")) void load();
    } finally {
      setBusy(false);
    }
  }

  function update(position: number, change: Partial<PageState>) {
    setPages((value) => value.map((item, index) => (index === position ? { ...item, ...change } : item)));
  }

  function move(position: number, offset: number) {
    setMoved(`Page ${pages[position].index + 1} moved ${offset < 0 ? "earlier" : "later"}.`);
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
  const sharesNote = (result: Summary) => result.revoked_shares ? ` ${result.revoked_shares} active share link${result.revoked_shares === 1 ? " was" : "s were"} revoked so they never serve different content.` : "";

  function saveVersion() {
    void run(async () => {
      const result = await request<Summary>(`/api/documents/${documentId}/pages`, {
        method: "POST",
        body: JSON.stringify({ order: kept.map((item) => item.index), rotate: rotations, accept_signature_loss: acceptSignature, version_number: info?.version_number }),
      });
      onChanged();
      await load();
      return `Saved as a new version. The previous file is kept below; the searchable PDF is being rebuilt.${sharesNote(result)}`;
    });
  }

  function split() {
    void run(async () => {
      const result = await request<{ documents: Summary[] }>(`/api/documents/${documentId}/split`, {
        method: "POST", body: JSON.stringify({ groups, rotate: rotations }),
      });
      setCreated(result.documents);
      setSplitAfter([]);
      return `Created ${result.documents.length} new documents. This document is unchanged.`;
    });
  }

  function restore(version: Version) {
    void run(async () => {
      const result = await request<Summary>(`/api/documents/${documentId}/versions/${version.id}/restore`, {
        method: "POST", body: JSON.stringify({ version_number: versions?.current.number }),
      });
      onChanged();
      await load();
      return `Version ${version.number} is current again. Nothing was deleted.${sharesNote(result)}`;
    });
  }

  function uploadVersion(file: File) {
    void run(async () => {
      const form = new FormData();
      form.append("file", file);
      if (versions) form.append("version_number", String(versions.current.number));
      const result = await request<Summary>(`/api/documents/${documentId}/versions`, { method: "POST", body: form });
      onChanged();
      await load();
      return `New version uploaded. The previous file is kept below.${sharesNote(result)}`;
    });
  }

  if (!opened) {
    return (
      <section className="pages-section" aria-labelledby="pages-heading">
        <h3 id="pages-heading"><Layers size={17} aria-hidden="true" /> Pages & versions</h3>
        <p>Rotate, remove, reorder, or split pages. Every change keeps the previous file.</p>
        <Button type="button" variant="secondary" onClick={() => setOpened(true)}>Open pages & versions</Button>
      </section>
    );
  }

  return (
    <section className="pages-section pages-panel" aria-labelledby="pages-heading">
      <h3 id="pages-heading"><Layers size={17} aria-hidden="true" /> Pages & versions</h3>
      {error && <div className="inline-error" role="alert">{error}</div>}
      {notice && <p className="bulk-notice" role="status">{notice}</p>}
      {created.length > 0 && (
        <div className="pages-created">
          {created.map((item) => <button type="button" key={item.id} onClick={() => onOpenDocument(item.id)}>Open “{item.title}”</button>)}
        </div>
      )}
      {!ready && <p>{editable ? "Page tools need a readable PDF. You can still upload a new version or make an older one current." : "Page tools become available when processing has finished."}</p>}
      {info && (
        <>
          <p>
            {info.count} page{info.count === 1 ? "" : "s"}
            {info.source === "searchable" && " · edits use the searchable PDF, because the original is not a PDF"}
          </p>
          {info.signed && (
            <div className="mail-warning pages-signed" role="note">
              <p>This PDF is digitally signed. Saving changed pages creates a new, unsigned version. The signed file stays available as an older version.</p>
              <label><input type="checkbox" checked={acceptSignature} onChange={(event) => setAcceptSignature(event.target.checked)} /> I understand the new version will not be signed</label>
            </div>
          )}
          <ol className="pages-grid">
            {pages.map((item, position) => (
              <li key={item.index} className={item.removed ? "removed" : undefined}>
                <div className="page-thumb">
                  <img src={`/api/documents/${documentId}/pages/${item.index + 1}.png?v=${info.version_number}`} alt={`Page ${item.index + 1}`}
                    style={{ transform: `rotate(${item.rotation}deg)` }} loading="lazy" />
                </div>
                <strong>Page {item.index + 1}{item.removed ? " · removed" : ""}</strong>
                <div className="page-actions">
                  <button type="button" aria-label={`Rotate page ${item.index + 1} left`} onClick={() => update(position, { rotation: (item.rotation + 270) % 360 })}><RotateCcw size={16} aria-hidden="true" /></button>
                  <button type="button" aria-label={`Rotate page ${item.index + 1} right`} onClick={() => update(position, { rotation: (item.rotation + 90) % 360 })}><RotateCw size={16} aria-hidden="true" /></button>
                  <button type="button" aria-label={`Move page ${item.index + 1} earlier`} aria-disabled={position === 0} onClick={() => position > 0 && move(position, -1)}><ArrowLeft size={16} aria-hidden="true" /></button>
                  <button type="button" aria-label={`Move page ${item.index + 1} later`} aria-disabled={position === pages.length - 1} onClick={() => position < pages.length - 1 && move(position, 1)}><ArrowRight size={16} aria-hidden="true" /></button>
                  <button type="button" aria-label={`Remove page ${item.index + 1}`} aria-pressed={item.removed}
                    onClick={() => update(position, { removed: !item.removed })}>{item.removed ? <Undo2 size={16} aria-hidden="true" /> : <Trash2 size={16} aria-hidden="true" />}</button>
                </div>
                {position < pages.length - 1 && (
                  <label className="page-split">
                    <input type="checkbox" checked={splitAfter.includes(position)} onChange={() => setSplitAfter((value) => value.includes(position) ? value.filter((entry) => entry !== position) : [...value, position])} />
                    New document after page {item.index + 1}
                  </label>
                )}
              </li>
            ))}
          </ol>
          {moved && !notice && <p className="visually-hidden" role="status">{moved}</p>}
          <div className="pages-footer">
            <Button type="button" disabled={busy || !changed || kept.length === 0 || needsConsent} onClick={saveVersion}>Save as new version</Button>
            <Button type="button" variant="secondary" disabled={busy || groups.length < 2} onClick={split}>
              <Scissors size={16} aria-hidden="true" /> {groups.length < 2 ? "Split into documents" : `Split into ${groups.length} documents`}
            </Button>
            {(changed || splitAfter.length > 0) && <Button type="button" variant="secondary" disabled={busy} onClick={() => void load()}>Undo changes</Button>}
          </div>
          {kept.length === 0 && <p className="mail-warning">Keep at least one page.</p>}
        </>
      )}
      {versions && (
        <div className="pages-versions">
          <h4><History size={16} aria-hidden="true" /> Versions</h4>
          <ul>
            <li>
              <strong>Version {versions.current.number} · current</strong>
              <span>{versions.current.note} · {new Date(versions.current.created_at).toLocaleString()} · {size(versions.current.size)}</span>
            </li>
            {versions.versions.map((version) => (
              <li key={version.id}>
                <strong>Version {version.number}</strong>
                <span>{version.note} · {new Date(version.created_at).toLocaleString()} · {size(version.size)}</span>
                <div className="page-actions">
                  <a href={`/api/documents/${documentId}/versions/${version.id}/download`}><ArrowDownToLine size={16} aria-hidden="true" /> Download</a>
                  <button type="button" disabled={busy || !editable} onClick={() => restore(version)}>Make current</button>
                </div>
              </li>
            ))}
          </ul>
          <label className={`pages-upload button button-secondary${busy || !editable ? " is-disabled" : ""}`}>
            <Upload size={16} aria-hidden="true" /> Upload a new version
            <input className="visually-hidden" type="file" accept="application/pdf,image/jpeg,image/png,.eml,.msg,.docx,.xlsx,.pptx,.doc,.xls,.ppt,.odt,.ods,.odp,.rtf"
              disabled={busy || !editable} onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ""; if (file) uploadVersion(file); }} />
          </label>
        </div>
      )}
    </section>
  );
}
