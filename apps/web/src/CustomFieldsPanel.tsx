import { FormEvent, useEffect, useRef, useState } from "react";
import { ListFilter, Pencil, Plus, Trash2, X } from "lucide-react";
import { CustomField, request } from "./api";
import { Button, Modal } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/CustomFieldsPanel";


type TypeChangePreview = {
  id: string;
  name: string;
  from_kind: CustomField["kind"];
  to_kind: CustomField["kind"];
  value_count: number;
  changed_count: number;
  examples: { before: string; after: string }[];
  invalid_count: number;
  invalid_examples: { document: string; value: string }[];
  saved_search_count: number;
  saved_searches: string[];
  can_change: boolean;
};

export default function CustomFieldsPanel({ documentId, onChanged }: { documentId: string; onChanged: () => void }) {
  const m = useMessages(messages);
  const kindLabels: Record<CustomField["kind"], string> = {
    text: m.kindText, number: m.kindNumber, date: m.kindDate, boolean: m.kindBoolean,
  };
  const [fields, setFields] = useState<CustomField[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [selectedFieldId, setSelectedFieldId] = useState("");
  const createDetails = useRef<HTMLDetailsElement>(null);
  const [name, setName] = useState("");
  const [kind, setKind] = useState<CustomField["kind"]>("text");
  const [renameId, setRenameId] = useState("");
  const [renameName, setRenameName] = useState("");
  const [changeTypeId, setChangeTypeId] = useState("");
  const [targetKind, setTargetKind] = useState<CustomField["kind"]>("text");
  const [typePreview, setTypePreview] = useState<TypeChangePreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    const result = await request<{ fields: CustomField[] }>(`/api/documents/${documentId}/custom-fields`);
    setFields(result.fields);
    setDrafts(Object.fromEntries(result.fields.map((field) => [field.id, field.value === null ? "" : String(field.value)])));
  }

  useEffect(() => {
    void load().catch((cause) => setError(cause instanceof Error ? cause.message : m.loadError));
  }, [documentId, m]);

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const created = await request<CustomField>("/api/custom-fields", { method: "POST", body: JSON.stringify({ name, kind }) });
      setName("");
      await load();
      setSelectedFieldId(created.id);
      if (createDetails.current) createDetails.current.open = false;
      setNotice(m.created);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.createError);
    } finally {
      setBusy(false);
    }
  }

  async function save(field: CustomField, clear = false) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const value = clear || drafts[field.id] === "" ? null : field.kind === "boolean" ? drafts[field.id] === "true" : drafts[field.id];
      await request(`/api/documents/${documentId}/custom-fields/${field.id}`, { method: "PUT", body: JSON.stringify({ value }) });
      await load();
      setSelectedFieldId("");
      onChanged();
      setNotice(clear || value === null ? m.cleared(field.name) : m.saved(field.name));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.saveError);
    } finally {
      setBusy(false);
    }
  }

  async function rename(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await request(`/api/custom-fields/${renameId}`, { method: "PATCH", body: JSON.stringify({ name: renameName }) });
      setRenameId("");
      await load();
      setNotice(m.renamed);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.renameError);
    } finally {
      setBusy(false);
    }
  }

  async function previewTypeChange(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const preview = await request<TypeChangePreview>(`/api/custom-fields/${changeTypeId}/change-type?kind=${targetKind}`);
      setTypePreview(preview);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.reviewError);
    } finally {
      setBusy(false);
    }
  }

  async function changeType() {
    if (!typePreview?.can_change) return;
    setBusy(true);
    setError("");
    try {
      await request(`/api/custom-fields/${typePreview.id}/change-type`, {
        method: "POST", body: JSON.stringify({ kind: typePreview.to_kind }),
      });
      const label = kindLabels[typePreview.to_kind];
      const count = typePreview.value_count;
      setTypePreview(null);
      setChangeTypeId("");
      await load();
      onChanged();
      setNotice(m.typeChanged(typePreview.name, label, count));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.changeTypeError);
    } finally {
      setBusy(false);
    }
  }

  async function remove(field: CustomField) {
    if (!window.confirm(m.confirmDelete(field.name))) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await request(`/api/custom-fields/${field.id}`, { method: "DELETE" });
      if (selectedFieldId === field.id) setSelectedFieldId("");
      await load();
      setNotice(m.deleted(field.name));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.deleteError);
    } finally {
      setBusy(false);
    }
  }

  const visibleFields = fields.filter((field) => field.value !== null || field.id === selectedFieldId);

  return <section className="custom-fields" aria-labelledby="custom-fields-heading">
    <h3 id="custom-fields-heading"><ListFilter size={17} /> {m.heading}</h3>
    <p>{m.intro}</p>
    {error && <div className="inline-error" role="alert">{error}</div>}
    {notice && <p className="bulk-notice" role="status">{notice}</p>}
    {visibleFields.length ? visibleFields.map((field) => <div className="custom-field-row" key={field.id}>
      <label htmlFor={`custom-${field.id}`}>{field.name} <small>{kindLabels[field.kind]}</small></label>
      <div className="custom-field-controls">
        {field.kind === "boolean" ? <select id={`custom-${field.id}`} value={drafts[field.id] ?? ""} onChange={(event) => setDrafts((current) => ({ ...current, [field.id]: event.target.value }))}><option value="">{m.notSet}</option><option value="true">{m.yes}</option><option value="false">{m.no}</option></select> :
          <input id={`custom-${field.id}`} type={field.kind === "text" ? "text" : field.kind} step={field.kind === "number" ? "any" : undefined} maxLength={field.kind === "text" ? 500 : undefined} value={drafts[field.id] ?? ""} onChange={(event) => setDrafts((current) => ({ ...current, [field.id]: event.target.value }))} />}
        <Button type="button" variant="secondary" disabled={busy || drafts[field.id] === ""} onClick={() => void save(field)}>{m.save}</Button>
        {field.value !== null && <button type="button" className="text-action" disabled={busy} onClick={() => void save(field, true)}>{m.clear}</button>}
      </div>
    </div>) : <p>{m.empty}</p>}
    {fields.some((field) => field.value === null) && <label className="custom-add-existing">{m.addExisting}
      <select value={selectedFieldId} onChange={(event) => setSelectedFieldId(event.target.value)}>
        <option value="">{m.chooseField}</option>
        {fields.filter((field) => field.value === null).map((field) => <option key={field.id} value={field.id}>{field.name}</option>)}
      </select>
    </label>}
    <details className="custom-create" ref={createDetails}>
      <summary>{m.addCustomField}</summary>
      <p>{m.addIntro}</p>
      <form onSubmit={(event) => void create(event)}>
        <label>{m.fieldName}<input value={name} onChange={(event) => setName(event.target.value)} maxLength={100} placeholder={m.fieldNamePlaceholder} required /></label>
        <label>{m.type}<select value={kind} onChange={(event) => setKind(event.target.value as CustomField["kind"])}><option value="text">{m.kindText}</option><option value="number">{m.kindNumber}</option><option value="date">{m.kindDate}</option><option value="boolean">{m.kindBoolean}</option></select></label>
        <Button disabled={busy || !name.trim()}><Plus size={16} /> {m.addField}</Button>
      </form>
    </details>
    {fields.length > 0 && <details className="custom-manage">
      <summary>{m.manage}</summary>
      <p>{m.manageIntro}</p>
      <ul>{fields.map((field) => <li key={field.id}>
        {renameId === field.id ? <form onSubmit={(event) => void rename(event)}>
          <input aria-label={m.newNameFor(field.name)} value={renameName} onChange={(event) => setRenameName(event.target.value)} maxLength={100} required />
          <Button disabled={busy || !renameName.trim()}>{m.saveName}</Button>
          <button type="button" aria-label={m.cancelRename} onClick={() => setRenameId("")}><X size={16} /></button>
        </form> : <><span>{field.name} · {kindLabels[field.kind]}</span>
          {changeTypeId === field.id ? <form className="custom-type-form" onSubmit={(event) => void previewTypeChange(event)}>
            <label>{m.newType}<select aria-label={m.newTypeFor(field.name)} value={targetKind} onChange={(event) => setTargetKind(event.target.value as CustomField["kind"])}>
              {Object.entries(kindLabels).filter(([value]) => value !== field.kind).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select></label>
            <Button disabled={busy}>{m.reviewChange}</Button>
            <button type="button" aria-label={m.cancelTypeChangeFor(field.name)} onClick={() => setChangeTypeId("")}><X size={16} /></button>
          </form> : <>
            <button type="button" aria-label={m.renameField(field.name)} disabled={busy} onClick={() => { setChangeTypeId(""); setRenameId(field.id); setRenameName(field.name); }}><Pencil size={16} /></button>
            <button type="button" aria-label={m.changeTypeOf(field.name)} disabled={busy} onClick={() => { setRenameId(""); setChangeTypeId(field.id); setTargetKind(field.kind === "text" ? "number" : "text"); }}>{m.changeType}</button>
            {!field.in_use && <button type="button" aria-label={m.deleteUnused(field.name)} disabled={busy} onClick={() => void remove(field)}><Trash2 size={16} /></button>}
          </>}
        </>}
      </li>)}</ul>
    </details>}
    {typePreview && <Modal titleId="type-change-title" panelClassName="add-modal type-change-modal" onClose={() => { if (!busy) setTypePreview(null); }}>
      <button type="button" className="modal-close" aria-label={m.close} disabled={busy} onClick={() => setTypePreview(null)}><X size={20} /></button>
      <h2 id="type-change-title">{m.changeTitle(typePreview.name, kindLabels[typePreview.to_kind])}</h2>
      <p>{m.valueSummary(typePreview.value_count, typePreview.changed_count)}</p>
      {typePreview.examples.length > 0 && <div className="type-change-examples"><strong>{m.examples}</strong><ul>{typePreview.examples.map((example, index) => <li key={index}>{example.before} → {example.after}</li>)}</ul></div>}
      {typePreview.invalid_count > 0 && <div className="type-change-blocker" role="alert"><strong>{m.invalidValues(typePreview.invalid_count, kindLabels[typePreview.to_kind])}</strong><ul>{typePreview.invalid_examples.map((example, index) => <li key={index}>{example.document}: {example.value}</li>)}</ul><p>{m.correctThen}</p></div>}
      {typePreview.saved_search_count > 0 && <div className="type-change-blocker" role="alert"><strong>{m.savedSearchesUse(typePreview.saved_search_count)}</strong><p>{typePreview.saved_searches.join(", ")}</p><p>{m.updateSavedSearches}</p></div>}
      {typePreview.can_change && <p>{m.canConvert}</p>}
      {error && <p className="inline-error" role="alert">{error}</p>}
      <div className="trash-confirm"><Button type="button" disabled={busy || !typePreview.can_change} onClick={() => void changeType()}>{m.confirmTypeChange}</Button><Button type="button" variant="secondary" disabled={busy} onClick={() => setTypePreview(null)}>{m.cancel}</Button></div>
    </Modal>}
  </section>;
}
