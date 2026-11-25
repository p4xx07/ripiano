import { FormEvent, useCallback, useEffect, useState } from "react";
import { ArrowRight, Plus, Printer, Tag as TagIcon, Trash2, X } from "lucide-react";
import { MatchMode, matchModes, request, Rule, Tag, tagPathLabel } from "./api";
import { Button } from "./ui";
import LearningPanel from "./LearningPanel";
import FilingVocabularyPanel from "./FilingVocabularyPanel";
import StoragePathsPanel from "./StoragePathsPanel";
import { ShareButton, SharePanel, useShareToggle } from "./ShareObject";
import { useMessages } from "./i18n";
import messages from "./locales/TagPanel";

export default function TagPanel() {
  const m = useMessages(messages);
  const [tags, setTags] = useState<Tag[]>([]);
  const sharing = useShareToggle();
  const [rules, setRules] = useState<Rule[]>([]);
  const [name, setName] = useState("");
  const [parentId, setParentId] = useState("");
  const [description, setDescription] = useState("");
  const [barcodeValue, setBarcodeValue] = useState("");
  const [keywords, setKeywords] = useState("");
  const [color, setColor] = useState("#5d8b66");
  const [newRuleTag, setNewRuleTag] = useState<string | null>(null);
  const [newRuleText, setNewRuleText] = useState("");
  const [newRuleMatch, setNewRuleMatch] = useState<MatchMode>("phrase");
  const [movingTagId, setMovingTagId] = useState<string | null>(null);
  const [editingBarcodeTagId, setEditingBarcodeTagId] = useState<string | null>(null);
  const [barcodeDraft, setBarcodeDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const tagById = new Map(tags.map((tag) => [tag.id, tag]));
  const pathCache = new Map<string, string>();
  function tagPath(tag: Tag) {
    const cached = pathCache.get(tag.id);
    if (cached) return cached;
    const path = tagPathLabel(tag, tagById);
    pathCache.set(tag.id, path);
    return path;
  }
  function isInBranch(candidate: Tag, rootId: string) {
    const seen = new Set<string>();
    let current: Tag | undefined = candidate;
    while (current && !seen.has(current.id)) {
      if (current.id === rootId) return true;
      seen.add(current.id);
      current = current.parent_id ? tagById.get(current.parent_id) : undefined;
    }
    return false;
  }
  const sortedTags = [...tags].sort((a, b) => tagPath(a).localeCompare(tagPath(b)));

  const load = useCallback(async () => {
    try {
      const [tagResult, ruleResult] = await Promise.all([
        request<{ tags: Tag[] }>("/api/tags"),
        request<{ rules: Rule[] }>("/api/rules"),
      ]);
      setTags(tagResult.tags);
      setRules(ruleResult.rules);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.loadError);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function addStarterTags() {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await request<{ added: number; tags: Tag[] }>("/api/tags/starter", { method: "POST" });
      setTags(result.tags);
      setNotice(result.added ? m.starterAdded(result.added) : m.starterAlreadyThere);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.starterError);
    } finally {
      setBusy(false);
    }
  }

  async function createTag(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await request("/api/tags", {
        method: "POST",
        body: JSON.stringify({
          name,
          parent_id: parentId || null,
          description,
          barcode_value: barcodeValue,
          color,
          keywords: keywords
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean),
        }),
      });
      setName("");
      setParentId("");
      setDescription("");
      setBarcodeValue("");
      setKeywords("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.createError);
    } finally {
      setBusy(false);
    }
  }

  async function addRule(event: FormEvent) {
    event.preventDefault();
    if (!newRuleTag) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await request("/api/rules", {
        method: "POST",
        body: JSON.stringify({
          tag_id: newRuleTag,
          pattern: newRuleText,
          field: "either",
          match: newRuleMatch,
        }),
      });
      setNewRuleTag(null);
      setNewRuleText("");
      setNewRuleMatch("phrase");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.addPhraseError);
    } finally {
      setBusy(false);
    }
  }

  async function removeRule(id: string) {
    setError("");
    setNotice("");
    try {
      await request(`/api/rules/${id}`, { method: "DELETE" });
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : m.removePhraseError,
      );
    }
  }

  async function removeTag(tag: Tag) {
    if (
      !window.confirm(
        m.confirmDelete(tag.name),
      )
    )
      return;
    setError("");
    setNotice("");
    try {
      await request(`/api/tags/${tag.id}`, { method: "DELETE" });
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.deleteError);
    }
  }

  async function moveTag(tag: Tag, nextParentId: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await request(`/api/tags/${tag.id}`, {
        method: "PATCH",
        body: JSON.stringify({ parent_id: nextParentId || null }),
      });
      await load();
      setMovingTagId(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.moveError);
    } finally {
      setBusy(false);
    }
  }

  async function saveBarcode(event: FormEvent, tag: Tag) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await request(`/api/tags/${tag.id}`, {
        method: "PATCH",
        body: JSON.stringify({ barcode_value: barcodeDraft }),
      });
      setEditingBarcodeTagId(null);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.barcodeError);
    } finally {
      setBusy(false);
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
            {m.title}<span className="heading-period">.</span>
          </h1>
          <p>
            {m.intro}
          </p>
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
      <div className="tag-layout">
        <section className="tag-list-section">
          <div className="section-heading">
            <div>
              <h2>{m.yourTags}</h2>
              <p>{m.yourTagsIntro}</p>
            </div>
          </div>
          <p className="starter-tags">
            <span>{m.starterIntro}</span>
            <button type="button" className="text-action" disabled={busy} onClick={() => void addStarterTags()}>
              <Plus size={15} /> {m.starterAction}
            </button>
          </p>
          <p className={notice ? "bulk-notice" : "visually-hidden"} role="status" aria-live="polite">{notice}</p>
          {tags.length ? (
            <div className="tag-list">
              {sortedTags.map((tag) => (
                <article className="tag-card" key={tag.id}>
                  <div className="tag-card-head">
                    <span
                      className="tag-color"
                      style={{ background: tag.color }}
                    />
                    <div>
                      <h3>{tag.name}</h3>
                      {tag.parent_id && <p className="tag-path">{tagPath(tag)}</p>}
                      {tag.description && <p>{tag.description}</p>}
                    </div>
                    <ShareButton kind="tag" id={tag.id} name={tag.name} open={sharing.openId === tag.id} onToggle={() => sharing.toggle(tag.id)} />
                    <button
                      className="tag-icon-button"
                      onClick={() => void removeTag(tag)}
                      aria-label={m.deleteNamed(tag.name)}
                      title={m.deleteTag}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                  {sharing.openId === tag.id && <SharePanel kind="tag" id={tag.id} />}
                  {movingTagId === tag.id ? (
                    <div className="tag-parent-editor">
                      <label className="tag-parent-control">
                        {m.under}
                        <select
                          aria-label={m.parentFor(tag.name)}
                          value={tag.parent_id ?? ""}
                          disabled={busy}
                          onChange={(event) => void moveTag(tag, event.target.value)}
                        >
                          <option value="">{m.topLevel}</option>
                          {sortedTags.filter((candidate) => !isInBranch(candidate, tag.id)).map((candidate) => (
                            <option key={candidate.id} value={candidate.id}>{tagPath(candidate)}</option>
                          ))}
                        </select>
                      </label>
                      <button type="button" className="tag-icon-button" aria-label={m.cancelMove} onClick={() => setMovingTagId(null)}>
                        <X size={16} />
                      </button>
                    </div>
                  ) : (
                    <button type="button" className="tag-move-button" aria-label={m.moveNamed(tag.name)} onClick={() => setMovingTagId(tag.id)}>
                      {tag.parent_id ? m.changeGroup : m.putUnder}
                    </button>
                  )}
                  {editingBarcodeTagId === tag.id ? <form className="tag-barcode-editor" onSubmit={(event) => void saveBarcode(event, tag)}>
                    <label className="detail-label">{m.barcodeFor(tag.name)}
                      <input autoFocus value={barcodeDraft} onChange={(event) => setBarcodeDraft(event.target.value)} maxLength={100} placeholder={m.barcodePlaceholder} />
                    </label>
                    <Button disabled={busy}>{m.saveCode}</Button>
                    <button type="button" className="tag-icon-button" aria-label={m.cancelBarcode(tag.name)} onClick={() => setEditingBarcodeTagId(null)}><X size={16} /></button>
                  </form> : <div className="tag-barcode-row">
                    <span>{tag.barcode_value ? m.barcode(tag.barcode_value) : m.noBarcode}</span>
                    {tag.barcode_value && <a className="text-action" href={`/api/tags/${tag.id}/label`} target="_blank" rel="noreferrer"><Printer size={15} /> {m.printLabel}</a>}
                    <button type="button" className="text-action" onClick={() => { setEditingBarcodeTagId(tag.id); setBarcodeDraft(tag.barcode_value); }}>{tag.barcode_value ? m.changeCode : m.setBarcode}</button>
                  </div>}
                  <div className="rule-list">
                    {rules
                      .filter((rule) => rule.tag_id === tag.id)
                      .map((rule) => (
                        <span className="rule-chip" key={rule.id}>
                          {rule.match && rule.match !== "phrase" ? <small className="rule-mode">{m.matchMode(rule.match)}:</small> : null}
                          {rule.pattern}
                          <button
                            onClick={() => void removeRule(rule.id)}
                            aria-label={m.removePhrase(rule.pattern)}
                          >
                            <X size={13} />
                          </button>
                        </span>
                      ))}
                    {newRuleTag === tag.id ? (
                      <form className="rule-form" onSubmit={addRule}>
                        <input
                          autoFocus
                          value={newRuleText}
                          onChange={(event) =>
                            setNewRuleText(event.target.value)
                          }
                          placeholder={m.phraseToMatch}
                          aria-label={m.phraseToMatch}
                          maxLength={200}
                          required
                        />
                        <select aria-label={m.howMatches} value={newRuleMatch} onChange={(event) => setNewRuleMatch(event.target.value as MatchMode)}>
                          {Object.keys(matchModes).map((value) => <option key={value} value={value}>{m.matchMode(value as MatchMode)}</option>)}
                        </select>
                        <Button
                          disabled={busy}
                        >
                          {m.add}
                        </Button>
                        <button
                          className="tag-icon-button"
                          type="button"
                          onClick={() => setNewRuleTag(null)}
                          aria-label={m.cancel}
                        >
                          <X size={16} />
                        </button>
                      </form>
                    ) : (
                      <button
                        className="add-rule"
                        onClick={() => {
                          (setNewRuleTag(tag.id), setNewRuleMatch("phrase"));
                          setNewRuleText("");
                        }}
                      >
                        <Plus size={14} /> {m.addPhrase}
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="tag-empty">
              <TagIcon size={24} />
              <strong>{m.noTags}</strong>
              <p>
                {m.noTagsIntro}
              </p>
            </div>
          )}
        </section>
        <section className="tag-create-card">
          <div className="tag-create-icon">
            <TagIcon size={21} />
          </div>
          <h2>{m.createHeading}</h2>
          <p>{m.createIntro}</p>
          <form onSubmit={createTag}>
            <label>
              {m.name}
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                maxLength={100}
                placeholder={m.namePlaceholder}
                required
              />
            </label>
            <label>
              {m.under} <small>{m.optional}</small>
              <select aria-label={m.parentTag} value={parentId} onChange={(event) => setParentId(event.target.value)}>
                <option value="">{m.topLevel}</option>
                {sortedTags.map((tag) => (
                  <option key={tag.id} value={tag.id}>{tagPath(tag)}</option>
                ))}
              </select>
            </label>
            <label>
              {m.matchingPhrases} <small>{m.matchingPhrasesHint}</small>
              <input
                value={keywords}
                onChange={(event) => setKeywords(event.target.value)}
                placeholder={m.keywordsPlaceholder}
              />
            </label>
            <label>
              {m.barcodeValue} <small>{m.barcodeValueHint}</small>
              <input value={barcodeValue} onChange={(event) => setBarcodeValue(event.target.value)} maxLength={100} placeholder={m.barcodeValuePlaceholder} />
            </label>
            <label>
              {m.description} <small>{m.optional}</small>
              <textarea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                maxLength={500}
                rows={3}
                placeholder={m.descriptionPlaceholder}
              />
            </label>
            <label className="color-label">
              {m.color}
              <input
                type="color"
                value={color}
                onChange={(event) => setColor(event.target.value)}
              />
            </label>
            <Button disabled={busy}>
              {busy ? m.creating : m.createTag}
              <ArrowRight size={17} />
            </Button>
          </form>
          <div className="tag-tip">
            {m.tip}
          </div>
        </section>
      </div>
      <div className="filing-vocabularies">
        <FilingVocabularyPanel kind="correspondents" />
        <FilingVocabularyPanel kind="document-types" />
        <LearningPanel />
        <StoragePathsPanel />
      </div>
    </>
  );
}
