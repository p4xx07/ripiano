import { FormEvent, useEffect, useState } from "react";
import {
  ArrowDownToLine,
  Building2,
  Copy,
  Eye,
  FileText,
  History,
  Layers,
  Mail,
  MapPin,
  MessageSquare,
  Plus,
  Printer,
  RotateCw,
  Save,
  Tag as TagIcon,
  Trash2,
  X,
} from "lucide-react";
import { Document, DocumentNote, FilingItem, FilingSuggestion, FilingSuggestions, Location, PhysicalCopy, request, suggestionBasis, Tag, tagPathLabel } from "./api";
import { Button, Field, Modal } from "./ui";
import DocumentLinks from "./DocumentLinks";
import DocumentHistory from "./DocumentHistory";
import CustomFieldsPanel from "./CustomFieldsPanel";
import ShareLinksPanel from "./ShareLinksPanel";
import DocumentAccessPanel from "./DocumentAccessPanel";
import PagesPanel from "./PagesPanel";
import SimilarPanel from "./SimilarPanel";
import EmailDocumentPanel from "./EmailDocumentPanel";
import { useMessages } from "./i18n";
import messages from "./locales/DocumentPanel";

export default function DocumentPanel({
  initial,
  onClose,
  onSaved,
  onOpenTags,
  onOpenLocations,
  onOpenDuplicate,
  onTrashed,
}: {
  initial: Document;
  onClose: () => void;
  onSaved: (document: Document) => void;
  onOpenTags: () => void;
  onOpenLocations: () => void;
  onOpenDuplicate: (id: string) => void;
  onTrashed: () => void;
}) {
  const m = useMessages(messages);
  const [current, setCurrent] = useState(initial);
  const [title, setTitle] = useState(initial.title);
  const [date, setDate] = useState(initial.document_date ?? "");
  const [asn, setAsn] = useState(initial.asn ? String(initial.asn) : "");
  const [correspondentId, setCorrespondentId] = useState(initial.correspondent?.id ?? "");
  const [documentTypeId, setDocumentTypeId] = useState(initial.document_type?.id ?? "");
  const [storagePathId, setStoragePathId] = useState(initial.storage_path?.id ?? "");
  const [storagePaths, setStoragePaths] = useState<FilingItem[]>([]);
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
  const [suggestions, setSuggestions] = useState<FilingSuggestions | null>(null);
  const [suggestionStatus, setSuggestionStatus] = useState("");
  const availableById = new Map(available.map((tag) => [tag.id, tag]));
  const sortedAvailable = [...available].sort((a, b) =>
    tagPathLabel(a, availableById).localeCompare(tagPathLabel(b, availableById)));
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
  const [copyNotice, setCopyNotice] = useState("");
  const [confirmTrash, setConfirmTrash] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    request<{ tags: Tag[] }>("/api/tags")
      .then((result) => setAvailable(result.tags))
      .catch((cause) => setError(cause.message));
  }, []);
  useEffect(() => {
    setSuggestions(null);
    setSuggestionStatus("");
    if (current.status !== "ready") return;
    let active = true;
    request<FilingSuggestions>(`/api/documents/${current.id}/filing-suggestions`)
      .then((result) => { if (active) setSuggestions(result); })
      .catch(() => { if (active) setSuggestions(null); });
    return () => { active = false; };
  }, [current.id, current.status]);
  useEffect(() => {
    request<{ locations: Location[] }>("/api/locations")
      .then((result) => setLocations(result.locations))
      .catch((cause) => setError(cause.message));
  }, []);
  useEffect(() => {
    Promise.all([
      request<{ correspondents: FilingItem[] }>("/api/correspondents"),
      request<{ document_types: FilingItem[] }>("/api/document-types"),
      request<{ storage_paths: FilingItem[] }>("/api/storage-paths").then((result) => setStoragePaths(result.storage_paths)).catch(() => undefined),
    ]).then(([senders, types]) => {
      setCorrespondents(senders.correspondents);
      setDocumentTypes(types.document_types);
    }).catch((cause) => setError(cause instanceof Error ? cause.message : m.loadFilingError));
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
          setReprocessNotice(updated.status === "ready" ? m.searchableReady : m.ocrFailedRetry);
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
      setNoteError(cause instanceof Error ? cause.message : m.loadNotesError);
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
      setNoteNotice(m.noteAdded);
    } catch (cause) {
      setNoteError(cause instanceof Error ? cause.message : m.addNoteError);
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
      setNoteNotice(m.noteDeleted);
    } catch (cause) {
      setNoteError(cause instanceof Error ? cause.message : m.deleteNoteError);
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
      setReprocessNotice(m.ocrQueued);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.queueOcrError);
    } finally {
      setBusy(false);
    }
  }
  async function moveToTrash() {
    setBusy(true);
    setError("");
    try {
      await request(`/api/documents/${current.id}/trash`, { method: "POST" });
      onTrashed();
      onClose();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.trashError);
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
      const asnText = asn.trim();
      if (asnText && !/^\d{1,9}$/.test(asnText)) throw new Error(m.asnInvalid);
      if (asnText !== (current.asn ? String(current.asn) : "")) changes.asn = asnText ? Number(asnText) : null;
      if (correspondentId !== (current.correspondent?.id ?? "")) changes.correspondent_id = correspondentId || null;
      if (documentTypeId !== (current.document_type?.id ?? "")) changes.document_type_id = documentTypeId || null;
      if (storagePathId !== (current.storage_path?.id ?? "")) changes.storage_path_id = storagePathId || null;
      const updated = await request<Document>(`/api/documents/${current.id}`, {
        method: "PATCH",
        body: JSON.stringify(changes),
      });
      setCurrent(updated);
      onSaved(updated);
      onClose();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : m.saveError,
      );
    } finally {
      setBusy(false);
    }
  }

  // The inline "add" controls replace the button that opened them, so focus is placed explicitly
  // once React has rendered the next control (otherwise it falls to <body>).
  function focusSoon(id: string) {
    requestAnimationFrame(() => document.getElementById(id)?.focus());
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
        focusSoon("detail-correspondent");
      } else {
        setDocumentTypes((current) => [...current, item].sort((a, b) => a.name.localeCompare(b.name)));
        setDocumentTypeId(item.id);
        setNewDocumentType("");
        setCreatingDocumentType(false);
        focusSoon("detail-document-type");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.createFilingError);
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
        cause instanceof Error ? cause.message : m.createStickerError,
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
        cause instanceof Error ? cause.message : m.moveCopyError,
      );
    } finally {
      setBusy(false);
    }
  }

  async function setCopyMissing(copy: PhysicalCopy, missing: boolean) {
    setBusy(true);
    setError("");
    setCopyNotice("");
    try {
      await request(`/api/copies/${copy.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ missing }),
      });
      await refreshCopies();
      await showHistory(copy);
      setCopyNotice(missing ? m.copyMarkedMissing(copy.sticker_code) : m.copyMarkedFound(copy.sticker_code));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.copyStatusError);
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
          : m.historyError,
      );
    }
  }

  const suggestedTags = suggestions?.tags.filter((item) => !selected.includes(item.id)) ?? [];
  const suggestedSenders = correspondentId ? [] : suggestions?.correspondents ?? [];
  const suggestedTypes = documentTypeId ? [] : suggestions?.document_types ?? [];
  async function acceptSuggestion(kind: "tag" | "sender" | "type", item: FilingSuggestion) {
    setBusy(true);
    setError("");
    setSuggestionStatus("");
    const fieldId = kind === "tag" ? `detail-tag-${item.id}` : kind === "sender" ? "detail-correspondent" : "detail-document-type";
    try {
      const body = kind === "tag" ? { add_tag_id: item.id } : kind === "sender" ? { correspondent_id: item.id } : { document_type_id: item.id };
      const updated = await request<Document>(`/api/documents/${current.id}`, { method: "PATCH", body: JSON.stringify(body) });
      const oldTags = new Set(current.tags.map((tag) => tag.id));
      setSelected((draft) => {
        const next = new Set(updated.tags.map((tag) => tag.id));
        for (const id of oldTags) if (!draft.includes(id)) next.delete(id);
        for (const id of draft) if (!oldTags.has(id)) next.add(id);
        return [...next];
      });
      setCorrespondentId((draft) => kind === "sender" || draft === (current.correspondent?.id ?? "") ? updated.correspondent?.id ?? "" : draft);
      setDocumentTypeId((draft) => kind === "type" || draft === (current.document_type?.id ?? "") ? updated.document_type?.id ?? "" : draft);
      setCurrent(updated);
      onSaved(updated);
      setSuggestionStatus(m.suggestionSaved(kind, item.name));
      requestAnimationFrame(() => document.getElementById(fieldId)?.focus());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.saveSuggestionError);
    } finally {
      setBusy(false);
    }
  }
  const visibleSuggestions = suggestedTags.length + suggestedSenders.length + suggestedTypes.length > 0;

  return (
    <Modal titleId="detail-heading" panelClassName="detail-panel" backdropClassName="detail-backdrop" onClose={onClose}>
        <button className="modal-close" onClick={onClose} aria-label={m.close}>
          <X size={20} />
        </button>
        <div className="eyebrow">
          <span className="eyebrow-line" /> {m.eyebrow}
        </div>
        {/* The dialog is named by the document, so screen-reader users know which one is open. */}
        <h2 id="detail-heading" className="detail-title">{current.title}</h2>
        <p className="detail-intro">
          <strong className="detail-tagline">{m.heading}</strong> {m.intro}
        </p>
        {current.duplicate_of && (
          <button
            className="duplicate-note"
            onClick={() => onOpenDuplicate(current.duplicate_of!.id)}
          >
            <Copy size={16} /> {m.exactCopy(current.duplicate_of.title)}
          </button>
        )}
        {current.split_parent && (
          <button type="button" className="split-note" onClick={() => onOpenDuplicate(current.split_parent!.id)}>
            <Layers size={16} aria-hidden="true" /> {m.splitPart}
          </button>
        )}
        {current.is_split_source && (
          <p className="email-origin"><Layers size={16} aria-hidden="true" /> {m.splitSource}</p>
        )}
        {current.email && (
          <p className="email-origin">
            <Mail size={16} aria-hidden="true" />
            <span>
              {m.fromEmail}{current.email.sender ? ` · ${current.email.sender}` : ""}
              {current.email.subject && <> · “{current.email.subject}”</>}
              <small>{current.email.account}{current.email.received_at ? ` · ${new Date(current.email.received_at).toLocaleString()}` : ""}</small>
            </span>
          </p>
        )}
        {error && (
          <div className="inline-error" role="alert">
            {error}
          </div>
        )}
        <form onSubmit={save}>
          <Field label={m.title} className="detail-label">
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={300}
              required
            />
          </Field>
          <Field label={m.asn} hint={m.asnHint} className="detail-label">
            <input inputMode="numeric" pattern="[0-9]*" maxLength={9} value={asn} onChange={(event) => setAsn(event.target.value)} />
          </Field>
          <Field label={m.documentDate} hint={m.optional} className="detail-label">
            <input
              type="date"
              value={date}
              onChange={(event) => setDate(event.target.value)}
            />
          </Field>
          {visibleSuggestions && (
            <section className="filing-suggestions" aria-labelledby="filing-suggestions-heading">
              <h3 id="filing-suggestions-heading">{m.suggestionsHeading}</h3>
              <p>{m.suggestionsIntro}</p>
              {suggestedTags.map((item) => (
                <button type="button" disabled={busy} key={`tag-${item.id}`} aria-label={m.addTag(item.name)} aria-describedby={`suggestion-tag-${item.id}`} onClick={() => void acceptSuggestion("tag", item)}>
                  <span className="suggestion-action"><TagIcon size={16} aria-hidden="true" /><span>{m.addTag(item.name)}</span></span>
                  <small id={`suggestion-tag-${item.id}`}>{suggestionBasis(item, m)}</small>
                </button>
              ))}
              {suggestedSenders.map((item) => (
                <button type="button" disabled={busy} key={`sender-${item.id}`} aria-label={m.setSender(item.name)} aria-describedby={`suggestion-sender-${item.id}`} onClick={() => void acceptSuggestion("sender", item)}>
                  <span className="suggestion-action"><Building2 size={16} aria-hidden="true" /><span>{m.setSender(item.name)}</span></span>
                  <small id={`suggestion-sender-${item.id}`}>{suggestionBasis(item, m)}</small>
                </button>
              ))}
              {suggestedTypes.map((item) => (
                <button type="button" disabled={busy} key={`type-${item.id}`} aria-label={m.setType(item.name)} aria-describedby={`suggestion-type-${item.id}`} onClick={() => void acceptSuggestion("type", item)}>
                  <span className="suggestion-action"><FileText size={16} aria-hidden="true" /><span>{m.setType(item.name)}</span></span>
                  <small id={`suggestion-type-${item.id}`}>{suggestionBasis(item, m)}</small>
                </button>
              ))}
            </section>
          )}
          {suggestionStatus && <p className="visually-hidden" role="status">{suggestionStatus}</p>}
          <Field label={m.from} hint={current.correspondent_origin === "rule" ? m.originRule : current.correspondent_origin === "source" ? m.originSource : current.correspondent_origin === "model" ? m.originModel : current.correspondent_origin === "learned" ? m.originLearned : m.senderHint} className="detail-label">
            <select id="detail-correspondent" value={correspondentId} onChange={(event) => setCorrespondentId(event.target.value)}>
              <option value="">{m.noSender}</option>
              {correspondents.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </Field>
          {creatingCorrespondent ? (
            <div className="filing-create">
              <input id="detail-new-sender" autoFocus aria-label={m.newSenderName} value={newCorrespondent} onChange={(event) => setNewCorrespondent(event.target.value)} maxLength={100} placeholder={m.senderPlaceholder} />
              <Button type="button" variant="secondary" disabled={busy || !newCorrespondent.trim()} onClick={() => void createFilingItem("correspondent")}>{m.addSender}</Button>
              <button type="button" aria-label={m.cancelNewSender} onClick={() => { setCreatingCorrespondent(false); focusSoon("detail-add-sender"); }}><X size={16} /></button>
            </div>
          ) : <button type="button" id="detail-add-sender" className="text-action" onClick={() => setCreatingCorrespondent(true)}><Plus size={15} /> {m.addASender}</button>}
          <Field label={m.documentType} hint={current.document_type_origin === "rule" ? m.originRule : current.document_type_origin === "source" ? m.originSource : current.document_type_origin === "model" ? m.originModel : current.document_type_origin === "learned" ? m.originLearned : m.optional} className="detail-label">
            <select id="detail-document-type" value={documentTypeId} onChange={(event) => setDocumentTypeId(event.target.value)}>
              <option value="">{m.noType}</option>
              {documentTypes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </Field>
          {creatingDocumentType ? (
            <div className="filing-create">
              <input id="detail-new-type" autoFocus aria-label={m.newTypeName} value={newDocumentType} onChange={(event) => setNewDocumentType(event.target.value)} maxLength={100} placeholder={m.typePlaceholder} />
              <Button type="button" variant="secondary" disabled={busy || !newDocumentType.trim()} onClick={() => void createFilingItem("document_type")}>{m.addType}</Button>
              <button type="button" aria-label={m.cancelNewType} onClick={() => { setCreatingDocumentType(false); focusSoon("detail-add-type"); }}><X size={16} /></button>
            </div>
          ) : <button type="button" id="detail-add-type" className="text-action" onClick={() => setCreatingDocumentType(true)}><Plus size={15} /> {m.addAType}</button>}
          {storagePaths.length > 0 && (
            <Field label={m.storagePath} hint={m.storagePathHint} className="detail-label">
              <select value={storagePathId} onChange={(event) => setStoragePathId(event.target.value)}>
                <option value="">{m.byYear}</option>
                {storagePaths.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </Field>
          )}
          <Field label={m.followUp} hint={m.optional} className="detail-label">
            <select value={actionStatus} onChange={(event) => setActionStatus(event.target.value as Document["action_status"])}>
              <option value="none">{m.nothingToDo}</option>
              <option value="open">{m.needsAction}</option>
              <option value="done">{m.completed}</option>
            </select>
          </Field>
          {actionStatus === "open" && <>
            <Field label={m.dueDate} hint={m.optional} className="detail-label">
              <input type="date" value={actionDueDate} onChange={(event) => setActionDueDate(event.target.value)} />
            </Field>
            <Field label={m.whatNeedsDoing} hint={m.optional} className="detail-label">
              <input value={actionNote} onChange={(event) => setActionNote(event.target.value)} maxLength={500} placeholder={m.actionPlaceholder} />
            </Field>
          </>}
          <div className="detail-label">
            {m.tags} <small>{current.tags.some((tag) => tag.origin === "learned") ? m.tagsLearned : m.tagsHint}</small>
          </div>
          {available.length ? (
            <div className="tag-choices">
              {sortedAvailable.map((tag) => (
                <label className="tag-choice" key={tag.id}>
                  <input
                    id={`detail-tag-${tag.id}`}
                    type="checkbox"
                    checked={selected.includes(tag.id)}
                    onChange={() => toggle(tag.id)}
                  />
                  <span
                    className="tag-color"
                    style={{ background: tag.color }}
                  />
                  {tagPathLabel(tag, availableById)}
                  {current.tags.find((item) => item.id === tag.id)?.origin ===
                    "rule" && <small>{m.originRuleBadge}</small>}
                  {current.tags.find((item) => item.id === tag.id)?.origin ===
                    "model" && <small>{m.originAgentBadge}</small>}
                  {current.tags.find((item) => item.id === tag.id)?.origin ===
                    "source" && <small>{m.originEmailBadge}</small>}
                </label>
              ))}
            </div>
          ) : (
            <button
              type="button"
              className="detail-create-tag"
              onClick={onOpenTags}
            >
              <TagIcon size={17} /> {m.createFirstTag}
            </button>
          )}
          <Button className="detail-save" disabled={busy}>
            <Save size={17} /> {busy ? m.saving : m.saveChanges}
          </Button>
        </form>
        <CustomFieldsPanel documentId={current.id} onChanged={() => { onSaved(current); setCurrent((value) => ({ ...value })); }} />
        <section className="detail-notes" aria-labelledby="document-notes-heading">
          <h3 id="document-notes-heading"><MessageSquare size={17} /> {m.notes}</h3>
          <p>{m.notesIntro}</p>
          {noteError && <div className="inline-error" role="alert">{noteError}</div>}
          {noteNotice && <p className="bulk-notice" role="status">{noteNotice}</p>}
          <form className="note-form" onSubmit={(event) => void addNote(event)}>
            <Field label={m.newNote}>
              <textarea value={noteDraft} onChange={(event) => setNoteDraft(event.target.value)} maxLength={2000} rows={3} placeholder={m.notePlaceholder} />
            </Field>
            <Button disabled={notesBusy || !noteDraft.trim()}><Plus size={16} /> {m.addNote}</Button>
          </form>
          {notesLoading && <p>{m.loadingNotes}</p>}
          {!notesLoading && !notes.length && <p>{m.noNotes}</p>}
          {notes.length > 0 && <ol className="note-list">
            {notes.map((note) => <li key={note.id}>
              <p>{note.body}</p>
              <div className="note-meta"><span>{note.author} · <time dateTime={note.created_at}>{new Date(note.created_at).toLocaleString()}</time></span>
                {deleteNoteId === note.id ? <span className="note-actions">
                  <button type="button" disabled={notesBusy} onClick={() => void deleteNote(note.id)}>{m.confirmDelete}</button>
                  <button type="button" disabled={notesBusy} onClick={() => setDeleteNoteId(null)}>{m.cancel}</button>
                </span> : <button type="button" disabled={notesBusy} aria-label={m.deleteNoteLabel(note.id)} onClick={() => setDeleteNoteId(note.id)}>{m.delete}</button>}
              </div>
            </li>)}
          </ol>}
          {nextNoteOffset !== null && <button type="button" className="text-action" disabled={notesLoading} onClick={() => void loadNotes(nextNoteOffset)}>{m.showOlderNotes}</button>}
        </section>
        <DocumentHistory documentId={current.id} refreshKey={current} />
        <DocumentLinks documentId={current.id} onOpenDocument={onOpenDuplicate} />
        <div className="detail-files">
          <h3>
            <FileText size={17} /> {m.files}
          </h3>
          {reprocessNotice && <p className="bulk-notice" role="status">{reprocessNotice}</p>}
          <a href={`/api/documents/${current.id}/original`}>
            <ArrowDownToLine size={17} /> {m.downloadOriginal}
          </a>
          <a href={`/api/documents/${current.id}/export`}>
            <ArrowDownToLine size={17} /> {m.exportZip}
          </a>
          {current.archive_available && (
            <a
              href={`/api/documents/${current.id}/archive`}
              target="_blank"
              rel="noreferrer"
            >
              <Eye size={17} /> {m.openSearchable}
            </a>
          )}
          {(current.status === "ready" || current.status === "failed") && (
            <Button type="button" variant="secondary" disabled={busy} onClick={() => void reprocess()}>
              <RotateCw size={16} /> {current.status === "failed" ? m.retryOcr : m.runOcrAgain}
            </Button>
          )}
          {(current.status === "pending" || current.status === "processing") && <p className="detail-processing">{m.ocrPreparing}</p>}
          {current.status === "failed" && current.error && <p className="inline-error">{current.error}</p>}
        </div>
        {!current.is_split_source && (
          <PagesPanel
            documentId={current.id}
            ready={current.status === "ready"}
            editable={current.status === "ready" || current.status === "failed"}
            onOpenDocument={onOpenDuplicate}
            onChanged={() => {
              void request<Document>(`/api/documents/${current.id}`).then((fresh) => { setCurrent(fresh); onSaved(fresh); }).catch(() => undefined);
            }}
          />
        )}
        <SimilarPanel documentId={current.id} ready={current.status === "ready"} onOpenDocument={onOpenDuplicate} />
        <DocumentAccessPanel documentId={current.id} />
        <ShareLinksPanel documentId={current.id} />
        <EmailDocumentPanel documentId={current.id} searchableReady={current.archive_available} />
        <div className="detail-files physical-copies">
          <h3>
            <MapPin size={17} /> {m.paperCopies}
          </h3>
          {copyNotice && <p className="bulk-notice" role="status">{copyNotice}</p>}
          {!copies.length && (
            <p>{m.digitalOnly}</p>
          )}
          {copies.map((copy) => (
            <div className={`copy-card ${copy.missing_at ? "copy-card-missing" : ""}`} key={copy.id}>
              <strong>{copy.sticker_code}</strong>
              <span>
                {copy.missing_at ? m.lastKnown : ""}{copy.location_path.join(" / ") || m.locationNotAssigned}
              </span>
              {copy.missing_at && <span className="copy-missing-label">{m.reportedMissing}</span>}
              <div className="copy-actions">
                <a
                  href={`/api/copies/${copy.id}/label`}
                  target="_blank"
                  rel="noreferrer"
                >
                  <Printer size={16} /> {m.printSticker}
                </a>
                <button onClick={() => void showHistory(copy)}>
                  <History size={16} /> {m.history}
                </button>
                <button type="button" disabled={busy} onClick={() => void setCopyMissing(copy, !copy.missing_at)}>
                  {copy.missing_at ? m.markFound : m.markMissing}
                </button>
              </div>
              <div className="copy-move">
                <select
                  aria-label={m.moveCopyTo(copy.sticker_code)}
                  disabled={busy || Boolean(copy.missing_at)}
                  value={moveChoices[copy.id] ?? copy.location_id ?? ""}
                  onChange={(event) =>
                    setMoveChoices((value) => ({
                      ...value,
                      [copy.id]: event.target.value,
                    }))
                  }
                >
                  <option value="">{m.noLocation}</option>
                  {locations.map((location) => (
                    <option key={location.id} value={location.id}>
                      {location.path.join(" / ")}
                    </option>
                  ))}
                </select>
                <Button
                  variant="secondary"
                  disabled={busy || Boolean(copy.missing_at)}
                  onClick={() => void moveCopy(copy)}
                >
                  {m.move}
                </Button>
              </div>
              {copy.missing_at && <p className="copy-missing-hint">{m.markFoundFirst}</p>}
              {histories[copy.id] && (
                <div className="copy-history">
                  {histories[copy.id].map((move, index) => (
                    <div key={index}>
                      {new Date(move.at).toLocaleDateString()} ·{" "}
                      {move.to.join(" / ") || m.noLocation}
                      {move.note && ` · ${move.note}`}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          <div className="new-copy">
            <select
              aria-label={m.newCopyLocation}
              value={newLocation}
              onChange={(event) => setNewLocation(event.target.value)}
            >
              <option value="">{m.noLocationYet}</option>
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
              <Plus size={16} /> {m.createSticker}
            </Button>
          </div>
          {!locations.length && (
            <button className="text-action" onClick={onOpenLocations}>
              {m.createLocationFirst} <Plus size={15} />
            </button>
          )}
        </div>
        <div className="detail-files trash-action">
          <h3><Trash2 size={17} /> {m.moveToTrash}</h3>
          <p>{m.trashIntro}</p>
          {confirmTrash ? <div className="trash-confirm">
            <strong>{m.trashConfirm(current.title)}</strong>
            {copies.length > 0 && <p>{m.trashStickers(copies.length)}</p>}
            <Button type="button" disabled={busy} onClick={() => void moveToTrash()}><Trash2 size={16} /> {m.confirmMove}</Button>
            <Button type="button" variant="secondary" disabled={busy} onClick={() => setConfirmTrash(false)}>{m.cancel}</Button>
          </div> : <Button type="button" variant="secondary" disabled={busy} onClick={() => setConfirmTrash(true)}><Trash2 size={16} /> {m.moveToTrash}</Button>}
        </div>
    </Modal>
  );
}
