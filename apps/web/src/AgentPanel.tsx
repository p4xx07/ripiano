import { FormEvent, useCallback, useEffect, useState } from "react";
import { Bot, Check, Copy, LockKeyhole, Plus, Shield, X } from "lucide-react";
import { request, Tag } from "./api";

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

const scopeNames: Record<string, string> = {
  "documents:search": "Find document titles and tags",
  "documents:text": "Read OCR text",
  "documents:tag": "Add or remove tags",
};

export default function AgentPanel() {
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
        cause instanceof Error ? cause.message : "Could not load agents",
      );
    }
  }, []);
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
        cause instanceof Error ? cause.message : "Could not create agent",
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
        cause instanceof Error ? cause.message : "Could not revoke agent",
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
      setError("Copy is unavailable here. Select and copy the token manually.");
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            <span className="eyebrow-line" /> CONTROLLED ACCESS
          </div>
          <h1>
            Agents<span className="heading-period">.</span>
          </h1>
          <p>Give each local or cloud agent its own limited access.</p>
        </div>
      </div>
      {error && (
        <div className="inline-error" role="alert">
          {error}
          <button onClick={() => setError("")} aria-label="Dismiss error">
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
                <strong>Copy this token now</strong>
              </div>
              <p>
                It will not be shown again. Give it only to the agent you named.
              </p>
              <div className="agent-token-row">
                <input
                  aria-label="New agent token"
                  readOnly
                  value={newToken}
                  onFocus={(event) => event.target.select()}
                />
                <button
                  className="button button-secondary"
                  onClick={() => void copyToken()}
                >
                  {copied ? <Check size={16} /> : <Copy size={16} />}
                  {copied ? "Copied" : "Copy"}
                </button>
              </div>
              <small>
                MCP URL: <code>{window.location.origin}/mcp</code>
              </small>
            </div>
          )}
          <div className="section-heading">
            <div>
              <h2>Connected agents</h2>
              <p>Each token has its own permissions and expiry.</p>
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
                        ? "Revoked"
                        : new Date(grant.expires_at) < new Date()
                          ? "Expired"
                          : "Active"}{" "}
                      · Expires{" "}
                      {new Date(grant.expires_at).toLocaleDateString()}
                    </span>
                    <div className="agent-scopes">
                      {grant.scopes.map((scope) => (
                        <small key={scope}>{scopeNames[scope] ?? scope}</small>
                      ))}
                    </div>
                    {grant.filter_tag_name && (
                      <span>Only documents tagged {grant.filter_tag_name}</span>
                    )}
                    {grant.last_used_at && (
                      <span>
                        Last used{" "}
                        {new Date(grant.last_used_at).toLocaleString()}
                      </span>
                    )}
                  </div>
                  {!grant.revoked_at && (
                    <button
                      className="button button-secondary"
                      disabled={busy}
                      onClick={() => void revoke(grant)}
                    >
                      Revoke
                    </button>
                  )}
                </article>
              ))}
            </div>
          ) : (
            <div className="tag-empty">
              <Bot size={27} />
              <strong>No agents connected</strong>
              <p>
                Your archive works without one. Add an agent only when you need
                it.
              </p>
            </div>
          )}
          <div className="section-heading agent-activity-heading">
            <div>
              <h2>Recent activity</h2>
              <p>Actions are logged without storing document text here.</p>
            </div>
          </div>
          {events.length ? (
            <div className="agent-events">
              {events.map((event, index) => (
                <div key={`${event.at}-${index}`}>
                  <span>{event.agent}</span>
                  <strong>{event.action.replaceAll("_", " ")}</strong>
                  <small>
                    {event.outcome} · {new Date(event.at).toLocaleString()}
                  </small>
                </div>
              ))}
            </div>
          ) : (
            <p className="agent-empty-activity">No agent activity yet.</p>
          )}
        </section>
        <section className="tag-create-card agent-create-card">
          <div className="tag-create-icon">
            <Shield size={21} />
          </div>
          <h2>Connect an agent</h2>
          <p>
            Sign in here as the owner, then create a separate token for the
            agent. Never give it your password.
          </p>
          <form onSubmit={create}>
            <label>
              Name
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. Local Mac classifier"
                maxLength={100}
                required
              />
            </label>
            <fieldset>
              <legend>Permissions</legend>
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
              Document access
              <select
                value={filterTag}
                onChange={(event) => setFilterTag(event.target.value)}
              >
                <option value="">All your documents</option>
                {tags.map((tag) => (
                  <option key={tag.id} value={tag.id}>
                    Only “{tag.name}” documents
                  </option>
                ))}
              </select>
            </label>
            <label>
              Expires after <small>Days, 1–365</small>
              <input
                type="number"
                min={1}
                max={365}
                value={days}
                onChange={(event) => setDays(Number(event.target.value))}
                required
              />
            </label>
            <button
              className="button button-primary"
              disabled={busy || scopes.length === 0}
            >
              <Plus size={17} /> {busy ? "Creating…" : "Create agent token"}
            </button>
          </form>
          <div className="tag-tip">
            A local model keeps processing local if its computer is private. A
            cloud agent may send text it reads to its provider. Choose “Read OCR
            text” only when that is acceptable.
          </div>
        </section>
      </div>
    </>
  );
}
