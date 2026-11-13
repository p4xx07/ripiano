import { useEffect, useState } from "react";
import { Brain, RotateCw } from "lucide-react";
import { formatDateTime, request } from "./api";
import { Button } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/LearningPanel";

type KindMetrics = { examples: number; labels: number; ready: boolean; precision?: number | null; coverage?: number; brier?: number; accuracy?: number };
type Status = {
  status: "none" | "queued" | "training" | "ready" | "not_enough" | "failed";
  trained_at: string | null;
  examples: number;
  threshold: number;
  error: string;
  metrics: Partial<Record<"correspondents" | "document_types" | "tags", KindMetrics>>;
};

type Text = typeof messages.en;

const kindLabels = { correspondents: "kindCorrespondents", document_types: "kindDocumentTypes", tags: "kindTags" } as const;

const needs = {
  correspondents: "needsCorrespondents",
  document_types: "needsDocumentTypes",
  tags: "needsTags",
} as const;

function describe(m: Text, kind: keyof typeof needs, metrics: KindMetrics | undefined) {
  if (!metrics) return m.notLearned;
  if (!metrics.ready) return m[needs[kind]];
  if (metrics.precision == null || !metrics.coverage) return m.notConfident(metrics.examples);
  return m.learned(metrics.examples, Math.round(metrics.precision * 100), Math.round(metrics.coverage * 100));
}

export default function LearningPanel() {
  const m = useMessages(messages);
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    try {
      setStatus(await request<Status>("/api/filing-model"));
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.loadError);
    }
  }

  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (status && status.status !== "queued" && status.status !== "training") setNotice("");
    if (status?.status !== "queued" && status?.status !== "training") return;
    const timer = window.setInterval(() => void load(), 3000);
    return () => window.clearInterval(timer);
  }, [status?.status]);

  async function retrain() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      setStatus(await request<Status>("/api/filing-model", { method: "POST" }));
      setNotice(m.started);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.startError);
    } finally {
      setBusy(false);
    }
  }

  const running = status?.status === "queued" || status?.status === "training";
  return <section className="tag-create-card learning-panel" aria-labelledby="learning-heading">
    <h2 id="learning-heading"><Brain size={18} aria-hidden="true" /> {m.heading}</h2>
    <p>{m.intro(Math.round((status?.threshold ?? 0.6) * 100))}</p>
    {error && <p className="inline-error" role="alert">{error}</p>}
    {notice && <p className="bulk-notice">{notice}</p>}
    {status && <>
      <p className="learning-state" role="status" aria-live="polite">
        {running ? m.learning : status.status === "failed" ? m.failed(status.error) : status.trained_at ? m.lastLearned(formatDateTime(status.trained_at)) : m.notLearned}
      </p>
      {status.trained_at && <dl className="shared-facts">
        {(Object.keys(kindLabels) as (keyof typeof kindLabels)[]).map((kind) => <div key={kind} className="learning-row">
          <dt>{m[kindLabels[kind]]}</dt><dd>{describe(m, kind, status.metrics[kind])}</dd>
        </div>)}
      </dl>}
    </>}
    <Button type="button" variant="secondary" disabled={busy || running} onClick={() => void retrain()}><RotateCw size={16} aria-hidden="true" /> {running ? m.learning : m.learnNow}</Button>
  </section>;
}
