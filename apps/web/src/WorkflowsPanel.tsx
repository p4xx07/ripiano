import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Bell, Clock, KeyRound, Plus, Tag as TagIcon, Workflow as WorkflowIcon, X } from "lucide-react";
import { FilingItem, request, Tag } from "./api";
import { Button } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/WorkflowsPanel";

type Trigger = "added" | "updated" | "scheduled";
type DateField = "created" | "document_date" | "action_due_date";
type Flow = {
  id: string; name: string; enabled: boolean; order: number; trigger: Trigger; schedule_field: DateField; schedule_days: number;
  filter_sources: string[]; filter_filename: string; filter_text: string; filter_tag_id: string | null;
  filter_correspondent_id: string | null; filter_document_type_id: string | null; add_tag_ids: string[]; remove_tag_ids: string[];
  set_correspondent_id: string | null; set_document_type_id: string | null; set_needs_action: boolean; action_note: string;
  add_note: string; webhook_url: string; email_to: string; email_attach: boolean; pdf_password_count: number;
};
type Run = { id: string; workflow: string; document: { id: string; title: string }; trigger: Trigger; status: "applied" | "failed"; detail: string; created_at: string };
type Draft = Omit<Flow, "id" | "filter_tag_id" | "filter_correspondent_id" | "filter_document_type_id" | "set_correspondent_id" | "set_document_type_id"> & {
  filter_tag_id: string; filter_correspondent_id: string; filter_document_type_id: string; set_correspondent_id: string; set_document_type_id: string;
  // Write-only: typed passwords are sent once and never shown again.
  pdf_passwords_text: string; clear_pdf_passwords: boolean;
};

const empty: Draft = {
  name: "", enabled: true, order: 0, trigger: "added", schedule_field: "created", schedule_days: 30, filter_sources: [], filter_filename: "",
  filter_text: "", filter_tag_id: "", filter_correspondent_id: "", filter_document_type_id: "", add_tag_ids: [], remove_tag_ids: [],
  set_correspondent_id: "", set_document_type_id: "", set_needs_action: false, action_note: "", add_note: "", webhook_url: "", email_to: "", email_attach: false,
  pdf_password_count: 0, pdf_passwords_text: "", clear_pdf_passwords: false,
};
type M = typeof messages.en;
const sourcesFor = (m: M): Record<string, string> => ({ web: m.sourceWeb, android: m.sourceAndroid, telegram: m.sourceTelegram, folder: m.sourceFolder, email: m.sourceEmail, s3: m.sourceS3 });
const triggersFor = (m: M): Record<Trigger, string> => ({ added: m.triggerAdded, updated: m.triggerUpdated, scheduled: m.triggerScheduled });
const dateFieldsFor = (m: M): Record<DateField, string> => ({ created: m.dateCreated, document_date: m.dateDocument, action_due_date: m.dateActionDue });
const recipesFor = (m: M): { label: string; icon: typeof TagIcon; draft: Partial<Draft> }[] => [
  { label: m.recipeTag, icon: TagIcon, draft: { name: m.recipeTagName, trigger: "added" } },
  { label: m.recipeReminder, icon: Clock, draft: { name: m.recipeReminderName, trigger: "scheduled", schedule_field: "document_date", schedule_days: 30, set_needs_action: true, action_note: m.recipeReminderNote } },
  { label: m.recipeNotify, icon: Bell, draft: { name: m.recipeNotifyName, trigger: "added", webhook_url: "https://" } },
  { label: m.recipeUnlock, icon: KeyRound, draft: { name: m.recipeUnlockName, trigger: "added" } },
];

function describe(flow: Flow, names: Map<string, string>, m: M) {
  const sources = sourcesFor(m);
  const when = flow.trigger === "scheduled"
    ? m.whenScheduled(Math.abs(flow.schedule_days), flow.schedule_days < 0, dateFieldsFor(m)[flow.schedule_field])
    : triggersFor(m)[flow.trigger].replace("When ", "when ");
  const conditions = [
    flow.filter_sources.length ? m.condFrom(flow.filter_sources.map((item) => sources[item] ?? item)) : "",
    flow.filter_text ? m.condMentions(flow.filter_text) : "",
    flow.filter_filename ? m.condFileName(flow.filter_filename) : "",
    flow.filter_tag_id ? m.condTagged(names.get(flow.filter_tag_id) ?? "…") : "",
    flow.filter_correspondent_id ? m.condSender(names.get(flow.filter_correspondent_id) ?? "…") : "",
    flow.filter_document_type_id ? m.condType(names.get(flow.filter_document_type_id) ?? "…") : "",
  ].filter(Boolean);
  const actions = [
    flow.add_tag_ids.length ? m.actAdd(flow.add_tag_ids.map((id) => names.get(id) ?? "…").join(", ")) : "",
    flow.remove_tag_ids.length ? m.actRemove(flow.remove_tag_ids.map((id) => names.get(id) ?? "…").join(", ")) : "",
    flow.set_correspondent_id ? m.actSetSender(names.get(flow.set_correspondent_id) ?? "…") : "",
    flow.set_document_type_id ? m.actSetType(names.get(flow.set_document_type_id) ?? "…") : "",
    flow.set_needs_action ? m.actNeedsAction : "",
    flow.add_note ? m.actAddNote : "",
    flow.webhook_url ? m.actWebhook : "",
    flow.email_to ? m.actEmail(flow.email_to) : "",
    flow.pdf_password_count ? m.actUnlock(flow.pdf_password_count) : "",
  ].filter(Boolean);
  return m.summary(`${when.charAt(0).toUpperCase()}${when.slice(1)}`, conditions, actions);
}

export default function WorkflowsPanel({ onOpenDocument }: { onOpenDocument: (id: string) => void }) {
  const m = useMessages(messages);
  const sources = sourcesFor(m);
  const triggers = triggersFor(m);
  const dateFields = dateFieldsFor(m);
  const recipes = recipesFor(m);
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
      setError(cause instanceof Error ? cause.message : m.loadError);
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
      set_document_type_id: flow.set_document_type_id ?? "", pdf_passwords_text: "", clear_pdf_passwords: false,
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
      const { pdf_passwords_text, clear_pdf_passwords, pdf_password_count: _count, ...fields } = draft;
      const typed = pdf_passwords_text.split("\n").filter((item) => item.length > 0);
      const passwords = draft.trigger !== "added" || clear_pdf_passwords ? (draft.pdf_password_count || clear_pdf_passwords ? [] : undefined)
        : typed.length ? typed : undefined;
      const body = JSON.stringify({
        ...fields,
        ...(passwords ? { pdf_passwords: passwords } : {}),
        webhook_url: draft.webhook_url === "https://" ? "" : draft.webhook_url,
        ...Object.fromEntries(["filter_tag_id", "filter_correspondent_id", "filter_document_type_id", "set_correspondent_id", "set_document_type_id"]
          .map((key) => [key, draft[key as keyof Draft] || null])),
      });
      if (editing) await request(`/api/workflows/${editing}`, { method: "PATCH", body });
      else await request("/api/workflows", { method: "POST", body });
      setStatus(m.saved(draft.name, draft.trigger === "scheduled"));
      setDraft(empty);
      setEditing(null);
      await load();
    }, m.saveError);
  }

  function toggle(flow: Flow) {
    void run(async () => {
      await request(`/api/workflows/${flow.id}`, { method: "PATCH", body: JSON.stringify({ enabled: !flow.enabled }) });
      await load();
    }, m.updateError);
  }

  function remove(flow: Flow) {
    void run(async () => {
      await request(`/api/workflows/${flow.id}`, { method: "DELETE" });
      setConfirming(null);
      setStatus(m.removed(flow.name));
      await load();
    }, m.removeError);
  }

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((current) => ({ ...current, [key]: value }));
  const toggleIn = (key: "add_tag_ids" | "remove_tag_ids" | "filter_sources", value: string) =>
    setDraft((current) => ({ ...current, [key]: current[key].includes(value) ? current[key].filter((item) => item !== value) : [...current[key], value] }));

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> {m.eyebrow}</div>
          <h1>{m.heading}<span className="heading-period">.</span></h1>
          <p>{m.intro}</p>
        </div>
      </div>
      {error && <div className="inline-error" role="alert">{error}<button onClick={() => setError("")} aria-label={m.dismissError}><X size={16} /></button></div>}
      {status && <p className="bulk-notice" role="status">{status}</p>}
      <div className="agent-layout">
        <section className="agent-main">
          <div className="section-heading"><div><h2>{m.yourWorkflows}</h2><p>{m.yourWorkflowsIntro}</p></div></div>
          {flows.length ? (
            <div className="agent-list">
              {flows.map((flow) => (
                <article className="agent-card mail-card" key={flow.id}>
                  <span className="agent-avatar"><WorkflowIcon size={21} aria-hidden="true" /></span>
                  <div className="agent-card-body">
                    <strong>{flow.name}{!flow.enabled && m.paused}</strong>
                    <span>{describe(flow, names, m)}</span>
                  </div>
                  <div className="mail-actions">
                    {confirming === flow.id ? (
                      <>
                        <span>{m.confirmRemove}</span>
                        <Button variant="danger" disabled={busy} onClick={() => remove(flow)}>{m.remove}</Button>
                        <Button variant="secondary" autoFocus onClick={() => setConfirming(null)}>{m.keep}</Button>
                      </>
                    ) : (
                      <>
                        <Button variant="secondary" disabled={busy} onClick={() => toggle(flow)}>{flow.enabled ? m.pause : m.resume}</Button>
                        <Button variant="secondary" onClick={() => edit(flow)}>{m.edit}</Button>
                        <Button variant="secondary" aria-label={m.removeLabel(flow.name)} onClick={() => setConfirming(flow.id)}>{m.remove}</Button>
                      </>
                    )}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="tag-empty">
              <WorkflowIcon size={27} aria-hidden="true" />
              <strong>{m.emptyTitle}</strong>
              <p>{m.emptyText}</p>
            </div>
          )}
          <div className="section-heading agent-activity-heading"><div><h2>{m.recentRuns}</h2><p>{m.recentRunsIntro}</p></div></div>
          {runs.length ? (
            <div className="agent-events">
              {runs.map((item) => (
                <div key={item.id}>
                  <span>{item.workflow} · {item.status === "failed" ? m.problem : m.applied}</span>
                  <strong><button type="button" className="text-action" onClick={() => onOpenDocument(item.document.id)}>{item.document.title}</button></strong>
                  <small>{item.detail} · {new Date(item.created_at).toLocaleString()}</small>
                </div>
              ))}
            </div>
          ) : <p className="agent-empty-activity">{m.noRuns}</p>}
        </section>

        <div className="mail-side">
          {!editing && (
            <section className="tag-create-card agent-create-card">
              <h2>{m.startFromRecipe}</h2>
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
            <h2>{editing ? m.editWorkflow : m.newWorkflow}</h2>
            <form ref={formRef} onSubmit={save} aria-label={m.formLabel}>
              <label>{m.name}<input value={draft.name} onChange={(event) => set("name", event.target.value)} maxLength={100} required placeholder={m.namePlaceholder} /></label>
              <label>{m.runs}
                <select value={draft.trigger} onChange={(event) => set("trigger", event.target.value as Trigger)}>
                  {Object.entries(triggers).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              {draft.trigger === "scheduled" && (
                <div className="mail-row">
                  <label>{m.daysAfter} <small>{m.negativeHint}</small><input type="number" min={-3650} max={3650} value={draft.schedule_days} onChange={(event) => set("schedule_days", Number(event.target.value))} required /></label>
                  <label>{m.countingFrom}
                    <select value={draft.schedule_field} onChange={(event) => set("schedule_field", event.target.value as DateField)}>
                      {Object.entries(dateFields).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </select>
                  </label>
                </div>
              )}
              <fieldset>
                <legend>{m.onlyDocuments} <small>{m.allOptional}</small></legend>
                <label>{m.mention}<input value={draft.filter_text} onChange={(event) => set("filter_text", event.target.value)} maxLength={200} placeholder={m.mentionPlaceholder} /></label>
                <label>{m.haveTag}
                  <select value={draft.filter_tag_id} onChange={(event) => set("filter_tag_id", event.target.value)}>
                    <option value="">{m.any}</option>{tags.map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}
                  </select>
                </label>
                <label>{m.haveSender}
                  <select value={draft.filter_correspondent_id} onChange={(event) => set("filter_correspondent_id", event.target.value)}>
                    <option value="">{m.any}</option>{senders.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label>{m.haveType}
                  <select value={draft.filter_document_type_id} onChange={(event) => set("filter_document_type_id", event.target.value)}>
                    <option value="">{m.any}</option>{types.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label>{m.fileNameMatches}<input value={draft.filter_filename} onChange={(event) => set("filter_filename", event.target.value)} maxLength={200} placeholder={m.fileNamePlaceholder} /></label>
                <div className="workflow-choices" role="group" aria-label={m.cameFrom}>
                  <span>{m.cameFrom}</span>
                  {Object.entries(sources).map(([value, label]) => (
                    <label className="agent-scope-choice" key={value}><input type="checkbox" checked={draft.filter_sources.includes(value)} onChange={() => toggleIn("filter_sources", value)} />{label}</label>
                  ))}
                </div>
              </fieldset>
              <fieldset>
                <legend>{m.then}</legend>
                {tags.length > 0 && (
                  <div className="workflow-choices" role="group" aria-labelledby="workflow-add-tags">
                    <span id="workflow-add-tags">{m.addTags}</span>
                    <div className="workflow-choices mail-tags">
                    {tags.map((tag) => <label className="agent-scope-choice" key={tag.id}><input type="checkbox" checked={draft.add_tag_ids.includes(tag.id)} onChange={() => toggleIn("add_tag_ids", tag.id)} />{tag.name}</label>)}
                    </div>
                  </div>
                )}
                {tags.length > 0 && (
                  <details className="workflow-remove">
                    <summary>{m.removeTags}</summary>
                    <div className="workflow-choices mail-tags" role="group" aria-label={m.removeTags}>
                      {tags.map((tag) => <label className="agent-scope-choice" key={tag.id}><input type="checkbox" checked={draft.remove_tag_ids.includes(tag.id)} onChange={() => toggleIn("remove_tag_ids", tag.id)} />{tag.name}</label>)}
                    </div>
                  </details>
                )}
                <label>{m.setSender}
                  <select value={draft.set_correspondent_id} onChange={(event) => set("set_correspondent_id", event.target.value)}>
                    <option value="">{m.dontChange}</option>{senders.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label>{m.setType}
                  <select value={draft.set_document_type_id} onChange={(event) => set("set_document_type_id", event.target.value)}>
                    <option value="">{m.dontChange}</option>{types.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label className="agent-scope-choice"><input type="checkbox" checked={draft.set_needs_action} onChange={(event) => set("set_needs_action", event.target.checked)} />{m.markNeedsAction}</label>
                {draft.set_needs_action && <label>{m.whatNeedsDoing}<input value={draft.action_note} onChange={(event) => set("action_note", event.target.value)} maxLength={500} /></label>}
                <label>{m.addNote}<textarea value={draft.add_note} onChange={(event) => set("add_note", event.target.value)} maxLength={2000} rows={2} /></label>
                <label>{m.callWebhook} <small>{m.webhookHint}</small>
                  <input type="url" value={draft.webhook_url} onChange={(event) => set("webhook_url", event.target.value)} maxLength={500} placeholder="https://" />
                </label>
                <label>{m.email} <small>{m.emailHint}</small>
                  <input value={draft.email_to} onChange={(event) => set("email_to", event.target.value)} maxLength={500} autoCapitalize="none" />
                </label>
                {draft.email_to && <label className="agent-scope-choice"><input type="checkbox" checked={draft.email_attach} onChange={(event) => set("email_attach", event.target.checked)} />{m.attachOriginal}</label>}
                {draft.trigger === "added" && (
                  <div className="workflow-unlock">
                    <label>{m.unlockPdfs} <small>{m.unlockHint}</small>
                      <textarea value={draft.pdf_passwords_text} onChange={(event) => set("pdf_passwords_text", event.target.value)} rows={2}
                        autoComplete="off" autoCapitalize="none" spellCheck={false} disabled={draft.clear_pdf_passwords}
                        placeholder={draft.pdf_password_count ? m.replacePasswords : ""} />
                    </label>
                    {draft.pdf_password_count > 0 && (
                      <label className="agent-scope-choice"><input type="checkbox" checked={draft.clear_pdf_passwords} onChange={(event) => set("clear_pdf_passwords", event.target.checked)} />
                        {m.forgetPasswords(draft.pdf_password_count)}</label>
                    )}
                  </div>
                )}
              </fieldset>
              <label>{m.order} <small>{m.orderHint}</small><input type="number" min={0} max={10000} value={draft.order} onChange={(event) => set("order", Number(event.target.value))} /></label>
              <Button disabled={busy}><Plus size={17} aria-hidden="true" /> {editing ? m.saveWorkflow : m.createWorkflow}</Button>
              {editing && <Button type="button" variant="secondary" onClick={() => { setEditing(null); setDraft(empty); }}>{m.cancel}</Button>}
            </form>
          </section>
        </div>
      </div>
    </>
  );
}
