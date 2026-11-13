import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Pencil, Plus, Trash2, X } from "lucide-react";
import { FilingItem, FilingRule, MatchMode, matchModes, request } from "./api";
import { Button } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/FilingVocabularyPanel";

export default function FilingVocabularyPanel({ kind }: { kind: "correspondents" | "document-types" }) {
  const m = useMessages(messages);
  const isSender = kind === "correspondents";
  const title = isSender ? m.titleSender : m.titleType;
  const loadError = isSender ? m.loadErrorSender : m.loadErrorType;
  const key = isSender ? "correspondents" : "document_types";
  const [items, setItems] = useState<FilingItem[]>([]);
  const [rules, setRules] = useState<FilingRule[]>([]);
  const [name, setName] = useState("");
  const [filter, setFilter] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [editedName, setEditedName] = useState("");
  const [newRuleTarget, setNewRuleTarget] = useState<string | null>(null);
  const [newRuleText, setNewRuleText] = useState("");
  const [newRuleMatch, setNewRuleMatch] = useState<MatchMode>("phrase");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const filterRef = useRef<HTMLInputElement>(null);
  const renameButtons = useRef(new Map<string, HTMLButtonElement>());
  const focusAfterEdit = useRef<string | null>(null);
  const addPhraseButtons = useRef(new Map<string, HTMLButtonElement>());
  const focusAfterPhrase = useRef<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [result, ruleResult] = await Promise.all([
        request<Record<typeof key, FilingItem[]>>(`/api/${kind}`),
        request<{ rules: FilingRule[] }>(`/api/filing-rules?kind=${isSender ? "correspondent" : "document_type"}`),
      ]);
      setItems(result[key]);
      setRules(ruleResult.rules);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : loadError);
    }
  }, [kind, key, loadError, isSender]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (editing || !focusAfterEdit.current) return;
    const target = focusAfterEdit.current;
    focusAfterEdit.current = null;
    if (target === "filter") filterRef.current?.focus();
    else (renameButtons.current.get(target) ?? filterRef.current)?.focus();
  }, [editing, items]);
  useEffect(() => {
    if (newRuleTarget || !focusAfterPhrase.current) return;
    const target = focusAfterPhrase.current;
    focusAfterPhrase.current = null;
    (addPhraseButtons.current.get(target) ?? filterRef.current)?.focus();
  }, [newRuleTarget, rules]);

  const visibleItems = items.filter((item) => item.name.toLocaleLowerCase().includes(filter.trim().toLocaleLowerCase()));

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await request(`/api/${kind}`, { method: "POST", body: JSON.stringify({ name }) });
      setNotice(m.added(name.trim()));
      setName("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : (isSender ? m.addErrorSender : m.addErrorType));
    } finally {
      setBusy(false);
    }
  }

  async function rename(event: FormEvent) {
    event.preventDefault();
    if (!editing) return;
    setBusy(true);
    setError("");
    try {
      await request(`/api/${kind}/${editing}`, { method: "PATCH", body: JSON.stringify({ name: editedName }) });
      focusAfterEdit.current = editing;
      setItems((current) => current.map((item) => item.id === editing ? { ...item, name: editedName.trim() } : item));
      setEditing(null);
      setNotice((isSender ? m.renamedSender : m.renamedType)(editedName.trim()));
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : (isSender ? m.renameErrorSender : m.renameErrorType));
    } finally {
      setBusy(false);
    }
  }

  async function remove(item: FilingItem) {
    if (!window.confirm(m.confirmDelete(item.name))) return;
    setBusy(true);
    setError("");
    try {
      await request(`/api/${kind}/${item.id}`, { method: "DELETE" });
      focusAfterEdit.current = "filter";
      setItems((current) => current.filter((currentItem) => currentItem.id !== item.id));
      setNotice(m.deleted(item.name));
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : (isSender ? m.deleteErrorSender : m.deleteErrorType));
    } finally {
      setBusy(false);
    }
  }

  async function addRule(event: FormEvent) {
    event.preventDefault();
    if (!newRuleTarget) return;
    setBusy(true);
    setError("");
    try {
      await request("/api/filing-rules", { method: "POST", body: JSON.stringify({
        kind: isSender ? "correspondent" : "document_type",
        target_id: newRuleTarget, pattern: newRuleText, field: "either", match: newRuleMatch,
      }) });
      focusAfterPhrase.current = newRuleTarget;
      setNewRuleTarget(null);
      setNewRuleText("");
      setNewRuleMatch("phrase");
      setNotice(m.phraseAdded);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.phraseAddError);
    } finally {
      setBusy(false);
    }
  }

  async function removeRule(rule: FilingRule) {
    setBusy(true);
    setError("");
    try {
      await request(`/api/filing-rules/${rule.id}`, { method: "DELETE" });
      focusAfterPhrase.current = rule.target_id;
      setRules((current) => current.filter((item) => item.id !== rule.id));
      setNotice(m.phraseRemoved);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.phraseRemoveError);
    } finally {
      setBusy(false);
    }
  }

  return <section className="filing-card">
    <h2>{title}</h2>
    <p>{isSender ? m.introSender : m.introType}</p>
    <div className="visually-hidden" role="status" aria-live="polite">{notice}</div>
    {error && <div className="inline-error" role="alert">{error}<button onClick={() => setError("")} aria-label={m.dismissError}><X size={16} /></button></div>}
    <form className="filing-vocabulary-form" onSubmit={create}>
      <input aria-label={isSender ? m.newNameSender : m.newNameType} value={name} onChange={(event) => setName(event.target.value)} maxLength={100} placeholder={isSender ? m.placeholderSender : m.placeholderType} required />
      <Button disabled={busy}><Plus size={16} /> {m.add}</Button>
    </form>
    <input ref={filterRef} className="filing-filter" aria-label={isSender ? m.filterSender : m.filterType} value={filter} onChange={(event) => setFilter(event.target.value)} placeholder={isSender ? m.filterPlaceholderSender : m.filterPlaceholderType} />
    {items.length === 0 ? <p className="filing-empty">{m.empty}</p> : visibleItems.length === 0 ? <p className="filing-empty">{m.noMatches}</p> : <ul className="filing-vocabulary-list">
      {visibleItems.map((item) => <li key={item.id}>
        <div className="filing-vocabulary-row">
          {editing === item.id ? <form onSubmit={rename}>
            <input autoFocus aria-label={m.rename(item.name)} value={editedName} onChange={(event) => setEditedName(event.target.value)} maxLength={100} required />
            <Button disabled={busy}>{m.save}</Button>
            <button type="button" aria-label={m.cancelRename} onClick={() => { focusAfterEdit.current = item.id; setEditing(null); setNotice(m.renameCancelled); }}><X size={16} /></button>
          </form> : <>
            <span>{item.name}</span>
            <button ref={(node) => { if (node) renameButtons.current.set(item.id, node); else renameButtons.current.delete(item.id); }} type="button" aria-label={m.rename(item.name)} onClick={() => { setEditing(item.id); setEditedName(item.name); }}><Pencil size={16} /></button>
            <button type="button" aria-label={m.remove(item.name)} disabled={busy} onClick={() => void remove(item)}><Trash2 size={16} /></button>
          </>}
        </div>
        <div className="filing-rule-list">
          {rules.filter((rule) => rule.target_id === item.id).map((rule) => <span className="rule-chip" key={rule.id}>{rule.match && rule.match !== "phrase" ? <small className="rule-mode">{m.matchMode(rule.match)}:</small> : null}{rule.pattern}<button type="button" aria-label={m.removePhrase(rule.pattern, item.name)} disabled={busy} onClick={() => void removeRule(rule)}><X size={13} /></button></span>)}
          {newRuleTarget === item.id ? <form className="filing-rule-form" onSubmit={addRule}>
            <input autoFocus aria-label={m.phraseFor(item.name)} value={newRuleText} onChange={(event) => setNewRuleText(event.target.value)} maxLength={200} placeholder={m.phrasePlaceholder} required />
            <select aria-label={m.howMatches(item.name)} value={newRuleMatch} onChange={(event) => setNewRuleMatch(event.target.value as MatchMode)}>
              {(Object.keys(matchModes) as MatchMode[]).map((value) => <option key={value} value={value}>{m.matchMode(value)}</option>)}
            </select>
            <Button disabled={busy}>{m.add}</Button>
            <button type="button" aria-label={m.cancelPhrase} onClick={() => { focusAfterPhrase.current = item.id; setNewRuleTarget(null); }}><X size={16} /></button>
          </form> : <button ref={(node) => { if (node) addPhraseButtons.current.set(item.id, node); else addPhraseButtons.current.delete(item.id); }} type="button" className="text-action" onClick={() => { setNewRuleTarget(item.id); setNewRuleText(""); setNewRuleMatch("phrase"); }}><Plus size={14} /> {m.addPhrase}</button>}
        </div>
      </li>)}
    </ul>}
  </section>;
}
