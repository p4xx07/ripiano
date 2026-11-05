import { FormEvent, useCallback, useEffect, useState } from "react";
import { ArrowRight, Plus, Tag as TagIcon, Trash2, X } from "lucide-react";
import { request, Rule, Tag } from "./api";
import { Button } from "./ui";

export default function TagPanel() {
  const [tags, setTags] = useState<Tag[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [keywords, setKeywords] = useState("");
  const [color, setColor] = useState("#5d8b66");
  const [newRuleTag, setNewRuleTag] = useState<string | null>(null);
  const [newRuleText, setNewRuleText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [tagResult, ruleResult] = await Promise.all([
        request<{ tags: Tag[] }>("/api/tags"),
        request<{ rules: Rule[] }>("/api/rules"),
      ]);
      setTags(tagResult.tags);
      setRules(ruleResult.rules);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load tags");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function createTag(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await request("/api/tags", {
        method: "POST",
        body: JSON.stringify({
          name,
          description,
          color,
          keywords: keywords
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean),
        }),
      });
      setName("");
      setDescription("");
      setKeywords("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create tag");
    } finally {
      setBusy(false);
    }
  }

  async function addRule(event: FormEvent) {
    event.preventDefault();
    if (!newRuleTag) return;
    setBusy(true);
    setError("");
    try {
      await request("/api/rules", {
        method: "POST",
        body: JSON.stringify({
          tag_id: newRuleTag,
          pattern: newRuleText,
          field: "either",
        }),
      });
      setNewRuleTag(null);
      setNewRuleText("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not add phrase");
    } finally {
      setBusy(false);
    }
  }

  async function removeRule(id: string) {
    setError("");
    try {
      await request(`/api/rules/${id}`, { method: "DELETE" });
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not remove phrase",
      );
    }
  }

  async function removeTag(tag: Tag) {
    if (
      !window.confirm(
        `Delete “${tag.name}”? It will be removed from all documents.`,
      )
    )
      return;
    setError("");
    try {
      await request(`/api/tags/${tag.id}`, { method: "DELETE" });
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete tag");
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            <span className="eyebrow-line" /> ORGANIZE ONCE
          </div>
          <h1>
            Tags that do the work<span className="heading-period">.</span>
          </h1>
          <p>
            Tell Ripiano which phrases matter. Matching documents are tagged
            after OCR.
          </p>
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
      <div className="tag-layout">
        <section className="tag-list-section">
          <div className="section-heading">
            <div>
              <h2>Your tags</h2>
              <p>Change a tag on any document whenever you need to.</p>
            </div>
          </div>
          {tags.length ? (
            <div className="tag-list">
              {tags.map((tag) => (
                <article className="tag-card" key={tag.id}>
                  <div className="tag-card-head">
                    <span
                      className="tag-color"
                      style={{ background: tag.color }}
                    />
                    <div>
                      <h3>{tag.name}</h3>
                      {tag.description && <p>{tag.description}</p>}
                    </div>
                    <button
                      className="tag-icon-button"
                      onClick={() => void removeTag(tag)}
                      aria-label={`Delete ${tag.name}`}
                      title="Delete tag"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                  <div className="rule-list">
                    {rules
                      .filter((rule) => rule.tag_id === tag.id)
                      .map((rule) => (
                        <span className="rule-chip" key={rule.id}>
                          {rule.pattern}
                          <button
                            onClick={() => void removeRule(rule.id)}
                            aria-label={`Remove phrase ${rule.pattern}`}
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
                          placeholder="Phrase to match"
                          maxLength={200}
                          required
                        />
                        <Button
                          disabled={busy}
                        >
                          Add
                        </Button>
                        <button
                          className="tag-icon-button"
                          type="button"
                          onClick={() => setNewRuleTag(null)}
                          aria-label="Cancel"
                        >
                          <X size={16} />
                        </button>
                      </form>
                    ) : (
                      <button
                        className="add-rule"
                        onClick={() => {
                          setNewRuleTag(tag.id);
                          setNewRuleText("");
                        }}
                      >
                        <Plus size={14} /> Add matching phrase
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="tag-empty">
              <TagIcon size={24} />
              <strong>No tags yet</strong>
              <p>
                Create one with a few phrases and future documents can file
                themselves.
              </p>
            </div>
          )}
        </section>
        <section className="tag-create-card">
          <div className="tag-create-icon">
            <TagIcon size={21} />
          </div>
          <h2>Create a tag</h2>
          <p>Start with the name you want to see in your archive.</p>
          <form onSubmit={createTag}>
            <label>
              Name
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                maxLength={100}
                placeholder="e.g. Bills"
                required
              />
            </label>
            <label>
              Matching phrases <small>Optional · separate with commas</small>
              <input
                value={keywords}
                onChange={(event) => setKeywords(event.target.value)}
                placeholder="invoice, electricity, fattura"
              />
            </label>
            <label>
              Description <small>Optional</small>
              <textarea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                maxLength={500}
                rows={3}
                placeholder="What belongs here?"
              />
            </label>
            <label className="color-label">
              Color
              <input
                type="color"
                value={color}
                onChange={(event) => setColor(event.target.value)}
              />
            </label>
            <Button disabled={busy}>
              {busy ? "Creating…" : "Create tag"}
              <ArrowRight size={17} />
            </Button>
          </form>
          <div className="tag-tip">
            Phrases are matched locally. Removing an automatic tag from a
            document is remembered as a correction.
          </div>
        </section>
      </div>
    </>
  );
}
