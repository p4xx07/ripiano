import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Cloud, Eye, Plus, RefreshCw, X } from "lucide-react";
import { FilingItem, request, Tag } from "./api";
import { Button } from "./ui";

type After = "keep" | "move" | "delete";
type Chat = { id: number; name: string };
type Source = {
  id: string; name: string; builtin: boolean; kind: "s3" | "webdav" | "folder" | "gdrive" | "onedrive" | "dropbox" | "telegram"; connected: boolean | null; enabled: boolean; allowed_chats: Chat[]; pending_chats: Chat[];
  endpoint: string; region: string; bucket: string; addressing: "path" | "virtual"; username: string; has_secret: boolean;
  path: string; recursive: boolean; include_patterns: string; exclude_patterns: string; file_types: string[];
  max_size_mb: number; modified_after: string | null; after: After; processed_path: string; retention_days: number;
  tag_ids: string[]; correspondent_id: string | null; document_type_id: string | null; poll_minutes: number;
  status: { running: boolean; last_checked_at: string | null; last_error: string; last_imported: number; total_imported: number };
};
type Draft = Omit<Source, "id" | "builtin" | "has_secret" | "connected" | "status" | "modified_after" | "correspondent_id" | "document_type_id" | "allowed_chats" | "pending_chats"> & {
  secret: string; modified_after: string; correspondent_id: string; document_type_id: string;
};
type Preview = { ok: boolean; matching: { path: string; size: number; modified: string }[]; skipped: Record<string, number>; already_imported: number; bot?: string; error?: string };

const empty: Draft = {
  name: "", kind: "s3", enabled: true, endpoint: "", region: "us-east-1", bucket: "", addressing: "path", username: "", secret: "",
  path: "", recursive: true, include_patterns: "", exclude_patterns: "", file_types: [], max_size_mb: 25, modified_after: "",
  after: "move", processed_path: "processed/", retention_days: 30, tag_ids: [], correspondent_id: "", document_type_id: "", poll_minutes: 15,
};
type App = { provider: string; label: string; console: string; client_id: string; configured: boolean; from_environment: boolean };
const cloudLabels: Record<string, string> = { gdrive: "Google Drive", onedrive: "OneDrive", dropbox: "Dropbox" };
const isCloud = (kind: string) => kind in cloudLabels;
const typeLabels: Record<string, string> = { pdf: "PDF", image: "Images", office: "Office documents", email: "Emails (.eml, .msg)" };
const afterLabels: Record<After, string> = {
  keep: "Leave the file and remember it",
  move: "Move it to a processed folder",
  delete: "Delete it from the storage",
};

function describe(source: Source) {
  if (source.kind === "telegram") {
    const chats = source.allowed_chats.length;
    return `Telegram bot · ${chats ? `${chats} allowed chat${chats === 1 ? "" : "s"}` : "no chat allowed yet: send /start to the bot"} · checked every minute.`;
  }
  if (source.builtin) {
    const after = source.after === "delete" ? "removed after import" : source.after === "move" ? `moved to ${source.processed_path}` : "left in place";
    return `Built in: drop files into the mounted consume folder${source.recursive ? " (subfolders too)" : ""}; ${after}. Checked ${source.poll_minutes === 1 ? "every minute" : `every ${source.poll_minutes} minutes`}.`;
  }
  const where = isCloud(source.kind) ? `${cloudLabels[source.kind]} /${source.path || ""}` : source.kind === "folder" ? `NAS folder /${source.path || ""}` : source.kind === "webdav" ? `${new URL(source.endpoint).host}/${source.path || ""}` : `${source.bucket}/${source.path || ""}`;
  const what = [source.recursive ? "including subfolders" : "this folder only", source.include_patterns && `names like ${source.include_patterns}`]
    .filter(Boolean).join(", ");
  const after = source.after === "move"
    ? `then moved to ${source.processed_path}${source.retention_days ? ` and deleted after ${source.retention_days} days` : ""}`
    : source.after === "delete" ? "then deleted from the storage" : "left in place";
  return `${where} · ${what}; ${after}. Checked every ${source.poll_minutes} minutes.`;
}

function size(bytes: number) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** External storages connected as document inputs, like Hyper Backup destinations in reverse. */
/** Archive owner: the OAuth apps registered once with Google, Microsoft, and Dropbox. */
function SignInApps() {
  const [data, setData] = useState<{ redirect_uri: string; providers: App[] } | null>(null);
  const [values, setValues] = useState<Record<string, { client_id: string; client_secret: string }>>({});
  const [message, setMessage] = useState("");
  const load = useCallback(async () => {
    const next = await request<{ redirect_uri: string; providers: App[] }>("/api/source-apps");
    setData(next);
    setValues(Object.fromEntries(next.providers.map((item) => [item.provider, { client_id: item.client_id, client_secret: "" }])));
  }, []);
  useEffect(() => { void load().catch(() => setMessage("Could not load sign-in apps")); }, [load]);
  if (!data) return null;
  async function save(provider: string) {
    try {
      const value = values[provider];
      await request("/api/source-apps", { method: "PUT", body: JSON.stringify({ provider, client_id: value.client_id, ...(value.client_secret ? { client_secret: value.client_secret } : {}) }) });
      setMessage(value.client_id ? "Saved." : "Removed.");
      await load();
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Could not save");
    }
  }
  return (
    <section className="tag-create-card agent-create-card">
      <h2>Sign-in apps</h2>
      <p className="source-note">Google Drive, OneDrive, and Dropbox need an OAuth app you register once with each provider. Use this redirect address there:</p>
      <code className="source-redirect">{data.redirect_uri}</code>
      {message && <p className="bulk-notice" role="status">{message}</p>}
      {data.providers.map((item) => (
        <details key={item.provider} className="source-app">
          <summary>{item.label} · {item.configured ? (item.from_environment ? "set up (mail sign-in settings)" : "set up") : "not set up"}</summary>
          <p className="source-note"><a href={item.console} target="_blank" rel="noreferrer">Open the {item.label} developer console</a></p>
          <label>Client ID<input value={values[item.provider]?.client_id ?? ""} autoCapitalize="none" spellCheck={false}
            onChange={(event) => setValues((current) => ({ ...current, [item.provider]: { ...current[item.provider], client_id: event.target.value } }))} /></label>
          <label>Client secret <small>{item.client_id ? "Saved and never shown. Type a new one to replace it." : "Stored encrypted."}</small>
            <input type="password" value={values[item.provider]?.client_secret ?? ""} autoComplete="new-password"
              onChange={(event) => setValues((current) => ({ ...current, [item.provider]: { ...current[item.provider], client_secret: event.target.value } }))} /></label>
          <Button type="button" variant="secondary" onClick={() => void save(item.provider)}>Save {item.label}</Button>
        </details>
      ))}
    </section>
  );
}

export default function SourcesPanel({ owner, notice }: { owner: boolean; notice: { kind: "ok" | "error"; text: string } | null }) {
  const [sources, setSources] = useState<Source[]>([]);
  const [fileTypes, setFileTypes] = useState<string[]>(["email", "image", "office", "pdf"]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [senders, setSenders] = useState<FilingItem[]>([]);
  const [types, setTypes] = useState<FilingItem[]>([]);
  const [draft, setDraft] = useState<Draft>(empty);
  const [editing, setEditing] = useState<Source | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ id: string; result: Preview } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(notice?.kind === "error" ? notice.text : "");
  const [status, setStatus] = useState(notice?.kind === "ok" ? notice.text : "");
  const formRef = useRef<HTMLFormElement>(null);

  const load = useCallback(async () => {
    try {
      const [list, tagResponse, senderResponse, typeResponse] = await Promise.all([
        request<{ sources: Source[]; file_types: string[] }>("/api/sources"),
        request<{ tags: Tag[] }>("/api/tags"),
        request<{ correspondents: FilingItem[] }>("/api/correspondents"),
        request<{ document_types: FilingItem[] }>("/api/document-types"),
      ]);
      setSources(list.sources);
      setFileTypes(list.file_types);
      setTags(tagResponse.tags);
      setSenders(senderResponse.correspondents);
      setTypes(typeResponse.document_types);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load sources");
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  async function run(action: () => Promise<void>, fallback: string) {
    setBusy(true);
    setError("");
    setStatus("");
    try { await action(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : fallback); }
    finally { setBusy(false); }
  }

  function focusForm() {
    requestAnimationFrame(() => {
      formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      formRef.current?.querySelector<HTMLInputElement>("input")?.focus({ preventScroll: true });
    });
  }

  function edit(source: Source) {
    setEditing(source);
    setPreview(null);
    setDraft({
      ...source, secret: "", modified_after: source.modified_after ?? "",
      max_size_mb: source.kind === "telegram" ? Math.min(source.max_size_mb, 20) : source.max_size_mb,
      correspondent_id: source.correspondent_id ?? "", document_type_id: source.document_type_id ?? "",
    });
    focusForm();
  }

  function save(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      const { secret, ...fields } = draft;
      const body = JSON.stringify({
        ...fields, ...(secret ? { secret } : {}),
        modified_after: draft.modified_after || null,
        correspondent_id: draft.correspondent_id || null, document_type_id: draft.document_type_id || null,
      });
      const saved = editing
        ? await request<Source>(`/api/sources/${editing.id}`, { method: "PATCH", body })
        : await request<Source>("/api/sources", { method: "POST", body });
      setEditing(saved);
      setDraft((current) => ({ ...current, secret: "" }));
      setStatus(`“${saved.name}” saved. Use Preview to see what it would import before the first check.`);
      await load();
    }, "Could not save the source");
  }

  function showPreview(source: Source) {
    void run(async () => {
      const result = await request<Preview>(`/api/sources/${source.id}/preview`, { method: "POST" });
      setPreview({ id: source.id, result });
    }, "Could not reach the storage");
  }

  function checkNow(source: Source) {
    void run(async () => {
      await request(`/api/sources/${source.id}/run`, { method: "POST" });
      setStatus(`Checking “${source.name}” now. New documents appear in the Library as they arrive.`);
      window.setTimeout(() => void load(), 4000);
    }, "Could not start the check");
  }

  function connect(source: Source) {
    void run(async () => {
      const { url } = await request<{ url: string }>(`/api/sources/${source.id}/connect`, { method: "POST" });
      window.location.assign(url);
    }, "Could not start the sign-in");
  }

  function changeChat(source: Source, body: { allow: number } | { remove: number }, done: string) {
    void run(async () => {
      await request(`/api/sources/${source.id}/chats`, { method: "POST", body: JSON.stringify(body) });
      setStatus(done);
      await load();
    }, "Could not update the chat");
  }

  function toggle(source: Source) {
    void run(async () => {
      await request(`/api/sources/${source.id}`, { method: "PATCH", body: JSON.stringify({ enabled: !source.enabled }) });
      await load();
    }, "Could not update the source");
  }

  function remove(source: Source) {
    void run(async () => {
      await request(`/api/sources/${source.id}`, { method: "DELETE" });
      setConfirming(null);
      if (editing?.id === source.id) { setEditing(null); setDraft(empty); }
      setStatus(`“${source.name}” removed. Documents it imported stay in your archive; files in the storage are not touched.`);
      await load();
    }, "Could not remove the source");
  }

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((current) => ({ ...current, [key]: value }));
  const toggleIn = (key: "file_types" | "tag_ids", value: string) =>
    setDraft((current) => ({ ...current, [key]: current[key].includes(value) ? current[key].filter((item) => item !== value) : [...current[key], value] }));

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> INPUTS</div>
          <h1>Sources<span className="heading-period">.</span></h1>
          <p>Connect a storage and Ripiano picks up new documents from it by itself.</p>
        </div>
      </div>
      {error && <div className="inline-error" role="alert">{error}<button onClick={() => setError("")} aria-label="Dismiss error"><X size={16} /></button></div>}
      {status && <p className="bulk-notice" role="status">{status}</p>}
      <div className="agent-layout">
        <section className="agent-main">
          <div className="section-heading"><div><h2>Connected storage</h2><p>Each file is imported once. Its original is safely stored before anything happens to it in the storage.</p></div></div>
          {sources.length ? (
            <div className="agent-list">
              {sources.map((source) => (
                <article className="agent-card mail-card source-card" key={source.id}>
                  <span className="agent-avatar"><Cloud size={21} aria-hidden="true" /></span>
                  <div className="agent-card-body">
                    <strong>{source.name}{!source.enabled && " · Paused"}</strong>
                    <span>{describe(source)}</span>
                    <small className={source.status.last_error || source.connected === false ? "source-problem" : undefined}>
                      {source.connected === false ? "Not connected yet: use Connect account."
                        : source.status.running ? "Checking now…"
                        : source.status.last_error ? `Problem: ${source.status.last_error}`
                        : source.status.last_checked_at ? `Last checked ${new Date(source.status.last_checked_at).toLocaleString()} · ${source.status.last_imported} new · ${source.status.total_imported} imported in total`
                        : "Not checked yet"}
                    </small>
                    {source.kind === "telegram" && (source.pending_chats.length > 0 || source.allowed_chats.length > 0) && (
                      <ul className="source-chats" aria-label={`Chats for ${source.name}`}>
                        {source.pending_chats.map((chat) => (
                          <li key={`p${chat.id}`}>
                            <span>{chat.name} <small>waiting</small></span>
                            <Button variant="secondary" disabled={busy} onClick={() => changeChat(source, { allow: chat.id }, `${chat.name} can now send documents.`)}>Allow</Button>
                            <Button variant="secondary" disabled={busy} aria-label={`Ignore ${chat.name}`} onClick={() => changeChat(source, { remove: chat.id }, `${chat.name} was ignored.`)}>Ignore</Button>
                          </li>
                        ))}
                        {source.allowed_chats.map((chat) => (
                          <li key={`a${chat.id}`}>
                            <span>{chat.name} <small>allowed</small></span>
                            <Button variant="secondary" disabled={busy} aria-label={`Remove ${chat.name}`} onClick={() => changeChat(source, { remove: chat.id }, `${chat.name} can no longer send documents.`)}>Remove</Button>
                          </li>
                        ))}
                      </ul>
                    )}
                    {preview?.id === source.id && (
                      <div className="source-preview" role="region" aria-label={`Preview of ${source.name}`}>
                        {preview.result.bot !== undefined ? <strong>Connected to @{preview.result.bot}.</strong> : preview.result.matching.length ? (
                          <>
                            <strong>The next check would import:</strong>
                            <ul>{preview.result.matching.map((item) => <li key={item.path}>{item.path} <small>{size(item.size)}</small></li>)}</ul>
                          </>
                        ) : <strong>Nothing new to import.</strong>}
                        <small>
                          {preview.result.already_imported ? `${preview.result.already_imported} already imported. ` : ""}
                          {Object.entries(preview.result.skipped).map(([reason, count]) => `${count} ${reason}`).join(" · ")}
                        </small>
                        <Button variant="secondary" type="button" onClick={() => setPreview(null)}>Close preview</Button>
                      </div>
                    )}
                  </div>
                  <div className="mail-actions">
                    {confirming === source.id ? (
                      <>
                        <span>Remove this source?</span>
                        <Button variant="danger" disabled={busy} onClick={() => remove(source)}>Remove</Button>
                        <Button variant="secondary" autoFocus onClick={() => setConfirming(null)}>Keep</Button>
                      </>
                    ) : (
                      <>
                        {source.connected === false && <Button disabled={busy} onClick={() => connect(source)}>Connect account</Button>}
                        {source.connected && <Button variant="secondary" disabled={busy} onClick={() => connect(source)}>Reconnect</Button>}
                        <Button variant="secondary" disabled={busy} onClick={() => showPreview(source)}><Eye size={16} aria-hidden="true" /> {source.kind === "telegram" ? "Test" : "Preview"}</Button>
                        <Button variant="secondary" disabled={busy || !source.enabled} onClick={() => checkNow(source)}><RefreshCw size={16} aria-hidden="true" /> Check now</Button>
                        <Button variant="secondary" disabled={busy} onClick={() => toggle(source)}>{source.enabled ? "Pause" : "Resume"}</Button>
                        <Button variant="secondary" onClick={() => edit(source)}>Edit</Button>
                        {!source.builtin && <Button variant="secondary" aria-label={`Remove source ${source.name}`} onClick={() => setConfirming(source.id)}>Remove</Button>}
                      </>
                    )}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="tag-empty">
              <Cloud size={27} aria-hidden="true" />
              <strong>No sources yet</strong>
              <p>Optional. Connect S3-compatible storage (AWS S3, Backblaze B2, Wasabi, Synology C2, MinIO, …), WebDAV (Nextcloud, Synology, ownCloud, …), Google Drive, OneDrive, Dropbox, a folder on the NAS, or a Telegram bot on the right.</p>
            </div>
          )}
        </section>

        <div className="mail-side">
          {owner && <SignInApps />}
          <section className="tag-create-card agent-create-card">
            <div className="tag-create-icon"><Cloud size={21} aria-hidden="true" /></div>
            <h2>{editing ? `Edit “${editing.name}”` : "New source"}</h2>
            <form ref={formRef} onSubmit={save} aria-label="Source">
              <label>Name<input value={draft.name} onChange={(event) => set("name", event.target.value)} maxLength={100} required placeholder="e.g. Scanner bucket" /></label>
              <fieldset>
                <legend>Connection</legend>
                {editing?.builtin ? <p className="source-note">The built-in consume folder: the NAS folder mounted with <code>RIPIANO_CONSUME_PATH</code>.</p> : <label>Storage
                  <select value={draft.kind} onChange={(event) => { const kind = event.target.value as Draft["kind"]; setDraft((current) => ({ ...current, kind, max_size_mb: kind === "telegram" ? Math.min(current.max_size_mb, 20) : current.max_size_mb, after: kind === "telegram" ? "keep" : current.after === "keep" ? "move" : current.after })); }}>
                    <option value="s3">S3-compatible storage</option>
                    <option value="webdav">WebDAV (Nextcloud, Synology, ownCloud, …)</option>
                    {owner && <option value="folder">Folder on the NAS</option>}
                    <option value="gdrive">Google Drive</option>
                    <option value="onedrive">OneDrive</option>
                    <option value="dropbox">Dropbox</option>
                    <option value="telegram">Telegram bot</option>
                  </select>
                </label>}
                {draft.kind === "telegram" ? (
                  <label>Bot token <small>{editing?.has_secret ? "Saved and never shown. Paste a new one to replace it." : "From BotFather; stored encrypted. Then send /start to the bot and allow your chat here."}</small>
                    <input type="password" value={draft.secret} onChange={(event) => set("secret", event.target.value)} required={!editing?.has_secret} maxLength={100} autoComplete="new-password" placeholder="123456789:AA…" />
                  </label>
                ) : isCloud(draft.kind) ? (
                  <p className="source-note">Save the source, then choose <strong>Connect account</strong> on its card to sign in to {cloudLabels[draft.kind]}. Ripiano keeps only an encrypted sign-in token; “Delete” moves files to the {draft.kind === "dropbox" ? "deleted files" : draft.kind === "onedrive" ? "recycle bin" : "trash"}.</p>
                ) : draft.kind === "folder" && !editing?.builtin ? (
                  <p className="source-note">Uses the NAS folder mounted with <code>RIPIANO_SOURCES_PATH</code>. Choose a subfolder of it below.</p>
                ) : draft.kind === "folder" ? (
                  null
                ) : draft.kind === "webdav" ? (
                  <>
                    <label>Address <small>Nextcloud: https://cloud.example.com/remote.php/dav/files/USER · Synology: https://nas.local:5006</small>
                      <input value={draft.endpoint} onChange={(event) => set("endpoint", event.target.value)} required maxLength={300} autoCapitalize="none" spellCheck={false} placeholder="https://cloud.example.com/remote.php/dav/files/ada" />
                    </label>
                    <label>User name<input value={draft.username} onChange={(event) => set("username", event.target.value)} required maxLength={200} autoCapitalize="none" spellCheck={false} autoComplete="off" /></label>
                    <label>Password <small>{editing?.has_secret ? "Saved and never shown. Type a new one to replace it." : "Use an app password if your service offers one. Stored encrypted."}</small>
                      <input type="password" value={draft.secret} onChange={(event) => set("secret", event.target.value)} required={!editing?.has_secret} maxLength={500} autoComplete="new-password" />
                    </label>
                  </>
                ) : (
                <>
                <label>Address<input value={draft.endpoint} onChange={(event) => set("endpoint", event.target.value)} required maxLength={300}
                  placeholder="https://s3.eu-south-1.amazonaws.com" autoCapitalize="none" spellCheck={false} /></label>
                <div className="mail-row">
                  <label>Bucket<input value={draft.bucket} onChange={(event) => set("bucket", event.target.value)} required maxLength={100} autoCapitalize="none" spellCheck={false} /></label>
                  <label>Region<input value={draft.region} onChange={(event) => set("region", event.target.value)} maxLength={50} autoCapitalize="none" spellCheck={false} /></label>
                </div>
                <label>Address style
                  <select value={draft.addressing} onChange={(event) => set("addressing", event.target.value as Draft["addressing"])}>
                    <option value="path">Path style (MinIO, SeaweedFS, most self-hosted)</option>
                    <option value="virtual">Virtual-hosted (AWS S3)</option>
                  </select>
                </label>
                <label>Access key<input value={draft.username} onChange={(event) => set("username", event.target.value)} required maxLength={200} autoCapitalize="none" spellCheck={false} autoComplete="off" /></label>
                <label>Secret key <small>{editing?.has_secret ? "Saved and never shown. Type a new one to replace it." : "Stored encrypted."}</small>
                  <input type="password" value={draft.secret} onChange={(event) => set("secret", event.target.value)} required={!editing?.has_secret} maxLength={500} autoComplete="new-password" />
                </label>
                </>
                )}
              </fieldset>
              <fieldset>
                <legend>What to import</legend>
                {draft.kind !== "telegram" && (
                  <>
                    <label>Folder <small>{isCloud(draft.kind) ? "From the top of your drive, e.g. Scans; empty for everything" : editing?.builtin ? "Inside the consume folder; empty for all of it" : draft.kind === "folder" ? "Inside the mounted NAS folder, e.g. Scanner" : draft.kind === "webdav" ? "Leave empty for the whole storage" : "Leave empty for the whole bucket"}</small><input value={draft.path} onChange={(event) => set("path", event.target.value)} maxLength={500} placeholder={draft.kind === "folder" ? "Scanner" : draft.kind === "webdav" ? "Documents/Scans" : "inbox/"} autoCapitalize="none" spellCheck={false} /></label>
                    <label className="agent-scope-choice"><input type="checkbox" checked={draft.recursive} onChange={(event) => set("recursive", event.target.checked)} />Include subfolders</label>
                  </>
                )}
                <label>Only names like <small>Comma-separated, e.g. fattura*, *.pdf</small><input value={draft.include_patterns} onChange={(event) => set("include_patterns", event.target.value)} maxLength={500} autoCapitalize="none" spellCheck={false} /></label>
                <label>Skip names or paths like <small>e.g. drafts/*, *-copy.pdf</small><input value={draft.exclude_patterns} onChange={(event) => set("exclude_patterns", event.target.value)} maxLength={500} autoCapitalize="none" spellCheck={false} /></label>
                <div className="workflow-choices" role="group" aria-label="File types">
                  <span>File types <small>None ticked: every supported type</small></span>
                  {fileTypes.map((value) => (
                    <label className="agent-scope-choice" key={value}><input type="checkbox" checked={draft.file_types.includes(value)} onChange={() => toggleIn("file_types", value)} />{typeLabels[value] ?? value}</label>
                  ))}
                </div>
                <label>Largest file (MB) {draft.kind === "telegram" && <small>Telegram allows bots up to 20 MB</small>}<input type="number" min={1} max={draft.kind === "telegram" ? 20 : 25} value={draft.max_size_mb} onChange={(event) => set("max_size_mb", Number(event.target.value))} /></label>
                <label>Only files changed after <small>Optional</small><input type="date" value={draft.modified_after} onChange={(event) => set("modified_after", event.target.value)} /></label>
              </fieldset>
              {draft.kind !== "telegram" && (
              <fieldset>
                <legend>After import</legend>
                {(Object.keys(afterLabels) as After[]).map((value) => (
                  <label className="agent-scope-choice" key={value}><input type="radio" name="source-after" checked={draft.after === value} onChange={() => set("after", value)} />{afterLabels[value]}</label>
                ))}
                {draft.after === "move" && (
                  <div className="mail-row">
                    <label>Processed folder<input value={draft.processed_path} onChange={(event) => set("processed_path", event.target.value)} required maxLength={500} autoCapitalize="none" spellCheck={false} /></label>
                    <label>Delete after (days) <small>0 keeps them</small><input type="number" min={0} max={3650} value={draft.retention_days} onChange={(event) => set("retention_days", Number(event.target.value))} /></label>
                  </div>
                )}
              </fieldset>
              )}
              <fieldset>
                <legend>File imported documents <small>Optional</small></legend>
                {tags.length > 0 && (
                  <div className="workflow-choices mail-tags" role="group" aria-label="Add tags">
                    {tags.map((tag) => <label className="agent-scope-choice" key={tag.id}><input type="checkbox" checked={draft.tag_ids.includes(tag.id)} onChange={() => toggleIn("tag_ids", tag.id)} />{tag.name}</label>)}
                  </div>
                )}
                <label>Sender
                  <select value={draft.correspondent_id} onChange={(event) => set("correspondent_id", event.target.value)}>
                    <option value="">Don’t set</option>{senders.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label>Type
                  <select value={draft.document_type_id} onChange={(event) => set("document_type_id", event.target.value)}>
                    <option value="">Don’t set</option>{types.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
              </fieldset>
              {draft.kind !== "telegram" && <label>Check every (minutes)<input type="number" min={draft.kind === "folder" ? 1 : 5} max={1440} value={draft.poll_minutes} onChange={(event) => set("poll_minutes", Number(event.target.value))} /></label>}
              <Button disabled={busy}><Plus size={17} aria-hidden="true" /> {editing ? "Save source" : "Add source"}</Button>
              {editing && <Button type="button" variant="secondary" onClick={() => { setEditing(null); setDraft(empty); setPreview(null); }}>New source instead</Button>}
            </form>
          </section>
        </div>
      </div>
    </>
  );
}
