import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Bookmark, Pencil, Plus, Trash2, X } from "lucide-react";
import { LibraryFilters, request, SavedView } from "./api";
import { Button } from "./ui";

type Props = {
  query: string;
  filters: LibraryFilters;
  onApply: (query: string, filters: LibraryFilters) => void;
};

function criteria(query: string, filters: LibraryFilters) {
  return {
    query: query.trim(),
    tag_id: filters.tag_id || null,
    correspondent_id: filters.correspondent_id || null,
    document_type_id: filters.document_type_id || null,
    date_from: filters.date_from || null,
    date_to: filters.date_to || null,
  };
}

function viewFilters(view: SavedView): LibraryFilters {
  return {
    tag_id: view.tag_id ?? "",
    correspondent_id: view.correspondent_id ?? "",
    document_type_id: view.document_type_id ?? "",
    date_from: view.date_from ?? "",
    date_to: view.date_to ?? "",
  };
}

export default function SavedSearchBar({ query, filters, onApply }: Props) {
  const [views, setViews] = useState<SavedView[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [form, setForm] = useState<{ kind: "create" } | { kind: "rename"; id: string } | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const saveButton = useRef<HTMLButtonElement>(null);
  const renameButtons = useRef(new Map<string, HTMLButtonElement>());
  const nameInput = useRef<HTMLInputElement>(null);
  const focusAfterSave = useRef<string | "save" | null>(null);

  const load = useCallback(async () => {
    try {
      const result = await request<{ views: SavedView[] }>("/api/saved-views");
      setViews(result.views);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load saved searches");
    }
  }, []);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (form) nameInput.current?.focus(); }, [form]);
  useEffect(() => {
    if (busy || !focusAfterSave.current) return;
    const target = focusAfterSave.current === "save" ? saveButton.current : renameButtons.current.get(focusAfterSave.current);
    focusAfterSave.current = null;
    target?.focus();
  }, [busy, views]);

  function closeForm(restoreFocus = true) {
    const target = form?.kind === "rename" ? renameButtons.current.get(form.id) : saveButton.current;
    setForm(null);
    setName("");
    if (restoreFocus) requestAnimationFrame(() => target?.focus());
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!form) return;
    setBusy(true);
    setError("");
    try {
      if (form.kind === "create") {
        const created = await request<SavedView>("/api/saved-views", {
          method: "POST", body: JSON.stringify({ name, ...criteria(query, filters) }),
        });
        setActiveId(created.id);
        setNotice(`${created.name} saved.`);
      } else {
        const updated = await request<SavedView>(`/api/saved-views/${form.id}`, {
          method: "PATCH", body: JSON.stringify({ name }),
        });
        setNotice(`Renamed to ${updated.name}.`);
      }
      const targetId = form.kind === "rename" ? form.id : null;
      closeForm(false);
      await load();
      focusAfterSave.current = targetId ?? "save";
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save search");
    } finally {
      setBusy(false);
    }
  }

  async function update(view: SavedView) {
    setBusy(true);
    setError("");
    try {
      await request(`/api/saved-views/${view.id}`, {
        method: "PATCH", body: JSON.stringify(criteria(query, filters)),
      });
      setNotice(`${view.name} updated with the current search.`);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update saved search");
    } finally {
      setBusy(false);
    }
  }

  async function remove(view: SavedView) {
    if (!window.confirm(`Delete saved search “${view.name}”?`)) return;
    setBusy(true);
    setError("");
    try {
      await request(`/api/saved-views/${view.id}`, { method: "DELETE" });
      setViews((current) => current.filter((item) => item.id !== view.id));
      if (activeId === view.id) setActiveId(null);
      setNotice(`${view.name} deleted. The current Library results are unchanged.`);
      focusAfterSave.current = "save";
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete saved search");
    } finally {
      setBusy(false);
    }
  }

  const active = views.find((view) => view.id === activeId);
  const changed = active ? JSON.stringify(criteria(query, filters)) !== JSON.stringify(criteria(active.query, viewFilters(active))) : false;

  return <section className="saved-search-bar" aria-label="Saved searches">
    <div className="saved-search-heading"><Bookmark size={16} /><strong>Saved searches</strong></div>
    <div className="saved-search-list">
      {views.length === 0 && <span className="saved-search-empty">Keep useful searches one tap away.</span>}
      {views.map((view) => <span className={`saved-search-chip ${activeId === view.id && !changed ? "active" : ""}`} key={view.id}>
        <button type="button" disabled={busy} aria-pressed={activeId === view.id && !changed} onClick={() => {
          setActiveId(view.id);
          setNotice(`${view.name} opened.`);
          onApply(view.query, viewFilters(view));
        }}>{view.name}</button>
        <button ref={(node) => { if (node) renameButtons.current.set(view.id, node); else renameButtons.current.delete(view.id); }} type="button" aria-label={`Rename saved search ${view.name}`} disabled={busy} onClick={() => { setForm({ kind: "rename", id: view.id }); setName(view.name); }}><Pencil size={14} /></button>
        <button type="button" aria-label={`Delete saved search ${view.name}`} disabled={busy} onClick={() => void remove(view)}><Trash2 size={14} /></button>
      </span>)}
    </div>
    <div className="saved-search-actions">
      <button ref={saveButton} type="button" className="text-action" disabled={busy} onClick={() => { setForm({ kind: "create" }); setName(""); }}><Plus size={15} /> Save this search</button>
      {active && changed && <button type="button" className="text-action" disabled={busy} onClick={() => void update(active)}>Update “{active.name}”</button>}
    </div>
    {form && <form className="saved-search-form" onSubmit={submit}>
      <input ref={nameInput} aria-label="Saved search name" value={name} onChange={(event) => setName(event.target.value)} maxLength={100} placeholder="Name this search" required />
      <Button disabled={busy}>{form.kind === "create" ? "Save search" : "Save name"}</Button>
      <button type="button" aria-label="Cancel saved search" disabled={busy} onClick={() => closeForm()}><X size={17} /></button>
    </form>}
    {error && <p className="inline-error" role="alert">{error}</p>}
    <span className="visually-hidden" role="status" aria-live="polite">{notice}</span>
  </section>;
}
