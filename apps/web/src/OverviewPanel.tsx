import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, X } from "lucide-react";
import { request } from "./api";

type Overview = {
  documents: { total: number; ready: number; waiting: number; failed: number; needs_action: number; overdue: number; untagged: number; duplicates: number; bytes: number };
  monthly: { month: string; count: number }[];
  by_type: { name: string; count: number }[];
  by_source: Record<string, number>;
  top_tags: { name: string; count: number }[];
  health: {
    backup: { status: string; at: string } | null;
    mailboxes: { total: number; with_errors: number };
    workflows: { enabled: number; failed_last_week: number };
    queues: { celery: number; maintenance: number } | null;
  };
};

const sources: Record<string, string> = { web: "Web", android: "Android", telegram: "Telegram", folder: "Watched folder", email: "Email" };

function size(bytes: number) {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(0)} MB`;
  return `${Math.max(0, Math.round(bytes / 1024))} KB`;
}

function monthLabel(value: string) {
  const [year, month] = value.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString(undefined, { month: "short", year: "2-digit" });
}

function Ranked({ title, rows }: { title: string; rows: { name: string; count: number }[] }) {
  const max = Math.max(1, ...rows.map((row) => row.count));
  return (
    <section className="overview-card" aria-labelledby={`overview-${title}`}>
      <h2 id={`overview-${title}`}>{title}</h2>
      {rows.length ? (
        <ol className="overview-ranked">
          {rows.map((row) => (
            <li key={row.name}>
              <span className="overview-ranked-name">{row.name}</span>
              <span className="overview-ranked-bar" aria-hidden="true"><i style={{ width: `${(row.count / max) * 100}%` }} /></span>
              <span className="overview-ranked-value">{row.count.toLocaleString()}</span>
            </li>
          ))}
        </ol>
      ) : <p className="agent-empty-activity">Nothing yet.</p>}
    </section>
  );
}

export default function OverviewPanel({ onNavigate, onOpenUntagged }: {
  onNavigate: (view: "inbox" | "actions" | "documents" | "backups" | "integrations" | "workflows") => void;
  onOpenUntagged: () => void;
}) {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [active, setActive] = useState<number | null>(null);

  useEffect(() => {
    request<Overview>("/api/overview").then(setData).catch((cause) => setError(cause instanceof Error ? cause.message : "Could not load the overview"));
  }, []);

  const docs = data?.documents;
  const max = Math.max(1, ...(data?.monthly ?? []).map((row) => row.count));
  const attention = docs ? [
    { count: docs.failed, label: "could not be read", view: "inbox" as const },
    { count: docs.overdue, label: "follow-ups are overdue", view: "actions" as const },
    { count: docs.duplicates, label: "exact copies to review", view: "inbox" as const },
    { count: data?.health.mailboxes.with_errors ?? 0, label: "mailboxes have a problem", view: "integrations" as const },
    { count: data?.health.workflows.failed_last_week ?? 0, label: "workflow runs failed this week", view: "workflows" as const },
  ].filter((item) => item.count > 0) : [];

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> AT A GLANCE</div>
          <h1>Overview<span className="heading-period">.</span></h1>
          <p>How your archive is growing, and anything that needs you.</p>
        </div>
      </div>
      {error && <div className="inline-error" role="alert">{error}<button onClick={() => setError("")} aria-label="Dismiss error"><X size={16} /></button></div>}
      {docs && data && (
        <>
          <div className="overview-tiles">
            <div className="overview-tile"><strong>{docs.total.toLocaleString()}</strong><span>documents</span></div>
            <div className="overview-tile"><strong>{size(docs.bytes)}</strong><span>of originals</span></div>
            <div className="overview-tile"><strong>{docs.needs_action.toLocaleString()}</strong><span>need action</span></div>
            <div className="overview-tile"><strong>{docs.waiting.toLocaleString()}</strong><span>being processed</span></div>
          </div>

          <section className={`overview-card overview-attention${attention.length ? "" : " calm"}`} aria-labelledby="overview-attention">
            <h2 id="overview-attention">{attention.length ? <><AlertTriangle size={18} aria-hidden="true" /> Needs a look</> : <><CheckCircle2 size={18} aria-hidden="true" /> All calm</>}</h2>
            {attention.length ? (
              <ul>
                {attention.map((item) => (
                  <li key={item.label}><button type="button" className="text-action" onClick={() => onNavigate(item.view)}>{item.count.toLocaleString()} {item.label}</button></li>
                ))}
              </ul>
            ) : <p>Nothing is waiting for you.</p>}
            <p className="overview-health">
              {data.health.backup ? `Last backup: ${data.health.backup.status === "complete" ? "completed" : data.health.backup.status} ${new Date(data.health.backup.at).toLocaleString()}` : "Backups are visible to the archive owner."}
              {" · "}{data.health.mailboxes.total} mailbox{data.health.mailboxes.total === 1 ? "" : "es"} · {data.health.workflows.enabled} active workflow{data.health.workflows.enabled === 1 ? "" : "s"}
              {" · "}{docs.untagged ? <button type="button" className="text-action" onClick={onOpenUntagged}>{docs.untagged.toLocaleString()} without tags · View in Library</button> : "0 without tags"}
              {data.health.queues && <>{" · "}Background queues: {data.health.queues.celery.toLocaleString()} OCR, {data.health.queues.maintenance.toLocaleString()} maintenance waiting</>}
            </p>
          </section>

          <section className="overview-card" aria-labelledby="overview-monthly">
            <h2 id="overview-monthly">Documents added per month</h2>
            {data.monthly.some((row) => row.count > 0) ? (
              <>
                <div className="overview-bars" role="img" aria-label={`Documents added per month over the last year, up to ${max.toLocaleString()} in one month`}>
                  {data.monthly.map((row, index) => (
                    <div key={row.month} className="overview-bar-slot" onMouseEnter={() => setActive(index)} onMouseLeave={() => setActive(null)}>
                      {active === index && <span className="overview-tooltip">{monthLabel(row.month)}: {row.count.toLocaleString()}</span>}
                      <i className={active === index ? "active" : undefined} style={{ height: `${Math.max(2, (row.count / max) * 100)}%` }} />
                      <small>{monthLabel(row.month)}</small>
                    </div>
                  ))}
                </div>
                <table className="visually-hidden">
                  <caption>Documents added per month</caption>
                  <thead><tr><th scope="col">Month</th><th scope="col">Documents</th></tr></thead>
                  <tbody>{data.monthly.map((row) => <tr key={row.month}><td>{monthLabel(row.month)}</td><td>{row.count}</td></tr>)}</tbody>
                </table>
              </>
            ) : <p className="agent-empty-activity">Nothing added in the last year.</p>}
          </section>

          <div className="overview-grid">
            <Ranked title="Document types" rows={data.by_type} />
            <Ranked title="Most used tags" rows={data.top_tags} />
            <Ranked title="Where documents come from" rows={Object.entries(data.by_source).map(([key, count]) => ({ name: sources[key] ?? key, count })).sort((a, b) => b.count - a.count)} />
          </div>
        </>
      )}
    </>
  );
}
