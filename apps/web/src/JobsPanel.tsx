import { useCallback, useEffect, useState } from "react";
import { Activity, X } from "lucide-react";
import { request } from "./api";
import { Button } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/JobsPanel";

type Jobs = {
  documents_waiting: { total: number; items: { id: string; title: string; status: "pending" | "processing"; since: string | null; can_cancel: boolean }[] };
  documents_failed: { total: number; items: { id: string; title: string; error: string; at: string | null }[] };
  purges: { id: string; status: "pending" | "running" | "failed"; error: string; at: string | null; can_retry: boolean }[];
  training: { status: "queued" | "training" | "failed"; error: string; at: string | null; can_retry: boolean } | null;
  workflow_failures: { id: string; workflow: string; document: { id: string; title: string }; detail: string; at: string | null }[];
};

const when = (value: string | null) => (value ? new Date(value).toLocaleString() : "");

/** Background work that is waiting or failed, with the safe controls for each kind. */
export default function JobsPanel({ onOpenDocument, onChanged }: { onOpenDocument: (id: string) => void; onChanged?: () => void }) {
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
  const more = (shown: number, total: number) => (total > shown ? <p className="jobs-more">{m.showing(shown, total.toLocaleString())}</p> : null);

  return (
    <section className="overview-card jobs-card" aria-labelledby="overview-jobs">
      <h2 id="overview-jobs"><Activity size={18} aria-hidden="true" /> {m.heading}</h2>
      {error && <div className="inline-error" role="alert">{error}<button onClick={() => setError("")} aria-label={m.dismissError}><X size={16} /></button></div>}
      {status && <p className="bulk-notice" role="status">{status}</p>}
      {empty && <p>{m.empty}</p>}

      {jobs.documents_waiting.total > 0 && (
        <div className="jobs-group">
          <h3>{m.waitingHeading} <small>{jobs.documents_waiting.total.toLocaleString()}</small></h3>
          <ul>
            {jobs.documents_waiting.items.map((item) => (
              <li key={item.id}>
                <div>
                  <button type="button" className="text-action" onClick={() => onOpenDocument(item.id)}>{item.title}</button>
                  <small>{item.status === "processing" ? m.processingSince(when(item.since)) : m.queuedSince(when(item.since))}</small>
                </div>
                {item.can_cancel && (
                  <Button variant="secondary" disabled={busy !== null} aria-label={m.cancelLabel(item.title)}
                    onClick={() => void act(`cancel-${item.id}`, `/api/documents/${item.id}/cancel-processing`, m.cancelled(item.title))}>
                    {m.cancel}
                  </Button>
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
