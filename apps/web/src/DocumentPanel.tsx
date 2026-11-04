import { FormEvent, useEffect, useState } from "react";
import {
  ArrowDownToLine,
  Eye,
  FileText,
  History,
  MapPin,
  Plus,
  Printer,
  Save,
  Tag as TagIcon,
  X,
} from "lucide-react";
import { Document, Location, PhysicalCopy, request, Tag } from "./api";

export default function DocumentPanel({
  initial,
  onClose,
  onSaved,
  onOpenTags,
  onOpenLocations,
}: {
  initial: Document;
  onClose: () => void;
  onSaved: (document: Document) => void;
  onOpenTags: () => void;
  onOpenLocations: () => void;
}) {
  const [current, setCurrent] = useState(initial);
  const [title, setTitle] = useState(initial.title);
  const [date, setDate] = useState(initial.document_date ?? "");
  const [selected, setSelected] = useState<string[]>(
    initial.tags.map((tag) => tag.id),
  );
  const [available, setAvailable] = useState<Tag[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [copies, setCopies] = useState<PhysicalCopy[]>(initial.physical_copies);
  const [newLocation, setNewLocation] = useState("");
  const [moveChoices, setMoveChoices] = useState<Record<string, string>>({});
  const [histories, setHistories] = useState<
    Record<string, { from: string[]; to: string[]; note: string; at: string }[]>
  >({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    request<{ tags: Tag[] }>("/api/tags")
      .then((result) => setAvailable(result.tags))
      .catch((cause) => setError(cause.message));
  }, []);
  useEffect(() => {
    request<{ locations: Location[] }>("/api/locations")
      .then((result) => setLocations(result.locations))
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

  async function refreshCopies() {
    const result = await request<{ copies: PhysicalCopy[] }>(
      `/api/documents/${current.id}/copies`,
    );
    setCopies(result.copies);
    onSaved(await request<Document>(`/api/documents/${current.id}`));
  }

  async function createCopy() {
    setBusy(true);
    setError("");
    try {
      await request(`/api/documents/${current.id}/copies`, {
        method: "POST",
        body: JSON.stringify({ location_id: newLocation || null }),
      });
      await refreshCopies();
      setNewLocation("");
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not create sticker",
      );
    } finally {
      setBusy(false);
    }
  }

  async function moveCopy(copy: PhysicalCopy) {
    setBusy(true);
    setError("");
    try {
      await request(`/api/copies/${copy.id}`, {
        method: "PATCH",
        body: JSON.stringify({ location_id: moveChoices[copy.id] || null }),
      });
      await refreshCopies();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not move paper copy",
      );
    } finally {
      setBusy(false);
    }
  }

  async function showHistory(copy: PhysicalCopy) {
    try {
      const result = await request<{
        movements: { from: string[]; to: string[]; note: string; at: string }[];
      }>(`/api/copies/${copy.id}/history`);
      setHistories((value) => ({ ...value, [copy.id]: result.movements }));
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not load movement history",
      );
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
        <div className="detail-files physical-copies">
          <h3>
            <MapPin size={17} /> Paper copies
          </h3>
          {!copies.length && (
            <p>Digital only. You can add a sticker if you keep a paper copy.</p>
          )}
          {copies.map((copy) => (
            <div className="copy-card" key={copy.id}>
              <strong>{copy.sticker_code}</strong>
              <span>
                {copy.location_path.join(" / ") || "Location not assigned"}
              </span>
              <div className="copy-actions">
                <a
                  href={`/api/copies/${copy.id}/label`}
                  target="_blank"
                  rel="noreferrer"
                >
                  <Printer size={16} /> Print sticker
                </a>
                <button onClick={() => void showHistory(copy)}>
                  <History size={16} /> History
                </button>
              </div>
              <div className="copy-move">
                <select
                  value={moveChoices[copy.id] ?? copy.location_id ?? ""}
                  onChange={(event) =>
                    setMoveChoices((value) => ({
                      ...value,
                      [copy.id]: event.target.value,
                    }))
                  }
                >
                  <option value="">No location</option>
                  {locations.map((location) => (
                    <option key={location.id} value={location.id}>
                      {location.path.join(" / ")}
                    </option>
                  ))}
                </select>
                <button
                  className="button button-secondary"
                  disabled={busy}
                  onClick={() => void moveCopy(copy)}
                >
                  Move
                </button>
              </div>
              {histories[copy.id] && (
                <div className="copy-history">
                  {histories[copy.id].map((move, index) => (
                    <div key={index}>
                      {new Date(move.at).toLocaleDateString()} ·{" "}
                      {move.to.join(" / ") || "No location"}
                      {move.note && ` · ${move.note}`}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          <div className="new-copy">
            <select
              value={newLocation}
              onChange={(event) => setNewLocation(event.target.value)}
            >
              <option value="">No location yet</option>
              {locations.map((location) => (
                <option key={location.id} value={location.id}>
                  {location.path.join(" / ")}
                </option>
              ))}
            </select>
            <button
              className="button button-secondary"
              disabled={busy}
              onClick={() => void createCopy()}
            >
              <Plus size={16} /> Create sticker
            </button>
          </div>
          {!locations.length && (
            <button className="text-action" onClick={onOpenLocations}>
              Create a location first <Plus size={15} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
