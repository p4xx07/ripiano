import { FormEvent, useEffect, useState } from "react";
import {
  ArrowDownToLine,
  Eye,
  FileText,
  Save,
  Tag as TagIcon,
  X,
} from "lucide-react";
import { Document, request, Tag } from "./api";

export default function DocumentPanel({
  initial,
  onClose,
  onSaved,
  onOpenTags,
}: {
  initial: Document;
  onClose: () => void;
  onSaved: (document: Document) => void;
  onOpenTags: () => void;
}) {
  const [current, setCurrent] = useState(initial);
  const [title, setTitle] = useState(initial.title);
  const [date, setDate] = useState(initial.document_date ?? "");
  const [selected, setSelected] = useState<string[]>(
    initial.tags.map((tag) => tag.id),
  );
  const [available, setAvailable] = useState<Tag[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    request<{ tags: Tag[] }>("/api/tags")
      .then((result) => setAvailable(result.tags))
      .catch((cause) => setError(cause.message));
  }, []);
  useEffect(() => {
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [onClose]);

  function toggle(id: string) {
    setSelected((value) =>
      value.includes(id) ? value.filter((item) => item !== id) : [...value, id],
    );
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const updated = await request<Document>(`/api/documents/${current.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title,
          document_date: date || null,
          tags: selected,
        }),
      });
      setCurrent(updated);
      onSaved(updated);
      onClose();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not save document",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="modal-backdrop detail-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className="detail-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="detail-heading"
      >
        <button className="modal-close" onClick={onClose} aria-label="Close">
          <X size={20} />
        </button>
        <div className="eyebrow">
          <span className="eyebrow-line" /> DOCUMENT
        </div>
        <h2 id="detail-heading">Keep it in place.</h2>
        <p className="detail-intro">
          The original is safe. Add details only when they help you find it
          later.
        </p>
        {error && (
          <div className="inline-error" role="alert">
            {error}
          </div>
        )}
        <form onSubmit={save}>
          <label className="detail-label">
            Title
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={300}
              required
            />
          </label>
          <label className="detail-label">
            Document date <small>Optional</small>
            <input
              type="date"
              value={date}
              onChange={(event) => setDate(event.target.value)}
            />
          </label>
          <div className="detail-label">
            Tags <small>Choose only what helps</small>
          </div>
          {available.length ? (
            <div className="tag-choices">
              {available.map((tag) => (
                <label className="tag-choice" key={tag.id}>
                  <input
                    type="checkbox"
                    checked={selected.includes(tag.id)}
                    onChange={() => toggle(tag.id)}
                  />
                  <span
                    className="tag-color"
                    style={{ background: tag.color }}
                  />
                  {tag.name}
                  {current.tags.find((item) => item.id === tag.id)?.origin ===
                    "rule" && <small>Automatic</small>}
                </label>
              ))}
            </div>
          ) : (
            <button
              type="button"
              className="detail-create-tag"
              onClick={onOpenTags}
            >
              <TagIcon size={17} /> Create your first tag
            </button>
          )}
          <button className="button button-primary detail-save" disabled={busy}>
            <Save size={17} /> {busy ? "Saving…" : "Save changes"}
          </button>
        </form>
        <div className="detail-files">
          <h3>
            <FileText size={17} /> Files
          </h3>
          <a href={`/api/documents/${current.id}/original`}>
            <ArrowDownToLine size={17} /> Download original
          </a>
          {current.archive_available && (
            <a
              href={`/api/documents/${current.id}/archive`}
              target="_blank"
              rel="noreferrer"
            >
              <Eye size={17} /> Open searchable PDF
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
