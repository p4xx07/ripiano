import { useEffect, useState } from "react";
import { Brain, RotateCw } from "lucide-react";
import { request } from "./api";
import { Button } from "./ui";

type KindMetrics = { examples: number; labels: number; ready: boolean; precision?: number | null; coverage?: number; brier?: number; accuracy?: number };
type Status = {
  status: "none" | "queued" | "training" | "ready" | "not_enough" | "failed";
  trained_at: string | null;
  examples: number;
  threshold: number;
  error: string;
  metrics: Partial<Record<"correspondents" | "document_types" | "tags", KindMetrics>>;
};

const kindLabels = { correspondents: "Senders", document_types: "Document types", tags: "Tags" } as const;

const needs = {
  correspondents: "file at least 3 documents each for 2 or more senders",
  document_types: "file at least 3 documents each for 2 or more types",
  tags: "tag at least 3 documents with the same tag",
} as const;

function describe(kind: keyof typeof needs, metrics: KindMetrics | undefined) {
  if (!metrics) return "Not learned yet";
  if (!metrics.ready) return `Needs more examples: ${needs[kind]} yourself`;
  if (metrics.precision == null || !metrics.coverage) return `Learned from ${metrics.examples} documents · not confident enough to suggest yet`;
  return `Learned from ${metrics.examples} documents · on documents it had not seen, ${Math.round(metrics.precision * 100)}% of its suggestions were right, and it suggested something for ${Math.round(metrics.coverage * 100)}% of them`;
}

export default function LearningPanel() {
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    try {
      setStatus(await request<Status>("/api/filing-model"));
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load learning status");
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
      setNotice("Learning started. This usually takes under a minute.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not start learning");
    } finally {
      setBusy(false);
    }
  }

  const running = status?.status === "queued" || status?.status === "training";
  return <section className="tag-create-card learning-panel" aria-labelledby="learning-heading">
    <h2 id="learning-heading"><Brain size={18} aria-hidden="true" /> Learned suggestions</h2>
    <p>Ripiano learns from senders, types, and tags you set yourself, on this server only. It suggests only when it is at least {Math.round((status?.threshold ?? 0.6) * 100)}% likely to be right, and never files anything without you. It relearns every night.</p>
    {error && <p className="inline-error" role="alert">{error}</p>}
    {notice && <p className="bulk-notice">{notice}</p>}
    {status && <>
      <p className="learning-state" role="status" aria-live="polite">
        {running ? "Learning…" : status.status === "failed" ? `Last attempt failed: ${status.error}` : status.trained_at ? `Last learned ${new Date(status.trained_at).toLocaleString()}` : "Not learned yet"}
      </p>
      {status.trained_at && <dl className="shared-facts">
        {(Object.keys(kindLabels) as (keyof typeof kindLabels)[]).map((kind) => <div key={kind} className="learning-row">
          <dt>{kindLabels[kind]}</dt><dd>{describe(kind, status.metrics[kind])}</dd>
        </div>)}
      </dl>}
    </>}
    <Button type="button" variant="secondary" disabled={busy || running} onClick={() => void retrain()}><RotateCw size={16} aria-hidden="true" /> {running ? "Learning…" : "Learn now"}</Button>
  </section>;
}
