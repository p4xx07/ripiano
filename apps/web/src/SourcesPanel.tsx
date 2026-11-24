import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Cloud, Eye, Plus, RefreshCw, X } from "lucide-react";
import { FilingItem, request, Tag } from "./api";
import { Button } from "./ui";
import { useLanguage, useMessages } from "./i18n";
import messages from "./locales/SourcesPanel";

type Messages = typeof messages.en;

type After = "keep" | "move" | "delete";
type Chat = { id: number; name: string };
type Source = {
  id: string; name: string; builtin: boolean; kind: "s3" | "webdav" | "folder" | "gdrive" | "onedrive" | "dropbox" | "telegram"; connected: boolean | null; enabled: boolean; allowed_chats: Chat[]; pending_chats: Chat[]; reply_language: "en" | "it";
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
  after: "move", processed_path: "processed/", retention_days: 30, tag_ids: [], correspondent_id: "", document_type_id: "", poll_minutes: 15, reply_language: "en",
};
type App = { provider: string; label: string; console: string; client_id: string; configured: boolean; from_environment: boolean };
const cloudLabels: Record<string, string> = { gdrive: "Google Drive", onedrive: "OneDrive", dropbox: "Dropbox" };
const isCloud = (kind: string) => kind in cloudLabels;
const afterChoices: After[] = ["keep", "move", "delete"];

function describe(source: Source, m: Messages) {
  if (source.kind === "telegram") {
    return m.describeTelegram(source.allowed_chats.length);
  }
  if (source.builtin) {
    return m.describeBuiltin(source.recursive, source.after, source.processed_path, source.poll_minutes);
  }
  const where = isCloud(source.kind) ? `${cloudLabels[source.kind]} /${source.path || ""}` : source.kind === "folder" ? m.nasFolder(source.path || "") : source.kind === "webdav" ? `${new URL(source.endpoint).host}/${source.path || ""}` : `${source.bucket}/${source.path || ""}`;
  return m.describeExternal(where, source.recursive, source.include_patterns, source.after, source.processed_path, source.retention_days, source.poll_minutes);
}

function size(bytes: number) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** External storages connected as document inputs, like Hyper Backup destinations in reverse. */
/** Archive owner: the OAuth apps registered once with Google, Microsoft, and Dropbox. */
function SignInApps() {
  const m = useMessages(messages);
  const [data, setData] = useState<{ redirect_uri: string; providers: App[] } | null>(null);
  const [values, setValues] = useState<Record<string, { client_id: string; client_secret: string }>>({});
  const [message, setMessage] = useState("");
  const load = useCallback(async () => {
    const next = await request<{ redirect_uri: string; providers: App[] }>("/api/source-apps");
    setData(next);
    setValues(Object.fromEntries(next.providers.map((item) => [item.provider, { client_id: item.client_id, client_secret: "" }])));
  }, []);
  useEffect(() => { void load().catch(() => setMessage(m.appsLoadError)); }, [load]);
  if (!data) return null;
  async function save(provider: string) {
    try {
      const value = values[provider];
      await request("/api/source-apps", { method: "PUT", body: JSON.stringify({ provider, client_id: value.client_id, ...(value.client_secret ? { client_secret: value.client_secret } : {}) }) });
      setMessage(value.client_id ? m.saved : m.removed);
      await load();
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : m.saveError);
    }
  }
  return (
    <section className="tag-create-card agent-create-card">
      <h2>{m.appsHeading}</h2>
      <p className="source-note">{m.appsNote}</p>
      <code className="source-redirect">{data.redirect_uri}</code>
      {message && <p className="bulk-notice" role="status">{message}</p>}
      {data.providers.map((item) => (
        <details key={item.provider} className="source-app">
          <summary>{item.label} · {item.configured ? (item.from_environment ? m.setUpFromEnvironment : m.setUp) : m.notSetUp}</summary>
          <p className="source-note"><a href={item.console} target="_blank" rel="noreferrer">{m.openConsole(item.label)}</a></p>
          <label>{m.clientId}<input value={values[item.provider]?.client_id ?? ""} autoCapitalize="none" spellCheck={false}
            onChange={(event) => setValues((current) => ({ ...current, [item.provider]: { ...current[item.provider], client_id: event.target.value } }))} /></label>
          <label>{m.clientSecret} <small>{item.client_id ? m.secretSaved : m.storedEncrypted}</small>
            <input type="password" value={values[item.provider]?.client_secret ?? ""} autoComplete="new-password"
              onChange={(event) => setValues((current) => ({ ...current, [item.provider]: { ...current[item.provider], client_secret: event.target.value } }))} /></label>
          <Button type="button" variant="secondary" onClick={() => void save(item.provider)}>{m.saveApp(item.label)}</Button>
        </details>
      ))}
    </section>
  );
}

export default function SourcesPanel({ owner, notice }: { owner: boolean; notice: { kind: "ok" | "error"; text: string } | null }) {
  const m = useMessages(messages);
  const [sources, setSources] = useState<Source[]>([]);
  const [fileTypes, setFileTypes] = useState<string[]>(["email", "image", "office", "pdf"]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [senders, setSenders] = useState<FilingItem[]>([]);
  const [types, setTypes] = useState<FilingItem[]>([]);
  const language = useLanguage();
  const fresh = (): Draft => ({ ...empty, reply_language: language === "it" ? "it" : "en" });
  const [draft, setDraft] = useState<Draft>(fresh);
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
      setError(cause instanceof Error ? cause.message : m.loadError);
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
      if (!formRef.current?.contains(document.activeElement)) formRef.current?.querySelector<HTMLInputElement>("input")?.focus({ preventScroll: true });
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
      setStatus(m.sourceSaved(saved.name));
      await load();
    }, m.saveSourceError);
  }

  function showPreview(source: Source) {
    void run(async () => {
      const result = await request<Preview>(`/api/sources/${source.id}/preview`, { method: "POST" });
      setPreview({ id: source.id, result });
    }, m.previewError);
  }

  function checkNow(source: Source) {
    void run(async () => {
      await request(`/api/sources/${source.id}/run`, { method: "POST" });
      setStatus(m.checkingSource(source.name));
      window.setTimeout(() => void load(), 4000);
    }, m.checkError);
  }

  function connect(source: Source) {
    void run(async () => {
      const { url } = await request<{ url: string }>(`/api/sources/${source.id}/connect`, { method: "POST" });
      window.location.assign(url);
    }, m.connectError);
  }

  function changeChat(source: Source, body: { allow: number } | { remove: number }, done: string) {
    void run(async () => {
      await request(`/api/sources/${source.id}/chats`, { method: "POST", body: JSON.stringify(body) });
      setStatus(done);
      await load();
    }, m.chatError);
  }

  function toggle(source: Source) {
    void run(async () => {
      await request(`/api/sources/${source.id}`, { method: "PATCH", body: JSON.stringify({ enabled: !source.enabled }) });
      await load();
    }, m.updateError);
  }

  function remove(source: Source) {
    void run(async () => {
      await request(`/api/sources/${source.id}`, { method: "DELETE" });
      setConfirming(null);
      if (editing?.id === source.id) { setEditing(null); setDraft(fresh()); }
      setStatus(m.sourceRemoved(source.name));
      await load();
    }, m.removeError);
  }

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((current) => ({ ...current, [key]: value }));
  const toggleIn = (key: "file_types" | "tag_ids", value: string) =>
    setDraft((current) => ({ ...current, [key]: current[key].includes(value) ? current[key].filter((item) => item !== value) : [...current[key], value] }));

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> {m.eyebrow}</div>
          <h1>{m.title}<span className="heading-period">.</span></h1>
          <p>{m.intro}</p>
        </div>
      </div>
      {error && <div className="inline-error" role="alert">{error}<button onClick={() => setError("")} aria-label={m.dismissError}><X size={16} /></button></div>}
      {status && <p className="bulk-notice" role="status">{status}</p>}
      <div className="agent-layout">
        <section className="agent-main">
          <div className="section-heading"><div><h2>{m.connectedHeading}</h2><p>{m.connectedIntro}</p></div></div>
          {sources.length ? (
            <div className="agent-list">
              {sources.map((source) => (
                <article className="agent-card mail-card source-card" key={source.id}>
                  <span className="agent-avatar"><Cloud size={21} aria-hidden="true" /></span>
                  <div className="agent-card-body">
                    <strong>{source.name}{!source.enabled && m.pausedSuffix}</strong>
                    <span>{describe(source, m)}</span>
                    <small className={source.status.last_error || source.connected === false ? "source-problem" : undefined}>
                      {source.connected === false ? m.notConnected
                        : source.status.running ? m.checkingNow
                        : source.status.last_error ? m.problem(source.status.last_error)
                        : source.status.last_checked_at ? m.lastChecked(new Date(source.status.last_checked_at).toLocaleString(), source.status.last_imported, source.status.total_imported)
                        : m.notChecked}
                    </small>
                    {source.kind === "telegram" && (source.pending_chats.length > 0 || source.allowed_chats.length > 0) && (
                      <ul className="source-chats" aria-label={m.chatsFor(source.name)}>
                        {source.pending_chats.map((chat) => (
                          <li key={`p${chat.id}`}>
                            <span>{chat.name} <small>{m.waiting}</small></span>
                            <Button variant="secondary" disabled={busy} onClick={() => changeChat(source, { allow: chat.id }, m.canSend(chat.name))}>{m.allow}</Button>
                            <Button variant="secondary" disabled={busy} aria-label={m.ignoreNamed(chat.name)} onClick={() => changeChat(source, { remove: chat.id }, m.ignored(chat.name))}>{m.ignore}</Button>
                          </li>
                        ))}
                        {source.allowed_chats.map((chat) => (
                          <li key={`a${chat.id}`}>
                            <span>{chat.name} <small>{m.allowed}</small></span>
                            <Button variant="secondary" disabled={busy} aria-label={m.removeNamed(chat.name)} onClick={() => changeChat(source, { remove: chat.id }, m.cannotSend(chat.name))}>{m.remove}</Button>
                          </li>
                        ))}
                      </ul>
                    )}
                    {preview?.id === source.id && (
                      <div className="source-preview" role="region" aria-label={m.previewOf(source.name)}>
                        {preview.result.bot !== undefined ? <strong>{m.connectedTo(preview.result.bot)}</strong> : preview.result.matching.length ? (
                          <>
                            <strong>{m.wouldImport}</strong>
                            <ul>{preview.result.matching.map((item) => <li key={item.path}>{item.path} <small>{size(item.size)}</small></li>)}</ul>
                          </>
                        ) : <strong>{m.nothingNew}</strong>}
                        <small>
                          {preview.result.already_imported ? m.alreadyImported(preview.result.already_imported) : ""}
                          {Object.entries(preview.result.skipped).map(([reason, count]) => `${count} ${reason}`).join(" · ")}
                        </small>
                        <Button variant="secondary" type="button" onClick={() => setPreview(null)}>{m.closePreview}</Button>
                      </div>
                    )}
                  </div>
                  <div className="mail-actions">
                    {confirming === source.id ? (
                      <>
                        <span>{m.removeConfirm}</span>
                        <Button variant="danger" disabled={busy} onClick={() => remove(source)}>{m.remove}</Button>
                        <Button variant="secondary" autoFocus onClick={() => setConfirming(null)}>{m.keep}</Button>
                      </>
                    ) : (
                      <>
                        {source.connected === false && <Button disabled={busy} onClick={() => connect(source)}>{m.connectAccount}</Button>}
                        {source.connected && <Button variant="secondary" disabled={busy} onClick={() => connect(source)}>{m.reconnect}</Button>}
                        <Button variant="secondary" disabled={busy} onClick={() => showPreview(source)}><Eye size={16} aria-hidden="true" /> {source.kind === "telegram" ? m.test : m.preview}</Button>
                        <Button variant="secondary" disabled={busy || !source.enabled} onClick={() => checkNow(source)}><RefreshCw size={16} aria-hidden="true" /> {m.checkNow}</Button>
                        <Button variant="secondary" disabled={busy} onClick={() => toggle(source)}>{source.enabled ? m.pause : m.resume}</Button>
                        <Button variant="secondary" onClick={() => edit(source)}>{m.edit}</Button>
                        {!source.builtin && <Button variant="secondary" aria-label={m.removeSource(source.name)} onClick={() => setConfirming(source.id)}>{m.remove}</Button>}
                      </>
                    )}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="tag-empty">
              <Cloud size={27} aria-hidden="true" />
              <strong>{m.noSources}</strong>
              <p>{m.noSourcesIntro}</p>
            </div>
          )}
        </section>

        <div className="mail-side">
          {owner && <SignInApps />}
          <section className="tag-create-card agent-create-card">
            <div className="tag-create-icon"><Cloud size={21} aria-hidden="true" /></div>
            <h2>{editing ? m.editNamed(editing.name) : m.newSource}</h2>
            <form ref={formRef} onSubmit={save} aria-label={m.formLabel}>
              <label>{m.name}<input value={draft.name} onChange={(event) => set("name", event.target.value)} maxLength={100} required placeholder={m.namePlaceholder} /></label>
              <fieldset>
                <legend>{m.connection}</legend>
                {editing?.builtin ? <p className="source-note">{m.builtinNote} <code>RIPIANO_CONSUME_PATH</code>.</p> : <label>{m.storage}
                  <select value={draft.kind} onChange={(event) => { const kind = event.target.value as Draft["kind"]; setDraft((current) => ({ ...current, kind, max_size_mb: kind === "telegram" ? Math.min(current.max_size_mb, 20) : current.max_size_mb, after: kind === "telegram" ? "keep" : current.after === "keep" ? "move" : current.after })); }}>
                    <option value="s3">{m.kindS3}</option>
                    <option value="webdav">WebDAV (Nextcloud, ownCloud, …)</option>
                    {owner && <option value="folder">{m.kindFolder}</option>}
                    <option value="gdrive">Google Drive</option>
                    <option value="onedrive">OneDrive</option>
                    <option value="dropbox">Dropbox</option>
                    <option value="telegram">{m.kindTelegram}</option>
                  </select>
                </label>}
                {draft.kind === "telegram" ? (
                  <>
                  <label>{m.botToken} <small>{editing?.has_secret ? m.botTokenSaved : m.botTokenHint}</small>
                    <input type="password" value={draft.secret} onChange={(event) => set("secret", event.target.value)} required={!editing?.has_secret} maxLength={100} autoComplete="new-password" placeholder="123456789:AA…" />
                  </label>
                  <label>{m.replyLanguage}
                    <select value={draft.reply_language} onChange={(event) => set("reply_language", event.target.value as Draft["reply_language"])}>
                      <option value="en">English</option>
                      <option value="it">Italiano</option>
                    </select>
                  </label>
                  </>
                ) : isCloud(draft.kind) ? (
                  <p className="source-note">{m.cloudNoteStart} <strong>{m.connectAccount}</strong>{m.cloudNoteEnd(cloudLabels[draft.kind], draft.kind)}</p>
                ) : draft.kind === "folder" && !editing?.builtin ? (
                  <p className="source-note">{m.folderNoteStart} <code>RIPIANO_SOURCES_PATH</code>{m.folderNoteEnd}</p>
                ) : draft.kind === "folder" ? (
                  null
                ) : draft.kind === "webdav" ? (
                  <>
                    <label>{m.address} <small>Nextcloud: https://cloud.example.com/remote.php/dav/files/USER</small>
                      <input value={draft.endpoint} onChange={(event) => set("endpoint", event.target.value)} required maxLength={300} autoCapitalize="none" spellCheck={false} placeholder="https://cloud.example.com/remote.php/dav/files/ada" />
                    </label>
                    <label>{m.userName}<input value={draft.username} onChange={(event) => set("username", event.target.value)} required maxLength={200} autoCapitalize="none" spellCheck={false} autoComplete="off" /></label>
                    <label>{m.password} <small>{editing?.has_secret ? m.secretSaved : m.appPasswordHint}</small>
                      <input type="password" value={draft.secret} onChange={(event) => set("secret", event.target.value)} required={!editing?.has_secret} maxLength={500} autoComplete="new-password" />
                    </label>
                  </>
                ) : (
                <>
                <label>{m.address}<input value={draft.endpoint} onChange={(event) => set("endpoint", event.target.value)} required maxLength={300}
                  placeholder="https://s3.eu-south-1.amazonaws.com" autoCapitalize="none" spellCheck={false} /></label>
                <div className="mail-row">
                  <label>{m.bucket}<input value={draft.bucket} onChange={(event) => set("bucket", event.target.value)} required maxLength={100} autoCapitalize="none" spellCheck={false} /></label>
                  <label>{m.region}<input value={draft.region} onChange={(event) => set("region", event.target.value)} maxLength={50} autoCapitalize="none" spellCheck={false} /></label>
                </div>
                <label>{m.addressStyle}
                  <select value={draft.addressing} onChange={(event) => set("addressing", event.target.value as Draft["addressing"])}>
                    <option value="path">{m.pathStyle}</option>
                    <option value="virtual">{m.virtualHosted}</option>
                  </select>
                </label>
                <label>{m.accessKey}<input value={draft.username} onChange={(event) => set("username", event.target.value)} required maxLength={200} autoCapitalize="none" spellCheck={false} autoComplete="off" /></label>
                <label>{m.secretKey} <small>{editing?.has_secret ? m.secretSaved : m.storedEncrypted}</small>
                  <input type="password" value={draft.secret} onChange={(event) => set("secret", event.target.value)} required={!editing?.has_secret} maxLength={500} autoComplete="new-password" />
                </label>
                </>
                )}
              </fieldset>
              <fieldset>
                <legend>{m.whatToImport}</legend>
                {draft.kind !== "telegram" && (
                  <>
                    <label>{m.folder} <small>{isCloud(draft.kind) ? m.folderHintCloud : editing?.builtin ? m.folderHintBuiltin : draft.kind === "folder" ? m.folderHintNas : draft.kind === "webdav" ? m.folderHintWebdav : m.folderHintBucket}</small><input value={draft.path} onChange={(event) => set("path", event.target.value)} maxLength={500} placeholder={draft.kind === "folder" ? "Scanner" : draft.kind === "webdav" ? m.webdavFolderPlaceholder : "inbox/"} autoCapitalize="none" spellCheck={false} /></label>
                    <label className="agent-scope-choice"><input type="checkbox" checked={draft.recursive} onChange={(event) => set("recursive", event.target.checked)} />{m.includeSubfolders}</label>
                  </>
                )}
                <label>{m.onlyNames} <small>{m.onlyNamesHint}</small><input value={draft.include_patterns} onChange={(event) => set("include_patterns", event.target.value)} maxLength={500} autoCapitalize="none" spellCheck={false} /></label>
                <label>{m.skipNames} <small>{m.skipNamesHint}</small><input value={draft.exclude_patterns} onChange={(event) => set("exclude_patterns", event.target.value)} maxLength={500} autoCapitalize="none" spellCheck={false} /></label>
                <div className="workflow-choices" role="group" aria-label={m.fileTypes}>
                  <span>{m.fileTypes} <small>{m.fileTypesHint}</small></span>
                  {fileTypes.map((value) => (
                    <label className="agent-scope-choice" key={value}><input type="checkbox" checked={draft.file_types.includes(value)} onChange={() => toggleIn("file_types", value)} />{m.fileType(value)}</label>
                  ))}
                </div>
                <label>{m.largestFile} {draft.kind === "telegram" && <small>{m.telegramLimit}</small>}<input type="number" min={1} max={draft.kind === "telegram" ? 20 : 25} value={draft.max_size_mb} onChange={(event) => set("max_size_mb", Number(event.target.value))} /></label>
                <label>{m.changedAfter} <small>{m.optional}</small><input type="date" value={draft.modified_after} onChange={(event) => set("modified_after", event.target.value)} /></label>
              </fieldset>
              {draft.kind !== "telegram" && (
              <fieldset>
                <legend>{m.afterImport}</legend>
                {afterChoices.map((value) => (
                  <label className="agent-scope-choice" key={value}><input type="radio" name="source-after" checked={draft.after === value} onChange={() => set("after", value)} />{m.afterLabel(value)}</label>
                ))}
                {draft.after === "move" && (
                  <div className="mail-row">
                    <label>{m.processedFolder}<input value={draft.processed_path} onChange={(event) => set("processed_path", event.target.value)} required maxLength={500} autoCapitalize="none" spellCheck={false} /></label>
                    <label>{m.deleteAfter} <small>{m.keepsThem}</small><input type="number" min={0} max={3650} value={draft.retention_days} onChange={(event) => set("retention_days", Number(event.target.value))} /></label>
                  </div>
                )}
              </fieldset>
              )}
              <fieldset>
                <legend>{m.fileImported} <small>{m.optional}</small></legend>
                {tags.length > 0 && (
                  <div className="workflow-choices mail-tags" role="group" aria-label={m.addTags}>
                    {tags.map((tag) => <label className="agent-scope-choice" key={tag.id}><input type="checkbox" checked={draft.tag_ids.includes(tag.id)} onChange={() => toggleIn("tag_ids", tag.id)} />{tag.name}</label>)}
                  </div>
                )}
                <label>{m.sender}
                  <select value={draft.correspondent_id} onChange={(event) => set("correspondent_id", event.target.value)}>
                    <option value="">{m.dontSet}</option>{senders.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label>{m.type}
                  <select value={draft.document_type_id} onChange={(event) => set("document_type_id", event.target.value)}>
                    <option value="">{m.dontSet}</option>{types.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
              </fieldset>
              {draft.kind !== "telegram" && <label>{m.checkEvery}<input type="number" min={draft.kind === "folder" ? 1 : 5} max={1440} value={draft.poll_minutes} onChange={(event) => set("poll_minutes", Number(event.target.value))} /></label>}
              <Button disabled={busy}><Plus size={17} aria-hidden="true" /> {editing ? m.saveSource : m.addSource}</Button>
              {editing && <Button type="button" variant="secondary" onClick={() => { setEditing(null); setDraft(fresh()); setPreview(null); }}>{m.newInstead}</Button>}
            </form>
          </section>
        </div>
      </div>
    </>
  );
}
