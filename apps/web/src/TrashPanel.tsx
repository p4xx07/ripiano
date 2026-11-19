import { useCallback, useEffect, useState } from "react";
import { FileText, RotateCcw, Trash2, X } from "lucide-react";
import { Document, formatDate, formatDateTime, request } from "./api";
import { Button, Modal } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/TrashPanel";

type RetentionPolicy = {
  enabled: boolean;
  days: number;
  eligible_count: number;
  updated_at: string | null;
};

type PurgeJob = {
  id: string;
  title: string;
  status: "pending" | "running" | "complete" | "failed";
  error: string;
  created_at: string;
  completed_at: string | null;
};

export default function TrashPanel({ refreshKey, onRestored }: { refreshKey: number; onRestored: () => void }) {
  const m = useMessages(messages);
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
  const [retention, setRetention] = useState<RetentionPolicy | null>(null);
  const [retentionDays, setRetentionDays] = useState("90");
  const [retentionError, setRetentionError] = useState("");
  const [reviewRetention, setReviewRetention] = useState<RetentionPolicy | null>(null);

  const load = useCallback(async (cursor?: string) => {
    setLoading(true);
    setError("");
    try {
      const result = await request<{ documents: Document[]; next_cursor: string | null }>(`/api/documents?view=trash${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`);
      setDocuments((previous) => cursor ? [...previous, ...result.documents] : result.documents);
      setNextCursor(result.next_cursor);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.loadError);
    } finally {
      setLoading(false);
    }
  }, [m]);

  const loadPurgeJobs = useCallback(async () => {
    try {
      const result = await request<{ jobs: PurgeJob[] }>("/api/purge-jobs");
      setPurgeJobs(result.jobs);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.loadJobsError);
    }
  }, [m]);

  useEffect(() => { void load(); void loadPurgeJobs(); }, [load, loadPurgeJobs, refreshKey]);
  const loadRetention = useCallback(async () => {
    setRetentionError("");
    try {
      const policy = await request<RetentionPolicy>("/api/trash-retention");
      setRetention(policy);
      setRetentionDays(String(policy.days));
    } catch (cause) {
      setRetentionError(cause instanceof Error ? cause.message : m.loadRetentionError);
    }
  }, [m]);
  useEffect(() => { void loadRetention(); }, [loadRetention, refreshKey]);
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
      setNotice(m.restoredOne(document.title));
      onRestored();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.restoreError);
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
      setNotice(m.restoredMany(result.updated));
      onRestored();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.restoreSelectedError);
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
      setNotice(m.purgeRequested);
      await loadPurgeJobs();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.purgeError);
    } finally {
      setBusyId(null);
    }
  }

  async function retryPurge(job: PurgeJob) {
    setBusyId(job.id);
    setError("");
    try {
      await request(`/api/purge-jobs/${job.id}/retry`, { method: "POST" });
      setNotice(m.retryQueued);
      await loadPurgeJobs();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.retryError);
    } finally {
      setBusyId(null);
    }
  }

  async function previewRetention() {
    const days = Number(retentionDays);
    if (!Number.isInteger(days) || days < 30 || days > 3650) {
      setRetentionError(m.daysRange);
      return;
    }
    setBusyId("retention");
    setRetentionError("");
    try {
      setReviewRetention(await request<RetentionPolicy>(`/api/trash-retention?days=${days}`));
    } catch (cause) {
      setRetentionError(cause instanceof Error ? cause.message : m.previewError);
    } finally {
      setBusyId(null);
    }
  }

  async function saveRetention(enabled: boolean, days: number) {
    setBusyId("retention");
    setRetentionError("");
    try {
      const policy = await request<RetentionPolicy>("/api/trash-retention", {
        method: "PUT", body: JSON.stringify({ enabled, days }),
      });
      setRetention(policy);
      setRetentionDays(String(policy.days));
      setReviewRetention(null);
      setNotice(enabled ? m.cleanupOnAfter(days) : m.cleanupOffNotice);
    } catch (cause) {
      setRetentionError(cause instanceof Error ? cause.message : m.saveRetentionError);
    } finally {
      setBusyId(null);
    }
  }

  return <>
    <div className="page-heading trash-heading"><div>
      <div className="eyebrow"><span className="eyebrow-line" /> {m.eyebrow}</div>
      <h1>{m.heading}<span className="heading-period">.</span></h1>
      <p>{m.intro}</p>
    </div></div>
    <div className="section-heading"><div><h2>{m.movedAside}</h2><p>{m.hiddenFrom} {retention ? retention.enabled ? m.cleanupOnAfter(retention.days) : m.nothingErased : m.reviewBelow}</p></div></div>
    {error && <div className="inline-error" role="alert">{error} <button type="button" onClick={() => void load()}>{m.retry}</button></div>}
    {notice && <p className="bulk-notice" role="status">{notice}</p>}
    {loading && !documents.length && <p role="status">{m.loading}</p>}
    {!loading && !documents.length && !error && <div className="empty-state"><div className="empty-icon"><Trash2 size={30} /></div><h3>{m.emptyTitle}</h3><p>{m.emptyText}</p></div>}
    {documents.length > 0 && <div className="bulk-controls">
      <button type="button" className="text-action" disabled={busyId !== null} onClick={() => { setSelectionMode((current) => !current); setSelectedIds([]); }}>
        {selectionMode ? m.doneSelecting : m.selectDocuments}
      </button>
      {selectionMode && <div className="bulk-actions">
        <strong>{m.selected(selectedIds.length)}</strong>
        <button type="button" className="text-action" disabled={busyId !== null} onClick={() => setSelectedIds(documents.slice(0, 100).map((document) => document.id))}>{m.selectLoaded}</button>
        {selectedIds.length > 0 && <button type="button" className="text-action" disabled={busyId !== null} onClick={() => setSelectedIds([])}>{m.clearSelection}</button>}
        <Button type="button" variant="secondary" disabled={busyId !== null || !selectedIds.length} onClick={() => void restoreSelected()}><RotateCcw size={16} /> {m.restoreSelected}</Button>
      </div>}
    </div>}
    {documents.length > 0 && <div className="document-list">{documents.map((document) => <article className={`document-row trash-row${selectionMode ? " trash-row-selecting" : ""}`} key={document.id}>
      {selectionMode && <label className="document-select"><input type="checkbox" aria-label={m.selectDocument(document.title)} checked={selectedIds.includes(document.id)} disabled={busyId !== null || (selectedIds.length >= 100 && !selectedIds.includes(document.id))} onChange={() => setSelectedIds((current) => current.includes(document.id) ? current.filter((id) => id !== document.id) : current.length < 100 ? [...current, document.id] : current)} /></label>}
      <div className="document-icon"><FileText size={21} /></div>
      <div className="document-info"><h3>{document.title}</h3><div className="document-meta">{m.moved(document.trashed_at ? formatDate(document.trashed_at) : m.toTrash)} · {document.original_name}{document.physical_copies.length > 0 && m.paperCopies(document.physical_copies.length)}</div></div>
      <Button type="button" variant="secondary" disabled={busyId !== null} onClick={() => void restore(document)}><RotateCcw size={16} /> {busyId === document.id ? m.restoring : m.restore}</Button>
      <Button type="button" variant="danger" disabled={busyId !== null} onClick={() => setConfirmPurge(document)}><Trash2 size={16} /> {m.deletePermanently}</Button>
    </article>)}</div>}
    {nextCursor && <Button type="button" variant="secondary" disabled={loading || busyId !== null} onClick={() => void load(nextCursor)}>{m.showMore}</Button>}
    <section className="trash-retention">
      <div><h2>{m.cleanupHeading}</h2><p>{retention ? retention.enabled ? m.cleanupOnStatus(retention.days) : m.cleanupOffStatus : m.cleanupLoading}</p></div>
      <div className="trash-retention-controls">
        <label>{m.deleteAfter} <input type="number" min="30" max="3650" step="1" inputMode="numeric" value={retentionDays} disabled={!retention || busyId !== null} onChange={(event) => setRetentionDays(event.target.value)} /> {m.daysInTrash}</label>
        <Button type="button" variant="secondary" disabled={busyId !== null || !retention || (retention.enabled && Number(retentionDays) === retention.days)} onClick={() => void previewRetention()}>{retention?.enabled ? m.reviewChange : m.reviewEnable}</Button>
        {retention?.enabled && <Button type="button" variant="secondary" disabled={busyId !== null} onClick={() => void saveRetention(false, retention.days)}>{m.turnOff}</Button>}
      </div>
      <small>{m.eligibleNote}</small>
      {retentionError && <p className="inline-error" role="alert">{retentionError} {!retention && <button type="button" onClick={() => void loadRetention()}>{m.retry}</button>}</p>}
    </section>
    {purgeJobs.length > 0 && <section className="purge-jobs">
      <h2>{m.recentDeletions}</h2>
      <p>{m.recentDeletionsText}</p>
      <ul>{purgeJobs.map((job) => <li key={job.id} data-job-id={job.id}>
        <span>{job.title || m.deletedJob(formatDateTime(job.completed_at || job.created_at), job.id.slice(0, 8))}</span>
        <span className={`status status-${job.status === "complete" ? "ready" : job.status === "failed" ? "failed" : "pending"}`}>{job.status === "complete" ? m.filesRemoved : job.status === "failed" ? m.cleanupFailed : m.cleaningUp}</span>
        {job.error && <small>{job.error}</small>}
        {job.status === "failed" && <Button type="button" variant="secondary" disabled={busyId !== null} onClick={() => void retryPurge(job)}><RotateCcw size={16} /> {m.retryCleanup}</Button>}
      </li>)}</ul>
    </section>}
    {reviewRetention && <Modal titleId="retention-title" panelClassName="add-modal purge-modal" onClose={() => { if (!busyId) setReviewRetention(null); }}>
      <button type="button" className="modal-close" aria-label={m.close} disabled={busyId !== null} onClick={() => setReviewRetention(null)}><X size={20} /></button>
      <h2 id="retention-title">{retention?.enabled ? m.changeCleanupTitle : m.enableCleanupTitle}</h2>
      <p>{m.cleanupConfirmText(reviewRetention.days, reviewRetention.eligible_count)}</p>
      {retentionError && <p className="inline-error" role="alert">{retentionError}</p>}
      <div className="trash-confirm">
        <Button type="button" variant="danger" disabled={busyId !== null} onClick={() => void saveRetention(true, reviewRetention.days)}>{m.confirmCleanup}</Button>
        <Button type="button" variant="secondary" disabled={busyId !== null} onClick={() => setReviewRetention(null)}>{m.cancel}</Button>
      </div>
    </Modal>}
    {confirmPurge && <Modal titleId="purge-title" panelClassName="add-modal purge-modal" onClose={() => { if (!busyId) setConfirmPurge(null); }}>
      <button type="button" className="modal-close" aria-label={m.close} disabled={busyId !== null} onClick={() => setConfirmPurge(null)}><X size={20} /></button>
      <h2 id="purge-title">{m.purgeTitle}</h2>
      <p>{m.purgeText(confirmPurge.title)}{confirmPurge.physical_copies.length > 0 && m.purgeStickers(confirmPurge.physical_copies.length)}{m.purgeBackups}</p>
      {error && <p className="inline-error" role="alert">{error}</p>}
      <div className="trash-confirm">
        <Button type="button" variant="danger" disabled={busyId !== null} onClick={() => void purge(confirmPurge)}><Trash2 size={16} /> {m.confirmPurge}</Button>
        <Button type="button" variant="secondary" disabled={busyId !== null} onClick={() => setConfirmPurge(null)}>{m.cancel}</Button>
      </div>
    </Modal>}
  </>;
}
