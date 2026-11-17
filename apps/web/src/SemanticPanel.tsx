import { FormEvent, useCallback, useEffect, useState } from "react";
import { Sparkles, X } from "lucide-react";
import { request } from "./api";
import { Button } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/SemanticPanel";

type Mode = "off" | "ollama" | "nas";
type Status = {
  mode: Mode; ollama_url: string; model_name: string; keep_loaded: boolean; effective_model: string | null;
  defaults: { ollama: string; nas: string }; database_supported: boolean; storage_ready: boolean;
  documents: { total: number; waiting: number | null; indexed: number | null };
  last_error: string; last_error_at: string | null;
};

/** Archive-owner settings for optional semantic search. */
export default function SemanticPanel() {
  const m = useMessages(messages);
  const modes: { value: Mode; label: string; detail: string }[] = [
    { value: "off", label: m.modeOff, detail: m.modeOffDetail },
    { value: "ollama", label: m.modeOllama, detail: m.modeOllamaDetail },
    { value: "nas", label: m.modeNas, detail: m.modeNasDetail },
  ];
  const [status, setStatus] = useState<Status | null>(null);
  const [mode, setMode] = useState<Mode>("off");
  const [url, setUrl] = useState("");
  const [model, setModel] = useState("");
  const [keep, setKeep] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const apply = (next: Status) => {
    setStatus(next);
    setMode(next.mode);
    setUrl(next.ollama_url);
    setModel(next.model_name);
    setKeep(next.keep_loaded);
  };
  const load = useCallback(async () => {
    try { apply(await request<Status>("/api/semantic-settings")); }
    catch (cause) { setError(cause instanceof Error ? cause.message : m.loadError); }
  }, [m]);
  useEffect(() => { void load(); }, [load]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try { await action(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : m.actionError); }
    finally { setBusy(false); }
  }

  function save(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      apply(await request<Status>("/api/semantic-settings", { method: "PATCH", body: JSON.stringify({ mode, ollama_url: url, model_name: model, keep_loaded: keep }) }));
      setNotice(mode === "off" ? m.savedOff : m.savedOn);
    });
  }

  function test() {
    void run(async () => {
      const result = await request<{ ok: boolean; dimensions: number; model: string }>("/api/semantic-settings/test", { method: "POST" });
      setNotice(m.connectionWorks(result.model));
      await load();
    });
  }

  if (!status) return error ? <div className="inline-error" role="alert">{error}</div> : null;
  const docs = status.documents;
  return (
    <section className="tag-create-card semantic-card" aria-labelledby="semantic-heading">
      <div className="tag-create-icon"><Sparkles size={21} aria-hidden="true" /></div>
      <h2 id="semantic-heading">{m.heading}</h2>
      <p>{m.intro}</p>
      {error && <div className="inline-error" role="alert">{error}<button onClick={() => setError("")} aria-label={m.dismissError}><X size={16} /></button></div>}
      {notice && <p className="bulk-notice" role="status">{notice}</p>}
      {!status.database_supported && (
        <p className="inline-error">{m.noPgvectorBefore}<code>pgvector/pgvector:pg17</code>{m.noPgvectorAfter}</p>
      )}
      <form onSubmit={save} aria-label={m.formLabel}>
        <fieldset>
          <legend>{m.whereModelRuns}</legend>
          {modes.map((item) => (
            <label className="agent-scope-choice semantic-mode" key={item.value}>
              <input type="radio" name="semantic-mode" value={item.value} checked={mode === item.value} onChange={() => setMode(item.value)} />
              <span><strong>{item.label}</strong><small>{item.detail}</small></span>
            </label>
          ))}
        </fieldset>
        {mode === "ollama" && (
          <label>{m.ollamaAddress}<input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="http://192.168.1.30:11434" required autoCapitalize="none" spellCheck={false} /></label>
        )}
        {mode !== "off" && (
          <>
            <label>{m.model}<small>{m.leaveEmpty(mode === "ollama" ? status.defaults.ollama : status.defaults.nas)}{mode === "ollama" ? m.ollamaPull : ""}</small>
              <input value={model} onChange={(event) => setModel(event.target.value)} maxLength={200} autoCapitalize="none" spellCheck={false} />
            </label>
            <label className="agent-scope-choice"><input type="checkbox" checked={keep} onChange={(event) => setKeep(event.target.checked)} />
              {m.keepLoaded}</label>
          </>
        )}
        <div className="semantic-actions">
          <Button disabled={busy}>{m.save}</Button>
          {status.mode !== "off" && <Button type="button" variant="secondary" disabled={busy} onClick={test}>{m.testConnection}</Button>}
        </div>
      </form>
      {status.mode !== "off" && (
        <p className="overview-health">
          {m.ready(docs.indexed?.toLocaleString() ?? "", docs.total.toLocaleString())}
          {docs.waiting ? m.waiting(docs.waiting.toLocaleString()) : ""}
          {status.last_error && <><br />{m.lastProblem(status.last_error, status.last_error_at ? new Date(status.last_error_at).toLocaleString() : null)}</>}
        </p>
      )}
    </section>
  );
}

type Result = { document: { id: string; title: string }; passage: string; similarity: number };
// Weaker matches are mostly noise for a person scanning the Library; agents still receive them via MCP.
const MIN_SIMILARITY = 0.3;

/** "Related by meaning" results shown above the Library list while semantic search is on. */
export function MeaningResults({ query, onOpenDocument }: { query: string; onOpenDocument: (id: string) => void }) {
  const m = useMessages(messages);
  const [available, setAvailable] = useState(false);
  const [results, setResults] = useState<Result[]>([]);
  const [problem, setProblem] = useState("");

  useEffect(() => {
    request<{ enabled: boolean }>("/api/semantic-search/available").then((value) => setAvailable(value.enabled)).catch(() => setAvailable(false));
  }, []);

  // Plain-language questions only: field syntax such as tag:… is handled by the normal search.
  const question = query.trim();
  const usable = available && question.length >= 3 && !/\b\w+:/.test(question);
  useEffect(() => {
    setResults([]);
    setProblem("");
    if (!usable) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      request<{ results: Result[]; error?: string }>(`/api/semantic-search?q=${encodeURIComponent(question)}`)
        .then((value) => { if (!cancelled) setResults(value.results.filter((item) => item.similarity >= MIN_SIMILARITY).slice(0, 5)); })
        .catch((cause) => { if (!cancelled) setProblem(cause instanceof Error ? cause.message : m.unavailable); });
    }, 600);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [question, usable, m]);

  if (!usable || (!results.length && !problem)) return null;
  return (
    <section className="meaning-results" aria-labelledby="meaning-heading">
      <h2 id="meaning-heading"><Sparkles size={16} aria-hidden="true" /> {m.related}</h2>
      {problem ? <p className="overview-health">{problem}</p> : (
        <ol>
          {results.map((item) => (
            <li key={item.document.id}>
              <button type="button" className="text-action" onClick={() => onOpenDocument(item.document.id)}>{item.document.title}</button>
              {item.passage && <small>{item.passage.length > 220 ? `${item.passage.slice(0, 220)}…` : item.passage}</small>}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
