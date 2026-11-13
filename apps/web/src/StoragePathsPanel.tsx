import { FormEvent, useCallback, useEffect, useState } from "react";
import { Trash2, X } from "lucide-react";
import { request } from "./api";
import { Button } from "./ui";

type StoragePath = { id: string; name: string; template: string; documents: number | null };

export default function StoragePathsPanel() {
  const [paths, setPaths] = useState<StoragePath[]>([]);
  const [placeholders, setPlaceholders] = useState<string[]>([]);
  const [name, setName] = useState("");
  const [template, setTemplate] = useState("{correspondent}/{year}");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    try {
      const result = await request<{ storage_paths: StoragePath[]; placeholders: string[] }>("/api/storage-paths");
      setPaths(result.storage_paths);
      setPlaceholders(result.placeholders);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load storage paths");
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await request<StoragePath & { example: string | null }>("/api/storage-paths", { method: "POST", body: JSON.stringify({ name, template }) });
      setNotice(result.example ? `Saved. Example folder: ${result.example}` : "Saved.");
      setName("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save the storage path");
    } finally {
      setBusy(false);
    }
  }

  async function remove(path: StoragePath) {
    setBusy(true);
    setError("");
    try {
      await request(`/api/storage-paths/${path.id}`, { method: "DELETE" });
      setNotice(`Removed “${path.name}”. Its documents go back to the year layout in the next NAS copy.`);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not remove the storage path");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="filing-card storage-paths" aria-labelledby="storage-paths-heading">
      <h2 id="storage-paths-heading">Storage paths</h2>
      <p>Folder layouts for the readable NAS copy. Originals inside Ripiano never move. Choose a path on each document.</p>
      {error && <div className="inline-error" role="alert">{error}<button onClick={() => setError("")} aria-label="Dismiss error"><X size={16} /></button></div>}
      {notice && <p className="bulk-notice" role="status">{notice}</p>}
      <form className="storage-path-form" onSubmit={create} aria-label="New storage path">
        <input aria-label="Storage path name" value={name} onChange={(event) => setName(event.target.value)} maxLength={100} placeholder="e.g. By sender" required />
        <input aria-label="Folder template" value={template} onChange={(event) => setTemplate(event.target.value)} maxLength={200} required spellCheck={false} />
        <Button disabled={busy}>Add</Button>
      </form>
      {placeholders.length > 0 && <small className="storage-placeholders">You can use {placeholders.map((item) => `{${item}}`).join(" ")}, separated by /.</small>}
      {paths.length > 0 && (
        <ul className="filing-vocabulary-list">
          {paths.map((path) => (
            <li key={path.id}>
              <span><strong>{path.name}</strong> <code>{path.template}</code>{path.documents ? ` · ${path.documents} document${path.documents === 1 ? "" : "s"}` : ""}</span>
              <button type="button" className="tag-icon-button" aria-label={`Remove storage path ${path.name}`} disabled={busy} onClick={() => void remove(path)}><Trash2 size={16} aria-hidden="true" /></button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
