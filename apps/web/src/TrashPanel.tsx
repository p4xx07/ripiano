import { useCallback, useEffect, useState } from "react";
import { FileText, RotateCcw, Trash2, X } from "lucide-react";
import { Document, formatDate, request } from "./api";
import { Button, Modal } from "./ui";

type PurgeJob = {
  id: string;
  title: string;
  status: "pending" | "running" | "complete" | "failed";
  error: string;
  created_at: string;
  completed_at: string | null;
};

export default function TrashPanel({ refreshKey, onRestored }: { refreshKey: number; onRestored: () => void }) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [confirmPurge, setConfirmPurge] = useState<Document | null>(null);
  const [purgeJobs, setPurgeJobs] = useState<PurgeJob[]>([]);

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

  const loadPurgeJobs = useCallback(async () => {
    try {
      const result = await request<{ jobs: PurgeJob[] }>("/api/purge-jobs");
      setPurgeJobs(result.jobs);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load deletion status");
    }
  }, []);

  useEffect(() => { void load(); void loadPurgeJobs(); }, [load, loadPurgeJobs, refreshKey]);
  useEffect(() => {
    if (!purgeJobs.some((job) => job.status === "pending" || job.status === "running")) return;
    const timer = window.setInterval(() => void loadPurgeJobs(), 5000);
    return () => window.clearInterval(timer);
  }, [purgeJobs, loadPurgeJobs]);

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

  async function purge(document: Document) {
    setBusyId(document.id);
    setError("");
    setNotice("");
    try {
      await request(`/api/documents/${document.id}/purge`, { method: "POST" });
      setDocuments((previous) => previous.filter((item) => item.id !== document.id));
      setSelectedIds((previous) => previous.filter((id) => id !== document.id));
      setConfirmPurge(null);
      setNotice("Deletion requested. Live files are removed after any running backup finishes; older backups follow their retention schedule.");
      await loadPurgeJobs();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete document");
    } finally {
      setBusyId(null);
    }
  }

  async function retryPurge(job: PurgeJob) {
    setBusyId(job.id);
    setError("");
    try {
      await request(`/api/purge-jobs/${job.id}/retry`, { method: "POST" });
      setNotice("File cleanup queued again.");
      await loadPurgeJobs();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not retry file cleanup");
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
      <Button type="button" variant="danger" disabled={busyId !== null} onClick={() => setConfirmPurge(document)}><Trash2 size={16} /> Delete permanently</Button>
    </article>)}</div>}
    {nextCursor && <Button type="button" variant="secondary" disabled={loading || busyId !== null} onClick={() => void load(nextCursor)}>Show more</Button>}
    {purgeJobs.length > 0 && <section className="purge-jobs">
      <h2>Recent permanent deletions</h2>
      <p>Live files are removed after any running backup finishes. Existing snapshots may retain them until their retention period ends.</p>
      <ul>{purgeJobs.map((job) => <li key={job.id} data-job-id={job.id}>
        <span>{job.title || `Deleted ${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(job.completed_at || job.created_at))} · Ref ${job.id.slice(0, 8)}`}</span>
        <span className={`status status-${job.status === "complete" ? "ready" : job.status === "failed" ? "failed" : "pending"}`}>{job.status === "complete" ? "Files removed" : job.status === "failed" ? "Cleanup failed" : "Cleaning up"}</span>
        {job.error && <small>{job.error}</small>}
        {job.status === "failed" && <Button type="button" variant="secondary" disabled={busyId !== null} onClick={() => void retryPurge(job)}><RotateCcw size={16} /> Retry cleanup</Button>}
      </li>)}</ul>
    </section>}
    {confirmPurge && <Modal titleId="purge-title" panelClassName="add-modal purge-modal" onClose={() => { if (!busyId) setConfirmPurge(null); }}>
      <button type="button" className="modal-close" aria-label="Close" disabled={busyId !== null} onClick={() => setConfirmPurge(null)}><X size={20} /></button>
      <h2 id="purge-title">Delete permanently?</h2>
      <p>“{confirmPurge.title}” and its original, searchable PDF, notes, tags, and paper-copy history will leave this archive. {confirmPurge.physical_copies.length > 0 && `${confirmPurge.physical_copies.length} real-world sticker ${confirmPurge.physical_copies.length === 1 ? "label will" : "labels will"} stop working. `}Older backups may retain copies until their retention period ends.</p>
      {error && <p className="inline-error" role="alert">{error}</p>}
      <div className="trash-confirm">
        <Button type="button" variant="danger" disabled={busyId !== null} onClick={() => void purge(confirmPurge)}><Trash2 size={16} /> Confirm permanent deletion</Button>
        <Button type="button" variant="secondary" disabled={busyId !== null} onClick={() => setConfirmPurge(null)}>Cancel</Button>
      </div>
    </Modal>}
  </>;
}
