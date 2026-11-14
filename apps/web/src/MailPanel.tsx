import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, Filter, Inbox, Mail, Plus, RefreshCw, X } from "lucide-react";
import { FilingItem, request, Tag } from "./api";
import { Button } from "./ui";

type Account = {
  id: string;
  name: string;
  host: string;
  port: number;
  security: "ssl" | "starttls" | "none";
  username: string;
  auth: "password" | "oauth";
  oauth_provider: string;
  enabled: boolean;
  checking: boolean;
  last_checked_at: string | null;
  last_error: string;
  last_imported: number;
};
type Rule = {
  id: string;
  account_id: string;
  name: string;
  enabled: boolean;
  folder: string;
  filter_from: string;
  filter_subject: string;
  filter_body: string;
  filter_attachment: string;
  include_inline: boolean;
  consume: "attachments" | "message" | "both";
  order: number;
  max_age_days: number;
  after: "mark_read" | "flag" | "move" | "nothing";
  move_to: string;
  title_from: "subject" | "filename";
  tag_ids: string[];
  correspondent_id: string | null;
  document_type_id: string | null;
};
type Processed = {
  id: number;
  rule: string;
  account: string;
  subject: string;
  sender: string;
  status: "imported" | "no_match" | "skipped" | "failed";
  detail: string;
  documents: number;
  processed_at: string;
};
type Overview = { accounts: Account[]; rules: Rule[]; recent: Processed[]; oauth_providers: { id: string; label: string }[] };

const afterLabels: Record<Rule["after"], string> = {
  mark_read: "Mark as read",
  flag: "Flag it",
  move: "Move to a folder",
  nothing: "Leave it unchanged",
};
const emptyAccount = { name: "", host: "", port: 993, security: "ssl" as Account["security"], username: "", password: "" };
const emptyRule = {
  account_id: "", name: "", folder: "INBOX", filter_from: "", filter_subject: "", filter_body: "", filter_attachment: "", include_inline: false, consume: "attachments" as Rule["consume"], order: 0,
  max_age_days: 30, after: "mark_read" as Rule["after"], move_to: "", title_from: "subject" as Rule["title_from"],
  tag_ids: [] as string[], correspondent_id: "", document_type_id: "",
};

const oauthErrors: Record<string, string> = {
  signin: "Sign in to Ripiano, then connect the mailbox again.",
  cancelled: "Sign-in was cancelled. Nothing was connected.",
  expired: "The sign-in took too long or was not started here. Start again.",
  other_user: "That sign-in was started by another Ripiano account.",
  not_configured: "This provider is not set up on this server.",
  offline: "The provider did not allow ongoing access. Try again and accept all permissions.",
  address: "The provider did not share the mailbox address. Try again.",
  provider: "The provider refused the sign-in. Try again later.",
};

function message(cause: unknown, fallback: string) {
  return cause instanceof Error ? cause.message : fallback;
}

export default function MailPanel({ notice }: { notice: { kind: "ok" | "error"; text: string } | null }) {
  const [data, setData] = useState<Overview | null>(null);
  const [tags, setTags] = useState<Tag[]>([]);
  const [senders, setSenders] = useState<FilingItem[]>([]);
  const [types, setTypes] = useState<FilingItem[]>([]);
  const [account, setAccount] = useState(emptyAccount);
  const [editingAccount, setEditingAccount] = useState<string | null>(null);
  const [rule, setRule] = useState(emptyRule);
  const [editingRule, setEditingRule] = useState<string | null>(null);
  const [folders, setFolders] = useState<Record<string, string[]>>({});
  const [results, setResults] = useState<Record<string, string>>({});
  const [confirming, setConfirming] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(notice?.kind === "error" ? oauthErrors[notice.text] ?? oauthErrors.provider : "");
  const [status, setStatus] = useState(notice?.kind === "ok" ? "Mailbox connected. Add a rule to start importing." : "");
  const accountFormRef = useRef<HTMLFormElement>(null);
  const ruleFormRef = useRef<HTMLFormElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  const load = useCallback(async () => {
    try {
      const [overview, tagResponse, senderResponse, typeResponse] = await Promise.all([
        request<Overview>("/api/mail"),
        request<{ tags: Tag[] }>("/api/tags"),
        request<{ correspondents: FilingItem[] }>("/api/correspondents"),
        request<{ document_types: FilingItem[] }>("/api/document-types"),
      ]);
      setData(overview);
      setTags(tagResponse.tags);
      setSenders(senderResponse.correspondents);
      setTypes(typeResponse.document_types);
    } catch (cause) {
      setError(message(cause, "Could not load email settings"));
    }
  }, []);
  useEffect(() => { void load(); }, [load]);
  // Account id → last_checked_at when "Check now" was pressed; refresh until it changes.
  const [waiting, setWaiting] = useState<Record<string, string | null>>({});
  useEffect(() => {
    if (Object.keys(waiting).length === 0) return;
    // Stop waiting if the worker never picks the check up; the result appears on a later visit.
    const timer = window.setTimeout(() => {
      setWaiting({});
      setStatus("The check is queued and will finish in the background.");
    }, 60000);
    return () => window.clearTimeout(timer);
  }, [waiting]);
  useEffect(() => {
    if (!data) return;
    setWaiting((value) => {
      const next = Object.fromEntries(Object.entries(value).filter(([id, before]) => {
        const item = data.accounts.find((account) => account.id === id);
        return item && (item.checking || item.last_checked_at === before);
      }));
      return Object.keys(next).length === Object.keys(value).length ? value : next;
    });
  }, [data]);
  useEffect(() => {
    if (!data?.accounts.some((item) => item.checking) && Object.keys(waiting).length === 0) return;
    const timer = window.setTimeout(() => void load(), 2000);
    return () => window.clearTimeout(timer);
  }, [data, load, waiting]);

  async function run(action: () => Promise<void>, fallback: string) {
    setBusy(true);
    setError("");
    setStatus("");
    try {
      await action();
    } catch (cause) {
      setError(message(cause, fallback));
    } finally {
      setBusy(false);
    }
  }

  function saveAccount(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      const { password, ...rest } = account;
      const body = JSON.stringify(password ? account : rest);
      const saved = editingAccount
        ? await request<Account>(`/api/mail/accounts/${editingAccount}`, { method: "PATCH", body })
        : await request<Account>("/api/mail/accounts", { method: "POST", body });
      setAccount(emptyAccount);
      setEditingAccount(null);
      await load();
      await test(saved);
    }, "Could not save the mailbox");
  }

  async function test(item: Account) {
    const result = await request<{ ok: boolean; folders?: string[]; error?: string }>(`/api/mail/accounts/${item.id}/test`, { method: "POST" });
    if (result.ok && result.folders) {
      setFolders((value) => ({ ...value, [item.id]: result.folders! }));
      setResults((value) => ({ ...value, [item.id]: `Connected · ${result.folders!.length} folder${result.folders!.length === 1 ? "" : "s"}` }));
      setStatus(`${item.name} is connected. ${result.folders.length} folder${result.folders.length === 1 ? "" : "s"} found.`);
    } else {
      setResults((value) => ({ ...value, [item.id]: result.error ?? "Could not connect" }));
      setError(`${item.name}: ${result.error ?? "Could not connect"}`);
    }
  }

  function startOAuth(provider: string) {
    void run(async () => {
      const { url } = await request<{ url: string }>(`/api/mail/oauth/${provider}/start`, { method: "POST" });
      window.location.assign(url);
    }, "Could not start sign-in");
  }

  function editAccount(item: Account) {
    setEditingAccount(item.id);
    setAccount({ name: item.name, host: item.host, port: item.port, security: item.security, username: item.username, password: "" });
    requestAnimationFrame(() => {
      accountFormRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      accountFormRef.current?.querySelector<HTMLInputElement>("input")?.focus({ preventScroll: true });
    });
  }

  function saveRule(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      const body = JSON.stringify({ ...rule, correspondent_id: rule.correspondent_id || null, document_type_id: rule.document_type_id || null });
      if (editingRule) await request(`/api/mail/rules/${editingRule}`, { method: "PATCH", body });
      else await request("/api/mail/rules", { method: "POST", body });
      setStatus(`Rule “${rule.name}” saved. New matching mail is checked every few minutes.`);
      setRule(emptyRule);
      setEditingRule(null);
      await load();
    }, "Could not save the rule");
  }

  function editRule(item: Rule) {
    setEditingRule(item.id);
    setRule({ ...item, correspondent_id: item.correspondent_id ?? "", document_type_id: item.document_type_id ?? "" });
    requestAnimationFrame(() => {
      ruleFormRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      ruleFormRef.current?.querySelector<HTMLInputElement>("input")?.focus({ preventScroll: true });
    });
  }

  function remove(kind: "accounts" | "rules", id: string) {
    void run(async () => {
      await request(`/api/mail/${kind}/${id}`, { method: "DELETE" });
      setConfirming(null);
      setStatus(kind === "accounts" ? "Mailbox removed. Imported documents stay in your archive." : "Rule removed.");
      headingRef.current?.focus();
      if (editingRule === id) { setEditingRule(null); setRule(emptyRule); }
      if (editingAccount === id) { setEditingAccount(null); setAccount(emptyAccount); }
      await load();
    }, "Could not remove it");
  }

  function check(item: Account) {
    void run(async () => {
      await request(`/api/mail/accounts/${item.id}/check`, { method: "POST" });
      setWaiting((value) => ({ ...value, [item.id]: item.last_checked_at }));
      setStatus(`Checking ${item.name}…`);
      await load();
    }, "Could not start the check");
  }

  function toggleAccount(item: Account) {
    void run(async () => {
      await request(`/api/mail/accounts/${item.id}`, { method: "PATCH", body: JSON.stringify({ enabled: !item.enabled }) });
      setStatus(item.enabled ? `${item.name} paused. Its rules will not run.` : `${item.name} resumed.`);
      await load();
    }, "Could not update the mailbox");
  }

  function toggleRule(item: Rule) {
    void run(async () => {
      await request(`/api/mail/rules/${item.id}`, { method: "PATCH", body: JSON.stringify({ enabled: !item.enabled }) });
      await load();
    }, "Could not update the rule");
  }

  const accounts = data?.accounts ?? [];
  const accountName = (id: string) => accounts.find((item) => item.id === id)?.name ?? "Mailbox";
  const ruleFolders = folders[rule.account_id] ?? [];

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> INTEGRATIONS</div>
          <h1 ref={headingRef} tabIndex={-1}>Email<span className="heading-period">.</span></h1>
          <p>Bring attachments from your mailboxes into the archive automatically.</p>
        </div>
      </div>
      {error && (
        <div className="inline-error" role="alert">
          {error}
          <button onClick={() => setError("")} aria-label="Dismiss error"><X size={16} /></button>
        </div>
      )}
      {status && <p className="bulk-notice" role="status">{status}</p>}
      <div className="agent-layout">
        <section className="agent-main">
          <div className="section-heading">
            <div>
              <h2>Mailboxes</h2>
              <p>Ripiano reads matching mail and never deletes it.</p>
            </div>
          </div>
          {accounts.length ? (
            <div className="agent-list">
              {accounts.map((item) => (
                <article className="agent-card mail-card" key={item.id}>
                  <span className="agent-avatar"><Mail size={21} aria-hidden="true" /></span>
                  <div className="agent-card-body">
                    <strong>{item.name}{!item.enabled && " · Paused"}</strong>
                    <span>{item.username} · {item.auth === "oauth" ? `Signed in with ${item.oauth_provider === "gmail" ? "Google" : "Microsoft"}` : `${item.host}:${item.port}`}</span>
                    <span className={item.last_error ? "mail-error" : undefined}>
                      {item.checking || item.id in waiting ? "Checking now…" : item.last_error ? item.last_error
                        : item.last_checked_at ? `Checked ${new Date(item.last_checked_at).toLocaleString()} · ${item.last_imported} new` : "Not checked yet"}
                    </span>
                    {results[item.id] && <span>{results[item.id]}</span>}
                  </div>
                  <div className="mail-actions">
                    {confirming === item.id ? (
                      <>
                        <span>Remove this mailbox and its rules?</span>
                        <Button variant="danger" disabled={busy} onClick={() => remove("accounts", item.id)}>Remove</Button>
                        <Button variant="secondary" autoFocus onClick={() => setConfirming(null)}>Keep</Button>
                      </>
                    ) : (
                      <>
                        <Button variant="secondary" disabled={busy} onClick={() => void run(() => test(item), "Could not test the mailbox")}>Test</Button>
                        <Button variant="secondary" disabled={busy || item.checking || item.id in waiting || !item.enabled} onClick={() => check(item)}><RefreshCw size={15} aria-hidden="true" /> Check now</Button>
                        <Button variant="secondary" disabled={busy} onClick={() => toggleAccount(item)}>{item.enabled ? "Pause" : "Resume"}</Button>
                        {item.auth === "password" && <Button variant="secondary" onClick={() => editAccount(item)}>Edit</Button>}
                        <Button variant="secondary" aria-label={`Remove mailbox ${item.name}`} onClick={() => setConfirming(item.id)}>Remove</Button>
                      </>
                    )}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="tag-empty">
              <Mail size={27} aria-hidden="true" />
              <strong>No mailbox connected</strong>
              <p>Optional. Connect one if bills or receipts arrive by email.</p>
            </div>
          )}

          <div className="section-heading agent-activity-heading">
            <div>
              <h2>Rules</h2>
              <p>Rules run in order. Each message is handled once per rule; editing a rule’s filters looks again at mail it skipped.</p>
            </div>
          </div>
          {data?.rules.length ? (
            <div className="agent-list">
              {data.rules.map((item) => (
                <article className="agent-card mail-card" key={item.id}>
                  <span className="agent-avatar"><Filter size={21} aria-hidden="true" /></span>
                  <div className="agent-card-body">
                    <strong>{item.name}{!item.enabled && " · Paused"}</strong>
                    <span>{accountName(item.account_id)} · {item.folder} · last {item.max_age_days} days</span>
                    <span>
                      {[item.filter_from && `from “${item.filter_from}”`, item.filter_subject && `subject “${item.filter_subject}”`,
                        item.filter_body && `text “${item.filter_body}”`, item.filter_attachment && `files “${item.filter_attachment}”`]
                        .filter(Boolean).join(" · ") || "All messages with attachments"}
                    </span>
                    <span>Imports {item.consume === "attachments" ? "attachments" : item.consume === "message" ? "the email itself" : "the email and attachments"} · then: {afterLabels[item.after].toLowerCase()}{item.after === "move" ? ` “${item.move_to}”` : ""}</span>
                  </div>
                  <div className="mail-actions">
                    {confirming === item.id ? (
                      <>
                        <span>Remove this rule?</span>
                        <Button variant="danger" disabled={busy} onClick={() => remove("rules", item.id)}>Remove</Button>
                        <Button variant="secondary" autoFocus onClick={() => setConfirming(null)}>Keep</Button>
                      </>
                    ) : (
                      <>
                        <Button variant="secondary" disabled={busy} onClick={() => toggleRule(item)}>{item.enabled ? "Pause" : "Resume"}</Button>
                        <Button variant="secondary" onClick={() => editRule(item)}>Edit</Button>
                        <Button variant="secondary" aria-label={`Remove rule ${item.name}`} onClick={() => setConfirming(item.id)}>Remove</Button>
                      </>
                    )}
                  </div>
                </article>
              ))}
            </div>
          ) : <p className="agent-empty-activity">{accounts.length ? "Add a rule to start importing." : "Connect a mailbox first."}</p>}

          <div className="section-heading agent-activity-heading">
            <div>
              <h2>Recent mail</h2>
              <p>What each rule did with the last messages it read.</p>
            </div>
          </div>
          {data?.recent.length ? (
            <div className="agent-events">
              {data.recent.map((item) => (
                <div key={item.id}>
                  <span>{item.rule} · {item.sender || item.account}</span>
                  <strong>{item.subject || "(no subject)"}</strong>
                  <small>
                    {item.status === "imported" ? `${item.documents} document${item.documents === 1 ? "" : "s"} added`
                      : item.status === "no_match" ? item.detail || "Nothing to import" : item.detail || "Skipped"}
                    {" · "}{new Date(item.processed_at).toLocaleString()}
                  </small>
                </div>
              ))}
            </div>
          ) : <p className="agent-empty-activity">No mail handled yet.</p>}
        </section>

        <div className="mail-side">
          <section className="tag-create-card agent-create-card">
            <div className="tag-create-icon"><Inbox size={21} aria-hidden="true" /></div>
            <h2>{editingAccount ? "Edit mailbox" : "Connect a mailbox"}</h2>
            {!editingAccount && data?.oauth_providers.length ? (
              <div className="mail-oauth">
                {data.oauth_providers.map((provider) => (
                  <Button key={provider.id} variant="secondary" disabled={busy} onClick={() => startOAuth(provider.id)}>
                    Sign in with {provider.id === "gmail" ? "Google" : "Microsoft"}
                  </Button>
                ))}
                <small>Or use an IMAP app password:</small>
              </div>
            ) : <p>Use your provider’s IMAP settings. An app password is safer than your main password.</p>}
            <form ref={accountFormRef} onSubmit={saveAccount} aria-label="Mailbox settings">
              <label>Name<input value={account.name} onChange={(event) => setAccount({ ...account, name: event.target.value })} placeholder="e.g. Home mail" maxLength={100} required /></label>
              <label>IMAP server<input value={account.host} onChange={(event) => setAccount({ ...account, host: event.target.value })} placeholder="imap.example.com" maxLength={255} required autoCapitalize="none" spellCheck={false} /></label>
              <div className="mail-row">
                <label>Security
                  <select value={account.security} onChange={(event) => {
                    const security = event.target.value as Account["security"];
                    setAccount({ ...account, security, port: security === "ssl" ? 993 : 143 });
                  }}>
                    <option value="ssl">SSL/TLS</option>
                    <option value="starttls">STARTTLS</option>
                    <option value="none">None (local only)</option>
                  </select>
                </label>
                <label>Port<input type="number" min={1} max={65535} value={account.port} onChange={(event) => setAccount({ ...account, port: Number(event.target.value) })} required /></label>
              </div>
              {account.security === "none" && (
                <p className="mail-warning" role="note">Without security, the password travels unencrypted. Use this only for a mail server on your own network.</p>
              )}
              <label>Username<input value={account.username} onChange={(event) => setAccount({ ...account, username: event.target.value })} autoComplete="off" autoCapitalize="none" spellCheck={false} maxLength={255} required /></label>
              <label>Password {editingAccount && <small>Leave empty to keep the saved one</small>}
                <input type="password" value={account.password} onChange={(event) => setAccount({ ...account, password: event.target.value })} autoComplete="new-password" maxLength={500} required={!editingAccount} />
              </label>
              <Button disabled={busy}><CheckCircle2 size={17} aria-hidden="true" /> {editingAccount ? "Save and test" : "Connect and test"}</Button>
              {editingAccount && <Button type="button" variant="secondary" onClick={() => { setEditingAccount(null); setAccount(emptyAccount); }}>Cancel</Button>}
            </form>
            <div className="tag-tip">Passwords are encrypted on your NAS and are never shown again.</div>
          </section>

          {accounts.length > 0 && (
            <section className="tag-create-card agent-create-card">
              <div className="tag-create-icon"><Filter size={21} aria-hidden="true" /></div>
              <h2>{editingRule ? "Edit rule" : "Add a rule"}</h2>
              <p>Import matching attachments, the email itself, or both.</p>
              <form ref={ruleFormRef} onSubmit={saveRule} aria-label="Mail rule">
                <label>Rule name<input value={rule.name} onChange={(event) => setRule({ ...rule, name: event.target.value })} placeholder="e.g. Utility bills" maxLength={100} required /></label>
                <label>Mailbox
                  <select value={rule.account_id} onChange={(event) => setRule({ ...rule, account_id: event.target.value })} required>
                    <option value="">Choose a mailbox</option>
                    {accounts.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label>Folder {ruleFolders.length === 0 && <small>Press Test on the mailbox to list folders</small>}
                  <input list="mail-folders" value={rule.folder} onChange={(event) => setRule({ ...rule, folder: event.target.value })} maxLength={200} required autoCapitalize="none" />
                </label>
                <datalist id="mail-folders">{ruleFolders.map((folder) => <option key={folder} value={folder} />)}</datalist>
                <label>What to import
                  <select value={rule.consume} onChange={(event) => setRule({ ...rule, consume: event.target.value as Rule["consume"] })}>
                    <option value="attachments">Attachments</option>
                    <option value="message">The email itself</option>
                    <option value="both">The email and its attachments</option>
                  </select>
                </label>
                <fieldset>
                  <legend>Only messages where <small>All optional</small></legend>
                  <label>Sender contains<input value={rule.filter_from} onChange={(event) => setRule({ ...rule, filter_from: event.target.value })} placeholder="e.g. @acme-energy.it" maxLength={200} /></label>
                  <label>Subject contains<input value={rule.filter_subject} onChange={(event) => setRule({ ...rule, filter_subject: event.target.value })} placeholder="e.g. invoice" maxLength={200} /></label>
                  <label>Text contains<input value={rule.filter_body} onChange={(event) => setRule({ ...rule, filter_body: event.target.value })} maxLength={200} /></label>
                  <label>File name matches<input value={rule.filter_attachment} onChange={(event) => setRule({ ...rule, filter_attachment: event.target.value })} placeholder="e.g. *.pdf or fattura*" maxLength={200} /></label>
                  <label className="agent-scope-choice">
                    <input type="checkbox" checked={rule.include_inline} onChange={(event) => setRule({ ...rule, include_inline: event.target.checked })} />
                    Also import pictures shown inside the email
                  </label>
                  <label>Received in the last <small>Days</small><input type="number" min={1} max={3650} value={rule.max_age_days} onChange={(event) => setRule({ ...rule, max_age_days: Number(event.target.value) })} required /></label>
                </fieldset>
                <label>Order <small>Lower numbers run first</small>
                  <input type="number" min={0} max={10000} value={rule.order} onChange={(event) => setRule({ ...rule, order: Number(event.target.value) })} required />
                </label>
                <label>After importing
                  <select value={rule.after} onChange={(event) => setRule({ ...rule, after: event.target.value as Rule["after"] })}>
                    {Object.entries(afterLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </label>
                {rule.after === "move" && (
                  <label>Move to folder<input list="mail-folders" value={rule.move_to} onChange={(event) => setRule({ ...rule, move_to: event.target.value })} maxLength={200} required /></label>
                )}
                <label>Document title
                  <select value={rule.title_from} onChange={(event) => setRule({ ...rule, title_from: event.target.value as Rule["title_from"] })}>
                    <option value="subject">Email subject</option>
                    <option value="filename">Attachment name</option>
                  </select>
                </label>
                <label>Sender
                  <select value={rule.correspondent_id} onChange={(event) => setRule({ ...rule, correspondent_id: event.target.value })}>
                    <option value="">Don’t set</option>
                    {senders.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label>Document type
                  <select value={rule.document_type_id} onChange={(event) => setRule({ ...rule, document_type_id: event.target.value })}>
                    <option value="">Don’t set</option>
                    {types.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                {tags.length > 0 && (
                  <fieldset className="mail-tags">
                    <legend>Add tags</legend>
                    {tags.map((tag) => (
                      <label className="agent-scope-choice" key={tag.id}>
                        <input type="checkbox" checked={rule.tag_ids.includes(tag.id)} onChange={() => setRule({
                          ...rule, tag_ids: rule.tag_ids.includes(tag.id) ? rule.tag_ids.filter((id) => id !== tag.id) : [...rule.tag_ids, tag.id],
                        })} />
                        {tag.name}
                      </label>
                    ))}
                  </fieldset>
                )}
                <Button disabled={busy}><Plus size={17} aria-hidden="true" /> {editingRule ? "Save rule" : "Add rule"}</Button>
                {editingRule && <Button type="button" variant="secondary" onClick={() => { setEditingRule(null); setRule(emptyRule); }}>Cancel</Button>}
              </form>
            </section>
          )}
        </div>
      </div>
    </>
  );
}
