import { useCallback, useEffect, useState } from "react";
import { FileText, RotateCcw, Trash2 } from "lucide-react";
import { Document, formatDate, request } from "./api";
import { Button } from "./ui";

export default function TrashPanel({ refreshKey, onRestored }: { refreshKey: number; onRestored: () => void }) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const load = useCallback(async (cursor?: string) => {
    setLoading(true);
    setError("");
    try {
      const result = await request<{ documents: Document[]; next_cursor: string | null }>(`/api/documents?view=trash${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`);
      setDocuments((previous) => cursor ? [...previous, ...result.documents] : result.documents);
      setNextCursor(result.next_cursor);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load Trash");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load, refreshKey]);

  async function restore(document: Document) {
    setBusyId(document.id);
    setError("");
    setNotice("");
    try {
      await request(`/api/documents/${document.id}/restore`, { method: "POST" });
      setDocuments((previous) => previous.filter((item) => item.id !== document.id));
      setSelectedIds((previous) => previous.filter((id) => id !== document.id));
      setNotice(`“${document.title}” is back in the Library.`);
      onRestored();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not restore document");
    } finally {
      setBusyId(null);
    }
  }

  async function restoreSelected() {
    if (!selectedIds.length) return;
    setBusyId("bulk");
    setError("");
    setNotice("");
    try {
      const result = await request<{ updated: number }>("/api/documents/bulk-trash", {
        method: "POST",
        body: JSON.stringify({ action: "restore", document_ids: selectedIds }),
      });
      setDocuments((previous) => previous.filter((item) => !selectedIds.includes(item.id)));
      setSelectedIds([]);
      setNotice(`Restored ${result.updated} ${result.updated === 1 ? "document" : "documents"} to the Library.`);
      onRestored();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not restore selected documents");
    } finally {
      setBusyId(null);
    }
  }

  return <>
    <div className="page-heading trash-heading"><div>
      <div className="eyebrow"><span className="eyebrow-line" /> RECOVER A DOCUMENT</div>
      <h1>Trash<span className="heading-period">.</span></h1>
      <p>Restore a document with its original, notes, tags, and paper stickers.</p>
    </div></div>
    <div className="section-heading"><div><h2>Moved aside</h2><p>Documents here are hidden from search, downloads, and agents. Nothing is erased automatically.</p></div></div>
    {error && <div className="inline-error" role="alert">{error} <button type="button" onClick={() => void load()}>Retry</button></div>}
    {notice && <p className="bulk-notice" role="status">{notice}</p>}
    {loading && !documents.length && <p role="status">Loading Trash…</p>}
    {!loading && !documents.length && !error && <div className="empty-state"><div className="empty-icon"><Trash2 size={30} /></div><h3>Trash is empty</h3><p>Documents moved here can be restored from this page.</p></div>}
    {documents.length > 0 && <div className="bulk-controls">
      <button type="button" className="text-action" disabled={busyId !== null} onClick={() => { setSelectionMode((current) => !current); setSelectedIds([]); }}>
        {selectionMode ? "Done selecting" : "Select documents"}
      </button>
      {selectionMode && <div className="bulk-actions">
        <strong>{selectedIds.length} selected</strong>
        <button type="button" className="text-action" disabled={busyId !== null} onClick={() => setSelectedIds(documents.slice(0, 100).map((document) => document.id))}>Select loaded</button>
        {selectedIds.length > 0 && <button type="button" className="text-action" disabled={busyId !== null} onClick={() => setSelectedIds([])}>Clear selection</button>}
        <Button type="button" variant="secondary" disabled={busyId !== null || !selectedIds.length} onClick={() => void restoreSelected()}><RotateCcw size={16} /> Restore selected</Button>
      </div>}
    </div>}
    {documents.length > 0 && <div className="document-list">{documents.map((document) => <article className={`document-row trash-row${selectionMode ? " trash-row-selecting" : ""}`} key={document.id}>
      {selectionMode && <label className="document-select"><input type="checkbox" aria-label={`Select ${document.title}`} checked={selectedIds.includes(document.id)} disabled={busyId !== null || (selectedIds.length >= 100 && !selectedIds.includes(document.id))} onChange={() => setSelectedIds((current) => current.includes(document.id) ? current.filter((id) => id !== document.id) : current.length < 100 ? [...current, document.id] : current)} /></label>}
      <div className="document-icon"><FileText size={21} /></div>
      <div className="document-info"><h3>{document.title}</h3><div className="document-meta">Moved {document.trashed_at ? formatDate(document.trashed_at) : "to Trash"} · {document.original_name}{document.physical_copies.length > 0 && ` · ${document.physical_copies.length} paper ${document.physical_copies.length === 1 ? "copy" : "copies"}`}</div></div>
      <Button type="button" variant="secondary" disabled={busyId !== null} onClick={() => void restore(document)}><RotateCcw size={16} /> {busyId === document.id ? "Restoring…" : "Restore"}</Button>
    </article>)}</div>}
    {nextCursor && <Button type="button" variant="secondary" disabled={loading || busyId !== null} onClick={() => void load(nextCursor)}>Show more</Button>}
  </>;
}
