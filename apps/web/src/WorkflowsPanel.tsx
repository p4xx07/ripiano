import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Bell, Clock, Plus, Tag as TagIcon, Workflow as WorkflowIcon, X } from "lucide-react";
import { FilingItem, request, Tag } from "./api";
import { Button } from "./ui";

type Trigger = "added" | "updated" | "scheduled";
type DateField = "created" | "document_date" | "action_due_date";
type Flow = {
  id: string; name: string; enabled: boolean; order: number; trigger: Trigger; schedule_field: DateField; schedule_days: number;
  filter_sources: string[]; filter_filename: string; filter_text: string; filter_tag_id: string | null;
  filter_correspondent_id: string | null; filter_document_type_id: string | null; add_tag_ids: string[]; remove_tag_ids: string[];
  set_correspondent_id: string | null; set_document_type_id: string | null; set_needs_action: boolean; action_note: string;
  add_note: string; webhook_url: string; email_to: string; email_attach: boolean;
};
type Run = { id: string; workflow: string; document: { id: string; title: string }; trigger: Trigger; status: "applied" | "failed"; detail: string; created_at: string };
type Draft = Omit<Flow, "id" | "filter_tag_id" | "filter_correspondent_id" | "filter_document_type_id" | "set_correspondent_id" | "set_document_type_id"> & {
  filter_tag_id: string; filter_correspondent_id: string; filter_document_type_id: string; set_correspondent_id: string; set_document_type_id: string;
};

const empty: Draft = {
  name: "", enabled: true, order: 0, trigger: "added", schedule_field: "created", schedule_days: 30, filter_sources: [], filter_filename: "",
  filter_text: "", filter_tag_id: "", filter_correspondent_id: "", filter_document_type_id: "", add_tag_ids: [], remove_tag_ids: [],
  set_correspondent_id: "", set_document_type_id: "", set_needs_action: false, action_note: "", add_note: "", webhook_url: "", email_to: "", email_attach: false,
};
const sources: Record<string, string> = { web: "Web upload", android: "Android scanner", telegram: "Telegram", folder: "Watched folder", email: "Email" };
const triggers: Record<Trigger, string> = { added: "When a document is added", updated: "When I change a document", scheduled: "Some days after a date" };
const dateFields: Record<DateField, string> = { created: "the date it was added", document_date: "the document date", action_due_date: "the follow-up due date" };
const recipes: { label: string; icon: typeof TagIcon; draft: Partial<Draft> }[] = [
  { label: "Tag new documents that mention a word", icon: TagIcon, draft: { name: "Tag by word", trigger: "added" } },
  { label: "Remind me some days after the document date", icon: Clock, draft: { name: "Review reminder", trigger: "scheduled", schedule_field: "document_date", schedule_days: 30, set_needs_action: true, action_note: "Review this document" } },
  { label: "Notify another app when a document is added", icon: Bell, draft: { name: "Notify on new document", trigger: "added", webhook_url: "https://" } },
];

function describe(flow: Flow, names: Map<string, string>) {
  const when = flow.trigger === "scheduled"
    ? `${Math.abs(flow.schedule_days)} days ${flow.schedule_days < 0 ? "before" : "after"} ${dateFields[flow.schedule_field]}`
    : triggers[flow.trigger].replace("When ", "when ");
  const conditions = [
    flow.filter_sources.length ? `from ${flow.filter_sources.map((item) => sources[item] ?? item).join(" or ")}` : "",
    flow.filter_text ? `mentions “${flow.filter_text}”` : "",
    flow.filter_filename ? `file name ${flow.filter_filename}` : "",
    flow.filter_tag_id ? `tagged ${names.get(flow.filter_tag_id) ?? "…"}` : "",
    flow.filter_correspondent_id ? `sender ${names.get(flow.filter_correspondent_id) ?? "…"}` : "",
    flow.filter_document_type_id ? `type ${names.get(flow.filter_document_type_id) ?? "…"}` : "",
  ].filter(Boolean);
  const actions = [
    flow.add_tag_ids.length ? `add ${flow.add_tag_ids.map((id) => names.get(id) ?? "…").join(", ")}` : "",
    flow.remove_tag_ids.length ? `remove ${flow.remove_tag_ids.map((id) => names.get(id) ?? "…").join(", ")}` : "",
    flow.set_correspondent_id ? `set sender ${names.get(flow.set_correspondent_id) ?? "…"}` : "",
    flow.set_document_type_id ? `set type ${names.get(flow.set_document_type_id) ?? "…"}` : "",
    flow.set_needs_action ? "mark as needing action" : "",
    flow.add_note ? "add a note" : "",
    flow.webhook_url ? "call a webhook" : "",
    flow.email_to ? `email ${flow.email_to}` : "",
  ].filter(Boolean);
  return `${when.charAt(0).toUpperCase()}${when.slice(1)}${conditions.length ? `, if it ${conditions.join(" and ")}` : ""}: ${actions.join(", ") || "nothing yet"}.`;
}

export default function WorkflowsPanel({ onOpenDocument }: { onOpenDocument: (id: string) => void }) {
  const [flows, setFlows] = useState<Flow[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [senders, setSenders] = useState<FilingItem[]>([]);
  const [types, setTypes] = useState<FilingItem[]>([]);
  const [draft, setDraft] = useState<Draft>(empty);
  const [editing, setEditing] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const formRef = useRef<HTMLFormElement>(null);

  const load = useCallback(async () => {
    try {
      const [overview, tagResponse, senderResponse, typeResponse] = await Promise.all([
        request<{ workflows: Flow[]; runs: Run[] }>("/api/workflows"),
        request<{ tags: Tag[] }>("/api/tags"),
        request<{ correspondents: FilingItem[] }>("/api/correspondents"),
        request<{ document_types: FilingItem[] }>("/api/document-types"),
      ]);
      setFlows(overview.workflows);
      setRuns(overview.runs);
      setTags(tagResponse.tags);
      setSenders(senderResponse.correspondents);
      setTypes(typeResponse.document_types);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load workflows");
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const names = new Map<string, string>([...tags, ...senders, ...types].map((item) => [item.id, item.name]));

  function focusForm() {
    requestAnimationFrame(() => {
      formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      formRef.current?.querySelector<HTMLInputElement>("input")?.focus({ preventScroll: true });
    });
  }

  function start(partial: Partial<Draft>) {
    setEditing(null);
    setDraft({ ...empty, ...partial });
    focusForm();
  }

  function edit(flow: Flow) {
    setEditing(flow.id);
    setDraft({
      ...flow, filter_tag_id: flow.filter_tag_id ?? "", filter_correspondent_id: flow.filter_correspondent_id ?? "",
      filter_document_type_id: flow.filter_document_type_id ?? "", set_correspondent_id: flow.set_correspondent_id ?? "",
      set_document_type_id: flow.set_document_type_id ?? "",
    });
    focusForm();
  }

  async function run(action: () => Promise<void>, fallback: string) {
    setBusy(true);
    setError("");
    setStatus("");
    try {
      await action();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : fallback);
    } finally {
      setBusy(false);
    }
  }

  function save(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      const body = JSON.stringify({
        ...draft,
        webhook_url: draft.webhook_url === "https://" ? "" : draft.webhook_url,
        ...Object.fromEntries(["filter_tag_id", "filter_correspondent_id", "filter_document_type_id", "set_correspondent_id", "set_document_type_id"]
          .map((key) => [key, draft[key as keyof Draft] || null])),
      });
      if (editing) await request(`/api/workflows/${editing}`, { method: "PATCH", body });
      else await request("/api/workflows", { method: "POST", body });
      setStatus(`Workflow “${draft.name}” saved. ${draft.trigger === "scheduled" ? "It runs each morning for documents that become due from now on." : "It applies to documents from now on."}`);
      setDraft(empty);
      setEditing(null);
      await load();
    }, "Could not save the workflow");
  }

  function toggle(flow: Flow) {
    void run(async () => {
      await request(`/api/workflows/${flow.id}`, { method: "PATCH", body: JSON.stringify({ enabled: !flow.enabled }) });
      await load();
    }, "Could not update the workflow");
  }

  function remove(flow: Flow) {
    void run(async () => {
      await request(`/api/workflows/${flow.id}`, { method: "DELETE" });
      setConfirming(null);
      setStatus(`Workflow “${flow.name}” removed. Changes it already made stay in place.`);
      await load();
    }, "Could not remove the workflow");
  }

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((current) => ({ ...current, [key]: value }));
  const toggleIn = (key: "add_tag_ids" | "remove_tag_ids" | "filter_sources", value: string) =>
    setDraft((current) => ({ ...current, [key]: current[key].includes(value) ? current[key].filter((item) => item !== value) : [...current[key], value] }));

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> AUTOMATION</div>
          <h1>Workflows<span className="heading-period">.</span></h1>
          <p>Let routine filing happen by itself. Each workflow acts once per document and leaves a record.</p>
        </div>
      </div>
      {error && <div className="inline-error" role="alert">{error}<button onClick={() => setError("")} aria-label="Dismiss error"><X size={16} /></button></div>}
      {status && <p className="bulk-notice" role="status">{status}</p>}
      <div className="agent-layout">
        <section className="agent-main">
          <div className="section-heading"><div><h2>Your workflows</h2><p>They run in order. Your own choices of sender and type are never overwritten.</p></div></div>
          {flows.length ? (
            <div className="agent-list">
              {flows.map((flow) => (
                <article className="agent-card mail-card" key={flow.id}>
                  <span className="agent-avatar"><WorkflowIcon size={21} aria-hidden="true" /></span>
                  <div className="agent-card-body">
                    <strong>{flow.name}{!flow.enabled && " · Paused"}</strong>
                    <span>{describe(flow, names)}</span>
                  </div>
                  <div className="mail-actions">
                    {confirming === flow.id ? (
                      <>
                        <span>Remove this workflow?</span>
                        <Button variant="danger" disabled={busy} onClick={() => remove(flow)}>Remove</Button>
                        <Button variant="secondary" autoFocus onClick={() => setConfirming(null)}>Keep</Button>
                      </>
                    ) : (
                      <>
                        <Button variant="secondary" disabled={busy} onClick={() => toggle(flow)}>{flow.enabled ? "Pause" : "Resume"}</Button>
                        <Button variant="secondary" onClick={() => edit(flow)}>Edit</Button>
                        <Button variant="secondary" aria-label={`Remove workflow ${flow.name}`} onClick={() => setConfirming(flow.id)}>Remove</Button>
                      </>
                    )}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="tag-empty">
              <WorkflowIcon size={27} aria-hidden="true" />
              <strong>No workflows yet</strong>
              <p>Optional. Start from a recipe on the right, or write your own.</p>
            </div>
          )}
          <div className="section-heading agent-activity-heading"><div><h2>Recent runs</h2><p>What each workflow did, and to which document.</p></div></div>
          {runs.length ? (
            <div className="agent-events">
              {runs.map((item) => (
                <div key={item.id}>
                  <span>{item.workflow} · {item.status === "failed" ? "Problem" : "Applied"}</span>
                  <strong><button type="button" className="text-action" onClick={() => onOpenDocument(item.document.id)}>{item.document.title}</button></strong>
                  <small>{item.detail} · {new Date(item.created_at).toLocaleString()}</small>
                </div>
              ))}
            </div>
          ) : <p className="agent-empty-activity">No workflow has run yet.</p>}
        </section>

        <div className="mail-side">
          {!editing && (
            <section className="tag-create-card agent-create-card">
              <h2>Start from a recipe</h2>
              <div className="mail-oauth">
                {recipes.map((recipe) => (
                  <Button key={recipe.label} type="button" variant="secondary" onClick={() => start(recipe.draft)}>
                    <recipe.icon size={16} aria-hidden="true" /> {recipe.label}
                  </Button>
                ))}
              </div>
            </section>
          )}
          <section className="tag-create-card agent-create-card">
            <div className="tag-create-icon"><WorkflowIcon size={21} aria-hidden="true" /></div>
            <h2>{editing ? "Edit workflow" : "New workflow"}</h2>
            <form ref={formRef} onSubmit={save} aria-label="Workflow">
              <label>Name<input value={draft.name} onChange={(event) => set("name", event.target.value)} maxLength={100} required placeholder="e.g. File utility bills" /></label>
              <label>Runs
                <select value={draft.trigger} onChange={(event) => set("trigger", event.target.value as Trigger)}>
                  {Object.entries(triggers).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              {draft.trigger === "scheduled" && (
                <div className="mail-row">
                  <label>Days after <small>Negative means before</small><input type="number" min={-3650} max={3650} value={draft.schedule_days} onChange={(event) => set("schedule_days", Number(event.target.value))} required /></label>
                  <label>Counting from
                    <select value={draft.schedule_field} onChange={(event) => set("schedule_field", event.target.value as DateField)}>
                      {Object.entries(dateFields).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </select>
                  </label>
                </div>
              )}
              <fieldset>
                <legend>Only documents that <small>All optional</small></legend>
                <label>Mention this word or phrase<input value={draft.filter_text} onChange={(event) => set("filter_text", event.target.value)} maxLength={200} placeholder="Searches the title and OCR text" /></label>
                <label>Have this tag
                  <select value={draft.filter_tag_id} onChange={(event) => set("filter_tag_id", event.target.value)}>
                    <option value="">Any</option>{tags.map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}
                  </select>
                </label>
                <label>Have this sender
                  <select value={draft.filter_correspondent_id} onChange={(event) => set("filter_correspondent_id", event.target.value)}>
                    <option value="">Any</option>{senders.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label>Have this type
                  <select value={draft.filter_document_type_id} onChange={(event) => set("filter_document_type_id", event.target.value)}>
                    <option value="">Any</option>{types.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label>File name matches<input value={draft.filter_filename} onChange={(event) => set("filter_filename", event.target.value)} maxLength={200} placeholder="e.g. fattura*.pdf" /></label>
                <div className="workflow-choices" role="group" aria-label="Came from">
                  <span>Came from</span>
                  {Object.entries(sources).map(([value, label]) => (
                    <label className="agent-scope-choice" key={value}><input type="checkbox" checked={draft.filter_sources.includes(value)} onChange={() => toggleIn("filter_sources", value)} />{label}</label>
                  ))}
                </div>
              </fieldset>
              <fieldset>
                <legend>Then</legend>
                {tags.length > 0 && (
                  <div className="workflow-choices" role="group" aria-labelledby="workflow-add-tags">
                    <span id="workflow-add-tags">Add tags</span>
                    <div className="workflow-choices mail-tags">
                    {tags.map((tag) => <label className="agent-scope-choice" key={tag.id}><input type="checkbox" checked={draft.add_tag_ids.includes(tag.id)} onChange={() => toggleIn("add_tag_ids", tag.id)} />{tag.name}</label>)}
                    </div>
                  </div>
                )}
                {tags.length > 0 && (
                  <details className="workflow-remove">
                    <summary>Remove tags</summary>
                    <div className="workflow-choices mail-tags" role="group" aria-label="Remove tags">
                      {tags.map((tag) => <label className="agent-scope-choice" key={tag.id}><input type="checkbox" checked={draft.remove_tag_ids.includes(tag.id)} onChange={() => toggleIn("remove_tag_ids", tag.id)} />{tag.name}</label>)}
                    </div>
                  </details>
                )}
                <label>Set sender
                  <select value={draft.set_correspondent_id} onChange={(event) => set("set_correspondent_id", event.target.value)}>
                    <option value="">Don’t change</option>{senders.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label>Set type
                  <select value={draft.set_document_type_id} onChange={(event) => set("set_document_type_id", event.target.value)}>
                    <option value="">Don’t change</option>{types.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label className="agent-scope-choice"><input type="checkbox" checked={draft.set_needs_action} onChange={(event) => set("set_needs_action", event.target.checked)} />Mark as needing action</label>
                {draft.set_needs_action && <label>What needs doing<input value={draft.action_note} onChange={(event) => set("action_note", event.target.value)} maxLength={500} /></label>}
                <label>Add a note<textarea value={draft.add_note} onChange={(event) => set("add_note", event.target.value)} maxLength={2000} rows={2} /></label>
                <label>Call a webhook <small>Sends title, tags, sender, type, and a link, never the text. Addresses on your home network need the server setting RIPIANO_WEBHOOK_ALLOW_PRIVATE.</small>
                  <input type="url" value={draft.webhook_url} onChange={(event) => set("webhook_url", event.target.value)} maxLength={500} placeholder="https://" />
                </label>
                <label>Email <small>Comma-separated addresses; needs the server’s mail settings</small>
                  <input value={draft.email_to} onChange={(event) => set("email_to", event.target.value)} maxLength={500} autoCapitalize="none" />
                </label>
                {draft.email_to && <label className="agent-scope-choice"><input type="checkbox" checked={draft.email_attach} onChange={(event) => set("email_attach", event.target.checked)} />Attach the original file (if it is small enough to email)</label>}
              </fieldset>
              <label>Order <small>Lower numbers run first</small><input type="number" min={0} max={10000} value={draft.order} onChange={(event) => set("order", Number(event.target.value))} /></label>
              <Button disabled={busy}><Plus size={17} aria-hidden="true" /> {editing ? "Save workflow" : "Create workflow"}</Button>
              {editing && <Button type="button" variant="secondary" onClick={() => { setEditing(null); setDraft(empty); }}>Cancel</Button>}
            </form>
          </section>
        </div>
      </div>
    </>
  );
}
