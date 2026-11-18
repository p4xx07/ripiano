import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, Filter, Inbox, Mail, Plus, RefreshCw, X } from "lucide-react";
import { FilingItem, request, Tag } from "./api";
import { Button } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/MailPanel";

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

type M = typeof messages.en;
const afterLabelsFor = (m: M): Record<Rule["after"], string> => ({
  mark_read: m.afterMarkRead,
  flag: m.afterFlag,
  move: m.afterMove,
  nothing: m.afterNothing,
});
const emptyAccount = { name: "", host: "", port: 993, security: "ssl" as Account["security"], username: "", password: "" };
const emptyRule = {
  account_id: "", name: "", folder: "INBOX", filter_from: "", filter_subject: "", filter_body: "", filter_attachment: "", include_inline: false, consume: "attachments" as Rule["consume"], order: 0,
  max_age_days: 30, after: "mark_read" as Rule["after"], move_to: "", title_from: "subject" as Rule["title_from"],
  tag_ids: [] as string[], correspondent_id: "", document_type_id: "",
};

const oauthErrorsFor = (m: M): Record<string, string> => ({
  signin: m.oauthSignin,
  cancelled: m.oauthCancelled,
  expired: m.oauthExpired,
  other_user: m.oauthOtherUser,
  not_configured: m.oauthNotConfigured,
  offline: m.oauthOffline,
  address: m.oauthAddress,
  provider: m.oauthProvider,
});

function message(cause: unknown, fallback: string) {
  return cause instanceof Error ? cause.message : fallback;
}

export default function MailPanel({ notice }: { notice: { kind: "ok" | "error"; text: string } | null }) {
  const m = useMessages(messages);
  const afterLabels = afterLabelsFor(m);
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
  const [error, setError] = useState(() => {
    if (notice?.kind !== "error") return "";
    const oauthErrors = oauthErrorsFor(m);
    return oauthErrors[notice.text] ?? oauthErrors.provider;
  });
  const [status, setStatus] = useState(notice?.kind === "ok" ? m.connectedNotice : "");
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
      setError(message(cause, m.loadError));
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
      setStatus(m.checkQueued);
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
    }, m.saveMailboxError);
  }

  async function test(item: Account) {
    const result = await request<{ ok: boolean; folders?: string[]; error?: string }>(`/api/mail/accounts/${item.id}/test`, { method: "POST" });
    if (result.ok && result.folders) {
      setFolders((value) => ({ ...value, [item.id]: result.folders! }));
      setResults((value) => ({ ...value, [item.id]: m.connectedResult(result.folders!.length) }));
      setStatus(m.connectedStatus(item.name, result.folders.length));
    } else {
      setResults((value) => ({ ...value, [item.id]: result.error ?? m.couldNotConnect }));
      setError(`${item.name}: ${result.error ?? m.couldNotConnect}`);
    }
  }

  function startOAuth(provider: string) {
    void run(async () => {
      const { url } = await request<{ url: string }>(`/api/mail/oauth/${provider}/start`, { method: "POST" });
      window.location.assign(url);
    }, m.startSignInError);
  }

  function editAccount(item: Account) {
    setEditingAccount(item.id);
    setAccount({ name: item.name, host: item.host, port: item.port, security: item.security, username: item.username, password: "" });
    requestAnimationFrame(() => {
      accountFormRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      if (!accountFormRef.current?.contains(document.activeElement)) accountFormRef.current?.querySelector<HTMLInputElement>("input")?.focus({ preventScroll: true });
    });
  }

  function saveRule(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      const body = JSON.stringify({ ...rule, correspondent_id: rule.correspondent_id || null, document_type_id: rule.document_type_id || null });
      if (editingRule) await request(`/api/mail/rules/${editingRule}`, { method: "PATCH", body });
      else await request("/api/mail/rules", { method: "POST", body });
      setStatus(m.ruleSaved(rule.name));
      setRule(emptyRule);
      setEditingRule(null);
      await load();
    }, m.saveRuleError);
  }

  function editRule(item: Rule) {
    setEditingRule(item.id);
    setRule({ ...item, correspondent_id: item.correspondent_id ?? "", document_type_id: item.document_type_id ?? "" });
    requestAnimationFrame(() => {
      ruleFormRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      if (!ruleFormRef.current?.contains(document.activeElement)) ruleFormRef.current?.querySelector<HTMLInputElement>("input")?.focus({ preventScroll: true });
    });
  }

  function remove(kind: "accounts" | "rules", id: string) {
    void run(async () => {
      await request(`/api/mail/${kind}/${id}`, { method: "DELETE" });
      setConfirming(null);
      setStatus(kind === "accounts" ? m.mailboxRemoved : m.ruleRemoved);
      headingRef.current?.focus();
      if (editingRule === id) { setEditingRule(null); setRule(emptyRule); }
      if (editingAccount === id) { setEditingAccount(null); setAccount(emptyAccount); }
      await load();
    }, m.removeError);
  }

  function check(item: Account) {
    void run(async () => {
      await request(`/api/mail/accounts/${item.id}/check`, { method: "POST" });
      setWaiting((value) => ({ ...value, [item.id]: item.last_checked_at }));
      setStatus(m.checking(item.name));
      await load();
    }, m.checkError);
  }

  function toggleAccount(item: Account) {
    void run(async () => {
      await request(`/api/mail/accounts/${item.id}`, { method: "PATCH", body: JSON.stringify({ enabled: !item.enabled }) });
      setStatus(item.enabled ? m.accountPaused(item.name) : m.accountResumed(item.name));
      await load();
    }, m.updateMailboxError);
  }

  function toggleRule(item: Rule) {
    void run(async () => {
      await request(`/api/mail/rules/${item.id}`, { method: "PATCH", body: JSON.stringify({ enabled: !item.enabled }) });
      await load();
    }, m.updateRuleError);
  }

  const accounts = data?.accounts ?? [];
  const accountName = (id: string) => accounts.find((item) => item.id === id)?.name ?? m.mailboxFallback;
  const ruleFolders = folders[rule.account_id] ?? [];

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> {m.eyebrow}</div>
          <h1 ref={headingRef} tabIndex={-1}>{m.heading}<span className="heading-period">.</span></h1>
          <p>{m.intro}</p>
        </div>
      </div>
      {error && (
        <div className="inline-error" role="alert">
          {error}
          <button onClick={() => setError("")} aria-label={m.dismissError}><X size={16} /></button>
        </div>
      )}
      {status && <p className="bulk-notice" role="status">{status}</p>}
      <div className="agent-layout">
        <section className="agent-main">
          <div className="section-heading">
            <div>
              <h2>{m.mailboxes}</h2>
              <p>{m.mailboxesIntro}</p>
            </div>
          </div>
          {accounts.length ? (
            <div className="agent-list">
              {accounts.map((item) => (
                <article className="agent-card mail-card" key={item.id}>
                  <span className="agent-avatar"><Mail size={21} aria-hidden="true" /></span>
                  <div className="agent-card-body">
                    <strong>{item.name}{!item.enabled && m.paused}</strong>
                    <span>{item.username} · {item.auth === "oauth" ? m.signedInWith(item.oauth_provider === "gmail" ? "Google" : "Microsoft") : `${item.host}:${item.port}`}</span>
                    <span className={item.last_error ? "mail-error" : undefined}>
                      {item.checking || item.id in waiting ? m.checkingNow : item.last_error ? item.last_error
                        : item.last_checked_at ? m.checked(new Date(item.last_checked_at).toLocaleString(), item.last_imported) : m.notChecked}
                    </span>
                    {results[item.id] && <span>{results[item.id]}</span>}
                  </div>
                  <div className="mail-actions">
                    {confirming === item.id ? (
                      <>
                        <span>{m.confirmRemoveMailbox}</span>
                        <Button variant="danger" disabled={busy} onClick={() => remove("accounts", item.id)}>{m.remove}</Button>
                        <Button variant="secondary" autoFocus onClick={() => setConfirming(null)}>{m.keep}</Button>
                      </>
                    ) : (
                      <>
                        <Button variant="secondary" disabled={busy} onClick={() => void run(() => test(item), m.testError)}>{m.test}</Button>
                        <Button variant="secondary" disabled={busy || item.checking || item.id in waiting || !item.enabled} onClick={() => check(item)}><RefreshCw size={15} aria-hidden="true" /> {m.checkNow}</Button>
                        <Button variant="secondary" disabled={busy} onClick={() => toggleAccount(item)}>{item.enabled ? m.pause : m.resume}</Button>
                        {item.auth === "password" && <Button variant="secondary" onClick={() => editAccount(item)}>{m.edit}</Button>}
                        <Button variant="secondary" aria-label={m.removeMailboxLabel(item.name)} onClick={() => setConfirming(item.id)}>{m.remove}</Button>
                      </>
                    )}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="tag-empty">
              <Mail size={27} aria-hidden="true" />
              <strong>{m.noMailbox}</strong>
              <p>{m.noMailboxText}</p>
            </div>
          )}

          <div className="section-heading agent-activity-heading">
            <div>
              <h2>{m.rules}</h2>
              <p>{m.rulesIntro}</p>
            </div>
          </div>
          {data?.rules.length ? (
            <div className="agent-list">
              {data.rules.map((item) => (
                <article className="agent-card mail-card" key={item.id}>
                  <span className="agent-avatar"><Filter size={21} aria-hidden="true" /></span>
                  <div className="agent-card-body">
                    <strong>{item.name}{!item.enabled && m.paused}</strong>
                    <span>{m.ruleScope(accountName(item.account_id), item.folder, item.max_age_days)}</span>
                    <span>
                      {[item.filter_from && m.filterFrom(item.filter_from), item.filter_subject && m.filterSubject(item.filter_subject),
                        item.filter_body && m.filterText(item.filter_body), item.filter_attachment && m.filterFiles(item.filter_attachment)]
                        .filter(Boolean).join(" · ") || m.allWithAttachments}
                    </span>
                    <span>{m.importsThen(item.consume === "attachments" ? m.importsAttachments : item.consume === "message" ? m.importsMessage : m.importsBoth,
                      `${afterLabels[item.after].toLowerCase()}${item.after === "move" ? ` “${item.move_to}”` : ""}`)}</span>
                  </div>
                  <div className="mail-actions">
                    {confirming === item.id ? (
                      <>
                        <span>{m.confirmRemoveRule}</span>
                        <Button variant="danger" disabled={busy} onClick={() => remove("rules", item.id)}>{m.remove}</Button>
                        <Button variant="secondary" autoFocus onClick={() => setConfirming(null)}>{m.keep}</Button>
                      </>
                    ) : (
                      <>
                        <Button variant="secondary" disabled={busy} onClick={() => toggleRule(item)}>{item.enabled ? m.pause : m.resume}</Button>
                        <Button variant="secondary" onClick={() => editRule(item)}>{m.edit}</Button>
                        <Button variant="secondary" aria-label={m.removeRuleLabel(item.name)} onClick={() => setConfirming(item.id)}>{m.remove}</Button>
                      </>
                    )}
                  </div>
                </article>
              ))}
            </div>
          ) : <p className="agent-empty-activity">{accounts.length ? m.addRuleToStart : m.connectFirst}</p>}

          <div className="section-heading agent-activity-heading">
            <div>
              <h2>{m.recentMail}</h2>
              <p>{m.recentMailIntro}</p>
            </div>
          </div>
          {data?.recent.length ? (
            <div className="agent-events">
              {data.recent.map((item) => (
                <div key={item.id}>
                  <span>{item.rule} · {item.sender || item.account}</span>
                  <strong>{item.subject || m.noSubject}</strong>
                  <small>
                    {item.status === "imported" ? m.documentsAdded(item.documents)
                      : item.status === "no_match" ? item.detail || m.nothingToImport : item.detail || m.skipped}
                    {" · "}{new Date(item.processed_at).toLocaleString()}
                  </small>
                </div>
              ))}
            </div>
          ) : <p className="agent-empty-activity">{m.noMail}</p>}
        </section>

        <div className="mail-side">
          <section className="tag-create-card agent-create-card">
            <div className="tag-create-icon"><Inbox size={21} aria-hidden="true" /></div>
            <h2>{editingAccount ? m.editMailbox : m.connectMailbox}</h2>
            {!editingAccount && data?.oauth_providers.length ? (
              <div className="mail-oauth">
                {data.oauth_providers.map((provider) => (
                  <Button key={provider.id} variant="secondary" disabled={busy} onClick={() => startOAuth(provider.id)}>
                    {m.signInWith(provider.id === "gmail" ? "Google" : "Microsoft")}
                  </Button>
                ))}
                <small>{m.orAppPassword}</small>
              </div>
            ) : <p>{m.imapHint}</p>}
            <form ref={accountFormRef} onSubmit={saveAccount} aria-label={m.mailboxSettings}>
              <label>{m.name}<input value={account.name} onChange={(event) => setAccount({ ...account, name: event.target.value })} placeholder={m.namePlaceholder} maxLength={100} required /></label>
              <label>{m.imapServer}<input value={account.host} onChange={(event) => setAccount({ ...account, host: event.target.value })} placeholder="imap.example.com" maxLength={255} required autoCapitalize="none" spellCheck={false} /></label>
              <div className="mail-row">
                <label>{m.security}
                  <select value={account.security} onChange={(event) => {
                    const security = event.target.value as Account["security"];
                    setAccount({ ...account, security, port: security === "ssl" ? 993 : 143 });
                  }}>
                    <option value="ssl">SSL/TLS</option>
                    <option value="starttls">STARTTLS</option>
                    <option value="none">{m.securityNone}</option>
                  </select>
                </label>
                <label>{m.port}<input type="number" min={1} max={65535} value={account.port} onChange={(event) => setAccount({ ...account, port: Number(event.target.value) })} required /></label>
              </div>
              {account.security === "none" && (
                <p className="mail-warning" role="note">{m.noSecurityWarning}</p>
              )}
              <label>{m.username}<input value={account.username} onChange={(event) => setAccount({ ...account, username: event.target.value })} autoComplete="off" autoCapitalize="none" spellCheck={false} maxLength={255} required /></label>
              <label>{m.password} {editingAccount && <small>{m.keepPassword}</small>}
                <input type="password" value={account.password} onChange={(event) => setAccount({ ...account, password: event.target.value })} autoComplete="new-password" maxLength={500} required={!editingAccount} />
              </label>
              <Button disabled={busy}><CheckCircle2 size={17} aria-hidden="true" /> {editingAccount ? m.saveAndTest : m.connectAndTest}</Button>
              {editingAccount && <Button type="button" variant="secondary" onClick={() => { setEditingAccount(null); setAccount(emptyAccount); }}>{m.cancel}</Button>}
            </form>
            <div className="tag-tip">{m.passwordsTip}</div>
          </section>

          {accounts.length > 0 && (
            <section className="tag-create-card agent-create-card">
              <div className="tag-create-icon"><Filter size={21} aria-hidden="true" /></div>
              <h2>{editingRule ? m.editRule : m.addARule}</h2>
              <p>{m.ruleIntro}</p>
              <form ref={ruleFormRef} onSubmit={saveRule} aria-label={m.mailRule}>
                <label>{m.ruleName}<input value={rule.name} onChange={(event) => setRule({ ...rule, name: event.target.value })} placeholder={m.ruleNamePlaceholder} maxLength={100} required /></label>
                <label>{m.mailbox}
                  <select value={rule.account_id} onChange={(event) => setRule({ ...rule, account_id: event.target.value })} required>
                    <option value="">{m.chooseMailbox}</option>
                    {accounts.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label>{m.folder} {ruleFolders.length === 0 && <small>{m.folderHint}</small>}
                  <input list="mail-folders" value={rule.folder} onChange={(event) => setRule({ ...rule, folder: event.target.value })} maxLength={200} required autoCapitalize="none" />
                </label>
                <datalist id="mail-folders">{ruleFolders.map((folder) => <option key={folder} value={folder} />)}</datalist>
                <label>{m.whatToImport}
                  <select value={rule.consume} onChange={(event) => setRule({ ...rule, consume: event.target.value as Rule["consume"] })}>
                    <option value="attachments">{m.optAttachments}</option>
                    <option value="message">{m.optMessage}</option>
                    <option value="both">{m.optBoth}</option>
                  </select>
                </label>
                <fieldset>
                  <legend>{m.onlyMessages} <small>{m.allOptional}</small></legend>
                  <label>{m.senderContains}<input value={rule.filter_from} onChange={(event) => setRule({ ...rule, filter_from: event.target.value })} placeholder={m.senderPlaceholder} maxLength={200} /></label>
                  <label>{m.subjectContains}<input value={rule.filter_subject} onChange={(event) => setRule({ ...rule, filter_subject: event.target.value })} placeholder={m.subjectPlaceholder} maxLength={200} /></label>
                  <label>{m.textContains}<input value={rule.filter_body} onChange={(event) => setRule({ ...rule, filter_body: event.target.value })} maxLength={200} /></label>
                  <label>{m.fileNameMatches}<input value={rule.filter_attachment} onChange={(event) => setRule({ ...rule, filter_attachment: event.target.value })} placeholder={m.fileNamePlaceholder} maxLength={200} /></label>
                  <label className="agent-scope-choice">
                    <input type="checkbox" checked={rule.include_inline} onChange={(event) => setRule({ ...rule, include_inline: event.target.checked })} />
                    {m.includeInline}
                  </label>
                  <label>{m.receivedInLast} <small>{m.days}</small><input type="number" min={1} max={3650} value={rule.max_age_days} onChange={(event) => setRule({ ...rule, max_age_days: Number(event.target.value) })} required /></label>
                </fieldset>
                <label>{m.order} <small>{m.orderHint}</small>
                  <input type="number" min={0} max={10000} value={rule.order} onChange={(event) => setRule({ ...rule, order: Number(event.target.value) })} required />
                </label>
                <label>{m.afterImporting}
                  <select value={rule.after} onChange={(event) => setRule({ ...rule, after: event.target.value as Rule["after"] })}>
                    {Object.entries(afterLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </label>
                {rule.after === "move" && (
                  <label>{m.moveToFolder}<input list="mail-folders" value={rule.move_to} onChange={(event) => setRule({ ...rule, move_to: event.target.value })} maxLength={200} required /></label>
                )}
                <label>{m.documentTitle}
                  <select value={rule.title_from} onChange={(event) => setRule({ ...rule, title_from: event.target.value as Rule["title_from"] })}>
                    <option value="subject">{m.emailSubject}</option>
                    <option value="filename">{m.attachmentName}</option>
                  </select>
                </label>
                <label>{m.sender}
                  <select value={rule.correspondent_id} onChange={(event) => setRule({ ...rule, correspondent_id: event.target.value })}>
                    <option value="">{m.dontSet}</option>
                    {senders.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label>{m.documentType}
                  <select value={rule.document_type_id} onChange={(event) => setRule({ ...rule, document_type_id: event.target.value })}>
                    <option value="">{m.dontSet}</option>
                    {types.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                {tags.length > 0 && (
                  <fieldset className="mail-tags">
                    <legend>{m.addTags}</legend>
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
                <Button disabled={busy}><Plus size={17} aria-hidden="true" /> {editingRule ? m.saveRule : m.addRule}</Button>
                {editingRule && <Button type="button" variant="secondary" onClick={() => { setEditingRule(null); setRule(emptyRule); }}>{m.cancel}</Button>}
              </form>
            </section>
          )}
        </div>
      </div>
    </>
  );
}
