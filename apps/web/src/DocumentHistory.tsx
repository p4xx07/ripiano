import { useEffect, useState } from "react";
import { History } from "lucide-react";
import { formatDate, formatDateTime, request } from "./api";
import { useMessages } from "./i18n";
import messages from "./locales/DocumentHistory";

type Change = { field: string; name?: string; kind?: string; from: string | string[] | null; to: string | string[] | null };
export type DocumentEvent = {
  id: string;
  created_at: string;
  action: "created" | "updated" | "filed_automatically" | "version_added" | "trashed" | "restored";
  actor: { kind: string; name: string; user: string | null };
  changes: Change[];
};

const COLLAPSED = 5;
const BRANDS: Record<string, string> = { gdrive: "Google Drive", onedrive: "OneDrive", dropbox: "Dropbox" };

/** The document's audit history: who changed which details, newest first. */
export default function DocumentHistory({ documentId, refreshKey }: { documentId: string; refreshKey?: unknown }) {
  const m = useMessages(messages);
  const [events, setEvents] = useState<DocumentEvent[]>([]);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState("");

  async function load(offset: number) {
    setLoading(true);
    setError("");
    try {
      const result = await request<{ events: DocumentEvent[]; next_offset: number | null }>(
        `/api/documents/${documentId}/history${offset ? `?offset=${offset}` : ""}`);
      setEvents((value) => (offset ? [...value, ...result.events] : result.events));
      setNextOffset(result.next_offset);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.loadError);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(0);
  }, [documentId, refreshKey]);

  function actor(event: DocumentEvent) {
    const { kind, name, user } = event.actor;
    if (kind === "agent") return m.agent(name);
    if (kind === "workflow") return m.workflow(name);
    if (kind === "email_rule") return name ? m.emailRule(name) : m.emailImport;
    if (kind === "source") return name ? m.source(name) : m.sourceImport;
    if (kind === "matching_rules") return m.matchingRules;
    if (kind === "learned_filing") return m.learnedFiling;
    if (kind === "barcodes") return m.barcodes;
    if (kind === "detection") return m.detection;
    return user ?? m.removedPerson;
  }

  function sourceLabel(value: string) {
    const labels: Record<string, string> = {
      web: m.sourceWeb, telegram: m.sourceTelegram, android: m.sourceAndroid, folder: m.sourceFolder,
      email: m.sourceEmail, s3: m.sourceS3, webdav: m.sourceWebdav, ...BRANDS,
    };
    return labels[value] ?? value;
  }

  function fieldLabel(change: Change) {
    const labels: Record<string, string> = {
      title: m.fieldTitle, document_date: m.fieldDate, correspondent: m.fieldSender, document_type: m.fieldType,
      storage_path: m.fieldStoragePath, asn: m.fieldAsn, tags: m.fieldTags, version: m.fieldVersion, source: m.fieldSource,
    };
    if (change.field === "access") return m.fieldAccess(change.name ?? "", change.kind === "group");
    return change.field === "custom_field" ? change.name ?? "" : labels[change.field] ?? change.field;
  }

  function value(change: Change, raw: string | string[] | null) {
    if (raw === null || raw === "" || (Array.isArray(raw) && !raw.length)) return m.noValue;
    if (Array.isArray(raw)) return raw.join(", ");
    if (change.field === "document_date") return formatDate(raw);
    if (change.field === "source") return sourceLabel(raw);
    if (change.field === "access") return raw === "edit" ? m.accessEdit : raw === "view" ? m.accessView : raw;
    return raw;
  }

  function describe(change: Change) {
    if (change.field === "tags") {
      const before = (change.from as string[] | null) ?? [];
      const after = (change.to as string[] | null) ?? [];
      const added = after.filter((tag) => !before.includes(tag)).map((tag) => `+${tag}`);
      const removed = before.filter((tag) => !after.includes(tag)).map((tag) => `−${tag}`);
      return [...added, ...removed].join(", ");
    }
    if (change.field === "source") return value(change, change.to);
    return `${value(change, change.from)} → ${value(change, change.to)}`;
  }

  const actionLabel: Partial<Record<DocumentEvent["action"], string>> = {
    created: m.created, trashed: m.trashed, restored: m.restored, version_added: m.versionAdded,
  };
  const visible = expanded ? events : events.slice(0, COLLAPSED);

  return (
    <section className="detail-notes document-history" aria-labelledby={`document-history-${documentId}`}>
      <h3 id={`document-history-${documentId}`}><History size={17} /> {m.heading}</h3>
      <p>{m.intro}</p>
      {error && <div className="inline-error" role="alert">{error}</div>}
      {loading && !events.length && <p>{m.loading}</p>}
      {!loading && !error && !events.length && <p>{m.empty}</p>}
      {visible.length > 0 && <ol className="history-list">
        {visible.map((event) => <li key={event.id}>
          <div className="note-meta">
            <span>{actor(event)} · <time dateTime={event.created_at}>{formatDateTime(event.created_at)}</time></span>
            {actionLabel[event.action] && <strong>{actionLabel[event.action]}</strong>}
          </div>
          {event.changes.length > 0 && <ul>
            {event.changes.map((change, index) => <li key={index}>
              <span className="history-field">{fieldLabel(change)}:</span> {describe(change)}
            </li>)}
          </ul>}
        </li>)}
      </ol>}
      {events.length > COLLAPSED && <button type="button" className="text-action" onClick={() => setExpanded((value) => !value)}>
        {expanded ? m.showFewer : m.showAll(events.length)}
      </button>}
      {expanded && nextOffset !== null && <button type="button" className="text-action" disabled={loading} onClick={() => void load(nextOffset)}>
        {m.showOlder}
      </button>}
    </section>
  );
}
