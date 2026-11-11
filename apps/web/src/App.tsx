import {
  ChangeEvent,
  DragEvent,
  FormEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  Bot,
  Camera,
  Check,
  Clock3,
  ClipboardList,
  Copy,
  DatabaseBackup,
  Eye,
  FileText,
  FolderOpen,
  ImagePlus,
  Inbox,
  LockKeyhole,
  LogOut,
  MapPin,
  Menu,
  Plus,
  RotateCcw,
  Search,
  SlidersHorizontal,
  Tag as TagIcon,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import { CustomField, Document, FilingItem, formatDate, LibraryFilters, request, Session, Tag } from "./api";
import DocumentPanel from "./DocumentPanel";
import ActionPanel from "./ActionPanel";
import InboxPanel from "./InboxPanel";
import AgentPanel from "./AgentPanel";
import PhysicalPanel from "./PhysicalPanel";
import TagPanel from "./TagPanel";
import SavedSearchBar from "./SavedSearchBar";
import TrashPanel from "./TrashPanel";
import { Button, Field, Modal } from "./ui";

type BackupRun = {
  id: string;
  status: "pending" | "running" | "complete" | "failed";
  trigger: string;
  snapshot_name: string;
  error: string;
  created_at: string;
};

const emptyLibraryFilters: LibraryFilters = {
  tag_id: "", correspondent_id: "", document_type_id: "", date_from: "", date_to: "", custom_field_id: "", custom_value: "", custom_min: "", custom_max: "",
};

function TagSummary({ tags }: { tags: Document["tags"] }) {
  const priority = { manual: 0, model: 1, rule: 2 };
  const visibleFirst = [...tags].sort((a, b) =>
    priority[a.origin] - priority[b.origin] || a.name.localeCompare(b.name));
  function chips(limit: number) {
    return <>
      {visibleFirst.slice(0, limit).map((tag) => (
        <span key={tag.id} title={tag.name}>
          <i style={{ background: tag.color }} />
          <span className="tag-name">{tag.name}</span>
        </span>
      ))}
      {visibleFirst.length > limit && (
        <span className="more-tags" title={visibleFirst.slice(limit).map((tag) => tag.name).join(", ")}>
          +{visibleFirst.length - limit} more
        </span>
      )}
    </>;
  }
  return <>
    <div className="document-tags document-tags-desktop">{chips(2)}</div>
    <div className="document-tags document-tags-mobile">{chips(1)}</div>
  </>;
}

declare global {
  interface Window {
    RipianoAndroid?: { postMessage(message: string): void };
  }
}

function AuthScreen({
  setup,
  onAuthenticated,
}: {
  setup: boolean;
  onAuthenticated: (value: Session) => void;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [setupKey, setSetupKey] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await request(setup ? "/api/setup" : "/api/session", {
        method: "POST",
        body: JSON.stringify({
          username,
          password,
          ...(setup ? { setup_key: setupKey } : {}),
        }),
      });
      onAuthenticated(await request<Session>("/api/session"));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not sign in");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-shell">
      <div className="auth-brand">
        <span className="brand-mark">
          <FolderOpen size={23} strokeWidth={2.1} />
        </span>
        <span>ripiano</span>
      </div>
      <div className="auth-card">
        <div className="eyebrow">
          <span className="eyebrow-line" /> PRIVATE DOCUMENT HOME
        </div>
        <h1>{setup ? "Make room for what matters." : "Welcome back."}</h1>
        <p>
          {setup
            ? "Create the first account for your archive. Your setup key is in your Portainer configuration."
            : "Sign in to find and keep your documents in place."}
        </p>
        <form onSubmit={submit}>
          <Field label="Username">
            <input
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
            />
          </Field>
          <Field label="Password">
            <input
              type="password"
              autoComplete={setup ? "new-password" : "current-password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={setup ? 12 : undefined}
              required
            />
          </Field>
          {setup && (
            <Field label="Setup key">
              <input
                type="password"
                value={setupKey}
                onChange={(event) => setSetupKey(event.target.value)}
                required
              />
            </Field>
          )}
          {error && (
            <div className="form-error" role="alert">
              {error}
            </div>
          )}
          <Button className="auth-submit" disabled={busy}>
            {busy ? "Please wait…" : setup ? "Create archive" : "Sign in"}{" "}
            <ArrowRight size={18} />
          </Button>
        </form>
      </div>
      <div className="auth-foot">
        <LockKeyhole size={14} /> Stored on your own server
      </div>
    </main>
  );
}

function BackupPanel() {
  const [runs, setRuns] = useState<BackupRun[]>([]);
  const [schedule, setSchedule] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try {
      const result = await request<{ schedule: string; runs: BackupRun[] }>(
        "/api/backups",
      );
      setRuns(result.runs);
      setSchedule(result.schedule);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not load backups",
      );
    }
  }, []);
  useEffect(() => {
    void load();
    const timer = window.setInterval(load, 10000);
    return () => window.clearInterval(timer);
  }, [load]);

  async function start() {
    setBusy(true);
    setError("");
    try {
      await request("/api/backups", { method: "POST" });
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not start backup",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            <span className="eyebrow-line" /> ARCHIVE SAFETY
          </div>
          <h1>
            Backups<span className="heading-period">.</span>
          </h1>
          <p>Verified snapshots of your database and original documents.</p>
        </div>
        <Button
          onClick={start}
          disabled={busy}
        >
          <DatabaseBackup size={18} /> {busy ? "Starting…" : "Back up now"}
        </Button>
      </div>
      <div className="backup-summary">
        <div>
          <strong>Automatic schedule</strong>
          <span>Every day at {schedule || "…"}</span>
        </div>
        <div>
          <strong>Backup output</strong>
          <span>Mounted backup volume · complete folder</span>
        </div>
      </div>
      {error && (
        <div className="inline-error" role="alert">
          {error}
        </div>
      )}
      <div className="section-heading">
        <div>
          <h2>Recent snapshots</h2>
          <p>A snapshot appears here after its checksums pass.</p>
        </div>
      </div>
      {runs.length ? (
        <div className="document-list backup-list">
          {runs.map((run) => (
            <div className="document-row" key={run.id}>
              <div className="document-icon">
                <DatabaseBackup size={20} />
              </div>
              <div className="document-info">
                <h3>
                  {run.snapshot_name ||
                    (run.trigger === "manual"
                      ? "Manual backup"
                      : "Scheduled backup")}
                </h3>
                <div className="document-meta">
                  {formatDate(run.created_at)} <span>·</span> {run.trigger}
                </div>
                {run.error && <p className="doc-error">{run.error}</p>}
              </div>
              <span
                className={`status status-${run.status === "complete" ? "ready" : run.status === "failed" ? "failed" : "pending"}`}
              >
                {run.status}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <div className="empty-icon">
            <DatabaseBackup size={32} />
          </div>
          <h3>No snapshots yet</h3>
          <p>
            Run the first backup to verify the mounted volume and create a
            restorable snapshot.
          </p>
        </div>
      )}
    </>
  );
}

function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [counts, setCounts] = useState({ total: 0, ready: 0, waiting: 0 });
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("");
  const [filters, setFilters] = useState<LibraryFilters>({ ...emptyLibraryFilters });
  const [showFilters, setShowFilters] = useState(false);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulkTagId, setBulkTagId] = useState("");
  const [bulkSenderId, setBulkSenderId] = useState("");
  const [bulkTypeId, setBulkTypeId] = useState("");
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkError, setBulkError] = useState("");
  const [bulkNotice, setBulkNotice] = useState("");
  const [filterOptions, setFilterOptions] = useState<{ tags: Tag[]; correspondents: FilingItem[]; document_types: FilingItem[]; custom_fields: CustomField[] }>({ tags: [], correspondents: [], document_types: [], custom_fields: [] });
  const [error, setError] = useState("");
  const [listError, setListError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState("");
  const [uploadReport, setUploadReport] = useState<{ total: number; failures: string[] } | null>(null);
  const [nativeScanner] = useState(() => Boolean(window.RipianoAndroid));
  const [dropActive, setDropActive] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const initialSticker =
    new URLSearchParams(window.location.search).get("sticker") ?? "";
  const initialLocation =
    new URLSearchParams(window.location.search).get("location") ?? "";
  const [view, setView] = useState<
    "documents" | "inbox" | "actions" | "tags" | "physical" | "backups" | "agents" | "trash"
  >(initialSticker || initialLocation ? "physical" : "documents");
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(
    null,
  );
  const [actionRefresh, setActionRefresh] = useState(0);
  const [inboxRefresh, setInboxRefresh] = useState(0);
  const [trashRefresh, setTrashRefresh] = useState(0);
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const latestSearch = useRef(0);
  const loadingMoreRef = useRef(false);

  const loadFilterOptions = useCallback(async () => {
    try {
      const [tags, correspondents, documentTypes, customFields] = await Promise.all([
        request<{ tags: Tag[] }>("/api/tags"),
        request<{ correspondents: FilingItem[] }>("/api/correspondents"),
        request<{ document_types: FilingItem[] }>("/api/document-types"),
        request<{ fields: CustomField[] }>("/api/custom-fields"),
      ]);
      setFilterOptions({ tags: tags.tags, correspondents: correspondents.correspondents, document_types: documentTypes.document_types, custom_fields: customFields.fields });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load filter choices");
    }
  }, []);

  function updateFilter(key: keyof LibraryFilters, value: string) {
    setFilters((current) => ({ ...current, [key]: value,
      ...(key === "custom_field_id" ? { custom_value: "", custom_min: "", custom_max: "" } : {}),
      ...(key === "custom_value" && value ? { custom_min: "", custom_max: "" } : {}),
      ...((key === "custom_min" || key === "custom_max") && value ? { custom_value: "" } : {}),
    }));
    setNextCursor(null);
  }

  function toggleSelected(id: string) {
    setSelectedIds((current) => current.includes(id)
      ? current.filter((item) => item !== id)
      : current.length < 100 ? [...current, id] : current);
  }

  async function applyBulkTag(action: "add" | "remove") {
    if (!selectedIds.length || !bulkTagId) return;
    setBulkBusy(true);
    setBulkError("");
    setBulkNotice("");
    try {
      const result = await request<{ updated: number }>("/api/documents/bulk-tags", {
        method: "POST",
        body: JSON.stringify({ action, document_ids: selectedIds, tag_id: bulkTagId }),
      });
      const tagName = filterOptions.tags.find((tag) => tag.id === bulkTagId)?.name ?? "tag";
      setBulkNotice(`${action === "add" ? "Added" : "Removed"} ${tagName} ${action === "add" ? "to" : "from"} ${result.updated} documents.`);
      setSelectedIds([]);
      await loadDocuments(query);
    } catch (cause) {
      setBulkError(cause instanceof Error ? cause.message : "Could not update selected documents");
    } finally {
      setBulkBusy(false);
    }
  }

  async function applyBulkFiling(field: "correspondent" | "document_type") {
    const choice = field === "correspondent" ? bulkSenderId : bulkTypeId;
    if (!selectedIds.length || !choice) return;
    setBulkBusy(true);
    setBulkError("");
    setBulkNotice("");
    try {
      const result = await request<{ updated: number }>("/api/documents/bulk-filing", {
        method: "POST",
        body: JSON.stringify({ field, document_ids: selectedIds, value_id: choice === "none" ? null : choice }),
      });
      const label = field === "correspondent" ? "sender" : "document type";
      const options = field === "correspondent" ? filterOptions.correspondents : filterOptions.document_types;
      const name = options.find((item) => item.id === choice)?.name;
      setBulkNotice(`${choice === "none" ? `Cleared ${label}` : `Set ${label} to ${name ?? "the selected value"}`} for ${result.updated} documents.`);
      setSelectedIds([]);
      await loadDocuments(query);
    } catch (cause) {
      setBulkError(cause instanceof Error ? cause.message : "Could not update selected documents");
    } finally {
      setBulkBusy(false);
    }
  }

  const loadDocuments = useCallback(async (search: string, cursor: string | null = null) => {
    if (cursor && loadingMoreRef.current) return;
    if (cursor) {
      loadingMoreRef.current = true;
      setLoadingMore(true);
    }
    const requestNumber = ++latestSearch.current;
    try {
      const params = new URLSearchParams({ q: search });
      for (const [key, value] of Object.entries(filters)) if (value) params.set(key, value);
      if (sort) params.set("sort", sort);
      if (cursor) params.set("cursor", cursor);
      const result = await request<{ documents: Document[]; counts: typeof counts; next_cursor: string | null }>(
        `/api/documents?${params}`,
      );
      if (requestNumber === latestSearch.current) {
        setDocuments((current) => cursor ? [...current, ...result.documents] : result.documents);
        setCounts(result.counts);
        setNextCursor(result.next_cursor);
        setListError("");
      }
    } catch (cause) {
      if (requestNumber !== latestSearch.current) return;
      const message = cause instanceof Error ? cause.message : "Could not load documents";
      if (cursor) setError(message);
      else {
        setDocuments([]);
        setCounts({ total: 0, ready: 0, waiting: 0 });
        setNextCursor(null);
        setListError(message);
      }
    } finally {
      if (cursor) loadingMoreRef.current = false;
      if (requestNumber === latestSearch.current) setLoadingMore(false);
    }
  }, [filters, sort]);

  useEffect(() => {
    request<Session>("/api/session")
      .then(setSession)
      .catch((cause) => setError(cause.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (session?.authenticated) window.RipianoAndroid?.postMessage("retry");
  }, [session?.authenticated]);

  useEffect(() => {
    if (!session?.authenticated || view !== "documents") return;
    const timer = window.setTimeout(() => loadDocuments(query), 200);
    return () => window.clearTimeout(timer);
  }, [session?.authenticated, query, view, loadDocuments]);

  useEffect(() => {
    setSelectedIds([]);
    setBulkError("");
    setBulkNotice("");
    if (view !== "documents") setSelectionMode(false);
  }, [query, filters, sort, view]);

  useEffect(() => {
    if (session?.authenticated && view === "documents") void loadFilterOptions();
  }, [session?.authenticated, view, loadFilterOptions]);

  useEffect(() => {
    function onNativeUpload(event: Event) {
      const detail = (event as CustomEvent<{ status: string; message?: string }>).detail;
      if (detail.status === "saved") void loadDocuments(query);
      if (detail.status === "failed") {
        setError(detail.message || "Scan upload failed. It is saved on this device and will be retried.");
      }
      if (detail.status !== "uploading") setUploading(false);
    }
    window.addEventListener("ripiano-native-upload", onNativeUpload);
    return () => window.removeEventListener("ripiano-native-upload", onNativeUpload);
  }, [query, loadDocuments]);

  useEffect(() => {
    if (
      !session?.authenticated || documents.length > 50 ||
      (!query.trim() &&
        !documents.some(
          (doc) => doc.status === "pending" || doc.status === "processing",
        ))
    )
      return;
    const timer = window.setInterval(() => loadDocuments(query), 5000);
    return () => window.clearInterval(timer);
  }, [session?.authenticated, documents, query, loadDocuments]);

  async function upload(files: FileList | File[] | null) {
    if (!files?.length) return;
    const chosen = Array.from(files);
    setUploading(true);
    setShowAdd(false);
    setView("documents");
    setQuery("");
    setFilters({ ...emptyLibraryFilters });
    setError("");
    setUploadReport(null);
    try {
      const failures: string[] = [];
      for (const [index, file] of chosen.entries()) {
        setUploadProgress(`Adding ${index + 1} of ${chosen.length}…`);
        try {
          const form = new FormData();
          form.append("document", file);
          await request<Document>("/api/documents", {
            method: "POST",
            body: form,
          });
        } catch (cause) {
          failures.push(`${file.name}: ${cause instanceof Error ? cause.message : "Upload failed"}`);
        }
      }
      await loadDocuments("");
      if (failures.length) setUploadReport({ total: chosen.length, failures });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Upload failed");
    } finally {
      setUploading(false);
      setUploadProgress("");
      if (cameraRef.current) cameraRef.current.value = "";
      if (galleryRef.current) galleryRef.current.value = "";
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  function drop(event: DragEvent) {
    event.preventDefault();
    setDropActive(false);
    void upload(event.dataTransfer.files);
  }

  function scan() {
    if (!window.RipianoAndroid) {
      cameraRef.current?.click();
      return;
    }
    setShowAdd(false);
    setUploading(true);
    setError("");
    window.RipianoAndroid.postMessage("scan");
  }

  async function signOut() {
    try {
      await request("/api/session", { method: "DELETE" });
      setSession(await request<Session>("/api/session"));
      setDocuments([]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not sign out");
    }
  }

  async function retryDocument(id: string) {
    try {
      await request(`/api/documents/${id}/retry`, { method: "POST" });
      await loadDocuments(query);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not retry document",
      );
    }
  }

  if (loading) return <div className="loading-screen">Opening Ripiano…</div>;
  if (!session)
    return (
      <div className="loading-screen error-screen">
        {error || "Could not connect to Ripiano"}{" "}
        <button onClick={() => location.reload()}>Try again</button>
      </div>
    );
  if (!session.authenticated)
    return (
      <AuthScreen setup={session.setup_required} onAuthenticated={setSession} />
    );

  const isEmpty = counts.total === 0;
  const activeFilterCount = Object.entries(filters).filter(([key, value]) => !["custom_value", "custom_min", "custom_max"].includes(key) && Boolean(value)).length;
  const selectedCustomField = filterOptions.custom_fields.find((field) => field.id === filters.custom_field_id);

  return (
    <div
      className="app-shell"
      onDragOver={(event) => {
        event.preventDefault();
        setDropActive(true);
      }}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node))
          setDropActive(false);
      }}
      onDrop={drop}
    >
      <aside className={`sidebar ${menuOpen ? "sidebar-open" : ""}`}>
        <div className="sidebar-brand">
          <span className="brand-mark">
            <FolderOpen size={22} strokeWidth={2.1} />
          </span>
          <span>ripiano</span>
        </div>
        <div className="sidebar-label">YOUR SPACE</div>
        <button
          className={`nav-link ${view === "inbox" ? "active" : ""}`}
          onClick={() => { setView("inbox"); setMenuOpen(false); }}
        >
          <Inbox size={18} /> Inbox
        </button>
        <button
          className={`nav-link ${view === "documents" ? "active" : ""}`}
          onClick={() => {
            setView("documents");
            setQuery("");
            setFilters({ ...emptyLibraryFilters });
            setMenuOpen(false);
          }}
        >
          <FolderOpen size={18} /> All documents
        </button>
        <button
          className={`nav-link ${view === "actions" ? "active" : ""}`}
          onClick={() => { setView("actions"); setMenuOpen(false); }}
        >
          <ClipboardList size={18} /> Needs action
        </button>
        <button
          className={`nav-link ${view === "tags" ? "active" : ""}`}
          onClick={() => {
            setView("tags");
            setMenuOpen(false);
          }}
        >
          <TagIcon size={18} /> Tags & filing
        </button>
        <button
          className={`nav-link ${view === "physical" ? "active" : ""}`}
          onClick={() => {
            setView("physical");
            setMenuOpen(false);
          }}
        >
          <MapPin size={18} /> Paper archive
        </button>
        <button className={`nav-link ${view === "trash" ? "active" : ""}`} onClick={() => { setView("trash"); setMenuOpen(false); }}>
          <Trash2 size={18} /> Trash
        </button>
        {session.owner && (
          <button
            className={`nav-link ${view === "agents" ? "active" : ""}`}
            onClick={() => {
              setView("agents");
              setMenuOpen(false);
            }}
          >
            <Bot size={18} /> Agents
          </button>
        )}
        {session.owner && (
          <button
            className={`nav-link ${view === "backups" ? "active" : ""}`}
            onClick={() => {
              setView("backups");
              setMenuOpen(false);
            }}
          >
            <DatabaseBackup size={18} /> Backups
          </button>
        )}
        <div className="sidebar-spacer" />
        <div className="sidebar-note">
          <div className="sidebar-note-icon">
            <LockKeyhole size={17} />
          </div>
          <strong>Made for your space.</strong>
          <span>
            Your documents stay on your server, ready when you need them.
          </span>
        </div>
        <button className="profile" onClick={signOut} title="Sign out">
          <span className="avatar">
            {session.username?.slice(0, 1).toUpperCase()}
          </span>
          <span className="profile-name">
            {session.username}
            <small>Archive owner</small>
          </span>
          <LogOut size={16} />
        </button>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Toggle menu"
          >
            <Menu size={21} />
          </button>
          <div className="topbar-crumb">
            Your archive <span>/</span>{" "}
            {view === "documents"
              ? "All documents"
              : view === "inbox"
                ? "Inbox"
              : view === "actions"
                ? "Needs action"
              : view === "trash"
                ? "Trash"
              : view === "tags"
                ? "Tags & filing"
                : view === "physical"
                  ? "Paper archive"
                  : view === "agents"
                    ? "Agents"
                    : "Backups"}
          </div>
          <div className="topbar-right">
            <span className="private-dot" /> Private & yours
          </div>
        </header>
        <section className="page-content">
          {view === "backups" ? (
            <BackupPanel />
          ) : view === "inbox" ? (
            <InboxPanel refreshKey={inboxRefresh} onOpenDocument={setSelectedDocument} />
          ) : view === "actions" ? (
            <ActionPanel refreshKey={actionRefresh} onOpenDocument={setSelectedDocument} />
          ) : view === "trash" ? (
            <TrashPanel refreshKey={trashRefresh} onRestored={() => { void loadDocuments(query); setActionRefresh((value) => value + 1); setInboxRefresh((value) => value + 1); }} />
          ) : view === "agents" ? (
            <AgentPanel />
          ) : view === "tags" ? (
            <TagPanel />
          ) : view === "physical" ? (
            <PhysicalPanel
              initialSticker={initialSticker}
              initialLocation={initialLocation}
              onOpenDocument={(id) => {
                void request<Document>(`/api/documents/${id}`)
                  .then((doc) => {
                    setSelectedDocument(doc);
                    setView("documents");
                  })
                  .catch((cause) => setError(cause.message));
              }}
            />
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">
                    <span className="eyebrow-line" /> YOUR DOCUMENT HOME
                  </div>
                  <h1>
                    Everything in its place
                    <span className="heading-period">.</span>
                  </h1>
                  <p>One calm place for the documents you want to keep.</p>
                </div>
                <Button
                  className="desktop-add"
                  onClick={() => setShowAdd(true)}
                >
                  <Plus size={19} /> Add document
                </Button>
              </div>

              <div className="summary-row">
                <div className="summary-card">
                  <span className="summary-icon">
                    <FileText size={20} />
                  </span>
                  <div>
                    <strong>{counts.total}</strong>
                    <span>{query || activeFilterCount ? "Matching documents" : "Documents"}</span>
                  </div>
                </div>
                <div className="summary-card">
                  <span className="summary-icon green">
                    <Check size={20} />
                  </span>
                  <div>
                    <strong>{counts.ready}</strong>
                    <span>Ready to find</span>
                  </div>
                </div>
                <div className="summary-card">
                  <span className="summary-icon amber">
                    <Clock3 size={20} />
                  </span>
                  <div>
                    <strong>{counts.waiting}</strong>
                    <span>Being processed</span>
                  </div>
                </div>
              </div>

              <div className="section-heading">
                <div>
                  <h2>Your documents</h2>
                  <p>Search document text, sender, type, tag, or sticker.</p>
                </div>
                <Button type="button" variant="secondary" aria-label="Refresh" title="Refresh documents" onClick={() => void loadDocuments(query)}>
                  <RotateCcw size={16} /> <span className="refresh-label">Refresh</span>
                </Button>
              </div>
              <SavedSearchBar query={query} filters={filters} onApply={(savedQuery, savedFilters) => {
                setQuery(savedQuery);
                setFilters(savedFilters);
                setNextCursor(null);
                setShowFilters(Object.values(savedFilters).some(Boolean));
              }} />
              <div className="toolbar">
                <div className="search-box">
                  <Search size={19} />
                  <input
                    value={query}
                    onChange={(event) => { setQuery(event.target.value); setNextCursor(null); }}
                    placeholder="Search text, sender, type, tag…"
                    aria-label="Search documents by text, sender, type, tag, or sticker"
                  />
                  {query && (
                    <button
                      onClick={() => setQuery("")}
                      aria-label="Clear search"
                    >
                      <X size={16} />
                    </button>
                  )}
                </div>
                <select className="library-sort" aria-label="Sort documents" value={sort} onChange={(event) => { setSort(event.target.value); setNextCursor(null); }}>
                  <option value="">Recommended order</option>
                  <option value="newest">Newest added</option>
                  <option value="oldest">Oldest added</option>
                  <option value="document_newest">Newest document date</option>
                  <option value="document_oldest">Oldest document date</option>
                  <option value="title_asc">Title A–Z</option>
                  <option value="title_desc">Title Z–A</option>
                </select>
                <Button type="button" variant="secondary" className="filter-toggle" aria-expanded={showFilters} aria-controls="library-filters" onClick={() => setShowFilters((current) => !current)}>
                  <SlidersHorizontal size={17} /> Filters{activeFilterCount ? ` (${activeFilterCount})` : ""}
                </Button>
                <Button
                  variant="secondary"
                  className="mobile-add"
                  onClick={() => setShowAdd(true)}
                >
                  <Plus size={18} /> Add
                </Button>
              </div>
              <details className="search-syntax">
                <summary>More precise search</summary>
                <p>Use <code>tag:tax</code>, <code>sender:"City office"</code>, or <code>date:2026-04-15</code>. You can also search by <code>title:</code>, <code>text:</code>, <code>note:</code>, <code>type:</code>, and <code>sticker:</code>. Combine fields and ordinary words to narrow results.</p>
              </details>
              {showFilters && <div className="library-filters" id="library-filters">
                <Field label="Tag" className="detail-label"><select value={filters.tag_id} onChange={(event) => updateFilter("tag_id", event.target.value)}><option value="">Any tag</option>{filterOptions.tags.map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}</select></Field>
                <Field label="From" className="detail-label"><select value={filters.correspondent_id} onChange={(event) => updateFilter("correspondent_id", event.target.value)}><option value="">Any sender</option>{filterOptions.correspondents.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field>
                <Field label="Document type" className="detail-label"><select value={filters.document_type_id} onChange={(event) => updateFilter("document_type_id", event.target.value)}><option value="">Any type</option>{filterOptions.document_types.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field>
                <Field label="Custom detail" className="detail-label custom-filter-field"><select value={filters.custom_field_id} onChange={(event) => updateFilter("custom_field_id", event.target.value)}><option value="">Any custom detail</option>{filterOptions.custom_fields.map((field) => <option key={field.id} value={field.id}>{field.name}</option>)}</select></Field>
                {selectedCustomField && <Field label={["number", "date"].includes(selectedCustomField.kind) ? "Exact value" : `${selectedCustomField.name} value`} className="detail-label custom-filter-value">{selectedCustomField.kind === "boolean" ? <select value={filters.custom_value} onChange={(event) => updateFilter("custom_value", event.target.value)}><option value="">Any value</option><option value="yes">Yes</option><option value="no">No</option></select> : <input aria-label={`${selectedCustomField.name} ${["number", "date"].includes(selectedCustomField.kind) ? "exactly" : "value"}`} type={selectedCustomField.kind === "text" ? "text" : selectedCustomField.kind} step={selectedCustomField.kind === "number" ? "any" : undefined} value={filters.custom_value} onChange={(event) => updateFilter("custom_value", event.target.value)} placeholder={selectedCustomField.kind === "text" ? "Contains…" : undefined} />}</Field>}
                {selectedCustomField && (selectedCustomField.kind === "number" || selectedCustomField.kind === "date") && <>
                  <Field label="From" className="detail-label custom-filter-value"><input aria-label={`${selectedCustomField.name} from`} type={selectedCustomField.kind} step={selectedCustomField.kind === "number" ? "any" : undefined} value={filters.custom_min} max={filters.custom_max || undefined} onChange={(event) => updateFilter("custom_min", event.target.value)} /></Field>
                  <Field label="To" className="detail-label custom-filter-value"><input aria-label={`${selectedCustomField.name} to`} type={selectedCustomField.kind} step={selectedCustomField.kind === "number" ? "any" : undefined} value={filters.custom_max} min={filters.custom_min || undefined} onChange={(event) => updateFilter("custom_max", event.target.value)} /></Field>
                </>}
                <Field label="Date from" className="detail-label"><input type="date" value={filters.date_from} max={filters.date_to || undefined} onChange={(event) => updateFilter("date_from", event.target.value)} /></Field>
                <Field label="Date to" className="detail-label"><input type="date" value={filters.date_to} min={filters.date_from || undefined} onChange={(event) => updateFilter("date_to", event.target.value)} /></Field>
                {activeFilterCount > 0 && <button type="button" className="text-action filter-clear" onClick={() => { setFilters({ ...emptyLibraryFilters }); setNextCursor(null); }}>Clear filters</button>}
              </div>}
              {error && (
                <div className="inline-error" role="alert">
                  {error}
                  <button
                    onClick={() => setError("")}
                    aria-label="Dismiss error"
                  >
                    <X size={16} />
                  </button>
                </div>
              )}
              {uploadReport && (
                <div className="inline-error upload-report" role="alert">
                  <strong>{uploadReport.failures.length} of {uploadReport.total} files could not be added.</strong>
                  {uploadReport.failures.length > 3 ? (
                    <details>
                      <summary>Review rejected files</summary>
                      <ul>{uploadReport.failures.map((failure, index) => <li key={`${failure}-${index}`}>{failure}</li>)}</ul>
                    </details>
                  ) : (
                    <ul>{uploadReport.failures.map((failure, index) => <li key={`${failure}-${index}`}>{failure}</li>)}</ul>
                  )}
                  <button onClick={() => setUploadReport(null)} aria-label="Dismiss upload report"><X size={16} /></button>
                </div>
              )}
              {listError && (
                <div className="inline-error" role="alert">
                  {listError}
                  <button onClick={() => void loadDocuments(query)}>Retry</button>
                </div>
              )}
              {uploading && (
                <div className="upload-progress" role="status" aria-live="polite" aria-atomic="true">
                  <UploadCloud size={19} /> {uploadProgress || "Adding your document…"}
                </div>
              )}
              {!listError && (!isEmpty || selectionMode || bulkNotice) && <div className="bulk-controls">
                <button type="button" className="text-action" disabled={bulkBusy || (isEmpty && !selectionMode)} onClick={() => { setSelectionMode(!selectionMode); setSelectedIds([]); setBulkError(""); setBulkNotice(""); }}>
                  {selectionMode ? "Done selecting" : "Select documents"}
                </button>
                {selectionMode && <div className="bulk-actions">
                  <strong>{selectedIds.length} selected</strong>
                  <button type="button" className="text-action" disabled={bulkBusy} onClick={() => setSelectedIds(documents.slice(0, 100).map((doc) => doc.id))}>
                    {documents.length > 100 ? "Select first 100 loaded" : "Select loaded"}
                  </button>
                  {selectedIds.length > 0 && <button type="button" className="text-action" disabled={bulkBusy} onClick={() => setSelectedIds([])}>Clear selection</button>}
                  <select aria-label="Tag for selected documents" value={bulkTagId} disabled={bulkBusy || !filterOptions.tags.length} onChange={(event) => setBulkTagId(event.target.value)}>
                    <option value="">Choose a tag</option>
                    {filterOptions.tags.map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}
                  </select>
                  <Button type="button" disabled={bulkBusy || !selectedIds.length || !bulkTagId} onClick={() => void applyBulkTag("add")}>Add tag</Button>
                  <Button type="button" variant="secondary" disabled={bulkBusy || !selectedIds.length || !bulkTagId} onClick={() => void applyBulkTag("remove")}>Remove tag</Button>
                  <details className="bulk-filing-details">
                    <summary>Change sender or document type</summary>
                    <div className="bulk-filing">
                    <select aria-label="Sender for selected documents" value={bulkSenderId} disabled={bulkBusy} onChange={(event) => setBulkSenderId(event.target.value)}>
                      <option value="">Choose sender</option>
                      <option value="none">Clear sender</option>
                      {filterOptions.correspondents.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                    </select>
                    <Button type="button" variant="secondary" disabled={bulkBusy || !selectedIds.length || !bulkSenderId} onClick={() => void applyBulkFiling("correspondent")}>Set sender</Button>
                    <select aria-label="Document type for selected documents" value={bulkTypeId} disabled={bulkBusy} onChange={(event) => setBulkTypeId(event.target.value)}>
                      <option value="">Choose type</option>
                      <option value="none">Clear type</option>
                      {filterOptions.document_types.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                    </select>
                    <Button type="button" variant="secondary" disabled={bulkBusy || !selectedIds.length || !bulkTypeId} onClick={() => void applyBulkFiling("document_type")}>Set type</Button>
                    </div>
                  </details>
                </div>}
                {bulkError && <p className="inline-error" role="alert">{bulkError}</p>}
                {bulkNotice && <p className="bulk-notice" role="status">{bulkNotice}</p>}
              </div>}

              {listError ? null : isEmpty ? (
                <div className="empty-state">
                  <div className="empty-icon">
                    <FileText size={33} strokeWidth={1.5} />
                  </div>
                  <h3>
                    {query || activeFilterCount
                      ? "Nothing found yet"
                      : "A fresh shelf, ready for you."}
                  </h3>
                  <p>
                    {query || activeFilterCount
                      ? "Try another search or clear your filters."
                      : "Add a document and Ripiano will make its text searchable."}
                  </p>
                  {!query && !activeFilterCount && (
                    <Button
                      onClick={() => setShowAdd(true)}
                    >
                      <Plus size={18} /> Add your first document
                    </Button>
                  )}
                </div>
              ) : (
                <>
                <div className="document-list">
                  {documents.map((doc) => (
                    <article className="document-row" key={doc.id}>
                      {selectionMode ? <label className="document-select">
                        <input type="checkbox" checked={selectedIds.includes(doc.id)} disabled={bulkBusy || (selectedIds.length >= 100 && !selectedIds.includes(doc.id))} onChange={() => toggleSelected(doc.id)} />
                        <span className="visually-hidden">Select {doc.title}</span>
                      </label> : <div className="document-icon"><FileText size={21} /></div>}
                      <div className="document-info">
                        <h3>
                          <button
                            className="document-title-button"
                            onClick={() => setSelectedDocument(doc)}
                          >
                            {doc.title}
                          </button>
                        </h3>
                        <div className="document-meta">
                          {formatDate(doc.created_at)} <span>·</span>{" "}
                          {doc.original_name}
                          {doc.correspondent && <>{" "}<span>·</span> From: {doc.correspondent.name}</>}
                          {doc.document_type && <>{" "}<span>·</span> Type: {doc.document_type.name}</>}
                          {doc.source === "telegram" && (
                            <>
                              {" "}
                              <span>·</span> via Telegram
                            </>
                          )}
                          {doc.source === "android" && (
                            <>
                              {" "}
                              <span>·</span> scanned on Android
                            </>
                          )}
                          {doc.source === "folder" && (
                            <>
                              {" "}
                              <span>·</span> from NAS folder
                            </>
                          )}
                        </div>
                        {doc.snippet && (
                          <p className="document-snippet">
                            <strong>{doc.snippet_source === "note" ? "Note" : doc.snippet_source === "sticker" ? "Sticker" : doc.snippet_source === "field" ? "Custom field" : "Document text"}:</strong> {doc.snippet}
                          </p>
                        )}
                        {doc.tags.length > 0 && <TagSummary tags={doc.tags} />}
                        {doc.duplicate_of && (
                          <span className="duplicate-chip">
                            <Copy size={12} /> Exact copy of{" "}
                            {doc.duplicate_of.title}
                          </span>
                        )}
                        {doc.physical_copies.length > 0 && (
                          <div className="document-physical">
                            <MapPin size={13} />{" "}
                            {doc.physical_copies[0].location_path.join(" / ") ||
                              "Paper copy awaiting a location"}
                            {doc.physical_copies.length > 1 &&
                              ` +${doc.physical_copies.length - 1}`}
                          </div>
                        )}
                        {doc.status === "failed" && (
                          <p className="doc-error">
                            Processing failed: {doc.error}
                          </p>
                        )}
                      </div>
                      <span className={`status status-${doc.status}`}>
                        {doc.status === "ready"
                          ? "Ready"
                          : doc.status === "failed"
                            ? "Needs attention"
                            : "Processing"}
                      </span>
                      {doc.status === "failed" && (
                        <button
                          className="download-link"
                          onClick={() => void retryDocument(doc.id)}
                          aria-label={`Retry ${doc.original_name}`}
                          title="Retry processing"
                        >
                          <RotateCcw size={18} />
                        </button>
                      )}
                      {doc.archive_available && (
                        <a
                          className="download-link"
                          href={`/api/documents/${doc.id}/archive`}
                          target="_blank"
                          rel="noreferrer"
                          aria-label={`View searchable PDF for ${doc.original_name}`}
                          title="View searchable PDF"
                        >
                          <Eye size={18} />
                        </a>
                      )}
                      <a
                        className="download-link"
                        href={`/api/documents/${doc.id}/original`}
                        aria-label={`Download ${doc.original_name}`}
                      >
                        <ArrowDownToLine size={18} />
                      </a>
                    </article>
                  ))}
                </div>
                {nextCursor !== null && (
                  <Button variant="secondary" className="load-more" disabled={loadingMore} onClick={() => void loadDocuments(query, nextCursor)}>
                    {loadingMore ? "Loading…" : "Show more documents"}
                  </Button>
                )}
                </>
              )}
            </>
          )}
          <div className="page-footer">
            <span>Ripiano · Documents at home</span>
            <span>Original files are preserved</span>
          </div>
        </section>
      </main>

      {dropActive && (
        <div className="drop-overlay">
          <UploadCloud size={40} />
          <strong>Drop to add documents</strong>
        </div>
      )}
      {showAdd && (
        <Modal titleId="add-heading" panelClassName="add-modal" onClose={() => setShowAdd(false)}>
            <input
              ref={cameraRef}
              className="visually-hidden"
              tabIndex={-1}
              type="file"
              accept="image/*"
              capture="environment"
              onChange={(event: ChangeEvent<HTMLInputElement>) => void upload(event.target.files)}
            />
            <input
              ref={galleryRef}
              className="visually-hidden"
              tabIndex={-1}
              type="file"
              accept="image/*"
              multiple
              onChange={(event) => void upload(event.target.files)}
            />
            <input
              ref={fileRef}
              className="visually-hidden"
              tabIndex={-1}
              type="file"
              accept="application/pdf,image/jpeg,image/png"
              multiple
              onChange={(event) => void upload(event.target.files)}
            />
            <button
              className="modal-close"
              onClick={() => setShowAdd(false)}
              aria-label="Close"
            >
              <X size={20} />
            </button>
            <div className="eyebrow">
              <span className="eyebrow-line" /> ADD TO YOUR ARCHIVE
            </div>
            <h2 id="add-heading">Bring a document in.</h2>
            <p>
              Choose the way that works for you. We’ll preserve the original and
              make its text searchable.
            </p>
            <div className="add-options">
              <button onClick={scan}>
                <span className="add-option-icon">
                  <Camera size={23} />
                </span>
                <span>
                  <strong>{nativeScanner ? "Scan pages" : "Take a photo"}</strong>
                  <small>{nativeScanner ? "Capture, crop and combine pages" : "Open your device camera"}</small>
                </span>
                <ArrowRight size={18} />
              </button>
              <button onClick={() => galleryRef.current?.click()}>
                <span className="add-option-icon">
                  <ImagePlus size={23} />
                </span>
                <span>
                  <strong>Choose from photos</strong>
                  <small>Pick an image from your gallery</small>
                </span>
                <ArrowRight size={18} />
              </button>
              <button onClick={() => fileRef.current?.click()}>
                <span className="add-option-icon">
                  <FolderOpen size={23} />
                </span>
                <span>
                  <strong>Browse files</strong>
                  <small>PDF, PNG, or JPEG</small>
                </span>
                <ArrowRight size={18} />
              </button>
            </div>
            <div className="modal-foot">
              {nativeScanner
                ? "Scans stay on this device until Ripiano confirms the upload."
                : "Camera behavior depends on your browser. Use the Android app for multi-page scanning."}
            </div>
        </Modal>
      )}
      {selectedDocument && (
        <DocumentPanel
          key={selectedDocument.id}
          initial={selectedDocument}
          onClose={() => setSelectedDocument(null)}
          onSaved={() => { void loadDocuments(query); void loadFilterOptions(); setActionRefresh((value) => value + 1); setInboxRefresh((value) => value + 1); }}
          onTrashed={() => { void loadDocuments(query); setTrashRefresh((value) => value + 1); setActionRefresh((value) => value + 1); setInboxRefresh((value) => value + 1); }}
          onOpenTags={() => {
            setSelectedDocument(null);
            setView("tags");
          }}
          onOpenLocations={() => {
            setSelectedDocument(null);
            setView("physical");
          }}
          onOpenDuplicate={(id) => {
            void request<Document>(`/api/documents/${id}`)
              .then(setSelectedDocument)
              .catch((cause) => setError(cause.message));
          }}
        />
      )}
    </div>
  );
}

export default App;
