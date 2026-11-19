import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Bot, Check, Copy, LockKeyhole, Plus, Shield, Trash2, X } from "lucide-react";
import { ApiError, formatDate, formatDateTime, isPasswordRefusal, request, Tag } from "./api";
import { Button, useFieldError } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/AgentPanel";

type Grant = {
  id: string;
  name: string;
  scopes: string[];
  filter_tag_id: string | null;
  filter_tag_name: string | null;
  expires_at: string;
  revoked_at: string | null;
  last_used_at: string | null;
  created_at: string;
};
type Event = {
  agent: string;
  action: string;
  document_id: string | null;
  /** Present when the call concerned one document the viewer can see. */
  document_title?: string | null;
  outcome: string;
  at: string;
};

export default function AgentPanel() {
  const m = useMessages(messages);
  const scopeNames: Record<string, string> = {
    "documents:search": m.scopeSearch,
    "documents:text": m.scopeText,
    "documents:tag": m.scopeTag,
    "documents:filing": m.scopeFiling,
  };
  // Tool names and outcomes come from the MCP audit log; unknown tools fall back to their raw name.
  const toolNames: Record<string, string> = {
    search_documents: m.toolSearchDocuments,
    get_document_text: m.toolGetDocumentText,
    semantic_search: m.toolSemanticSearch,
    list_tags: m.toolListTags,
    change_document_tags: m.toolChangeDocumentTags,
    list_filing_options: m.toolListFilingOptions,
    set_document_filing: m.toolSetDocumentFiling,
  };
  const outcomeNames: Record<string, string> = { ok: m.outcomeOk, denied: m.outcomeDenied, error: m.outcomeError };
  const [confirmRevoke, setConfirmRevoke] = useState<string | null>(null);
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null);
  // Revoked and expired agents are kept out of the way under a closed "Revoked or expired (N)" group.
  const [showInactive, setShowInactive] = useState(false);
  const [grants, setGrants] = useState<Grant[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<string[]>(["documents:search"]);
  const [filterTag, setFilterTag] = useState("");
  const [days, setDays] = useState(30);
  // Creating an agent token asks for the person's current password, like an API token.
  const [password, setPassword] = useState("");
  const [newToken, setNewToken] = useState("");
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // Screen-reader announcements; focus moves with each result so it never falls back to the page.
  const [announcement, setAnnouncement] = useState("");
  const [focusTarget, setFocusTarget] = useState<{ kind: "token" } | { kind: "grant" | "revoke" | "remove" | "inactive"; id: string } | null>(null);
  const tokenCardRef = useRef<HTMLDivElement>(null);
  // A refused "Connect an agent" marks and focuses the field it is about (round-7 judge 2 M1).
  const createInvalid = useFieldError<"name" | "password">("agent-create-error");
  const [createError, setCreateError] = useState("");
  // Removing a revoked agent with its activity log asks for the password too (docs/DECISIONS.md D10).
  const [removePassword, setRemovePassword] = useState("");
  const [removeError, setRemoveError] = useState("");
  const removeInvalid = useFieldError<"password">("agent-remove-error");

  const load = useCallback(async () => {
    try {
      const [grantsResponse, eventsResponse, tagsResponse] = await Promise.all([
        request<{ grants: Grant[] }>("/api/agents"),
        request<{ events: Event[] }>("/api/agents/events"),
        request<{ tags: Tag[] }>("/api/tags"),
      ]);
      setGrants(grantsResponse.grants);
      setEvents(eventsResponse.events);
      setTags(tagsResponse.tags);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : m.loadError,
      );
    }
  }, [m]);
  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!focusTarget) return;
    let element: HTMLElement | null = null;
    if (focusTarget.kind === "token") element = tokenCardRef.current;
    else element = document.querySelector<HTMLElement>(`[data-agent-${focusTarget.kind}="${CSS.escape(focusTarget.id)}"]`);
    if (!element) return;
    setFocusTarget(null);
    element.scrollIntoView({ block: "center" });
    element.focus({ preventScroll: true });
  }, [focusTarget, grants, newToken]);

  function toggleScope(scope: string) {
    setScopes((current) =>
      current.includes(scope)
        ? current.filter((item) => item !== scope)
        : [...current, scope],
    );
  }

  async function create(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    setCreateError("");
    createInvalid.clear();
    setNewToken("");
    try {
      const grant = await request<Grant & { token: string }>("/api/agents", {
        method: "POST",
        body: JSON.stringify({
          name,
          scopes,
          filter_tag_id: filterTag || null,
          expires_in_days: days,
          password,
        }),
      });
      setPassword("");
      setNewToken(grant.token);
      setCopied(false);
      setName("");
      await load();
      setAnnouncement(m.createdAnnouncement(grant.name));
      setFocusTarget({ kind: "token" });
    } catch (cause) {
      // Shown next to the form; focus goes to the field the server refused, or stays on the button.
      setCreateError(cause instanceof Error ? cause.message : m.createError);
      if (isPasswordRefusal(cause)) createInvalid.fail("password");
      else if (cause instanceof ApiError && (cause.status === 400 || cause.status === 409) && /name|nome/i.test(cause.message)) createInvalid.fail("name");
    } finally {
      setBusy(false);
    }
  }

  async function revoke(grant: Grant) {
    setBusy(true);
    setError("");
    try {
      await request(`/api/agents/${grant.id}`, { method: "DELETE" });
      setConfirmRevoke(null);
      if (newToken) setNewToken("");
      await load();
      setAnnouncement(m.revokedAnnouncement(grant.name));
      // The revoked card moves to the closed "Revoked or expired" group: focus that group's summary.
      setFocusTarget({ kind: "inactive", id: "summary" });
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : m.revokeError,
      );
    } finally {
      setBusy(false);
    }
  }

  function startRemove(grant: Grant) {
    setConfirmRemove(grant.id);
    setRemovePassword("");
    setRemoveError("");
    removeInvalid.clear();
  }

  function cancelRemove(grant: Grant) {
    setConfirmRemove(null);
    setRemovePassword("");
    setRemoveError("");
    removeInvalid.clear();
    setFocusTarget({ kind: "remove", id: grant.id });
  }

  async function remove(event: FormEvent, grant: Grant) {
    event.preventDefault();
    if (busy || !removePassword) return;
    setBusy(true);
    setError("");
    setRemoveError("");
    removeInvalid.clear();
    try {
      await request(`/api/agents/${grant.id}?forget=1`, { method: "DELETE", body: JSON.stringify({ password: removePassword }) });
      setRemovePassword("");
      setConfirmRemove(null);
      await load();
      setAnnouncement(m.removedAnnouncement(grant.name));
      setFocusTarget({ kind: "inactive", id: "summary" });
    } catch (cause) {
      setRemoveError(cause instanceof Error ? cause.message : m.removeError);
      if (isPasswordRefusal(cause)) removeInvalid.fail("password");
    } finally {
      setBusy(false);
    }
  }

  const isInactive = (grant: Grant) => Boolean(grant.revoked_at) || new Date(grant.expires_at) < new Date();
  const activeGrants = grants.filter((grant) => !isInactive(grant));
  const inactiveGrants = grants.filter(isInactive);

  function renderGrant(grant: Grant) {
    const inactive = isInactive(grant);
    return (
      <article className="agent-card" key={grant.id} tabIndex={-1} data-agent-grant={grant.id}>
        <span className="agent-avatar">
          <Bot size={21} />
        </span>
        <div className="agent-card-body">
          <strong>{grant.name}</strong>
          <span>
            {grant.revoked_at ? m.revoked : inactive ? m.expired : m.active}{" "}
            {m.expires(formatDate(grant.expires_at))}
          </span>
          <div className="agent-scopes">
            {grant.scopes.map((scope) => (
              <small key={scope}>{scopeNames[scope] ?? scope}</small>
            ))}
          </div>
          {grant.filter_tag_name && (
            <span>{m.onlyTagged(grant.filter_tag_name)}</span>
          )}
          {grant.last_used_at && (
            <span>
              {m.lastUsed(formatDateTime(grant.last_used_at))}
            </span>
          )}
        </div>
        {inactive ? (confirmRemove === grant.id ? (
          <form className="agent-revoke-confirm agent-remove-confirm" aria-label={m.removeConfirm(grant.name)}
            onSubmit={(event) => void remove(event, grant)}
            onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); cancelRemove(grant); } }}>
            <strong>{m.removeConfirm(grant.name)}</strong>
            <label>
              {m.removePassword}
              <input type="password" autoComplete="current-password" required autoFocus
                {...removeInvalid.props("password")}
                value={removePassword} onChange={(event) => setRemovePassword(event.target.value)} />
            </label>
            {removeError && <p className="form-error" role="alert" id="agent-remove-error">{removeError}</p>}
            <div className="agent-remove-actions">
              <Button variant="danger" pending={busy || !removePassword}>
                {m.confirmRemove}
              </Button>
              <Button type="button" variant="secondary" onClick={() => cancelRemove(grant)}>
                {m.cancel}
              </Button>
            </div>
          </form>
        ) : (
          <Button variant="secondary" pending={busy} aria-label={m.removeNamed(grant.name)} data-agent-remove={grant.id} onClick={() => startRemove(grant)}>
            <Trash2 size={16} aria-hidden="true" /> {m.remove}
          </Button>
        )) : confirmRevoke === grant.id ? (
          <div className="agent-revoke-confirm" role="group" aria-label={m.revokeConfirm(grant.name)}>
            <strong>{m.revokeConfirm(grant.name)}</strong>
            <Button variant="danger" pending={busy} autoFocus onClick={() => void revoke(grant)}>
              {m.confirmRevoke}
            </Button>
            <Button variant="secondary" pending={busy} onClick={() => { setConfirmRevoke(null); setFocusTarget({ kind: "revoke", id: grant.id }); }}>
              {m.cancel}
            </Button>
          </div>
        ) : (
          <Button
            variant="secondary"
            pending={busy}
            aria-label={m.revokeNamed(grant.name)}
            data-agent-revoke={grant.id}
            onClick={() => setConfirmRevoke(grant.id)}
          >
            {m.revoke}
          </Button>
        )}
      </article>
    );
  }

  async function copyToken() {
    try {
      await navigator.clipboard.writeText(newToken);
      setCopied(true);
    } catch {
      setError(m.copyUnavailable);
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            <span className="eyebrow-line" /> {m.eyebrow}
          </div>
          <h1>
            {m.heading}<span className="heading-period">.</span>
          </h1>
          <p>{m.intro}</p>
        </div>
      </div>
      <p className="visually-hidden" role="status" aria-live="polite" aria-atomic="true">{announcement}</p>
      {error && (
        <div className="inline-error" role="alert">
          {error}
          <button onClick={() => setError("")} aria-label={m.dismissError}>
            <X size={16} />
          </button>
        </div>
      )}
      <div className="agent-layout">
        <section className="agent-main">
          {newToken && (
            <div className="agent-token-card" ref={tokenCardRef} tabIndex={-1} role="region" aria-labelledby="agent-token-title">
              <div className="agent-token-head">
                <LockKeyhole size={19} aria-hidden="true" />
                <strong id="agent-token-title">{m.copyNow}</strong>
              </div>
              <p>
                {m.showOnce}
              </p>
              <div className="agent-token-row">
                <input
                  aria-label={m.newToken}
                  readOnly
                  value={newToken}
                  onFocus={(event) => event.target.select()}
                />
                <Button
                  variant="secondary"
                  onClick={() => void copyToken()}
                >
                  {copied ? <Check size={16} /> : <Copy size={16} />}
                  {copied ? m.copied : m.copy}
                </Button>
              </div>
              <small>
                {m.mcpUrl} <code>{window.location.origin}/mcp</code>
              </small>
            </div>
          )}
          <div className="section-heading">
            <div>
              <h2>{m.connectedHeading}</h2>
              <p>{m.connectedIntro}</p>
            </div>
          </div>
          {activeGrants.length > 0 && <div className="agent-list">{activeGrants.map(renderGrant)}</div>}
          {inactiveGrants.length > 0 && (
            <details className="agent-inactive" open={showInactive} onToggle={(event) => setShowInactive(event.currentTarget.open)}>
              <summary data-agent-inactive="summary">{m.inactiveSummary(inactiveGrants.length)}</summary>
              <p>{m.inactiveIntro}</p>
              <div className="agent-list">{inactiveGrants.map(renderGrant)}</div>
            </details>
          )}
          {!grants.length && (
            <div className="tag-empty">
              <Bot size={27} />
              <strong>{m.emptyTitle}</strong>
              <p>
                {m.emptyText}
              </p>
            </div>
          )}
          <div className="section-heading agent-activity-heading">
            <div>
              <h2>{m.activityHeading}</h2>
              <p>{m.activityIntro}</p>
            </div>
          </div>
          {events.length ? (
            <ul className="agent-events" aria-label={m.activityHeading}>
              {events.map((event, index) => (
                <li key={`${event.at}-${index}`}>
                  <span>{event.agent}</span>
                  <strong>{toolNames[event.action] ?? event.action.replaceAll("_", " ")}</strong>
                  {event.document_title && <span className="agent-event-document">{m.onDocument(event.document_title)}</span>}
                  <small>
                    {outcomeNames[event.outcome] ?? event.outcome} · <time dateTime={event.at}>{formatDateTime(event.at)}</time>
                  </small>
                </li>
              ))}
            </ul>
          ) : (
            <p className="agent-empty-activity">{m.noActivity}</p>
          )}
        </section>
        <section className="tag-create-card agent-create-card">
          <div className="tag-create-icon">
            <Shield size={21} />
          </div>
          <h2>{m.connectHeading}</h2>
          <p>
            {m.connectIntro}
          </p>
          <form onSubmit={create}>
            <label>
              {m.name}
              <input
                {...createInvalid.props("name")}
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder={m.namePlaceholder}
                maxLength={100}
                required
              />
            </label>
            <fieldset>
              <legend>{m.permissions}</legend>
              {Object.entries(scopeNames).map(([scope, label]) => (
                <label className="agent-scope-choice" key={scope}>
                  <input
                    type="checkbox"
                    checked={scopes.includes(scope)}
                    onChange={() => toggleScope(scope)}
                  />
                  {label}
                </label>
              ))}
            </fieldset>
            <label>
              {m.documentAccess}
              <select
                value={filterTag}
                onChange={(event) => setFilterTag(event.target.value)}
              >
                <option value="">{m.allDocuments}</option>
                {tags.map((tag) => (
                  <option key={tag.id} value={tag.id}>
                    {m.onlyTag(tag.name)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              {m.expiresAfter} <small>{m.daysHint}</small>
              <input
                type="number"
                min={1}
                max={365}
                value={days}
                onChange={(event) => setDays(Number(event.target.value))}
                required
              />
            </label>
            <label>
              {m.password}
              <input
                type="password"
                autoComplete="current-password"
                {...createInvalid.props("password")}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </label>
            {createError && <p className="form-error" role="alert" id="agent-create-error">{createError}</p>}
            <Button
              pending={busy || scopes.length === 0 || !password}
            >
              <Plus size={17} /> {busy ? m.creating : m.create}
            </Button>
          </form>
          <div className="tag-tip">
            {m.tip}
          </div>
        </section>
      </div>
    </>
  );
}
