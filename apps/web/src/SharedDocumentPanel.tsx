import { FormEvent, useEffect, useState } from "react";
import { ArrowDownToLine, Eye, FileText, MessageSquare, Plus, Save, Users, X } from "lucide-react";
import { Document, DocumentNote, formatDate, request } from "./api";
import { Button, Field, Modal } from "./ui";

/** A document someone else owns and shared with the signed-in person. */
type SharedItem = { id: string; name: string; level: "view" | "edit"; owner: { id: number; name: string } };

export default function SharedDocumentPanel({ initial, username, onClose, onSaved }: {
  initial: Document;
  username: string | null;
  onClose: () => void;
  onSaved: (document: Document) => void;
}) {
  const [current, setCurrent] = useState(initial);
  const canEdit = current.access === "edit";
  // The owner's tags, senders, and types shared with me, for filing this document.
  const [filing, setFiling] = useState<{ tags: SharedItem[]; correspondents: SharedItem[]; document_types: SharedItem[] }>({ tags: [], correspondents: [], document_types: [] });
  const [sharedTagIds, setSharedTagIds] = useState<string[]>([]);
  const [senderId, setSenderId] = useState("");
  const [typeId, setTypeId] = useState("");
  useEffect(() => {
    if (!canEdit) return;
    request<{ tags: SharedItem[]; correspondents: SharedItem[]; document_types: SharedItem[] }>("/api/shared-filing").then((all) => {
      const mine = (items: SharedItem[]) => items.filter((item) => item.owner.id === current.shared_by_id);
      setFiling({ tags: mine(all.tags), correspondents: mine(all.correspondents), document_types: mine(all.document_types) });
    }).catch(() => undefined);
  }, [canEdit, current.shared_by_id]);
  useEffect(() => {
    setSharedTagIds(current.tags.map((tag) => tag.id));
    setSenderId(current.correspondent?.id ?? "");
    setTypeId(current.document_type?.id ?? "");
  }, [current]);
  const filingShared = filing.tags.length + filing.correspondents.length + filing.document_types.length > 0;
  const [title, setTitle] = useState(initial.title);
  const [date, setDate] = useState(initial.document_date ?? "");
  const [actionStatus, setActionStatus] = useState(initial.action_status);
  const [actionDueDate, setActionDueDate] = useState(initial.action_due_date ?? "");
  const [actionNote, setActionNote] = useState(initial.action_note);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [notes, setNotes] = useState<DocumentNote[]>([]);
  const [nextNoteOffset, setNextNoteOffset] = useState<number | null>(null);
  const [notesLoading, setNotesLoading] = useState(true);
  const [noteDraft, setNoteDraft] = useState("");
  const [noteError, setNoteError] = useState("");
  const [noteNotice, setNoteNotice] = useState("");
  const [deleteNoteId, setDeleteNoteId] = useState<string | null>(null);

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

  useEffect(() => { void loadNotes(0); }, [current.id]);

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const updated = await request<Document>(`/api/documents/${current.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title, document_date: date || null, action_status: actionStatus,
          action_due_date: actionStatus === "open" && actionDueDate ? actionDueDate : null,
          action_note: actionStatus === "open" ? actionNote : "",
          ...(filing.tags.length ? { tags: sharedTagIds.filter((id) => filing.tags.some((tag) => tag.id === id)) } : {}),
          ...(senderId && senderId !== (current.correspondent?.id ?? "") ? { correspondent_id: senderId } : {}),
          ...(typeId && typeId !== (current.document_type?.id ?? "") ? { document_type_id: typeId } : {}),
        }),
      });
      setCurrent(updated);
      onSaved(updated);
      setNotice("Changes saved.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save changes");
    } finally {
      setBusy(false);
    }
  }

  async function noteAction(action: () => Promise<unknown>, message: string) {
    setNoteError("");
    setNoteNotice("");
    setBusy(true);
    try {
      await action();
      await loadNotes(0);
      setNoteNotice(message);
    } catch (cause) {
      setNoteError(cause instanceof Error ? cause.message : "Could not change notes");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal titleId="shared-detail-heading" panelClassName="detail-panel" backdropClassName="detail-backdrop" onClose={onClose}>
      <button className="modal-close" onClick={onClose} aria-label="Close"><X size={20} /></button>
      <div className="eyebrow"><span className="eyebrow-line" /> SHARED WITH YOU</div>
      <h2 id="shared-detail-heading">{current.title}</h2>
      <p className="email-origin">
        <Users size={16} aria-hidden="true" />
        <span>Shared by {current.shared_by} · {canEdit ? "you can edit its details and add notes" : "you can view it"}</span>
      </p>
      <dl className="shared-facts">
        {current.correspondent && <><dt>From</dt><dd>{current.correspondent.name}</dd></>}
        {current.document_type && <><dt>Type</dt><dd>{current.document_type.name}</dd></>}
        {current.tags.length > 0 && <><dt>Tags</dt><dd>{current.tags.map((tag) => tag.name).join(", ")}</dd></>}
        <dt>Added</dt><dd>{formatDate(current.created_at)}</dd>
      </dl>
      {error && <div className="inline-error" role="alert">{error}</div>}
      {notice && <p className="bulk-notice" role="status">{notice}</p>}
      {canEdit ? (
        <form onSubmit={(event) => void save(event)}>
          <Field label="Title" className="detail-label">
            <input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={300} required />
          </Field>
          <Field label="Document date" hint="Optional" className="detail-label">
            <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
          </Field>
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
              <input value={actionNote} onChange={(event) => setActionNote(event.target.value)} maxLength={500} />
            </Field>
          </>}
          {filingShared && <fieldset className="shared-filing">
            <legend>Filing <small>With the tags, senders, and types {current.shared_by} shared with you</small></legend>
            {filing.tags.length > 0 && <div className="workflow-choices mail-tags" role="group" aria-label="Shared tags">
              {filing.tags.map((tag) => <label className="agent-scope-choice" key={tag.id}>
                <input type="checkbox" checked={sharedTagIds.includes(tag.id)} onChange={() => setSharedTagIds((ids) => ids.includes(tag.id) ? ids.filter((id) => id !== tag.id) : [...ids, tag.id])} />{tag.name}
              </label>)}
            </div>}
            {filing.correspondents.length > 0 && <Field label="Sender" className="detail-label">
              <select value={senderId} onChange={(event) => setSenderId(event.target.value)}>
                <option value="">{current.correspondent && !filing.correspondents.some((item) => item.id === current.correspondent?.id) ? current.correspondent.name : "Not set"}</option>
                {filing.correspondents.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </Field>}
            {filing.document_types.length > 0 && <Field label="Type" className="detail-label">
              <select value={typeId} onChange={(event) => setTypeId(event.target.value)}>
                <option value="">{current.document_type && !filing.document_types.some((item) => item.id === current.document_type?.id) ? current.document_type.name : "Not set"}</option>
                {filing.document_types.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </Field>}
          </fieldset>}
          <Button className="detail-save" disabled={busy}><Save size={17} /> {busy ? "Saving…" : "Save changes"}</Button>
        </form>
      ) : (
        <dl className="shared-facts">
          <dt>Document date</dt><dd>{current.document_date ? formatDate(`${current.document_date}T00:00:00`) : "Not set"}</dd>
          {current.action_status === "open" && <><dt>Follow-up</dt><dd>Needs action{current.action_due_date ? ` by ${formatDate(`${current.action_due_date}T00:00:00`)}` : ""}{current.action_note ? ` · ${current.action_note}` : ""}</dd></>}
        </dl>
      )}
      <section className="detail-notes" aria-labelledby="shared-notes-heading">
        <h3 id="shared-notes-heading"><MessageSquare size={17} /> Notes</h3>
        {noteError && <div className="inline-error" role="alert">{noteError}</div>}
        {noteNotice && <p className="bulk-notice" role="status">{noteNotice}</p>}
        {canEdit && <form className="note-form" onSubmit={(event) => {
          event.preventDefault();
          if (noteDraft.trim()) void noteAction(() => request(`/api/documents/${current.id}/notes`, { method: "POST", body: JSON.stringify({ body: noteDraft }) }).then(() => setNoteDraft("")), "Note added.");
        }}>
          <Field label="New note">
            <textarea value={noteDraft} onChange={(event) => setNoteDraft(event.target.value)} maxLength={2000} rows={3} />
          </Field>
          <Button disabled={busy || !noteDraft.trim()}><Plus size={16} /> Add note</Button>
        </form>}
        {notesLoading && <p>Loading notes…</p>}
        {!notesLoading && !notes.length && <p>No notes yet.</p>}
        {notes.length > 0 && <ol className="note-list">
          {notes.map((note) => <li key={note.id}>
            <p>{note.body}</p>
            <div className="note-meta"><span>{note.author} · <time dateTime={note.created_at}>{new Date(note.created_at).toLocaleString()}</time></span>
              {canEdit && note.author === username && (deleteNoteId === note.id ? <span className="note-actions">
                <button type="button" disabled={busy} onClick={() => void noteAction(() => request(`/api/documents/${current.id}/notes/${note.id}`, { method: "DELETE" }).then(() => setDeleteNoteId(null)), "Note deleted.")}>Confirm delete</button>
                <button type="button" disabled={busy} onClick={() => setDeleteNoteId(null)}>Cancel</button>
              </span> : <button type="button" disabled={busy} onClick={() => setDeleteNoteId(note.id)}>Delete</button>)}
            </div>
          </li>)}
        </ol>}
        {nextNoteOffset !== null && <button type="button" className="text-action" disabled={notesLoading} onClick={() => void loadNotes(nextNoteOffset)}>Show older notes</button>}
      </section>
      <div className="detail-files">
        <h3><FileText size={17} /> Files</h3>
        <a href={`/api/documents/${current.id}/original`}><ArrowDownToLine size={17} /> Download original</a>
        {current.archive_available && <a href={`/api/documents/${current.id}/archive`} target="_blank" rel="noreferrer"><Eye size={17} /> Open searchable PDF</a>}
      </div>
    </Modal>
  );
}
