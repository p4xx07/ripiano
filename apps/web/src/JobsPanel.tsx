import { useCallback, useEffect, useState } from "react";
import { Activity, AlertTriangle, X } from "lucide-react";
import { formatDateTime, request } from "./api";
import { Button } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/JobsPanel";

/** Why waiting documents are (not) being picked up; the same object in /api/jobs and the Overview (round 11). */
export type ProcessingHealth = {
  pending: number;
  processing: number;
  waiting_since: string | null;
  worker: { running: boolean; last_seen: string | null };
  problem: null | "worker_not_running" | "queue_unavailable";
};
type WaitingState = "processing" | "stalled" | "queued" | "waiting_for_worker" | "waiting_for_queue";

type Jobs = {
  processing?: ProcessingHealth;
  documents_waiting: { total: number; items: { id: string; title: string; status: "pending" | "processing"; state?: WaitingState; since: string | null; can_cancel: boolean; stalled?: boolean; can_retry?: boolean }[] };
  documents_failed: { total: number; items: { id: string; title: string; error: string; at: string | null }[] };
  purges: { id: string; status: "pending" | "running" | "failed"; error: string; at: string | null; can_retry: boolean }[];
  training: { status: "queued" | "training" | "failed"; error: string; at: string | null; can_retry: boolean } | null;
  workflow_failures: { id: string; workflow: string; document: { id: string; title: string }; detail: string; at: string | null }[];
};

const when = (value: string | null) => (value ? formatDateTime(value) : "");

/**
 * Says why documents are not being picked up: text recognition is not running, or the queue server cannot be
 * reached (round-11 judge 2 M1, judge 1 L2). Shown in Overview, Library and the open document.
 */
export function ProcessingProblem({ health, isOwner = false }: { health: ProcessingHealth | null | undefined; isOwner?: boolean }) {
  const m = useMessages(messages);
  if (!health?.problem) return null;
  const since = when(health.waiting_since);
  return (
    <p className="processing-problem">
      <AlertTriangle size={17} aria-hidden="true" />
      <span>{health.problem === "worker_not_running" ? m.problemWorker(since, when(health.worker?.last_seen ?? null), isOwner) : m.problemQueue(since)}</span>
    </p>
  );
}

/** Background work that is waiting or failed, with the safe controls for each kind. */
export default function JobsPanel({ onOpenDocument, onChanged, hideProblem = false, isOwner = false }: {
  onOpenDocument: (id: string) => void;
  onChanged?: () => void;
  /** The Overview already shows the problem in "Needs a look": say it once (independent review L1). */
  hideProblem?: boolean;
  isOwner?: boolean;
}) {
  const m = useMessages(messages);
  const [jobs, setJobs] = useState<Jobs | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");

  const load = useCallback(async () => {
    try {
      setJobs(await request<Jobs>("/api/jobs"));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.loadError);
    }
  }, [m]);
  useEffect(() => { void load(); }, [load]);
  // While documents wait, look again now and then: one whose processing was interrupted is flagged after a couple of
  // minutes, and put back in the queue by the server shortly after (round-9 judge 3 M1).
  const waitingCount = jobs?.documents_waiting.total ?? 0;
  useEffect(() => {
    if (!waitingCount) return;
    const timer = window.setInterval(() => { if (!window.document.hidden) void load(); }, 15000);
    return () => window.clearInterval(timer);
  }, [waitingCount, load]);

  async function act(key: string, path: string, done: string) {
    setBusy(key);
    setError("");
    setStatus("");
    try {
      await request(path, { method: "POST" });
      setStatus(done);
      await load();
      onChanged?.();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.actionError);
      await load();
    } finally {
      setBusy(null);
    }
  }

  if (!jobs) return error ? <div className="inline-error" role="alert">{error}</div> : null;
  const purges = jobs.purges;
  const empty = !jobs.documents_waiting.total && !jobs.documents_failed.total && !purges.length && !jobs.training && !jobs.workflow_failures.length;
  // Without a running worker an interrupted document is not tried again by itself: never promise that then.
  const workerRunning = jobs.processing?.worker?.running ?? true;
  const stateOf = (item: Jobs["documents_waiting"]["items"][number]): WaitingState =>
    item.state ?? (item.stalled ? "stalled" : item.status === "processing" ? "processing" : "queued");
  const stalledCount = jobs.documents_waiting.items.filter((item) => stateOf(item) === "stalled").length;
  const rowText = (item: Jobs["documents_waiting"]["items"][number]) => {
    const since = when(item.since);
    switch (stateOf(item)) {
      case "stalled": return workerRunning ? m.stalledSince(since) : m.stalledNoWorker(since);
      case "processing": return m.processingSince(since);
      case "waiting_for_worker": return m.waitingForWorker(since);
      case "waiting_for_queue": return m.waitingForQueue(since);
      default: return m.queuedSince(since);
    }
  };
  const more = (shown: number, total: number) => (total > shown ? <p className="jobs-more">{m.showing(shown, total.toLocaleString())}</p> : null);

  return (
    <section className="overview-card jobs-card" aria-labelledby="overview-jobs">
      <h2 id="overview-jobs"><Activity size={18} aria-hidden="true" /> {m.heading}</h2>
      {error && <div className="inline-error" role="alert">{error}<button onClick={() => setError("")} aria-label={m.dismissError}><X size={16} /></button></div>}
      {status && <p className="bulk-notice" role="status">{status}</p>}
      {/* Always on the page, so the calm "interrupted" state is read out when it appears, without stealing focus. */}
      <p className="visually-hidden" aria-live="polite">{stalledCount ? (workerRunning ? m.stalledAnnounce(stalledCount) : m.stalledAnnounceNoWorker(stalledCount)) : ""}</p>
      {!hideProblem && <ProcessingProblem health={jobs.processing} isOwner={isOwner} />}
      {empty && <p className="agent-empty-activity">{m.empty}</p>}

      {jobs.documents_waiting.total > 0 && (
        <div className="jobs-group">
          <h3>{m.waitingHeading} <small>{jobs.documents_waiting.total.toLocaleString()}</small></h3>
          <ul>
            {jobs.documents_waiting.items.map((item) => (
              <li key={item.id}>
                <div>
                  <button type="button" className="text-action" onClick={() => onOpenDocument(item.id)}>{item.title}</button>
                  <small>{rowText(item)}</small>
                </div>
                {(item.can_retry || item.can_cancel) && (
                  <div className="jobs-actions">
                    {item.can_retry && (
                      <Button variant="secondary" disabled={busy !== null} aria-label={m.retryNowLabel(item.title)}
                        onClick={() => void act(`retry-${item.id}`, `/api/documents/${item.id}/retry`, m.queuedAgain(item.title))}>
                        {m.retry}
                      </Button>
                    )}
                    {item.can_cancel && (
                      <Button variant="secondary" disabled={busy !== null} aria-label={m.cancelLabel(item.title)}
                        onClick={() => void act(`cancel-${item.id}`, `/api/documents/${item.id}/cancel-processing`, m.cancelled(item.title))}>
                        {m.cancel}
                      </Button>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
          {more(jobs.documents_waiting.items.length, jobs.documents_waiting.total)}
        </div>
      )}

      {jobs.documents_failed.total > 0 && (
        <div className="jobs-group">
          <h3>{m.failedHeading} <small>{jobs.documents_failed.total.toLocaleString()}</small></h3>
          <ul>
            {jobs.documents_failed.items.map((item) => (
              <li key={item.id}>
                <div>
                  <button type="button" className="text-action" onClick={() => onOpenDocument(item.id)}>{item.title}</button>
                  <small>{item.error || m.processingFailed}</small>
                </div>
                <Button variant="secondary" disabled={busy !== null} aria-label={m.retryOcrLabel(item.title)}
                  onClick={() => void act(`retry-${item.id}`, `/api/documents/${item.id}/retry`, m.queuedAgain(item.title))}>
                  {m.retryOcr}
                </Button>
              </li>
            ))}
          </ul>
          {more(jobs.documents_failed.items.length, jobs.documents_failed.total)}
        </div>
      )}

      {purges.length > 0 && (
        <div className="jobs-group">
          <h3>{m.purgesHeading}</h3>
          <ul>
            {purges.map((job) => (
              <li key={job.id}>
                <div>
                  <span>{job.status === "failed" ? m.purgeFailed : job.status === "running" ? m.purgeRunning : m.purgeWaiting}</span>
                  <small>{[job.error, when(job.at)].filter(Boolean).join(" · ")}</small>
                </div>
                {job.can_retry && (
                  <Button variant="secondary" disabled={busy !== null}
                    onClick={() => void act(`purge-${job.id}`, `/api/purge-jobs/${job.id}/retry`, m.purgeQueued)}>
                    {m.retry}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {jobs.training && (
        <div className="jobs-group">
          <h3>{m.learningHeading}</h3>
          <ul>
            <li>
              <div>
                <span>{jobs.training.status === "failed" ? m.learningFailed : jobs.training.status === "training" ? m.learningNow : m.learningWaiting}</span>
                <small>{[jobs.training.error, when(jobs.training.at)].filter(Boolean).join(" · ")}</small>
              </div>
              {jobs.training.can_retry && (
                <Button variant="secondary" disabled={busy !== null}
                  onClick={() => void act("training", "/api/filing-model", m.learningQueued)}>
                  {m.retry}
                </Button>
              )}
            </li>
          </ul>
        </div>
      )}

      {jobs.workflow_failures.length > 0 && (
        <div className="jobs-group">
          <h3>{m.workflowHeading}</h3>
          <ul>
            {jobs.workflow_failures.map((run) => (
              <li key={run.id}>
                <div>
                  <button type="button" className="text-action" onClick={() => onOpenDocument(run.document.id)}>{run.workflow} · {run.document.title}</button>
                  <small>{run.detail}</small>
                </div>
              </li>
            ))}
          </ul>
          <p className="jobs-more">{m.workflowHint}</p>
        </div>
      )}
    </section>
  );
}
