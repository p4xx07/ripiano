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
  Layers,
  Mail,
  BarChart3,
  ShieldCheck,
  Workflow,
  Camera,
  Check,
  CircleAlert,
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
  UserCog,
  Users,
  UploadCloud,
  X,
} from "lucide-react";
import { ApiError, CustomField, Document, FilingItem, formatDate, LibraryFilters, request, Session, Tag, tagPathLabel } from "./api";
import DocumentPanel from "./DocumentPanel";
import ActionPanel from "./ActionPanel";
import InboxPanel from "./InboxPanel";
import AgentPanel from "./AgentPanel";
import MailPanel from "./MailPanel";
import WorkflowsPanel from "./WorkflowsPanel";
import SecurityPanel from "./SecurityPanel";
import PeoplePanel from "./PeoplePanel";
import SharedPanel from "./SharedPanel";
import SharedDocumentPanel from "./SharedDocumentPanel";
import BundlePanel from "./BundlePanel";
import OverviewPanel from "./OverviewPanel";
import PhysicalPanel from "./PhysicalPanel";
import TagPanel from "./TagPanel";
import SavedSearchBar from "./SavedSearchBar";
import TrashPanel from "./TrashPanel";
import { Button, Field, Modal } from "./ui";
import { applyTheme, readThemePreference, saveThemePreference, ThemePreference } from "./theme";
import { setLanguagePreference, useLanguagePreference, useMessages, type LanguagePreference } from "./i18n";
import appMessages from "./locales/App";
import backupMessages from "./locales/AppBackups";
import libraryMessages from "./locales/AppLibrary";

function AppearanceControl({ preference, onChange }: {
  preference: ThemePreference;
  onChange: (preference: ThemePreference) => void;
}) {
  const m = useMessages(appMessages);
  const languagePreference = useLanguagePreference();
  return (
    <>
    <label className="appearance-control">
      <span>{m.appearance}</span>
      <select value={preference} onChange={(event) => onChange(event.target.value as ThemePreference)}>
        <option value="system">{m.themeSystem}</option>
        <option value="light">{m.themeLight}</option>
        <option value="dark">{m.themeDark}</option>
        <option value="amoled">{m.themeAmoled}</option>
      </select>
    </label>
    <label className="appearance-control">
      <span>{m.language}</span>
      <select value={languagePreference} onChange={(event) => setLanguagePreference(event.target.value as LanguagePreference)}>
        <option value="system">{m.languageSystem}</option>
        <option value="en">English</option>
        <option value="it">{m.italianPreview}</option>
      </select>
    </label>
    </>
  );
}

type BackupRun = {
  id: string;
  status: "pending" | "running" | "complete" | "failed" | "cancelled";
  trigger: string;
  snapshot_name: string;
  error: string;
  created_at: string;
  can_cancel: boolean;
  can_retry: boolean;
  retry_of: string | null;
};

type BrowseExportRun = {
  id: string;
  status: "pending" | "running" | "complete" | "failed" | "cancelled";
  document_count: number;
  folder: string | null;
  error: string;
  created_at: string;
  can_cancel: boolean;
  can_retry: boolean;
  retry_of: string | null;
};

const emptyLibraryFilters: LibraryFilters = {
  tag_id: "", copy_status: "", correspondent_id: "", document_type_id: "", date_from: "", date_to: "", custom_field_id: "", custom_value: "", custom_min: "", custom_max: "",
};

function TagSummary({ tags }: { tags: Document["tags"] }) {
  const m = useMessages(appMessages);
  const priority = { manual: 0, source: 1, model: 2, learned: 3, rule: 4 };
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
          {m.moreTags(visibleFirst.length - limit)}
        </span>
      )}
    </>;
  }
  return <>
    <div className="document-tags document-tags-desktop">{chips(2)}</div>
    <div className="document-tags document-tags-mobile">{chips(1)}</div>
  </>;
}

function PaperCopySummary({ copies }: { copies: Document["physical_copies"] }) {
  const m = useMessages(appMessages);
  const located = copies.filter((copy) => !copy.missing_at);
  const missingCount = copies.length - located.length;
  return <div className="document-physical">
    {located.length > 0 && <span className="physical-location">
      <MapPin size={13} />
      {located[0].location_path.join(" / ") || m.paperAwaitingLocation}
      {located.length > 1 && ` +${located.length - 1}`}
    </span>}
    {missingCount > 0 && <span className="physical-missing">
      <CircleAlert size={13} />
      {m.paperMissing(missingCount)}
    </span>}
  </div>;
}

declare global {
  interface Window {
    RipianoAndroid?: { postMessage(message: string): void };
  }
}

function AuthScreen({
  setup,
  onAuthenticated,
  appearance,
  onAppearanceChange,
}: {
  setup: boolean;
  onAuthenticated: (value: Session) => void;
  appearance: ThemePreference;
  onAppearanceChange: (preference: ThemePreference) => void;
}) {
  const m = useMessages(appMessages);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [setupKey, setSetupKey] = useState("");
  const [code, setCode] = useState("");
  const [needsCode, setNeedsCode] = useState(false);
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
          ...(needsCode ? { code } : {}),
        }),
      });
      onAuthenticated(await request<Session>("/api/session"));
    } catch (cause) {
      if (cause instanceof ApiError && cause.data.two_factor_required) {
        if (!needsCode) {
          setNeedsCode(true);
          return;
        }
        setCode("");
      }
      setError(cause instanceof Error ? cause.message : m.signInError);
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
          <span className="eyebrow-line" /> {m.authEyebrow}
        </div>
        <h1>{setup ? m.setupTitle : m.signInTitle}</h1>
        <p>
          {setup
            ? m.setupIntro
            : m.signInIntro}
        </p>
        <form onSubmit={submit}>
          <Field label={m.username}>
            <input
              autoComplete="username"
              value={username}
              onChange={(event) => { setUsername(event.target.value); setNeedsCode(false); setCode(""); }}
              required
            />
          </Field>
          <Field label={m.password}>
            <input
              type="password"
              autoComplete={setup ? "new-password" : "current-password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={setup ? 12 : undefined}
              required
            />
          </Field>
          {needsCode && <p className="visually-hidden" role="status">{m.twoStepOn}</p>}
          {needsCode && (
            <Field label={m.authenticatorCode} hint={m.authenticatorHint}>
              <input
                autoComplete="one-time-code"
                inputMode="text"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                maxLength={32}
                autoFocus
                required
              />
            </Field>
          )}
          {setup && (
            <Field label={m.setupKey}>
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
            {busy ? m.pleaseWait : setup ? m.createArchive : m.signIn}{" "}
            <ArrowRight size={18} />
          </Button>
        </form>
      </div>
      <div className="auth-foot">
        <LockKeyhole size={14} /> {m.storedOnServer}
      </div>
      <AppearanceControl preference={appearance} onChange={onAppearanceChange} />
    </main>
  );
}

function BackupPanel() {
  const m = useMessages(backupMessages);
  const [runs, setRuns] = useState<BackupRun[]>([]);
  const [browseRuns, setBrowseRuns] = useState<BrowseExportRun[]>([]);
  const [schedule, setSchedule] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [browseBusy, setBrowseBusy] = useState(false);
  const [jobBusy, setJobBusy] = useState("");
  const [jobFocus, setJobFocus] = useState("");
  const load = useCallback(async () => {
    try {
      const [result, browse] = await Promise.all([
        request<{ schedule: string; runs: BackupRun[] }>("/api/backups"),
        request<{ runs: BrowseExportRun[] }>("/api/browse-exports"),
      ]);
      setRuns(result.runs);
      setBrowseRuns(browse.runs);
      setSchedule(result.schedule);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : m.loadError,
      );
    }
  }, [m]);
  useEffect(() => {
    void load();
    const timer = window.setInterval(load, 10000);
    return () => window.clearInterval(timer);
  }, [load]);
  useEffect(() => {
    if (!jobFocus) return;
    const target = document.querySelector<HTMLElement>(`[data-job-focus="${jobFocus}"]`);
    if (target) {
      target.focus();
      setJobFocus("");
    }
  }, [jobFocus, runs, browseRuns]);

  async function start() {
    setBusy(true);
    setError("");
    try {
      await request("/api/backups", { method: "POST" });
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : m.startError,
      );
    } finally {
      setBusy(false);
    }
  }

  async function startBrowse() {
    setBrowseBusy(true);
    setError("");
    try {
      await request("/api/browse-exports", { method: "POST" });
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.browseError);
    } finally {
      setBrowseBusy(false);
    }
  }

  async function controlJob(kind: "backup" | "browse", id: string, action: "cancel" | "retry") {
    setJobBusy(id);
    setError("");
    try {
      const path = kind === "backup" ? "backups" : "browse-exports";
      const result = await request<{ id: string }>(`/api/${path}/${id}/${action}`, { method: "POST" });
      await load();
      setJobFocus(`${kind}-${action === "cancel" ? id + "-retry" : result.id + "-status"}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.jobError(action));
    } finally {
      setJobBusy("");
    }
  }

  const browseActive = browseRuns.some((run) => run.status === "pending" || run.status === "running");

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            <span className="eyebrow-line" /> {m.eyebrow}
          </div>
          <h1>
            {m.heading}<span className="heading-period">.</span>
          </h1>
          <p>{m.intro}</p>
        </div>
        <Button
          onClick={start}
          disabled={busy}
        >
          <DatabaseBackup size={18} /> {busy ? m.starting : m.backUpNow}
        </Button>
      </div>
      <div className="backup-summary">
        <div>
          <strong>{m.schedule}</strong>
          <span>{m.everyDay(schedule || "…")}</span>
        </div>
        <div>
          <strong>{m.output}</strong>
          <span>{m.outputText}</span>
        </div>
      </div>
      {error && (
        <div className="inline-error" role="alert">
          {error}
        </div>
      )}
      <section className="browse-section" aria-label={m.browseSection}>
        <div className="section-heading browse-heading">
          <div>
            <h2>{m.browseHeading}</h2>
            <p>{m.browseIntro}</p>
          </div>
          <Button variant="secondary" onClick={startBrowse} disabled={browseBusy || browseActive}>
            <FolderOpen size={18} /> {browseBusy ? m.starting : browseActive ? m.buildingCopy : m.buildCopy}
          </Button>
        </div>
        {browseRuns.length ? (
          <div className="document-list backup-list">
            {browseRuns.map((run) => (
              <div className="document-row" key={run.id}>
                <div className="document-icon"><FolderOpen size={20} /></div>
                <div className="document-info">
                  <h3>{run.folder ? m.readyOnNas(run.document_count) : m.browseCopyOn(formatDate(run.created_at))}</h3>
                  <div className="document-meta">{m.created(formatDate(run.created_at))}{run.retry_of ? m.retrySuffix : ""}</div>
                  {run.folder && <p className="browse-folder"><code>{run.folder}</code></p>}
                  {run.error && <p className="doc-error">{run.error}</p>}
                  {run.status === "running" && <p className="job-running-hint">{m.runningHint}</p>}
                </div>
                <span tabIndex={-1} data-job-focus={`browse-${run.id}-status`} className={`status status-${run.status === "complete" ? "ready" : run.status === "failed" ? "failed" : run.status === "cancelled" ? "cancelled" : "pending"}`}>
                  {run.status === "complete" && !run.folder ? m.removed : m.status(run.status)}
                </span>
                {(run.can_cancel || (run.can_retry && !browseActive)) && <div className="job-controls">
                  {run.can_cancel && <button type="button" aria-label={m.cancelBrowseLabel(run.id.slice(0, 8))} disabled={!!jobBusy} onClick={() => void controlJob("browse", run.id, "cancel")}>{m.cancelQueued}</button>}
                  {run.can_retry && !browseActive && <button type="button" data-job-focus={`browse-${run.id}-retry`} aria-label={m.retryBrowseLabel(run.id.slice(0, 8))} disabled={!!jobBusy} onClick={() => void controlJob("browse", run.id, "retry")}>{m.tryAgain}</button>}
                </div>}
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state browse-empty">
            <div className="empty-icon"><FolderOpen size={32} /></div>
            <h3>{m.noBrowseTitle}</h3>
            <p>{m.noBrowseText}</p>
          </div>
        )}
      </section>
      <div className="section-heading">
        <div>
          <h2>{m.recentHeading}</h2>
          <p>{m.recentIntro}</p>
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
                      ? m.manualBackup
                      : run.trigger === "retry" ? m.backupRetry : m.scheduledBackup)}
                </h3>
                <div className="document-meta">
                  {formatDate(run.created_at)} <span>·</span> {m.trigger(run.trigger)}
                </div>
                {run.error && <p className="doc-error">{run.error}</p>}
                {run.status === "running" && <p className="job-running-hint">{m.runningHint}</p>}
              </div>
              <span tabIndex={-1} data-job-focus={`backup-${run.id}-status`}
                className={`status status-${run.status === "complete" ? "ready" : run.status === "failed" ? "failed" : run.status === "cancelled" ? "cancelled" : "pending"}`}
              >
                {m.status(run.status)}
              </span>
              {(run.can_cancel || run.can_retry) && <div className="job-controls">
                {run.can_cancel && <button type="button" aria-label={m.cancelBackupLabel(run.id.slice(0, 8))} disabled={!!jobBusy} onClick={() => void controlJob("backup", run.id, "cancel")}>{m.cancelQueued}</button>}
                {run.can_retry && <button type="button" data-job-focus={`backup-${run.id}-retry`} aria-label={m.retryBackupLabel(run.id.slice(0, 8))} disabled={!!jobBusy} onClick={() => void controlJob("backup", run.id, "retry")}>{m.tryAgain}</button>}
              </div>}
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <div className="empty-icon">
            <DatabaseBackup size={32} />
          </div>
          <h3>{m.noSnapshotsTitle}</h3>
          <p>{m.noSnapshotsText}</p>
        </div>
      )}
    </>
  );
}

function App() {
  const m = useMessages(appMessages);
  const l = useMessages(libraryMessages);
  const [appearance, setAppearance] = useState<ThemePreference>(readThemePreference);
  useEffect(() => {
    applyTheme(appearance);
    const media = matchMedia("(prefers-color-scheme: dark)");
    const update = () => { if (appearance === "system") applyTheme(appearance); };
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [appearance]);
  function changeAppearance(preference: ThemePreference) {
    setAppearance(preference);
    saveThemePreference(preference);
  }
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
  const [bulkDate, setBulkDate] = useState("");
  const [bulkBusy, setBulkBusy] = useState(false);
  const [confirmBulkTrash, setConfirmBulkTrash] = useState(false);
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
  const [initialMailNotice] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    const connected = params.get("mail_connected");
    const failed = params.get("mail_error");
    if (!connected && !failed) return null;
    window.history.replaceState(null, "", window.location.pathname);
    return failed ? { kind: "error" as const, text: failed } : { kind: "ok" as const, text: connected ?? "" };
  });
  const [view, setView] = useState<
    "documents" | "inbox" | "actions" | "tags" | "physical" | "backups" | "agents" | "trash" | "integrations" | "workflows" | "security" | "overview" | "shared" | "people"
  >(initialSticker || initialLocation ? "physical" : initialMailNotice ? "integrations" : "documents");
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(
    null,
  );
  const [actionRefresh, setActionRefresh] = useState(0);
  const [inboxRefresh, setInboxRefresh] = useState(0);
  const [trashRefresh, setTrashRefresh] = useState(0);
  const [sharedRefresh, setSharedRefresh] = useState(0);
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const latestSearch = useRef(0);
  const loadingMoreRef = useRef(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const focusSearchOnView = useRef(false);

  // Links from workflow emails and webhooks open one document: /?document=<id>
  useEffect(() => {
    if (!session) return;
    const params = new URLSearchParams(window.location.search);
    const id = params.get("document");
    if (!id) return;
    params.delete("document");
    window.history.replaceState(null, "", `${window.location.pathname}${params.size ? `?${params}` : ""}${window.location.hash}`);
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) return;
    void request<Document>(`/api/documents/${id}`).then(setSelectedDocument).catch(() => setError(m.documentUnavailable));
  }, [session, m]);

  useEffect(() => {
    if (view === "documents" && focusSearchOnView.current) {
      focusSearchOnView.current = false;
      searchRef.current?.focus();
    }
  }, [view]);

  useEffect(() => {
    if (!session?.authenticated) return;
    function shortcut(event: KeyboardEvent) {
      if (event.defaultPrevented || event.repeat || event.isComposing ||
          event.altKey || event.ctrlKey || event.metaKey ||
          document.querySelector('[role="dialog"]')) return;
      const focused = document.activeElement;
      if (focused instanceof HTMLElement &&
          (focused.isContentEditable || focused.matches("input, textarea, select"))) return;
      if (event.key === "/") {
        event.preventDefault();
        setMenuOpen(false);
        if (view === "documents") searchRef.current?.focus();
        else {
          focusSearchOnView.current = true;
          setView("documents");
        }
      } else if (event.key.toLowerCase() === "n") {
        event.preventDefault();
        setMenuOpen(false);
        setShowAdd(true);
      }
    }
    document.addEventListener("keydown", shortcut);
    return () => document.removeEventListener("keydown", shortcut);
  }, [session?.authenticated, view]);

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
      setError(cause instanceof Error ? cause.message : l.loadFilterChoicesFailed);
    }
  }, [l]);

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

  async function applyBulkDate(clear: boolean) {
    if (!selectedIds.length || (!clear && !bulkDate)) return;
    setBulkBusy(true);
    setBulkError("");
    setBulkNotice("");
    try {
      const result = await request<{ updated: number }>("/api/documents/bulk-date", {
        method: "POST",
        body: JSON.stringify({ document_ids: selectedIds, document_date: clear ? null : bulkDate }),
      });
      setBulkNotice(`${clear ? "Cleared document date" : `Set document date to ${bulkDate}`} for ${result.updated} ${result.updated === 1 ? "document" : "documents"}.`);
      setSelectedIds([]);
      await loadDocuments(query);
    } catch (cause) {
      setBulkError(cause instanceof Error ? cause.message : "Could not update document dates");
    } finally {
      setBulkBusy(false);
    }
  }

  async function applyBulkOcr(mode: "retry" | "rebuild") {
    if (!selectedIds.length) return;
    setBulkBusy(true);
    setBulkError("");
    setBulkNotice("");
    try {
      const result = await request<{ scheduled: number; skipped: number; skipped_ids: string[] }>(
        "/api/documents/bulk-reprocess", {
          method: "POST",
          body: JSON.stringify({ mode, document_ids: selectedIds }),
        },
      );
      setSelectedIds(result.skipped_ids);
      setBulkNotice(result.scheduled
        ? `Started OCR for ${result.scheduled} ${result.scheduled === 1 ? "document" : "documents"}.${result.skipped ? ` ${result.skipped} still selected because ${result.skipped === 1 ? "it was" : "they were"} not eligible.` : ""}`
        : "No selected documents are eligible for this OCR action.");
      if (result.scheduled) await loadDocuments(query);
    } catch (cause) {
      setBulkError(cause instanceof Error ? cause.message : "Could not start OCR");
    } finally {
      setBulkBusy(false);
    }
  }

  async function mergeSelected() {
    if (selectedIds.length < 2) return;
    setBulkBusy(true);
    setBulkError("");
    setBulkNotice("");
    try {
      const merged = await request<{ id: string; title: string }>("/api/documents/merge", {
        method: "POST",
        body: JSON.stringify({ document_ids: selectedIds }),
      });
      setSelectedIds([]);
      setBulkNotice(`Created “${merged.title}”. The selected documents are unchanged.`);
      await loadDocuments(query);
    } catch (cause) {
      setBulkError(cause instanceof Error ? cause.message : "Could not merge documents");
    } finally {
      setBulkBusy(false);
    }
  }

  async function applyBulkTrash() {
    if (!selectedIds.length) return;
    setBulkBusy(true);
    setBulkError("");
    setBulkNotice("");
    try {
      const result = await request<{ updated: number }>("/api/documents/bulk-trash", {
        method: "POST",
        body: JSON.stringify({ action: "trash", document_ids: selectedIds }),
      });
      setSelectedIds([]);
      setConfirmBulkTrash(false);
      setBulkNotice(`Moved ${result.updated} ${result.updated === 1 ? "document" : "documents"} to Trash. Restore them from Trash if needed.`);
      await loadDocuments(query);
      setTrashRefresh((value) => value + 1);
      setActionRefresh((value) => value + 1);
      setInboxRefresh((value) => value + 1);
    } catch (cause) {
      setBulkError(cause instanceof Error ? cause.message : "Could not move documents to Trash");
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
      const message = cause instanceof Error ? cause.message : l.loadDocumentsFailed;
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
  }, [filters, sort, l]);

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
        setError(detail.message || l.scanUploadFailed);
      }
      if (detail.status !== "uploading") setUploading(false);
    }
    window.addEventListener("ripiano-native-upload", onNativeUpload);
    return () => window.removeEventListener("ripiano-native-upload", onNativeUpload);
  }, [query, loadDocuments, l]);

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
        setUploadProgress(l.addingProgress(index + 1, chosen.length));
        try {
          const form = new FormData();
          form.append("document", file);
          await request<Document>("/api/documents", {
            method: "POST",
            body: form,
          });
        } catch (cause) {
          failures.push(`${file.name}: ${cause instanceof Error ? cause.message : l.uploadFailed}`);
        }
      }
      await loadDocuments("");
      if (failures.length) setUploadReport({ total: chosen.length, failures });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : l.uploadFailed);
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
      // The next person to sign in on this device starts at the Library, with nothing left open.
      setSelectedDocument(null);
      setView("documents");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.signOutError);
    }
  }

  async function retryDocument(id: string) {
    try {
      await request(`/api/documents/${id}/retry`, { method: "POST" });
      await loadDocuments(query);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : l.retryDocumentFailed,
      );
    }
  }

  if (loading) return <div className="loading-screen">{m.opening}</div>;
  if (!session)
    return (
      <div className="loading-screen error-screen">
        {error || m.connectError}{" "}
        <button onClick={() => location.reload()}>{m.tryAgain}</button>
      </div>
    );
  if (!session.authenticated)
    return (
      <AuthScreen setup={session.setup_required} onAuthenticated={setSession}
        appearance={appearance} onAppearanceChange={changeAppearance} />
    );

  const isEmpty = counts.total === 0;
  const activeFilterCount = Object.entries(filters).filter(([key, value]) => !["custom_value", "custom_min", "custom_max"].includes(key) && Boolean(value)).length;
  const selectedCustomField = filterOptions.custom_fields.find((field) => field.id === filters.custom_field_id);
  const tagById = new Map(filterOptions.tags.map((tag) => [tag.id, tag]));
  const tagOptions = [...filterOptions.tags].sort((a, b) =>
    tagPathLabel(a, tagById).localeCompare(tagPathLabel(b, tagById)));
  const viewLabels = {
    documents: m.allDocuments, inbox: m.inbox, actions: m.needsAction, tags: m.tags,
    physical: m.physical, backups: m.backups, agents: m.agents, trash: m.trash,
    integrations: m.email, workflows: m.workflows, security: m.security,
    overview: m.overview, shared: m.shared, people: m.people,
  };

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
          <button className="sidebar-close" aria-label={m.dismissNavigation} onClick={() => setMenuOpen(false)}>
            <X size={19} />
          </button>
        </div>
        <div className="sidebar-label">{m.yourSpace}</div>
        <button
          className={`nav-link ${view === "inbox" ? "active" : ""}`}
          onClick={() => { setView("inbox"); setMenuOpen(false); }}
        >
          <Inbox size={18} /> {m.inbox}
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
          <FolderOpen size={18} /> {m.allDocuments}
        </button>
        <button
          className={`nav-link ${view === "actions" ? "active" : ""}`}
          onClick={() => { setView("actions"); setMenuOpen(false); }}
        >
          <ClipboardList size={18} /> {m.needsAction}
        </button>
        <button
          className={`nav-link ${view === "tags" ? "active" : ""}`}
          onClick={() => {
            setView("tags");
            setMenuOpen(false);
          }}
        >
          <TagIcon size={18} /> {m.tags}
        </button>
        <button
          className={`nav-link ${view === "physical" ? "active" : ""}`}
          onClick={() => {
            setView("physical");
            setMenuOpen(false);
          }}
        >
          <MapPin size={18} /> {m.physical}
        </button>
        <button className={`nav-link ${view === "overview" ? "active" : ""}`} onClick={() => { setView("overview"); setMenuOpen(false); }}>
          <BarChart3 size={18} /> {m.overview}
        </button>
        <button className={`nav-link ${view === "workflows" ? "active" : ""}`} onClick={() => { setView("workflows"); setMenuOpen(false); }}>
          <Workflow size={18} /> {m.workflows}
        </button>
        <button className={`nav-link ${view === "security" ? "active" : ""}`} onClick={() => { setView("security"); setMenuOpen(false); }}>
          <ShieldCheck size={18} /> {m.security}
        </button>
        <button className={`nav-link ${view === "integrations" ? "active" : ""}`} onClick={() => { setView("integrations"); setMenuOpen(false); }}>
          <Mail size={18} /> {m.email}
        </button>
        <button className={`nav-link ${view === "shared" ? "active" : ""}`} onClick={() => { setView("shared"); setMenuOpen(false); }}>
          <Users size={18} /> {m.shared}
        </button>
        <button className={`nav-link ${view === "trash" ? "active" : ""}`} onClick={() => { setView("trash"); setMenuOpen(false); }}>
          <Trash2 size={18} /> {m.trash}
        </button>
        {session.owner && (
          <button
            className={`nav-link ${view === "agents" ? "active" : ""}`}
            onClick={() => {
              setView("agents");
              setMenuOpen(false);
            }}
          >
            <Bot size={18} /> {m.agents}
          </button>
        )}
        {session.owner && (
          <button className={`nav-link ${view === "people" ? "active" : ""}`} onClick={() => { setView("people"); setMenuOpen(false); }}>
            <UserCog size={18} /> {m.people}
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
            <DatabaseBackup size={18} /> {m.backups}
          </button>
        )}
        <div className="sidebar-spacer" />
        <AppearanceControl preference={appearance} onChange={changeAppearance} />
        <div className="sidebar-note">
          <div className="sidebar-note-icon">
            <LockKeyhole size={17} />
          </div>
          <strong>{m.sidebarNoteTitle}</strong>
          <span>{m.sidebarNoteText}</span>
        </div>
        <button className="profile" onClick={signOut} title={m.signOut}>
          <span className="avatar">
            {session.username?.slice(0, 1).toUpperCase()}
          </span>
          <span className="profile-name">
            {session.username}
            <small>{session.owner ? m.admin : m.yourArchive}</small>
          </span>
          <LogOut size={16} />
        </button>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label={m.toggleMenu}
          >
            <Menu size={21} />
          </button>
          <div className="topbar-crumb">
            {m.yourArchive} <span>/</span> {viewLabels[view]}
          </div>
          <div className="topbar-right">
            <span className="private-dot" /> {m.privateAndYours}
          </div>
        </header>
        <section className="page-content">
          {view === "backups" ? (
            <BackupPanel />
          ) : view === "shared" ? (
            <SharedPanel refreshKey={sharedRefresh} onOpenDocument={setSelectedDocument} />
          ) : view === "people" ? (
            <PeoplePanel currentUsername={session.username} />
          ) : view === "inbox" ? (
            <InboxPanel refreshKey={inboxRefresh} onOpenDocument={setSelectedDocument} />
          ) : view === "actions" ? (
            <ActionPanel refreshKey={actionRefresh} onOpenDocument={setSelectedDocument} />
          ) : view === "trash" ? (
            <TrashPanel refreshKey={trashRefresh} onRestored={() => { void loadDocuments(query); setActionRefresh((value) => value + 1); setInboxRefresh((value) => value + 1); }} />
          ) : view === "agents" ? (
            <AgentPanel />
          ) : view === "overview" ? (
            <OverviewPanel onNavigate={(target) => setView(target)} onOpenUntagged={() => {
              setQuery("is:untagged");
              setFilters({ ...emptyLibraryFilters });
              setNextCursor(null);
              setView("documents");
            }} />
          ) : view === "security" ? (
            <SecurityPanel />
          ) : view === "workflows" ? (
            <WorkflowsPanel onOpenDocument={(id) => void request<Document>(`/api/documents/${id}`).then(setSelectedDocument).catch((cause) => setError(cause.message))} />
          ) : view === "integrations" ? (
            <MailPanel notice={initialMailNotice} />
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
                    <span className="eyebrow-line" /> {l.eyebrow}
                  </div>
                  <h1>
                    {l.title}
                    <span className="heading-period">.</span>
                  </h1>
                  <p>{l.intro}</p>
                </div>
                <Button
                  className="desktop-add"
                  onClick={() => setShowAdd(true)}
                >
                  <Plus size={19} /> {l.addDocument}
                </Button>
              </div>

              <div className="summary-row">
                <div className="summary-card">
                  <span className="summary-icon">
                    <FileText size={20} />
                  </span>
                  <div>
                    <strong>{counts.total}</strong>
                    <span>{query || activeFilterCount ? l.matchingDocuments : l.documents}</span>
                  </div>
                </div>
                <div className="summary-card">
                  <span className="summary-icon green">
                    <Check size={20} />
                  </span>
                  <div>
                    <strong>{counts.ready}</strong>
                    <span>{l.readyToFind}</span>
                  </div>
                </div>
                <div className="summary-card">
                  <span className="summary-icon amber">
                    <Clock3 size={20} />
                  </span>
                  <div>
                    <strong>{counts.waiting}</strong>
                    <span>{l.beingProcessed}</span>
                  </div>
                </div>
              </div>

              <div className="section-heading">
                <div>
                  <h2>{l.yourDocuments}</h2>
                  <p>{l.searchIntro}</p>
                </div>
                <Button type="button" variant="secondary" aria-label={l.refresh} title={l.refreshTitle} onClick={() => void loadDocuments(query)}>
                  <RotateCcw size={16} /> <span className="refresh-label">{l.refresh}</span>
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
                    ref={searchRef}
                    value={query}
                    onChange={(event) => { setQuery(event.target.value); setNextCursor(null); }}
                    placeholder={l.searchPlaceholder}
                    aria-label={l.searchAria}
                  />
                  {!query && <kbd className="search-shortcut" aria-hidden="true">/</kbd>}
                  {query && (
                    <button
                      onClick={() => setQuery("")}
                      aria-label={l.clearSearch}
                    >
                      <X size={16} />
                    </button>
                  )}
                </div>
                <select className="library-sort" aria-label={l.sortAria} value={sort} onChange={(event) => { setSort(event.target.value); setNextCursor(null); }}>
                  <option value="">{l.recommendedOrder}</option>
                  <option value="newest">{l.newestAdded}</option>
                  <option value="oldest">{l.oldestAdded}</option>
                  <option value="document_newest">{l.newestDocumentDate}</option>
                  <option value="document_oldest">{l.oldestDocumentDate}</option>
                  <option value="title_asc">{l.titleAscending}</option>
                  <option value="title_desc">{l.titleDescending}</option>
                </select>
                <Button type="button" variant="secondary" className="filter-toggle" aria-expanded={showFilters} aria-controls="library-filters" onClick={() => setShowFilters((current) => !current)}>
                  <SlidersHorizontal size={17} /> {l.filters}{activeFilterCount ? ` (${activeFilterCount})` : ""}
                </Button>
                <Button
                  variant="secondary"
                  className="mobile-add"
                  onClick={() => setShowAdd(true)}
                >
                  <Plus size={18} /> {l.addShort}
                </Button>
              </div>
              <details className="search-syntax">
                <summary>{l.preciseSearch}</summary>
                <p>{l.searchHelpUse} <code>{l.tagExample}</code>, <code>{l.senderExample}</code>, <code>date:2026-04-15</code> {l.searchHelpOr} <code>is:untagged</code>. {l.searchHelpAlso} <code>title:</code>, <code>text:</code>, <code>note:</code>, <code>type:</code>, <code>sticker:</code>, {l.searchHelpOr} <code>is:tagged</code>. {l.searchHelpCombine} {l.searchHelpPress} <kbd>/</kbd> {l.searchHelpToSearch} <kbd>N</kbd> {l.searchHelpToAdd}</p>
              </details>
              {showFilters && <div className="library-filters" id="library-filters">
                <Field label={l.tag} className="detail-label"><select value={filters.tag_id} onChange={(event) => updateFilter("tag_id", event.target.value)}><option value="">{l.anyTag}</option>{tagOptions.map((tag) => <option key={tag.id} value={tag.id}>{tagPathLabel(tag, tagById)}</option>)}</select></Field>
                <Field label={l.paperCopy} hint={l.paperHint} className="detail-label"><select value={filters.copy_status} onChange={(event) => updateFilter("copy_status", event.target.value)}><option value="">{l.any}</option><option value="paper">{l.hasPaper}</option><option value="virtual">{l.digitalOnly}</option><option value="missing">{l.missing}</option></select></Field>
                <Field label={l.from} className="detail-label"><select value={filters.correspondent_id} onChange={(event) => updateFilter("correspondent_id", event.target.value)}><option value="">{l.anySender}</option>{filterOptions.correspondents.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field>
                <Field label={l.documentType} className="detail-label"><select value={filters.document_type_id} onChange={(event) => updateFilter("document_type_id", event.target.value)}><option value="">{l.anyType}</option>{filterOptions.document_types.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field>
                <Field label={l.customDetail} className="detail-label custom-filter-field"><select value={filters.custom_field_id} onChange={(event) => updateFilter("custom_field_id", event.target.value)}><option value="">{l.anyCustomDetail}</option>{filterOptions.custom_fields.map((field) => <option key={field.id} value={field.id}>{field.name}</option>)}</select></Field>
                {selectedCustomField && <Field label={["number", "date"].includes(selectedCustomField.kind) ? l.exactValue : l.namedValue(selectedCustomField.name)} className="detail-label custom-filter-value">{selectedCustomField.kind === "boolean" ? <select value={filters.custom_value} onChange={(event) => updateFilter("custom_value", event.target.value)}><option value="">{l.anyValue}</option><option value="yes">{l.yes}</option><option value="no">{l.no}</option></select> : <input aria-label={`${selectedCustomField.name} ${["number", "date"].includes(selectedCustomField.kind) ? l.exactly : l.value}`} type={selectedCustomField.kind === "text" ? "text" : selectedCustomField.kind} step={selectedCustomField.kind === "number" ? "any" : undefined} value={filters.custom_value} onChange={(event) => updateFilter("custom_value", event.target.value)} placeholder={selectedCustomField.kind === "text" ? l.contains : undefined} />}</Field>}
                {selectedCustomField && (selectedCustomField.kind === "number" || selectedCustomField.kind === "date") && <>
                  <Field label={l.from} className="detail-label custom-filter-value"><input aria-label={`${selectedCustomField.name} ${l.from}`} type={selectedCustomField.kind} step={selectedCustomField.kind === "number" ? "any" : undefined} value={filters.custom_min} max={filters.custom_max || undefined} onChange={(event) => updateFilter("custom_min", event.target.value)} /></Field>
                  <Field label={l.to} className="detail-label custom-filter-value"><input aria-label={`${selectedCustomField.name} ${l.to}`} type={selectedCustomField.kind} step={selectedCustomField.kind === "number" ? "any" : undefined} value={filters.custom_max} min={filters.custom_min || undefined} onChange={(event) => updateFilter("custom_max", event.target.value)} /></Field>
                </>}
                <Field label={l.dateFrom} className="detail-label"><input type="date" value={filters.date_from} max={filters.date_to || undefined} onChange={(event) => updateFilter("date_from", event.target.value)} /></Field>
                <Field label={l.dateTo} className="detail-label"><input type="date" value={filters.date_to} min={filters.date_from || undefined} onChange={(event) => updateFilter("date_to", event.target.value)} /></Field>
                {activeFilterCount > 0 && <button type="button" className="text-action filter-clear" onClick={() => { setFilters({ ...emptyLibraryFilters }); setNextCursor(null); }}>{l.clearFilters}</button>}
              </div>}
              {error && (
                <div className="inline-error" role="alert">
                  {error}
                  <button
                    onClick={() => setError("")}
                    aria-label={l.dismissError}
                  >
                    <X size={16} />
                  </button>
                </div>
              )}
              {uploadReport && (
                <div className="inline-error upload-report" role="alert">
                  <strong>{l.rejectedFiles(uploadReport.failures.length, uploadReport.total)}</strong>
                  {uploadReport.failures.length > 3 ? (
                    <details>
                      <summary>{l.reviewRejected}</summary>
                      <ul>{uploadReport.failures.map((failure, index) => <li key={`${failure}-${index}`}>{failure}</li>)}</ul>
                    </details>
                  ) : (
                    <ul>{uploadReport.failures.map((failure, index) => <li key={`${failure}-${index}`}>{failure}</li>)}</ul>
                  )}
                  <button onClick={() => setUploadReport(null)} aria-label={l.dismissReport}><X size={16} /></button>
                </div>
              )}
              {listError && (
                <div className="inline-error" role="alert">
                  {listError}
                  <button onClick={() => void loadDocuments(query)}>{l.retry}</button>
                </div>
              )}
              {uploading && (
                <div className="upload-progress" role="status" aria-live="polite" aria-atomic="true">
                  <UploadCloud size={19} /> {uploadProgress || l.addingDocument}
                </div>
              )}
              {!listError && (!isEmpty || selectionMode || bulkNotice) && <div className="bulk-controls">
                <button type="button" className="text-action" disabled={bulkBusy || (isEmpty && !selectionMode)} onClick={() => { setSelectionMode(!selectionMode); setSelectedIds([]); setConfirmBulkTrash(false); setBulkError(""); setBulkNotice(""); }}>
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
                    {tagOptions.map((tag) => <option key={tag.id} value={tag.id}>{tagPathLabel(tag, tagById)}</option>)}
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
                  <details className="bulk-filing-details">
                    <summary>Change document date</summary>
                    <div className="bulk-filing">
                      <input type="date" aria-label="Document date for selected documents" value={bulkDate} disabled={bulkBusy} onChange={(event) => setBulkDate(event.target.value)} />
                      <Button type="button" variant="secondary" disabled={bulkBusy || !selectedIds.length || !bulkDate} onClick={() => void applyBulkDate(false)}>Set date</Button>
                      <Button type="button" variant="secondary" disabled={bulkBusy || !selectedIds.length} onClick={() => void applyBulkDate(true)}>Clear date</Button>
                    </div>
                  </details>
                  <details className="bulk-filing-details">
                    <summary>OCR actions</summary>
                    <div className="bulk-filing">
                      <Button type="button" variant="secondary" disabled={bulkBusy || !selectedIds.length} onClick={() => void applyBulkOcr("retry")}>
                        <RotateCcw size={16} /> Retry failed OCR
                      </Button>
                      <Button type="button" variant="secondary" disabled={bulkBusy || !selectedIds.length} onClick={() => void applyBulkOcr("rebuild")}>
                        <RotateCcw size={16} /> Rebuild searchable PDFs
                      </Button>
                    </div>
                  </details>
                  <details className="bulk-filing-details">
                    <summary>Merge into one PDF</summary>
                    <div className="bulk-filing">
                      <p>Creates a new document with the pages of the selected documents, in this order. The originals stay as they are.</p>
                      {selectedIds.length > 1 && <ol className="merge-order">{selectedIds.map((id) => <li key={id}>{documents.find((item) => item.id === id)?.title ?? "Selected document"}</li>)}</ol>}
                      <Button type="button" variant="secondary" disabled={bulkBusy || selectedIds.length < 2 || selectedIds.length > 50} onClick={() => void mergeSelected()}>
                        <Layers size={16} /> Merge {selectedIds.length} {selectedIds.length === 1 ? "document" : "documents"}
                      </Button>
                    </div>
                  </details>
                  <BundlePanel selectedIds={selectedIds} />
                  <details className="bulk-filing-details">
                    <summary>Export selected</summary>
                    <div className="bulk-filing">
                      <p>Download originals, searchable PDFs, OCR text, and metadata in one ZIP. Select up to 20 documents.</p>
                      {selectedIds.length > 20 && <p className="inline-error">Choose 20 or fewer documents for one export.</p>}
                      {selectedIds.length > 0 && selectedIds.length <= 20 && !bulkBusy && <a className="button button-secondary" href={`/api/documents/export?${new URLSearchParams(selectedIds.map((id) => ["document_ids", id]))}`} download="ripiano-documents.zip"><ArrowDownToLine size={16} /> Download {selectedIds.length} {selectedIds.length === 1 ? "document" : "documents"}</a>}
                    </div>
                  </details>
                  <details className="bulk-filing-details" open={confirmBulkTrash} onToggle={(event) => setConfirmBulkTrash(event.currentTarget.open)}>
                    <summary>Move to Trash</summary>
                    <div className="bulk-filing">
                      <p>The selected documents will disappear from search and agent access. Originals, notes, and paper sticker history stay available for restore.</p>
                      {confirmBulkTrash && <Button type="button" variant="danger" disabled={bulkBusy || !selectedIds.length} onClick={() => void applyBulkTrash()}>
                        <Trash2 size={16} /> Confirm move of {selectedIds.length}
                      </Button>}
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
                      ? l.nothingFound
                      : l.freshShelf}
                  </h3>
                  <p>
                    {query || activeFilterCount
                      ? l.tryAnotherSearch
                      : l.addSearchable}
                  </p>
                  {!query && !activeFilterCount && (
                    <Button
                      onClick={() => setShowAdd(true)}
                    >
                      <Plus size={18} /> {l.addFirst}
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
                        <span className="visually-hidden">{l.selectDocument(doc.title)}</span>
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
                          {doc.document_date ? l.dated(formatDate(doc.document_date)) : l.added(formatDate(doc.created_at))} <span>·</span>{" "}
                          {doc.original_name}
                          {doc.correspondent && <>{" "}<span>·</span> {l.fromSender} {doc.correspondent.name}</>}
                          {doc.document_type && <>{" "}<span>·</span> {l.type} {doc.document_type.name}</>}
                          {doc.source === "telegram" && (
                            <>
                              {" "}
                              <span>·</span> {l.viaTelegram}
                            </>
                          )}
                          {doc.source === "android" && (
                            <>
                              {" "}
                              <span>·</span> {l.scannedAndroid}
                            </>
                          )}
                          {doc.source === "folder" && (
                            <>
                              {" "}
                              <span>·</span> {l.fromNas}
                            </>
                          )}
                        </div>
                        {doc.snippet && (
                          <p className="document-snippet">
                            <strong>{doc.snippet_source === "note" ? l.note : doc.snippet_source === "sticker" ? l.sticker : doc.snippet_source === "field" ? l.customField : l.documentText}:</strong> {doc.snippet}
                          </p>
                        )}
                        {doc.tags.length > 0 && <TagSummary tags={doc.tags} />}
                        {doc.duplicate_of && (
                          <span className="duplicate-chip">
                            <Copy size={12} /> {l.exactCopyOf}{" "}
                            {doc.duplicate_of.title}
                          </span>
                        )}
                        {doc.physical_copies.length > 0 && <PaperCopySummary copies={doc.physical_copies} />}
                        {doc.status === "failed" && (
                          <p className="doc-error">
                            {l.processingFailed} {doc.error}
                          </p>
                        )}
                      </div>
                      <span className={`status status-${doc.status}`}>
                        {doc.status === "ready"
                          ? l.ready
                          : doc.status === "failed"
                            ? l.needsAttention
                            : l.processing}
                      </span>
                      {doc.status === "failed" && (
                        <button
                          className="download-link"
                          onClick={() => void retryDocument(doc.id)}
                          aria-label={l.retryNamed(doc.original_name)}
                          title={l.retryProcessing}
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
                          aria-label={l.viewPdfNamed(doc.original_name)}
                          title={l.viewPdf}
                        >
                          <Eye size={18} />
                        </a>
                      )}
                      <a
                        className="download-link"
                        href={`/api/documents/${doc.id}/original`}
                        aria-label={l.downloadNamed(doc.original_name)}
                      >
                        <ArrowDownToLine size={18} />
                      </a>
                    </article>
                  ))}
                </div>
                {nextCursor !== null && (
                  <Button variant="secondary" className="load-more" disabled={loadingMore} onClick={() => void loadDocuments(query, nextCursor)}>
                    {loadingMore ? l.loading : l.showMore}
                  </Button>
                )}
                </>
              )}
            </>
          )}
          <div className="page-footer">
            <span>{m.footerBrand}</span>
            <span>{m.footerOriginals}</span>
          </div>
        </section>
      </main>

      {dropActive && (
        <div className="drop-overlay">
          <UploadCloud size={40} />
          <strong>{l.dropToAdd}</strong>
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
              accept="application/pdf,image/jpeg,image/png,.eml,.msg,.docx,.xlsx,.pptx,.doc,.xls,.ppt,.odt,.ods,.odp,.rtf"
              multiple
              onChange={(event) => void upload(event.target.files)}
            />
            <button
              className="modal-close"
              onClick={() => setShowAdd(false)}
              aria-label={l.close}
            >
              <X size={20} />
            </button>
            <div className="eyebrow">
              <span className="eyebrow-line" /> {l.addEyebrow}
            </div>
            <h2 id="add-heading">{l.addTitle}</h2>
            <p>{l.addIntro}</p>
            <div className="add-options">
              <button onClick={scan}>
                <span className="add-option-icon">
                  <Camera size={23} />
                </span>
                <span>
                  <strong>{nativeScanner ? l.scanPages : l.takePhoto}</strong>
                  <small>{nativeScanner ? l.scanHint : l.cameraHint}</small>
                </span>
                <ArrowRight size={18} />
              </button>
              <button onClick={() => galleryRef.current?.click()}>
                <span className="add-option-icon">
                  <ImagePlus size={23} />
                </span>
                <span>
                  <strong>{l.choosePhotos}</strong>
                  <small>{l.photosHint}</small>
                </span>
                <ArrowRight size={18} />
              </button>
              <button onClick={() => fileRef.current?.click()}>
                <span className="add-option-icon">
                  <FolderOpen size={23} />
                </span>
                <span>
                  <strong>{l.browseFiles}</strong>
                  <small>{l.filesHint}</small>
                </span>
                <ArrowRight size={18} />
              </button>
            </div>
            <div className="modal-foot">
              {nativeScanner
                ? l.nativeScannerFoot
                : l.browserCameraFoot}
            </div>
        </Modal>
      )}
      {selectedDocument && selectedDocument.access !== "owner" && (
        <SharedDocumentPanel
          key={selectedDocument.id}
          initial={selectedDocument}
          username={session.username}
          onClose={() => setSelectedDocument(null)}
          onSaved={() => setSharedRefresh((value) => value + 1)}
        />
      )}
      {selectedDocument && selectedDocument.access === "owner" && (
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
