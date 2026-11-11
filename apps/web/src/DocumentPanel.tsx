import { FormEvent, useEffect, useState } from "react";
import {
  ArrowDownToLine,
  Copy,
  Eye,
  FileText,
  History,
  MapPin,
  MessageSquare,
  Plus,
  Printer,
  RotateCw,
  Save,
  Tag as TagIcon,
  X,
} from "lucide-react";
import { Document, DocumentNote, FilingItem, Location, PhysicalCopy, request, Tag } from "./api";
import { Button, Field, Modal } from "./ui";

export default function DocumentPanel({
  initial,
  onClose,
  onSaved,
  onOpenTags,
  onOpenLocations,
  onOpenDuplicate,
}: {
  initial: Document;
  onClose: () => void;
  onSaved: (document: Document) => void;
  onOpenTags: () => void;
  onOpenLocations: () => void;
  onOpenDuplicate: (id: string) => void;
}) {
  const [current, setCurrent] = useState(initial);
  const [title, setTitle] = useState(initial.title);
  const [date, setDate] = useState(initial.document_date ?? "");
  const [correspondentId, setCorrespondentId] = useState(initial.correspondent?.id ?? "");
  const [documentTypeId, setDocumentTypeId] = useState(initial.document_type?.id ?? "");
  const [correspondents, setCorrespondents] = useState<FilingItem[]>([]);
  const [documentTypes, setDocumentTypes] = useState<FilingItem[]>([]);
  const [newCorrespondent, setNewCorrespondent] = useState("");
  const [newDocumentType, setNewDocumentType] = useState("");
  const [creatingCorrespondent, setCreatingCorrespondent] = useState(false);
  const [creatingDocumentType, setCreatingDocumentType] = useState(false);
  const [actionStatus, setActionStatus] = useState(initial.action_status);
  const [actionDueDate, setActionDueDate] = useState(initial.action_due_date ?? "");
  const [actionNote, setActionNote] = useState(initial.action_note);
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
  const [notes, setNotes] = useState<DocumentNote[]>([]);
  const [noteDraft, setNoteDraft] = useState("");
  const [nextNoteOffset, setNextNoteOffset] = useState<number | null>(null);
  const [notesBusy, setNotesBusy] = useState(false);
  const [notesLoading, setNotesLoading] = useState(true);
  const [noteError, setNoteError] = useState("");
  const [noteNotice, setNoteNotice] = useState("");
  const [deleteNoteId, setDeleteNoteId] = useState<string | null>(null);
  const [reprocessNotice, setReprocessNotice] = useState("");
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
    Promise.all([
      request<{ correspondents: FilingItem[] }>("/api/correspondents"),
      request<{ document_types: FilingItem[] }>("/api/document-types"),
    ]).then(([senders, types]) => {
      setCorrespondents(senders.correspondents);
      setDocumentTypes(types.document_types);
    }).catch((cause) => setError(cause instanceof Error ? cause.message : "Could not load filing details"));
  }, []);
  useEffect(() => {
    void loadNotes(0);
  }, [current.id]);
  useEffect(() => {
    if (current.status !== "pending" && current.status !== "processing") return;
    let active = true;
    const timer = window.setInterval(() => {
      void request<Document>(`/api/documents/${current.id}`).then((updated) => {
        if (!active) return;
        setCurrent(updated);
        if (updated.status === "ready" || updated.status === "failed") {
          onSaved(updated);
          setReprocessNotice(updated.status === "ready" ? "Searchable PDF is ready." : "OCR failed. You can retry it here.");
        }
      }).catch(() => {});
    }, 2500);
    return () => { active = false; window.clearInterval(timer); };
  }, [current.id, current.status]);

  async function loadNotes(offset: number) {
    setNotesLoading(true);
    try {
      const result = await request<{ notes: DocumentNote[]; next_offset: number | null }>(`/api/documents/${current.id}/notes?offset=${offset}`);
      setNotes((existing) => offset ? [...existing, ...result.notes] : result.notes);
      setNextNoteOffset(result.next_offset);
      setNoteError("");
    } catch (cause) {
      setNoteError(cause instanceof Error ? cause.message : "Could not load notes");
    } finally {
      setNotesLoading(false);
    }
  }

  async function addNote(event: FormEvent) {
    event.preventDefault();
    if (!noteDraft.trim()) return;
    setNotesBusy(true);
    setNoteError("");
    setNoteNotice("");
    try {
      await request(`/api/documents/${current.id}/notes`, { method: "POST", body: JSON.stringify({ body: noteDraft }) });
      setNoteDraft("");
      await loadNotes(0);
      onSaved(current);
      setNoteNotice("Note added.");
    } catch (cause) {
      setNoteError(cause instanceof Error ? cause.message : "Could not add note");
    } finally {
      setNotesBusy(false);
    }
  }

  async function deleteNote(id: string) {
    setNotesBusy(true);
    setNoteError("");
    setNoteNotice("");
    try {
      await request(`/api/documents/${current.id}/notes/${id}`, { method: "DELETE" });
      setDeleteNoteId(null);
      await loadNotes(0);
      onSaved(current);
      setNoteNotice("Note deleted.");
    } catch (cause) {
      setNoteError(cause instanceof Error ? cause.message : "Could not delete note");
    } finally {
      setNotesBusy(false);
    }
  }

  async function reprocess() {
    setBusy(true);
    setError("");
    setReprocessNotice("");
    try {
      const updated = await request<Document>(`/api/documents/${current.id}/reprocess`, { method: "POST" });
      setCurrent(updated);
      onSaved(updated);
      setReprocessNotice("OCR queued from the preserved original.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not queue OCR");
    } finally {
      setBusy(false);
    }
  }
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
      const changes: Record<string, unknown> = {
        title,
        document_date: date || null,
        action_status: actionStatus,
        action_due_date: actionDueDate || null,
        action_note: actionNote,
      };
      const previousTags = current.tags.map((tag) => tag.id).sort();
      const chosenTags = [...selected].sort();
      if (chosenTags.length !== previousTags.length || chosenTags.some((id, index) => id !== previousTags[index])) {
        changes.tags = selected;
      }
      if (correspondentId !== (current.correspondent?.id ?? "")) changes.correspondent_id = correspondentId || null;
      if (documentTypeId !== (current.document_type?.id ?? "")) changes.document_type_id = documentTypeId || null;
      const updated = await request<Document>(`/api/documents/${current.id}`, {
        method: "PATCH",
        body: JSON.stringify(changes),
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

  async function createFilingItem(kind: "correspondent" | "document_type") {
    const name = kind === "correspondent" ? newCorrespondent.trim() : newDocumentType.trim();
    if (!name) return;
    setBusy(true);
    setError("");
    try {
      const endpoint = kind === "correspondent" ? "/api/correspondents" : "/api/document-types";
      const item = await request<FilingItem>(endpoint, { method: "POST", body: JSON.stringify({ name }) });
      if (kind === "correspondent") {
        setCorrespondents((current) => [...current, item].sort((a, b) => a.name.localeCompare(b.name)));
        setCorrespondentId(item.id);
        setNewCorrespondent("");
        setCreatingCorrespondent(false);
      } else {
        setDocumentTypes((current) => [...current, item].sort((a, b) => a.name.localeCompare(b.name)));
        setDocumentTypeId(item.id);
        setNewDocumentType("");
        setCreatingDocumentType(false);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create filing detail");
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
    <Modal titleId="detail-heading" panelClassName="detail-panel" backdropClassName="detail-backdrop" onClose={onClose}>
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
        {current.duplicate_of && (
          <button
            className="duplicate-note"
            onClick={() => onOpenDuplicate(current.duplicate_of!.id)}
          >
            <Copy size={16} /> Exact copy of “{current.duplicate_of.title}” ·
            Open earlier copy
          </button>
        )}
        {error && (
          <div className="inline-error" role="alert">
            {error}
          </div>
        )}
        <form onSubmit={save}>
          <Field label="Title" className="detail-label">
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={300}
              required
            />
          </Field>
          <Field label="Document date" hint="Optional" className="detail-label">
            <input
              type="date"
              value={date}
              onChange={(event) => setDate(event.target.value)}
            />
          </Field>
          <Field label="From" hint={current.correspondent_origin === "rule" ? "Added by matching phrase · change it if needed" : "Optional sender or organization"} className="detail-label">
            <select value={correspondentId} onChange={(event) => setCorrespondentId(event.target.value)}>
              <option value="">No sender</option>
              {correspondents.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </Field>
          {creatingCorrespondent ? (
            <div className="filing-create">
              <input aria-label="New sender name" value={newCorrespondent} onChange={(event) => setNewCorrespondent(event.target.value)} maxLength={100} placeholder="e.g. City of Milan" />
              <Button type="button" variant="secondary" disabled={busy || !newCorrespondent.trim()} onClick={() => void createFilingItem("correspondent")}>Add sender</Button>
              <button type="button" aria-label="Cancel new sender" onClick={() => setCreatingCorrespondent(false)}><X size={16} /></button>
            </div>
          ) : <button type="button" className="text-action" onClick={() => setCreatingCorrespondent(true)}><Plus size={15} /> Add a sender</button>}
          <Field label="Document type" hint={current.document_type_origin === "rule" ? "Added by matching phrase · change it if needed" : "Optional"} className="detail-label">
            <select value={documentTypeId} onChange={(event) => setDocumentTypeId(event.target.value)}>
              <option value="">No type</option>
              {documentTypes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </Field>
          {creatingDocumentType ? (
            <div className="filing-create">
              <input aria-label="New document type name" value={newDocumentType} onChange={(event) => setNewDocumentType(event.target.value)} maxLength={100} placeholder="e.g. Insurance policy" />
              <Button type="button" variant="secondary" disabled={busy || !newDocumentType.trim()} onClick={() => void createFilingItem("document_type")}>Add type</Button>
              <button type="button" aria-label="Cancel new type" onClick={() => setCreatingDocumentType(false)}><X size={16} /></button>
            </div>
          ) : <button type="button" className="text-action" onClick={() => setCreatingDocumentType(true)}><Plus size={15} /> Add a type</button>}
          <Field label="Follow-up" hint="Optional" className="detail-label">
            <select value={actionStatus} onChange={(event) => setActionStatus(event.target.value as Document["action_status"])}>
              <option value="none">Nothing to do</option>
              <option value="open">Needs action</option>
              <option value="done">Completed</option>
            </select>
          </Field>
          {actionStatus === "open" && <>
            <Field label="Due date" hint="Optional" className="detail-label">
              <input type="date" value={actionDueDate} onChange={(event) => setActionDueDate(event.target.value)} />
            </Field>
            <Field label="What needs doing?" hint="Optional" className="detail-label">
              <input value={actionNote} onChange={(event) => setActionNote(event.target.value)} maxLength={500} placeholder="For example, pay by Friday" />
            </Field>
          </>}
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
                    "rule" && <small>Rule</small>}
                  {current.tags.find((item) => item.id === tag.id)?.origin ===
                    "model" && <small>Agent</small>}
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
          <Button className="detail-save" disabled={busy}>
            <Save size={17} /> {busy ? "Saving…" : "Save changes"}
          </Button>
        </form>
        <section className="detail-notes" aria-labelledby="document-notes-heading">
          <h3 id="document-notes-heading"><MessageSquare size={17} /> Notes</h3>
          <p>Keep context here without creating a follow-up.</p>
          {noteError && <div className="inline-error" role="alert">{noteError}</div>}
          {noteNotice && <p className="bulk-notice" role="status">{noteNotice}</p>}
          <form className="note-form" onSubmit={(event) => void addNote(event)}>
            <Field label="New note">
              <textarea value={noteDraft} onChange={(event) => setNoteDraft(event.target.value)} maxLength={2000} rows={3} placeholder="For example, original received in person" />
            </Field>
            <Button disabled={notesBusy || !noteDraft.trim()}><Plus size={16} /> Add note</Button>
          </form>
          {notesLoading && <p>Loading notes…</p>}
          {!notesLoading && !notes.length && <p>No notes yet.</p>}
          {notes.length > 0 && <ol className="note-list">
            {notes.map((note) => <li key={note.id}>
              <p>{note.body}</p>
              <div className="note-meta"><span>{note.author} · <time dateTime={note.created_at}>{new Date(note.created_at).toLocaleString()}</time></span>
                {deleteNoteId === note.id ? <span className="note-actions">
                  <button type="button" disabled={notesBusy} onClick={() => void deleteNote(note.id)}>Confirm delete</button>
                  <button type="button" disabled={notesBusy} onClick={() => setDeleteNoteId(null)}>Cancel</button>
                </span> : <button type="button" disabled={notesBusy} aria-label={`Delete note ${note.id}`} onClick={() => setDeleteNoteId(note.id)}>Delete</button>}
              </div>
            </li>)}
          </ol>}
          {nextNoteOffset !== null && <button type="button" className="text-action" disabled={notesLoading} onClick={() => void loadNotes(nextNoteOffset)}>Show older notes</button>}
        </section>
        <div className="detail-files">
          <h3>
            <FileText size={17} /> Files
          </h3>
          {reprocessNotice && <p className="bulk-notice" role="status">{reprocessNotice}</p>}
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
          {(current.status === "ready" || current.status === "failed") && (
            <Button type="button" variant="secondary" disabled={busy} onClick={() => void reprocess()}>
              <RotateCw size={16} /> {current.status === "failed" ? "Retry OCR" : "Run OCR again"}
            </Button>
          )}
          {(current.status === "pending" || current.status === "processing") && <p className="detail-processing">OCR is being prepared. The original is available above.</p>}
          {current.status === "failed" && current.error && <p className="inline-error">{current.error}</p>}
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
                <Button
                  variant="secondary"
                  disabled={busy}
                  onClick={() => void moveCopy(copy)}
                >
                  Move
                </Button>
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
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => void createCopy()}
            >
              <Plus size={16} /> Create sticker
            </Button>
          </div>
          {!locations.length && (
            <button className="text-action" onClick={onOpenLocations}>
              Create a location first <Plus size={15} />
            </button>
          )}
        </div>
    </Modal>
  );
}
