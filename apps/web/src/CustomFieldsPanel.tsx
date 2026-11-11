import { FormEvent, useEffect, useRef, useState } from "react";
import { ListFilter, Pencil, Plus, Trash2, X } from "lucide-react";
import { CustomField, request } from "./api";
import { Button } from "./ui";

const kindLabels: Record<CustomField["kind"], string> = {
  text: "Text", number: "Number", date: "Date", boolean: "Yes or no",
};

export default function CustomFieldsPanel({ documentId, onChanged }: { documentId: string; onChanged: () => void }) {
  const [fields, setFields] = useState<CustomField[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [selectedFieldId, setSelectedFieldId] = useState("");
  const createDetails = useRef<HTMLDetailsElement>(null);
  const [name, setName] = useState("");
  const [kind, setKind] = useState<CustomField["kind"]>("text");
  const [renameId, setRenameId] = useState("");
  const [renameName, setRenameName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    const result = await request<{ fields: CustomField[] }>(`/api/documents/${documentId}/custom-fields`);
    setFields(result.fields);
    setDrafts(Object.fromEntries(result.fields.map((field) => [field.id, field.value === null ? "" : String(field.value)])));
  }

  useEffect(() => {
    void load().catch((cause) => setError(cause instanceof Error ? cause.message : "Could not load custom details"));
  }, [documentId]);

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
      setNotice("Custom field added. You can now set it on this document.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create custom field");
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
      setNotice(clear || value === null ? `${field.name} cleared.` : `${field.name} saved.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save custom field");
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
      setNotice("Field renamed on all documents.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not rename field");
    } finally {
      setBusy(false);
    }
  }

  async function remove(field: CustomField) {
    if (!window.confirm(`Delete unused field “${field.name}”?`)) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await request(`/api/custom-fields/${field.id}`, { method: "DELETE" });
      if (selectedFieldId === field.id) setSelectedFieldId("");
      await load();
      setNotice(`Deleted unused field “${field.name}”.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete field");
    } finally {
      setBusy(false);
    }
  }

  const visibleFields = fields.filter((field) => field.value !== null || field.id === selectedFieldId);

  return <section className="custom-fields" aria-labelledby="custom-fields-heading">
    <h3 id="custom-fields-heading"><ListFilter size={17} /> Custom details</h3>
    <p>Keep specific details here, then find them in the Library.</p>
    {error && <div className="inline-error" role="alert">{error}</div>}
    {notice && <p className="bulk-notice" role="status">{notice}</p>}
    {visibleFields.length ? visibleFields.map((field) => <div className="custom-field-row" key={field.id}>
      <label htmlFor={`custom-${field.id}`}>{field.name} <small>{kindLabels[field.kind]}</small></label>
      <div className="custom-field-controls">
        {field.kind === "boolean" ? <select id={`custom-${field.id}`} value={drafts[field.id] ?? ""} onChange={(event) => setDrafts((current) => ({ ...current, [field.id]: event.target.value }))}><option value="">Not set</option><option value="true">Yes</option><option value="false">No</option></select> :
          <input id={`custom-${field.id}`} type={field.kind === "text" ? "text" : field.kind} step={field.kind === "number" ? "any" : undefined} maxLength={field.kind === "text" ? 500 : undefined} value={drafts[field.id] ?? ""} onChange={(event) => setDrafts((current) => ({ ...current, [field.id]: event.target.value }))} />}
        <Button type="button" variant="secondary" disabled={busy || drafts[field.id] === ""} onClick={() => void save(field)}>Save</Button>
        {field.value !== null && <button type="button" className="text-action" disabled={busy} onClick={() => void save(field, true)}>Clear</button>}
      </div>
    </div>) : <p>No custom details yet.</p>}
    {fields.some((field) => field.value === null) && <label className="custom-add-existing">Add an existing field
      <select value={selectedFieldId} onChange={(event) => setSelectedFieldId(event.target.value)}>
        <option value="">Choose a field</option>
        {fields.filter((field) => field.value === null).map((field) => <option key={field.id} value={field.id}>{field.name}</option>)}
      </select>
    </label>}
    <details className="custom-create" ref={createDetails}>
      <summary>Add a custom field</summary>
      <p>This field becomes available on all your documents.</p>
      <form onSubmit={(event) => void create(event)}>
        <label>Field name<input value={name} onChange={(event) => setName(event.target.value)} maxLength={100} placeholder="e.g. Policy number" required /></label>
        <label>Type<select value={kind} onChange={(event) => setKind(event.target.value as CustomField["kind"])}><option value="text">Text</option><option value="number">Number</option><option value="date">Date</option><option value="boolean">Yes or no</option></select></label>
        <Button disabled={busy || !name.trim()}><Plus size={16} /> Add field</Button>
      </form>
    </details>
    {fields.length > 0 && <details className="custom-manage">
      <summary>Manage field names</summary>
      <p>Renaming updates every document. Delete a field after removing its values and saved searches.</p>
      <ul>{fields.map((field) => <li key={field.id}>
        {renameId === field.id ? <form onSubmit={(event) => void rename(event)}>
          <input aria-label={`New name for ${field.name}`} value={renameName} onChange={(event) => setRenameName(event.target.value)} maxLength={100} required />
          <Button disabled={busy || !renameName.trim()}>Save name</Button>
          <button type="button" aria-label="Cancel rename" onClick={() => setRenameId("")}><X size={16} /></button>
        </form> : <><span>{field.name} · {kindLabels[field.kind]}</span>
          <button type="button" aria-label={`Rename ${field.name}`} disabled={busy} onClick={() => { setRenameId(field.id); setRenameName(field.name); }}><Pencil size={16} /></button>
          {!field.in_use && <button type="button" aria-label={`Delete unused field ${field.name}`} disabled={busy} onClick={() => void remove(field)}><Trash2 size={16} /></button>}
        </>}
      </li>)}</ul>
    </details>}
  </section>;
}
