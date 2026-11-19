import { FormEvent, useCallback, useEffect, useState } from "react";
import { Trash2, X } from "lucide-react";
import { request } from "./api";
import { Button } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/StoragePathsPanel";

type StoragePath = { id: string; name: string; template: string; documents: number | null };

export default function StoragePathsPanel() {
  const m = useMessages(messages);
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
      setError(cause instanceof Error ? cause.message : m.loadError);
    }
  }, [m]);
  useEffect(() => { void load(); }, [load]);

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await request<StoragePath & { example: string | null }>("/api/storage-paths", { method: "POST", body: JSON.stringify({ name, template }) });
      setNotice(result.example ? m.savedExample(result.example) : m.saved);
      setName("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.saveError);
    } finally {
      setBusy(false);
    }
  }

  async function remove(path: StoragePath) {
    setBusy(true);
    setError("");
    try {
      await request(`/api/storage-paths/${path.id}`, { method: "DELETE" });
      setNotice(m.removed(path.name));
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.removeError);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="filing-card storage-paths" aria-labelledby="storage-paths-heading">
      <h2 id="storage-paths-heading">{m.heading}</h2>
      <p>{m.intro}</p>
      {error && <div className="inline-error" role="alert">{error}<button onClick={() => setError("")} aria-label={m.dismissError}><X size={16} /></button></div>}
      {notice && <p className="bulk-notice" role="status">{notice}</p>}
      <form className="storage-path-form" onSubmit={create} aria-label={m.newPath}>
        <input aria-label={m.nameLabel} value={name} onChange={(event) => setName(event.target.value)} maxLength={100} placeholder={m.namePlaceholder} required />
        <input aria-label={m.templateLabel} value={template} onChange={(event) => setTemplate(event.target.value)} maxLength={200} required spellCheck={false} />
        <Button disabled={busy}>{m.add}</Button>
      </form>
      {placeholders.length > 0 && <small className="storage-placeholders">{m.placeholders(placeholders.map((item) => `{${item}}`).join(" "))}</small>}
      {paths.length > 0 && (
        <ul className="filing-vocabulary-list">
          {paths.map((path) => (
            <li key={path.id}>
              <span><strong>{path.name}</strong> <code>{path.template}</code>{path.documents ? ` · ${m.documents(path.documents)}` : ""}</span>
              <button type="button" className="tag-icon-button" aria-label={m.removePath(path.name)} disabled={busy} onClick={() => void remove(path)}><Trash2 size={16} aria-hidden="true" /></button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
