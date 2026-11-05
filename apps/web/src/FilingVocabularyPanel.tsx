import { FormEvent, useCallback, useEffect, useState } from "react";
import { Pencil, Plus, Trash2, X } from "lucide-react";
import { FilingItem, request } from "./api";
import { Button } from "./ui";

export default function FilingVocabularyPanel({ kind }: { kind: "correspondents" | "document-types" }) {
  const isSender = kind === "correspondents";
  const title = isSender ? "Senders & organizations" : "Document types";
  const singular = isSender ? "sender" : "type";
  const key = isSender ? "correspondents" : "document_types";
  const [items, setItems] = useState<FilingItem[]>([]);
  const [name, setName] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [editedName, setEditedName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const result = await request<Record<typeof key, FilingItem[]>>(`/api/${kind}`);
      setItems(result[key]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : `Could not load ${title.toLowerCase()}`);
    }
  }, [kind, key, title]);

  useEffect(() => { void load(); }, [load]);

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await request(`/api/${kind}`, { method: "POST", body: JSON.stringify({ name }) });
      setName("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : `Could not add ${singular}`);
    } finally {
      setBusy(false);
    }
  }

  async function rename(event: FormEvent) {
    event.preventDefault();
    if (!editing) return;
    setBusy(true);
    setError("");
    try {
      await request(`/api/${kind}/${editing}`, { method: "PATCH", body: JSON.stringify({ name: editedName }) });
      setEditing(null);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : `Could not rename ${singular}`);
    } finally {
      setBusy(false);
    }
  }

  async function remove(item: FilingItem) {
    if (!window.confirm(`Delete “${item.name}”? Remove it from documents first if it is in use.`)) return;
    setBusy(true);
    setError("");
    try {
      await request(`/api/${kind}/${item.id}`, { method: "DELETE" });
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : `Could not delete ${singular}`);
    } finally {
      setBusy(false);
    }
  }

  return <section className="filing-card">
    <h2>{title}</h2>
    <p>{isSender ? "Find documents by who sent them." : "Group documents by what they are."}</p>
    {error && <div className="inline-error" role="alert">{error}<button onClick={() => setError("")} aria-label="Dismiss error"><X size={16} /></button></div>}
    <form className="filing-vocabulary-form" onSubmit={create}>
      <input aria-label={`New ${singular} name`} value={name} onChange={(event) => setName(event.target.value)} maxLength={100} placeholder={isSender ? "e.g. City of Milan" : "e.g. Insurance policy"} required />
      <Button disabled={busy}><Plus size={16} /> Add</Button>
    </form>
    {items.length === 0 ? <p className="filing-empty">None yet. Add one here or while editing a document.</p> : <ul className="filing-vocabulary-list">
      {items.map((item) => <li key={item.id}>
        {editing === item.id ? <form onSubmit={rename}>
          <input aria-label={`Rename ${item.name}`} value={editedName} onChange={(event) => setEditedName(event.target.value)} maxLength={100} required />
          <Button disabled={busy}>Save</Button>
          <button type="button" aria-label="Cancel rename" onClick={() => setEditing(null)}><X size={16} /></button>
        </form> : <>
          <span>{item.name}</span>
          <button type="button" aria-label={`Rename ${item.name}`} onClick={() => { setEditing(item.id); setEditedName(item.name); }}><Pencil size={16} /></button>
          <button type="button" aria-label={`Delete ${item.name}`} disabled={busy} onClick={() => void remove(item)}><Trash2 size={16} /></button>
        </>}
      </li>)}
    </ul>}
  </section>;
}
