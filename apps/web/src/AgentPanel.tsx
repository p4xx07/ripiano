import { FormEvent, useCallback, useEffect, useState } from "react";
import { Bot, Check, Copy, LockKeyhole, Plus, Shield, X } from "lucide-react";
import { formatDate, formatDateTime, request, Tag } from "./api";
import { Button } from "./ui";
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
  const [grants, setGrants] = useState<Grant[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<string[]>(["documents:search"]);
  const [filterTag, setFilterTag] = useState("");
  const [days, setDays] = useState(30);
  const [newToken, setNewToken] = useState("");
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

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

  function toggleScope(scope: string) {
    setScopes((current) =>
      current.includes(scope)
        ? current.filter((item) => item !== scope)
        : [...current, scope],
    );
  }

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNewToken("");
    try {
      const grant = await request<Grant & { token: string }>("/api/agents", {
        method: "POST",
        body: JSON.stringify({
          name,
          scopes,
          filter_tag_id: filterTag || null,
          expires_in_days: days,
        }),
      });
      setNewToken(grant.token);
      setName("");
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : m.createError,
      );
    } finally {
      setBusy(false);
    }
  }

  async function revoke(grant: Grant) {
    setBusy(true);
    setError("");
    try {
      await request(`/api/agents/${grant.id}`, { method: "DELETE" });
      if (newToken) setNewToken("");
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : m.revokeError,
      );
    } finally {
      setBusy(false);
    }
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
            <div className="agent-token-card">
              <div className="agent-token-head">
                <LockKeyhole size={19} />
                <strong>{m.copyNow}</strong>
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
          {grants.length ? (
            <div className="agent-list">
              {grants.map((grant) => (
                <article className="agent-card" key={grant.id}>
                  <span className="agent-avatar">
                    <Bot size={21} />
                  </span>
                  <div className="agent-card-body">
                    <strong>{grant.name}</strong>
                    <span>
                      {grant.revoked_at
                        ? m.revoked
                        : new Date(grant.expires_at) < new Date()
                          ? m.expired
                          : m.active}{" "}
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
                  {!grant.revoked_at && (
                    <Button
                      variant="secondary"
                      disabled={busy}
                      onClick={() => void revoke(grant)}
                    >
                      {m.revoke}
                    </Button>
                  )}
                </article>
              ))}
            </div>
          ) : (
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
            <div className="agent-events">
              {events.map((event, index) => (
                <div key={`${event.at}-${index}`}>
                  <span>{event.agent}</span>
                  <strong>{event.action.replaceAll("_", " ")}</strong>
                  <small>
                    {event.outcome} · {formatDateTime(event.at)}
                  </small>
                </div>
              ))}
            </div>
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
            <Button
              disabled={busy || scopes.length === 0}
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
