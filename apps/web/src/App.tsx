import {
  ChangeEvent,
  DragEvent,
  FormEvent,
  KeyboardEvent as ReactKeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  Bot,
  Brain,
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
  Cloud,
  WifiOff,
  X,
} from "lucide-react";
import { ApiError, CustomField, Document, FilingItem, formatDate, formatDateTime, formatTime, LibraryFilters, onSessionEnded, request, Session, Tag, tagPathLabel } from "./api";
import * as uploadQueue from "./uploadQueue";
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
import SourcesPanel from "./SourcesPanel";
import KeyboardHelp from "./KeyboardHelp";
import SemanticPanel from "./SemanticPanel";
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

function AppearanceControl({ preference, onChange, compact = false }: {
  preference: ThemePreference;
  onChange: (preference: ThemePreference) => void;
  /** In the sidebar footer: one short row per setting, label beside the select, always in view. */
  compact?: boolean;
}) {
  const m = useMessages(appMessages);
  const languagePreference = useLanguagePreference();
  const className = compact ? "appearance-control appearance-control-compact" : "appearance-control";
  return (
    <>
    <label className={className}>
      <span>{m.appearance}</span>
      <select value={preference} onChange={(event) => onChange(event.target.value as ThemePreference)}>
        <option value="system">{m.themeSystem}</option>
        <option value="light">{m.themeLight}</option>
        <option value="dark">{m.themeDark}</option>
        <option value="amoled">{m.themeAmoled}</option>
      </select>
    </label>
    <label className={className}>
      <span>{m.language}</span>
      <select value={languagePreference} onChange={(event) => setLanguagePreference(event.target.value as LanguagePreference)}>
        <option value="system">{m.languageSystem}</option>
        <option value="en">English</option>
        <option value="it">{m.italian}</option>
      </select>
    </label>
    </>
  );
}

/** Server messages are shown as they are; raw system errors kept by older runs get a readable text. */
function readableJobError(error: string, fallback: string) {
  return /^\[Errno\b|^Traceback|^[A-Za-z]+Error:/.test(error.trim()) ? fallback : error;
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
  notice = "",
}: {
  setup: boolean;
  onAuthenticated: (value: Session) => void;
  appearance: ThemePreference;
  onAppearanceChange: (preference: ThemePreference) => void;
  notice?: string;
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
        {notice && <p className="form-notice" role="status">{notice}</p>}
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
                  {run.error && <p className="doc-error">{readableJobError(run.error, m.rawJobError)}</p>}
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
                  {formatDateTime(run.created_at)} <span>·</span> {m.trigger(run.trigger)}
                </div>
                {run.error && <p className="doc-error">{readableJobError(run.error, m.rawJobError)}</p>}
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

function viewLabelsFor(m: typeof appMessages.en) {
  return {
    documents: m.allDocuments, inbox: m.inbox, actions: m.needsAction, tags: m.tags,
    physical: m.physical, backups: m.backups, agents: m.agents, trash: m.trash,
    integrations: m.email, sources: m.sources, workflows: m.workflows, security: m.security,
    overview: m.overview, shared: m.shared, people: m.people,
  };
}

type View =
  "documents" | "inbox" | "actions" | "tags" | "physical" | "backups" | "agents" | "trash" | "integrations" | "sources" | "workflows" | "security" | "overview" | "shared" | "people";

/** Each screen has its own address, so Back, bookmarks and reloads land on the same screen.
 *  nginx and the service worker answer every one of these paths with index.html. */
const VIEW_PATHS: Record<View, string> = {
  documents: "/", inbox: "/inbox", actions: "/actions", tags: "/tags", physical: "/paper", backups: "/backups",
  agents: "/agents", trash: "/trash", integrations: "/email", sources: "/sources", workflows: "/workflows",
  security: "/security", overview: "/overview", shared: "/shared", people: "/people",
};
const OWNER_VIEWS: View[] = ["people", "backups"];
const DOCUMENT_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function viewFromPath(pathname: string): View | null {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  return (Object.keys(VIEW_PATHS) as View[]).find((view) => VIEW_PATHS[view] === path) ?? null;
}

/** Delays between attempts to send waiting uploads while the device is online (the last one repeats). */
const WAITING_RETRY_DELAYS = [3000, 10000, 30000, 60000];

const GO_TO_VIEWS: Record<string, View> = {
  l: "documents", i: "inbox", a: "actions", t: "tags", o: "overview", s: "shared", w: "workflows", r: "sources",
};

// The last person signed in on this device (username only, never a secret), so a reload while
// offline can say whose queued uploads are waiting instead of showing a bare connection error.
const LAST_USER_KEY = "ripiano.lastSignedIn";
function rememberSignedIn(username: string | null) {
  try {
    if (username) localStorage.setItem(LAST_USER_KEY, username);
    else localStorage.removeItem(LAST_USER_KEY);
  } catch {
    // Storage blocked: the offline screen simply does not name anyone.
  }
}
function lastSignedIn(): string | null {
  try {
    return localStorage.getItem(LAST_USER_KEY);
  } catch {
    return null;
  }
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
  // False until a list has loaded (or after a failed search): the counts then show a dash, never "0".
  const [countsKnown, setCountsKnown] = useState(false);
  // Set when Ripiano cannot be reached: the last loaded list stays on screen, marked as stale.
  const [staleSince, setStaleSince] = useState<Date | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [semanticAvailable, setSemanticAvailable] = useState(false);
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
  // After an upload: how many went in and which document to show first (announced politely).
  const [uploadDone, setUploadDone] = useState<{ count: number; firstId: string } | null>(null);
  const [revealDocument, setRevealDocument] = useState<string | null>(null);
  const [appAnnouncement, setAppAnnouncement] = useState("");
  // A document just moved to the Trash from its dialog: said politely, with Undo (restore).
  const [trashedNotice, setTrashedNotice] = useState<{ id: string; title: string; state: "trashed" | "restoring" | "restored" | "failed" } | null>(null);
  // Where focus goes once the list has reloaded after Trash or Undo: the row now in the trashed
  // document's place, the restored row, or the screen heading.
  const [pendingFocus, setPendingFocus] = useState<{ index?: number; id?: string } | null>(null);
  const [waitingUploads, setWaitingUploads] = useState(0);
  const sendingWaiting = useRef(false);
  // Waiting uploads after a failed attempt while the device is online: retried soon with backoff
  // (WAITING_RETRY_DELAYS), not only on the one-minute check or the next "online" event.
  const waitingRetryTimer = useRef<number | null>(null);
  const waitingAttempt = useRef(0);
  const [waitingRetrying, setWaitingRetrying] = useState(false);
  const sendWaitingRef = useRef<() => Promise<void>>(async () => {});
  const signedInAs = useRef<string | null>(null);
  const [confirmSignOut, setConfirmSignOut] = useState(false);
  const [nativeScanner] = useState(() => Boolean(window.RipianoAndroid));
  const [dropActive, setDropActive] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  // Keyboard navigation in the Library list (j / k / Enter); -1 when nothing is highlighted.
  const [activeRow, setActiveRow] = useState(-1);
  const goPending = useRef(0);
  const [menuOpen, setMenuOpen] = useState(false);
  // On narrow screens the navigation is an off-canvas drawer: while closed it must not take focus
  // or be read out. The width matches the CSS breakpoint for the drawer.
  const [narrowLayout, setNarrowLayout] = useState(() => window.matchMedia("(max-width: 800px)").matches);
  // Phone width (matches the 570px CSS breakpoint): the Library keeps saved searches and search help
  // behind Filters so the first documents fit on the first screen.
  const [phoneLayout, setPhoneLayout] = useState(() => window.matchMedia("(max-width: 570px)").matches);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const sidebarRef = useRef<HTMLElement>(null);
  const sidebarFrameRef = useRef<HTMLDivElement>(null);
  const sidebarScrollRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [initialSticker] = useState(() => new URLSearchParams(window.location.search).get("sticker") ?? "");
  const [initialLocation] = useState(() => new URLSearchParams(window.location.search).get("location") ?? "");
  // Links from workflow emails and webhooks open one document: /?document=<id>. Read before the
  // address is tidied up below.
  const [initialDocumentId] = useState(() => new URLSearchParams(window.location.search).get("document") ?? "");
  const [initialMailNotice] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    const connected = params.get("mail_connected");
    const failed = params.get("mail_error");
    if (!connected && !failed) return null;
    window.history.replaceState(null, "", window.location.pathname);
    return failed ? { kind: "error" as const, text: failed } : { kind: "ok" as const, text: connected ?? "" };
  });
  const [initialSourceNotice] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    const connected = params.get("source_connected");
    const failed = params.get("source_error");
    if (!connected && !failed) return null;
    window.history.replaceState(null, "", window.location.pathname);
    return failed ? { kind: "error" as const, text: failed } : { kind: "ok" as const, text: m.sourceConnected(connected ?? "") };
  });
  const [view, setView] = useState<View>(() =>
    initialSticker || initialLocation ? "physical" : initialMailNotice ? "integrations" : initialSourceNotice ? "sources"
      : viewFromPath(window.location.pathname) ?? "documents");
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

  // A document link opens its dialog once signed in. The address was already reduced to the screen,
  // so opening the dialog adds a history entry and Back closes it instead of leaving the app.
  const openedInitialDocument = useRef(false);
  useEffect(() => {
    if (!session?.authenticated || openedInitialDocument.current || !initialDocumentId) return;
    openedInitialDocument.current = true;
    if (!DOCUMENT_ID.test(initialDocumentId)) return;
    void request<Document>(`/api/documents/${initialDocumentId}`).then(setSelectedDocument).catch(() => setError(m.documentUnavailable));
  }, [session?.authenticated, initialDocumentId, m]);

  // History: the address mirrors the screen and the open document (?document=<id>). Moving to
  // another screen or opening a document adds an entry; Back (browser, Android gesture, installed
  // PWA) walks back through them. Same-screen moves add nothing.
  const historyReady = useRef(false);
  const replaceNextUrl = useRef(false);
  const awaitingBack = useRef(false);
  const restoringDocument = useRef<string | null>(null);
  const [historyTick, setHistoryTick] = useState(0);
  const viewRef = useRef(view);
  viewRef.current = view;
  const selectedRef = useRef(selectedDocument);
  selectedRef.current = selectedDocument;
  useEffect(() => {
    if (awaitingBack.current) return;
    const url = new URL(window.location.href);
    const currentView = viewFromPath(url.pathname);
    const currentDocument = url.searchParams.get("document");
    const documentId = selectedDocument?.id ?? null;
    if (!documentId && currentDocument && currentDocument === restoringDocument.current) return;
    if (currentView === view && currentDocument === documentId) {
      historyReady.current = true;
      return;
    }
    const state = (window.history.state ?? {}) as { ripianoDialog?: boolean };
    // Closing a dialog this app opened: step back, so the entry is not left behind for Back.
    if (historyReady.current && !documentId && currentDocument && currentView === view && state.ripianoDialog) {
      awaitingBack.current = true;
      window.history.back();
      return;
    }
    if (currentView !== view) {
      url.pathname = VIEW_PATHS[view];
      // Query values such as ?sticker= belong to the screen they came with.
      if (historyReady.current) url.search = "";
    }
    url.hash = "";
    if (documentId) url.searchParams.set("document", documentId);
    else url.searchParams.delete("document");
    const replace = !historyReady.current || replaceNextUrl.current || currentDocument !== null;
    const dialog = documentId ? (currentDocument ? Boolean(state.ripianoDialog) : true) : false;
    const address = `${url.pathname}${url.search}`;
    if (replace) window.history.replaceState({ ripianoDialog: dialog }, "", address);
    else window.history.pushState({ ripianoDialog: dialog }, "", address);
    historyReady.current = true;
    replaceNextUrl.current = false;
  }, [view, selectedDocument, historyTick]);

  useEffect(() => {
    function restore() {
      setMenuOpen(false);
      if (awaitingBack.current) {
        // Our own step back after closing a dialog: keep what is on screen and re-check the address.
        awaitingBack.current = false;
        setHistoryTick((tick) => tick + 1);
        return;
      }
      const url = new URL(window.location.href);
      const target = viewFromPath(url.pathname) ?? "documents";
      const documentId = url.searchParams.get("document");
      if (target !== viewRef.current) {
        focusHeadingOnView.current = !documentId;
        setView(target);
      }
      if (!documentId) {
        restoringDocument.current = null;
        setSelectedDocument(null);
      } else if (documentId !== selectedRef.current?.id) {
        setSelectedDocument(null);
        if (!DOCUMENT_ID.test(documentId)) return;
        restoringDocument.current = documentId;
        void request<Document>(`/api/documents/${documentId}`)
          .then((doc) => { if (restoringDocument.current === documentId) setSelectedDocument(doc); })
          .catch(() => setError(m.documentUnavailable))
          .finally(() => {
            if (restoringDocument.current === documentId) restoringDocument.current = null;
            setHistoryTick((tick) => tick + 1);
          });
      }
    }
    window.addEventListener("popstate", restore);
    return () => window.removeEventListener("popstate", restore);
  }, [m]);

  useEffect(() => {
    if (view === "documents" && focusSearchOnView.current) {
      focusSearchOnView.current = false;
      searchRef.current?.focus();
    }
  }, [view]);

  // Moving between screens from the menu or a "g" shortcut puts focus on the new screen's heading,
  // so keyboard and screen-reader users land at the top of what they asked for (not on first load).
  const focusHeadingOnView = useRef(false);
  function goTo(target: typeof view) {
    if (target === view) {
      // Already here: close the drawer without dropping focus inside it.
      if (menuOpen) closeMenu();
      return;
    }
    setMenuOpen(false);
    focusHeadingOnView.current = true;
    setView(target);
  }
  useEffect(() => {
    if (!focusHeadingOnView.current) return;
    focusHeadingOnView.current = false;
    const frame = requestAnimationFrame(() => {
      const heading = document.querySelector<HTMLElement>("#main-content h1");
      if (heading && !heading.hasAttribute("tabindex")) heading.tabIndex = -1;
      (heading ?? document.getElementById("main-content"))?.focus();
    });
    return () => cancelAnimationFrame(frame);
  }, [view]);

  useEffect(() => {
    const media = window.matchMedia("(max-width: 800px)");
    const phone = window.matchMedia("(max-width: 570px)");
    const update = () => setNarrowLayout(media.matches);
    const updatePhone = () => setPhoneLayout(phone.matches);
    media.addEventListener("change", update);
    phone.addEventListener("change", updatePhone);
    return () => {
      media.removeEventListener("change", update);
      phone.removeEventListener("change", updatePhone);
    };
  }, []);
  // Opening the drawer puts focus on the current screen's link; Esc closes it and returns focus
  // to the menu button.
  useEffect(() => {
    if (!menuOpen || !narrowLayout) return;
    const frame = requestAnimationFrame(() => {
      const sidebar = sidebarRef.current;
      (sidebar?.querySelector<HTMLElement>(".nav-link[aria-current=page]") ?? sidebar?.querySelector<HTMLElement>(".nav-link"))?.focus();
    });
    function escape(event: KeyboardEvent) {
      if (event.defaultPrevented || document.querySelector('[role="dialog"]')) return;
      if (event.key === "Tab") {
        // The page behind the open drawer is inert; keep Tab cycling inside the drawer.
        const sidebar = sidebarRef.current;
        if (!sidebar) return;
        const items = Array.from(sidebar.querySelectorAll<HTMLElement>(
          "a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])",
        )).filter((item) => item.tabIndex >= 0 && item.getClientRects().length > 0);
        if (!items.length) return;
        const first = items[0];
        const last = items[items.length - 1];
        const inside = sidebar.contains(document.activeElement);
        if (event.shiftKey && (!inside || document.activeElement === first)) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && (!inside || document.activeElement === last)) {
          event.preventDefault();
          first.focus();
        }
        return;
      }
      if (event.key !== "Escape") return;
      event.preventDefault();
      closeMenu();
    }
    document.addEventListener("keydown", escape);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("keydown", escape);
    };
  }, [menuOpen, narrowLayout]);
  // The menu button sits in the page that is inert while the drawer is open: focus it once the
  // drawer has closed and the page is interactive again.
  const focusMenuButton = useRef(false);
  function closeMenu() {
    focusMenuButton.current = true;
    setMenuOpen(false);
  }
  useEffect(() => {
    if (menuOpen || !focusMenuButton.current) return;
    focusMenuButton.current = false;
    menuButtonRef.current?.focus();
  }, [menuOpen]);
  const drawerCoversPage = narrowLayout && menuOpen;

  // Sidebar scroll affordance: mark the frame when the list can scroll further up or down, so a fade
  // shows at that edge. Set directly on the element (no re-render on every scroll event).
  useEffect(() => {
    const frame = sidebarFrameRef.current;
    const list = sidebarScrollRef.current;
    if (!frame || !list) return;
    const update = () => {
      frame.classList.toggle("can-scroll-up", list.scrollTop > 2);
      frame.classList.toggle("can-scroll-down", list.scrollTop + list.clientHeight < list.scrollHeight - 2);
    };
    update();
    list.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(update);
    observer?.observe(list);
    if (list.firstElementChild) observer?.observe(list.firstElementChild);
    return () => {
      list.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
      observer?.disconnect();
    };
  }, [session?.authenticated, session?.owner, loading]);

  // The browser tab names the current screen, in the interface language.
  useEffect(() => {
    document.title = session?.authenticated ? m.pageTitle(viewLabelsFor(m)[view]) : m.documentTitle;
  }, [view, session?.authenticated, m]);

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
      } else if (event.key === "?") {
        event.preventDefault();
        setShowShortcuts(true);
      } else if (Date.now() - goPending.current < 1500 && event.key.toLowerCase() in GO_TO_VIEWS) {
        // "g" then a letter: go to a screen.
        event.preventDefault();
        goPending.current = 0;
        goTo(GO_TO_VIEWS[event.key.toLowerCase()]);
      } else if (event.key.toLowerCase() === "g") {
        goPending.current = Date.now();
      } else if (event.key.toLowerCase() === "n") {
        event.preventDefault();
        setMenuOpen(false);
        setShowAdd(true);
      } else if (view === "documents" && (event.key === "j" || event.key === "k") && documents.length) {
        event.preventDefault();
        setActiveRow((row) => event.key === "j" ? Math.min(documents.length - 1, row + 1) : Math.max(0, row - 1));
      } else if (view === "documents" && event.key === "Enter" && activeRow >= 0 && documents[activeRow]) {
        event.preventDefault();
        // The dialog returns focus to whatever had it when it opened: make that the row's title.
        document.querySelector<HTMLElement>(".document-row.keyboard-active .document-title-button")?.focus({ preventScroll: true });
        setSelectedDocument(documents[activeRow]);
      }
    }
    document.addEventListener("keydown", shortcut);
    return () => document.removeEventListener("keydown", shortcut);
  }, [session?.authenticated, view, documents, activeRow]);

  // Keep the keyboard selection on the same document when the list refreshes (it reloads every few seconds while
  // something is processing); clear it only when that document is no longer listed or the screen changes.
  const activeDocumentId = useRef<string | null>(null);
  useEffect(() => { activeDocumentId.current = activeRow >= 0 ? documents[activeRow]?.id ?? null : null; }, [activeRow]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const id = activeDocumentId.current;
    setActiveRow(id ? documents.findIndex((item) => item.id === id) : -1);
  }, [documents]);
  useEffect(() => { activeDocumentId.current = null; setActiveRow(-1); }, [view]);
  useEffect(() => {
    if (activeRow < 0) return;
    // j / k move real focus to the row's title, so screen readers announce it and closing the
    // document returns focus to that row instead of the page.
    const row = document.querySelector(".document-row.keyboard-active");
    row?.querySelector<HTMLElement>(".document-title-button")?.focus({ preventScroll: true });
    row?.scrollIntoView({ block: "nearest" });
  }, [activeRow]);

  // Scroll to a document row (after an upload, or from "Show") and put focus on its title.
  useEffect(() => {
    if (!revealDocument || view !== "documents") return;
    const row = document.querySelector<HTMLElement>(`.document-row[data-document-id="${CSS.escape(revealDocument)}"]`);
    if (!row) return;
    setRevealDocument(null);
    row.scrollIntoView({ block: "center" });
    row.querySelector<HTMLElement>(".document-title-button")?.focus({ preventScroll: true });
  }, [revealDocument, documents, view]);

  useEffect(() => {
    // Wait until the document dialog has closed: while it is open the page behind it is inert.
    if (!pendingFocus || selectedDocument) return;
    const frame = requestAnimationFrame(() => {
      setPendingFocus(null);
      const titles = Array.from(document.querySelectorAll<HTMLElement>("#main-content .document-row .document-title-button"));
      let target: HTMLElement | undefined;
      if (pendingFocus.id) {
        target = document.querySelector<HTMLElement>(`#main-content .document-row[data-document-id="${CSS.escape(pendingFocus.id)}"] .document-title-button`) ?? undefined;
      } else if (pendingFocus.index !== undefined && pendingFocus.index >= 0 && titles.length) {
        target = titles[Math.min(pendingFocus.index, titles.length - 1)];
      }
      if (!target) {
        const heading = document.querySelector<HTMLElement>("#main-content h1");
        if (heading && !heading.hasAttribute("tabindex")) heading.tabIndex = -1;
        target = heading ?? document.getElementById("main-content") ?? undefined;
      }
      target?.closest(".document-row")?.scrollIntoView({ block: "nearest" });
      target?.focus({ preventScroll: Boolean(target.closest(".document-row")) });
    });
    return () => cancelAnimationFrame(frame);
  }, [pendingFocus, selectedDocument]);
  useEffect(() => { setTrashedNotice(null); }, [view]);

  function refreshAfterTrashChange() {
    setTrashRefresh((value) => value + 1);
    setActionRefresh((value) => value + 1);
    setInboxRefresh((value) => value + 1);
  }

  async function documentTrashed(trashed: Document) {
    const index = view === "documents" ? documents.findIndex((doc) => doc.id === trashed.id) : -1;
    setTrashedNotice({ id: trashed.id, title: trashed.title, state: "trashed" });
    refreshAfterTrashChange();
    await loadDocuments(query);
    setPendingFocus({ index });
  }

  async function undoTrash() {
    if (!trashedNotice || trashedNotice.state !== "trashed") return;
    const { id, title } = trashedNotice;
    setTrashedNotice({ id, title, state: "restoring" });
    try {
      await request(`/api/documents/${id}/restore`, { method: "POST" });
      setTrashedNotice({ id, title, state: "restored" });
      refreshAfterTrashChange();
      await loadDocuments(query);
      setPendingFocus(view === "documents" ? { id } : {});
    } catch {
      setTrashedNotice({ id, title, state: "failed" });
      setPendingFocus({});
    }
  }

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
      const tagName = filterOptions.tags.find((tag) => tag.id === bulkTagId)?.name ?? l.tagFallback;
      setBulkNotice(action === "add" ? l.bulkTagAdded(tagName, result.updated) : l.bulkTagRemoved(tagName, result.updated));
      setSelectedIds([]);
      await loadDocuments(query);
    } catch (cause) {
      setBulkError(cause instanceof Error ? cause.message : l.bulkUpdateFailed);
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
      const options = field === "correspondent" ? filterOptions.correspondents : filterOptions.document_types;
      const name = options.find((item) => item.id === choice)?.name ?? l.selectedValue;
      setBulkNotice(field === "correspondent"
        ? (choice === "none" ? l.senderCleared(result.updated) : l.senderSet(name, result.updated))
        : (choice === "none" ? l.typeCleared(result.updated) : l.typeSet(name, result.updated)));
      setSelectedIds([]);
      await loadDocuments(query);
    } catch (cause) {
      setBulkError(cause instanceof Error ? cause.message : l.bulkUpdateFailed);
    } finally {
      setBulkBusy(false);
    }
  }

  async function applyBulkLearnedFiling() {
    if (!selectedIds.length) return;
    setBulkBusy(true);
    setBulkError("");
    setBulkNotice("");
    try {
      const result = await request<{ updated: number; assignments: number; skipped: number; skipped_ids: string[] }>(
        "/api/documents/bulk-learned-filing", {
          method: "POST",
          body: JSON.stringify({ document_ids: selectedIds }),
        },
      );
      setSelectedIds(result.skipped_ids);
      setBulkNotice(result.updated
        ? l.learnedFiled(result.assignments, result.updated, result.skipped)
        : l.learnedNone);
      if (result.updated) await loadDocuments(query);
    } catch (cause) {
      setBulkError(cause instanceof Error ? cause.message : l.learnedFailed);
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
      setBulkNotice(clear ? l.dateCleared(result.updated) : l.dateSet(bulkDate, result.updated));
      setSelectedIds([]);
      await loadDocuments(query);
    } catch (cause) {
      setBulkError(cause instanceof Error ? cause.message : l.dateFailed);
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
        ? l.ocrStarted(result.scheduled, result.skipped)
        : l.ocrNone);
      if (result.scheduled) await loadDocuments(query);
    } catch (cause) {
      setBulkError(cause instanceof Error ? cause.message : l.ocrFailed);
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
      setBulkNotice(l.mergeCreated(merged.title));
      await loadDocuments(query);
    } catch (cause) {
      setBulkError(cause instanceof Error ? cause.message : l.mergeFailed);
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
      setBulkNotice(l.trashMoved(result.updated));
      await loadDocuments(query);
      setTrashRefresh((value) => value + 1);
      setActionRefresh((value) => value + 1);
      setInboxRefresh((value) => value + 1);
    } catch (cause) {
      setBulkError(cause instanceof Error ? cause.message : l.trashFailed);
    } finally {
      setBulkBusy(false);
    }
  }

  const listLoadedRef = useRef(false);
  const lastLoadedAt = useRef<Date | null>(null);
  const [suggestion, setSuggestion] = useState(""); // "Did you mean …?" when a search found nothing
  const lastLoadedView = useRef(""); // search + filters + sort of the list on screen
  const loadDocuments = useCallback(async (search: string, cursor: string | null = null) => {
    if (cursor && loadingMoreRef.current) return;
    if (cursor) {
      loadingMoreRef.current = true;
      setLoadingMore(true);
    }
    const requestNumber = ++latestSearch.current;
    let viewKey = "";
    try {
      const params = new URLSearchParams({ q: search });
      for (const [key, value] of Object.entries(filters)) if (value) params.set(key, value);
      if (sort) params.set("sort", sort);
      viewKey = params.toString();
      if (cursor) params.set("cursor", cursor);
      const result = await request<{ documents: Document[]; counts: typeof counts; next_cursor: string | null; suggestion?: string | null }>(
        `/api/documents?${params}`,
      );
      if (requestNumber === latestSearch.current) {
        setDocuments((current) => cursor ? [...current, ...result.documents] : result.documents);
        if (!cursor) setSuggestion(result.suggestion ?? "");
        setCounts(result.counts);
        setCountsKnown(true);
        listLoadedRef.current = true;
        lastLoadedAt.current = new Date();
        lastLoadedView.current = viewKey;
        setNextCursor(result.next_cursor);
        setListError("");
        setStaleSince(null);
      }
    } catch (cause) {
      if (requestNumber !== latestSearch.current) return;
      const message = cause instanceof Error ? cause.message : l.loadDocumentsFailed;
      // Offline, or the server is restarting, while reloading the list that is already on screen: keep it rather
      // than showing an empty archive; the notice says it is from earlier and offers a retry. A different search
      // or filter that fails shows its error instead: old results must never pass for the new search's answer.
      const unreachable = cause instanceof ApiError && (cause.status === 0 || (cause.status >= 502 && cause.status <= 504));
      if (unreachable && listLoadedRef.current && lastLoadedView.current === viewKey) {
        setStaleSince((value) => value ?? lastLoadedAt.current ?? new Date());
        setListError("");
      } else if (cursor) setError(message);
      else {
        setDocuments([]);
        setCountsKnown(false);
        setNextCursor(null);
        setListError(message);
        setStaleSince(null);
        // Nothing is on screen any more, so there is no "last loaded list" to keep on the next failure.
        listLoadedRef.current = false;
        lastLoadedView.current = "";
      }
    } finally {
      if (cursor) loadingMoreRef.current = false;
      if (requestNumber === latestSearch.current) setLoadingMore(false);
    }
  }, [filters, sort, l]);

  // Opening Ripiano without a connection (or while the server restarts) shows an offline screen
  // that keeps trying, with the files still waiting on this device, rather than a sign-in form.
  const [offline, setOffline] = useState<{ username: string | null; waiting: number } | null>(null);
  const checkSession = useCallback(async () => {
    try {
      const value = await request<Session>("/api/session");
      setOffline(null);
      setError("");
      setSession(value);
    } catch (cause) {
      const unreachable = cause instanceof ApiError && (cause.status === 0 || (cause.status >= 502 && cause.status <= 504));
      if (!unreachable) {
        setError(cause instanceof Error ? cause.message : "");
        return;
      }
      const username = lastSignedIn();
      setOffline((current) => ({ username, waiting: current?.username === username ? current.waiting : 0 }));
      if (username) {
        try {
          const waiting = (await uploadQueue.pending(username)).length;
          setOffline((current) => current && current.username === username ? { ...current, waiting } : current);
        } catch {
          // The queue cannot be read here: show the screen without a count.
        }
      }
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { void checkSession(); }, [checkSession]);
  const isOffline = offline !== null;
  useEffect(() => {
    if (!isOffline) return;
    const retry = () => void checkSession();
    window.addEventListener("online", retry);
    const timer = window.setInterval(retry, 15000);
    return () => { window.removeEventListener("online", retry); window.clearInterval(timer); };
  }, [isOffline, checkSession]);
  useEffect(() => {
    if (session) rememberSignedIn(session.authenticated ? session.username : null);
  }, [session]);

  // A 401 on any request while signed in (signed out elsewhere, session expired, account disabled):
  // go back to the sign-in screen with a short notice instead of showing an empty archive. The screen
  // address is kept, so signing in again returns to it.
  const [sessionNotice, setSessionNotice] = useState("");
  useEffect(() => onSessionEnded(() => {
    const previous = signedInAs.current;
    if (!previous) return;
    signedInAs.current = null; // one check at a time
    const ended = () => {
      setSelectedDocument(null);
      setShowAdd(false);
      setShowShortcuts(false);
      setMenuOpen(false);
      setSessionNotice(m.sessionEnded);
    };
    request<Session>("/api/session")
      .then((value) => {
        if (value.authenticated) signedInAs.current = value.username; // a false alarm: nothing is closed, carry on
        else ended();
        setSession(value);
      })
      .catch(() => {
        ended();
        setSession((current) => current ? { ...current, authenticated: false, username: null, owner: false } : current);
      });
  }), [m]);

  useEffect(() => {
    if (session?.authenticated) window.RipianoAndroid?.postMessage("retry");
  }, [session?.authenticated]);

  // Owner-only screens opened from an address by someone else fall back to the Library.
  useEffect(() => {
    if (session?.authenticated && !session.owner && OWNER_VIEWS.includes(view)) {
      replaceNextUrl.current = true;
      setView("documents");
    }
  }, [session?.authenticated, session?.owner, view]);

  // A list kept on screen while offline belongs to the person who loaded it: never carry it over to
  // the next sign-in on this device.
  useEffect(() => {
    setDocuments([]);
    setCountsKnown(false);
    setStaleSince(null);
    listLoadedRef.current = false;
    lastLoadedAt.current = null;
  }, [session?.username]);

  // Back online: load the list again straight away.
  useEffect(() => {
    if (!staleSince || !session?.authenticated) return;
    const retry = () => void loadDocuments(query);
    window.addEventListener("online", retry);
    return () => window.removeEventListener("online", retry);
  }, [staleSince, session?.authenticated, query, loadDocuments]);

  useEffect(() => {
    if (!session?.authenticated || view !== "documents") return;
    let cancelled = false;
    request<{ enabled: boolean }>("/api/semantic-search/available")
      .then((value) => { if (!cancelled) setSemanticAvailable(value.enabled); })
      .catch(() => { if (!cancelled) setSemanticAvailable(false); });
    return () => { cancelled = true; };
  }, [session?.authenticated, view]);

  useEffect(() => {
    if (!session?.authenticated || view !== "documents") return;
    const useMeaning = semanticAvailable && query.trim().length >= 3 && !/\b\w+:/.test(query) && (!sort || sort === "relevance");
    const timer = window.setTimeout(() => loadDocuments(query), useMeaning ? 600 : 200);
    return () => window.clearTimeout(timer);
  }, [session?.authenticated, query, view, sort, semanticAvailable, loadDocuments]);

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

  async function refreshWaiting() {
    const count = session?.username ? (await uploadQueue.pending(session.username)).length : 0;
    setWaitingUploads(count);
    return count;
  }

  function clearWaitingRetry() {
    if (waitingRetryTimer.current !== null) window.clearTimeout(waitingRetryTimer.current);
    waitingRetryTimer.current = null;
  }

  /** Try the waiting files again soon: 3 s, 10 s, 30 s, then every 60 s while online. Offline, the
   *  "online" event sends them instead, and the banner says so. */
  function scheduleWaitingRetry() {
    clearWaitingRetry();
    if (!navigator.onLine) {
      setWaitingRetrying(false);
      return;
    }
    const delay = WAITING_RETRY_DELAYS[Math.min(waitingAttempt.current, WAITING_RETRY_DELAYS.length - 1)];
    waitingAttempt.current += 1;
    setWaitingRetrying(true);
    waitingRetryTimer.current = window.setTimeout(() => {
      waitingRetryTimer.current = null;
      void sendWaitingRef.current();
    }, delay);
  }

  /** Send files kept while offline, oldest first. Stops at the first network failure; refused files are reported. */
  /** "Send now": try at once and start the backoff again from the shortest delay. */
  function sendWaitingNow() {
    waitingAttempt.current = 0;
    void sendWaiting();
  }

  async function sendWaiting() {
    const owner = session?.username;
    if (!owner || sendingWaiting.current) return;
    sendingWaiting.current = true;
    clearWaitingRetry();
    const failures: string[] = [];
    let sent = 0;
    let stoppedOnFailure = false;
    let left = 0;
    try {
      for (const item of await uploadQueue.pending(owner)) {
        const form = new FormData();
        form.append("document", new File([item.blob], item.name, { type: item.type }));
        if (signedInAs.current !== owner) break; // someone else signed in meanwhile: never send into their account
        try {
          await request<Document>("/api/documents", { method: "POST", body: form, headers: { "X-Ripiano-Scan-ID": item.scanId ?? uploadQueue.newScanId(), "X-Ripiano-Client": "web" } });
          sent += 1;
          await uploadQueue.forget(item.id);
        } catch (cause) {
          // Keep the file unless the server refused the file itself (signed out, throttled, or server errors keep it).
          if (!(cause instanceof ApiError) || !uploadQueue.isRefusal(cause.status)) {
            stoppedOnFailure = true;
            break;
          }
          failures.push(`${item.name}: ${cause.message}`);
          await uploadQueue.forget(item.id);
        }
      }
    } finally {
      sendingWaiting.current = false;
      left = await refreshWaiting();
    }
    if (stoppedOnFailure && left > 0 && signedInAs.current === owner) scheduleWaitingRetry();
    else if (!left) {
      waitingAttempt.current = 0;
      setWaitingRetrying(false);
    }
    if (failures.length) setUploadReport({ total: sent + failures.length, failures });
    if (sent) void loadDocuments(query);
  }

  sendWaitingRef.current = sendWaiting;

  useEffect(() => {
    signedInAs.current = session?.authenticated ? session.username : null;
    if (!session?.authenticated) return;
    void sendWaiting();
    const retry = () => void sendWaitingRef.current();
    const backOnline = () => { waitingAttempt.current = 0; void sendWaitingRef.current(); };
    const wentOffline = () => { clearWaitingRetry(); setWaitingRetrying(false); };
    window.addEventListener("online", backOnline);
    window.addEventListener("offline", wentOffline);
    const timer = window.setInterval(retry, 60000);
    return () => {
      window.removeEventListener("online", backOnline);
      window.removeEventListener("offline", wentOffline);
      window.clearInterval(timer);
      clearWaitingRetry();
      waitingAttempt.current = 0;
      setWaitingRetrying(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.authenticated, session?.username]);

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
    setUploadDone(null);
    try {
      const failures: string[] = [];
      const added: string[] = [];
      for (const [index, file] of chosen.entries()) {
        setUploadProgress(l.addingProgress(index + 1, chosen.length));
        // One ID per file from its first attempt: if the answer is lost and the file is sent again from the
        // queue, the server recognises it instead of storing a second copy.
        const scanId = uploadQueue.newScanId();
        try {
          const form = new FormData();
          form.append("document", file);
          const created = await request<Document>("/api/documents", {
            method: "POST",
            body: form,
            headers: { "X-Ripiano-Scan-ID": scanId, "X-Ripiano-Client": "web" },
          });
          added.push(created.id);
        } catch (cause) {
          // Offline, server unavailable, or session ended: keep the file for this person to retry after sign-in.
          if (cause instanceof ApiError && uploadQueue.isRetryable(cause.status) && session?.username && await uploadQueue.keep(session.username, file, scanId)) {
            continue; // shown in the "waiting to upload" banner, not as a rejected file
          } else {
            failures.push(`${file.name}: ${cause instanceof Error ? cause.message : l.uploadFailed}`);
          }
        }
      }
      const waitingNow = await refreshWaiting();
      // A file just kept because Ripiano could not be reached: try it again in a few seconds.
      if (waitingNow > 0 && !sendingWaiting.current && waitingRetryTimer.current === null) {
        waitingAttempt.current = 0;
        scheduleWaitingRetry();
      }
      await loadDocuments("");
      if (failures.length) setUploadReport({ total: chosen.length, failures });
      if (added.length) {
        setUploadDone({ count: added.length, firstId: added[0] });
        // On a phone the new card sits far below the fold: bring it into view.
        if (window.matchMedia("(max-width: 800px)").matches) setRevealDocument(added[0]);
      }
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

  /** With files still waiting on this device, ask first: keep them for the next sign-in here, or discard them. */
  async function requestSignOut(discardWaiting = false) {
    if (waitingUploads > 0 && !confirmSignOut) {
      setConfirmSignOut(true);
      return;
    }
    if (discardWaiting && session?.username) await uploadQueue.forgetAll(session.username);
    setConfirmSignOut(false);
    signedInAs.current = null;
    await signOut();
  }

  async function signOut() {
    try {
      await request("/api/session", { method: "DELETE" });
      setSession(await request<Session>("/api/session"));
      setDocuments([]);
      // The next person to sign in on this device starts at the Library (/), with nothing left open.
      // Only when something will actually change: otherwise the flag would linger and make the first
      // navigation after the next sign-in replace the entry, so Back would leave the app.
      replaceNextUrl.current = view !== "documents" || selectedDocument !== null;
      setSelectedDocument(null);
      setMenuOpen(false);
      setView("documents");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.signOutError);
    }
  }

  /** Escape in the search field hands the keyboard back to the results, so j / k / Enter work right away:
   *  focus goes to the first result, or (while results are still loading, or there are none) to the page,
   *  where j / k start on the first row. The query is kept; "/" returns to the field. */
  function leaveSearchOnEscape(event: ReactKeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Escape" || event.nativeEvent.isComposing) return;
    event.preventDefault();
    const firstTitle = document.querySelector<HTMLElement>("#main-content .library-list .document-row .document-title-button");
    if (documents.length && firstTitle) {
      firstTitle.focus();
      setActiveRow(0);
      return;
    }
    event.currentTarget.blur();
    document.getElementById("main-content")?.focus({ preventScroll: true });
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
  if (!session && offline)
    return (
      <main className="offline-screen">
        <div className="offline-card">
          <WifiOff size={30} aria-hidden="true" />
          <h1>{m.offlineTitle}</h1>
          <p role="status">{m.offlineText}</p>
          {offline.username && <p>{m.offlineSignedInAs(offline.username)}</p>}
          {offline.username && offline.waiting > 0 && (
            <p className="offline-waiting"><UploadCloud size={19} aria-hidden="true" /> {m.offlineWaiting(offline.waiting)}</p>
          )}
          <button type="button" onClick={() => void checkSession()}>{m.tryAgain}</button>
        </div>
      </main>
    );
  if (!session)
    return (
      <div className="loading-screen error-screen">
        {error || m.connectError}{" "}
        <button onClick={() => location.reload()}>{m.tryAgain}</button>
      </div>
    );
  if (!session.authenticated)
    return (
      <AuthScreen setup={session.setup_required}
        onAuthenticated={(value) => { setSessionNotice(""); setSession(value); }}
        notice={sessionNotice}
        appearance={appearance} onAppearanceChange={changeAppearance} />
    );

  const isEmpty = countsKnown && counts.total === 0;
  const savedSearchBar = (
    <SavedSearchBar query={query} filters={filters} onApply={(savedQuery, savedFilters) => {
      setQuery(savedQuery);
      setFilters(savedFilters);
      setNextCursor(null);
      setShowFilters(Object.values(savedFilters).some(Boolean));
    }} />
  );
  const activeFilterCount = Object.entries(filters).filter(([key, value]) => !["custom_value", "custom_min", "custom_max"].includes(key) && Boolean(value)).length;
  const selectedCustomField = filterOptions.custom_fields.find((field) => field.id === filters.custom_field_id);
  const tagById = new Map(filterOptions.tags.map((tag) => [tag.id, tag]));
  const tagOptions = [...filterOptions.tags].sort((a, b) =>
    tagPathLabel(a, tagById).localeCompare(tagPathLabel(b, tagById)));
  const viewLabels = viewLabelsFor(m);

  const navItems: [View, typeof Inbox, string][] = [
    ["inbox", Inbox, m.inbox], ["documents", FolderOpen, m.allDocuments], ["actions", ClipboardList, m.needsAction],
    ["tags", TagIcon, m.tags], ["physical", MapPin, m.physical], ["overview", BarChart3, m.overview],
    ["workflows", Workflow, m.workflows], ["security", ShieldCheck, m.security], ["integrations", Mail, m.email],
    ["sources", Cloud, m.sources], ["shared", Users, m.shared], ["trash", Trash2, m.trash],
    // Everyone may connect agents to their own archive; instance settings stay with the admin.
    ["agents", Bot, m.agents],
    ...(session.owner ? [["people", UserCog, m.people], ["backups", DatabaseBackup, m.backups]] as [View, typeof Inbox, string][] : []),
  ];

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
      <a className="skip-link" href="#main-content" inert={drawerCoversPage}>{m.skipToContent}</a>
      <p className="visually-hidden" aria-live="polite" aria-atomic="true">{appAnnouncement}</p>
      {showShortcuts && <KeyboardHelp onClose={() => setShowShortcuts(false)} />}
      <aside id="app-sidebar" ref={sidebarRef} className={`sidebar ${menuOpen ? "sidebar-open" : ""}`}
        inert={narrowLayout && !menuOpen} aria-hidden={narrowLayout && !menuOpen ? true : undefined}>
        <div className="sidebar-brand">
          <span className="brand-mark">
            <FolderOpen size={22} strokeWidth={2.1} />
          </span>
          <span>ripiano</span>
          <button className="sidebar-close" aria-label={m.dismissNavigation} onClick={closeMenu}>
            <X size={19} />
          </button>
        </div>
        {/* The list scrolls on short screens; a fade at the top or bottom edge shows there is more. */}
        <div className="sidebar-scroll-frame" ref={sidebarFrameRef}>
        <div className="sidebar-scroll" ref={sidebarScrollRef}>
          <nav className="sidebar-nav" aria-label={m.mainNavigation}>
            <div className="sidebar-label">{m.yourSpace}</div>
            {navItems.map(([target, Icon, label]) => (
              <button
                key={target}
                className={`nav-link ${view === target ? "active" : ""}`}
                aria-current={view === target ? "page" : undefined}
                onClick={() => {
                  if (target === "documents") {
                    setQuery("");
                    setFilters({ ...emptyLibraryFilters });
                  }
                  goTo(target);
                }}
              >
                <Icon size={18} aria-hidden="true" /> {label}
              </button>
            ))}
          </nav>
          <div className="sidebar-spacer" />
          <div className="sidebar-note">
            <div className="sidebar-note-icon">
              <LockKeyhole size={17} />
            </div>
            <strong>{m.sidebarNoteTitle}</strong>
            <span>{m.sidebarNoteText}</span>
          </div>
        </div>
        </div>
        {/* Appearance and language stay next to the account row, visible on any screen height. */}
        <div className="sidebar-settings">
          <AppearanceControl preference={appearance} onChange={changeAppearance} compact />
        </div>
        <div className="profile">
          <span className="avatar" aria-hidden="true">
            {session.username?.slice(0, 1).toUpperCase()}
          </span>
          <span className="profile-name">
            {session.username}
            <small>{session.owner ? m.admin : m.yourArchive}</small>
          </span>
          {confirmSignOut ? (
            <div className="sign-out-confirm" role="alert">
              <p>{m.signOutWaiting(waitingUploads)}</p>
              <button type="button" onClick={() => void requestSignOut(false)}>{m.signOutKeep}</button>
              <button type="button" onClick={() => void requestSignOut(true)}>{m.signOutDiscard}</button>
              <button type="button" onClick={() => setConfirmSignOut(false)}>{m.cancelSignOut}</button>
            </div>
          ) : (
            <button type="button" className="sign-out" onClick={() => void requestSignOut()} title={m.signOut}>
              <LogOut size={16} aria-hidden="true" /> {m.signOut}
            </button>
          )}
        </div>
      </aside>
      {/* Tapping anywhere outside the open phone menu closes it (Esc does the same on a keyboard). */}
      {narrowLayout && menuOpen && <div className="sidebar-backdrop" aria-hidden="true" onClick={closeMenu} />}

      <main className="main-content" id="main-content" tabIndex={-1} inert={drawerCoversPage}>
        <header className={`topbar${view === "documents" ? " topbar-with-add" : ""}`}>
          <button
            ref={menuButtonRef}
            type="button"
            className="icon-button mobile-menu"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label={m.toggleMenu}
            aria-expanded={menuOpen}
            aria-controls="app-sidebar"
          >
            <Menu size={21} aria-hidden="true" />
          </button>
          <div className="topbar-crumb">
            {m.yourArchive} <span>/</span> {viewLabels[view]}
          </div>
          <div className="topbar-right">
            <span className="private-dot" /> {m.privateAndYours}
          </div>
          {/* On a phone, adding a document is the main action: it sits in the top bar, in thumb reach
              of the list, instead of under the search and filter controls. */}
          {view === "documents" && (
            <Button className="topbar-add" onClick={() => setShowAdd(true)}>
              <Plus size={18} aria-hidden="true" /> {l.addShort}
            </Button>
          )}
        </header>
        <section className={`page-content${view === "documents" && query.trim() ? " library-searching" : ""}`}>
          <div className="trash-undo-region" aria-live="polite" aria-atomic="true">
            {trashedNotice && (
              <div className="upload-progress upload-done trash-undo-notice">
                <Check size={19} aria-hidden="true" />{" "}
                <span>{trashedNotice.state === "restored" ? l.restoredFromTrash(trashedNotice.title)
                  : trashedNotice.state === "failed" ? l.undoTrashFailed(trashedNotice.title)
                  : l.movedToTrash(trashedNotice.title)}</span>
                {(trashedNotice.state === "trashed" || trashedNotice.state === "restoring") && (
                  <button type="button" className="text-action" disabled={trashedNotice.state === "restoring"}
                    aria-label={l.undoTrashLabel(trashedNotice.title)} onClick={() => void undoTrash()}>
                    <RotateCcw size={16} aria-hidden="true" /> {l.undoTrash}
                  </button>
                )}
                <button type="button" className="upload-done-dismiss" aria-label={l.dismissAdded} onClick={() => setTrashedNotice(null)}><X size={16} aria-hidden="true" /></button>
              </div>
            )}
          </div>
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
            <>
              <AgentPanel />
              {/* Semantic search is an instance-wide setting: admin only. */}
              {session.owner && <div className="semantic-settings"><SemanticPanel /></div>}
            </>
          ) : view === "overview" ? (
            <OverviewPanel onNavigate={(target) => setView(target)}
              onOpenDocument={(id) => void request<Document>(`/api/documents/${id}`).then(setSelectedDocument).catch((cause) => setError(cause.message))}
              onOpenUntagged={() => {
              setQuery("is:untagged");
              setFilters({ ...emptyLibraryFilters });
              setNextCursor(null);
              setView("documents");
            }} />
          ) : view === "security" ? (
            <SecurityPanel />
          ) : view === "workflows" ? (
            <WorkflowsPanel onOpenDocument={(id) => void request<Document>(`/api/documents/${id}`).then(setSelectedDocument).catch((cause) => setError(cause.message))} />
          ) : view === "sources" ? (
            <SourcesPanel owner={session.owner} notice={initialSourceNotice} />
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
              <div className="page-heading library-heading">
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
                    <strong>{countsKnown ? counts.total : "–"}</strong>
                    <span>{query || activeFilterCount ? l.matchingDocuments : l.documents}</span>
                  </div>
                </div>
                <div className="summary-card">
                  <span className="summary-icon green">
                    <Check size={20} />
                  </span>
                  <div>
                    <strong>{countsKnown ? counts.ready : "–"}</strong>
                    <span>{l.readyToFind}</span>
                  </div>
                </div>
                <div className="summary-card">
                  <span className="summary-icon amber">
                    <Clock3 size={20} />
                  </span>
                  <div>
                    <strong>{countsKnown ? counts.waiting : "–"}</strong>
                    <span>{l.beingProcessed}</span>
                  </div>
                </div>
              </div>

              <div className="section-heading library-section-heading">
                <div>
                  <h2>{l.yourDocuments}</h2>
                  <p>{l.searchIntro}</p>
                  {/* Phones show the counts as one line instead of the three cards above. */}
                  {countsKnown && <p className="library-counts" role="status" aria-live="polite" aria-atomic="true">{l.compactCounts(counts.total, counts.waiting, Boolean(query || activeFilterCount))}</p>}
                </div>
                <Button type="button" variant="secondary" aria-label={l.refresh} title={l.refreshTitle} onClick={() => void loadDocuments(query)}>
                  <RotateCcw size={16} /> <span className="refresh-label">{l.refresh}</span>
                </Button>
              </div>
              {!phoneLayout && savedSearchBar}
              <div className="toolbar">
                <div className="search-box">
                  <Search size={19} />
                  <input
                    ref={searchRef}
                    value={query}
                    onChange={(event) => { setQuery(event.target.value); setNextCursor(null); }}
                    onKeyDown={leaveSearchOnEscape}
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
              </div>
              {phoneLayout && showFilters && savedSearchBar}
              <details className={`search-syntax${phoneLayout && !showFilters ? " phone-collapsed" : ""}`}>
                <summary>{l.preciseSearch}</summary>
                <p>{l.searchHelpUse} <code>{l.tagExample}</code>, <code>{l.senderExample}</code>, <code>{l.dateExample}</code> {l.searchHelpOr} <code>is:untagged</code>. {l.searchHelpAlso} {l.moreFields.split(" ").map((field) => <span key={field}><code>{field}</code>, </span>)}{l.searchHelpOr} <code>is:tagged</code>. {l.searchHelpCombine}{l.otherLanguageFields ? ` ${l.otherLanguageFields}` : ""} {l.searchHelpPress} <kbd>/</kbd> {l.searchHelpToSearch} <kbd>N</kbd> {l.searchHelpToAdd}</p>
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
              {staleSince && (
                <div className="stale-notice" role="status">
                  <WifiOff size={18} aria-hidden="true" />
                  <span>{l.offlineShowingLast(formatTime(staleSince))}</span>
                  <button type="button" className="text-action" onClick={() => void loadDocuments(query)}>{l.retry}</button>
                </div>
              )}
              {waitingUploads > 0 && (
                <div className="upload-progress" role="status" aria-live="polite">
                  <UploadCloud size={19} /> {waitingRetrying ? l.waitingUploadsRetrying(waitingUploads) : l.waitingUploads(waitingUploads)}
                  <button type="button" className="text-action" onClick={sendWaitingNow}>{l.sendWaitingNow}</button>
                </div>
              )}
              {uploading && (
                <div className="upload-progress" role="status" aria-live="polite" aria-atomic="true">
                  <UploadCloud size={19} /> {uploadProgress || l.addingDocument}
                </div>
              )}
              <div className="upload-done-region" aria-live="polite" aria-atomic="true">
                {uploadDone && !uploading && (
                  <div className="upload-progress upload-done">
                    <Check size={19} aria-hidden="true" /> <span>{l.addedDocuments(uploadDone.count)}</span>
                    {documents.some((doc) => doc.id === uploadDone.firstId) && (
                      <button type="button" className="text-action" aria-label={l.showAddedLabel(uploadDone.count)}
                        onClick={() => setRevealDocument(uploadDone.firstId)}>{l.showAdded}</button>
                    )}
                    <button type="button" className="upload-done-dismiss" aria-label={l.dismissAdded} onClick={() => setUploadDone(null)}><X size={16} aria-hidden="true" /></button>
                  </div>
                )}
              </div>
              {!listError && (!isEmpty || selectionMode || bulkNotice) && <div className="bulk-controls">
                <button type="button" className="text-action" disabled={bulkBusy || (isEmpty && !selectionMode)} onClick={() => { setSelectionMode(!selectionMode); setSelectedIds([]); setConfirmBulkTrash(false); setBulkError(""); setBulkNotice(""); }}>
                  {selectionMode ? l.doneSelecting : l.selectDocuments}
                </button>
                {selectionMode && <div className="bulk-actions">
                  <strong>{l.selectedCount(selectedIds.length)}</strong>
                  <button type="button" className="text-action" disabled={bulkBusy || documents.length === 0} onClick={() => setSelectedIds(documents.slice(0, 100).map((doc) => doc.id))}>
                    {documents.length > 100 ? l.selectFirstLoaded : l.selectLoaded}
                  </button>
                  {selectedIds.length > 0 && <button type="button" className="text-action" disabled={bulkBusy} onClick={() => setSelectedIds([])}>{l.clearSelection}</button>}
                  {selectedIds.length === 0 && <p className="bulk-selection-hint">{l.selectionHint}</p>}
                  <div className="bulk-action-content" hidden={selectedIds.length === 0}>
                  <select aria-label={l.bulkTagAria} value={bulkTagId} disabled={bulkBusy || !filterOptions.tags.length} onChange={(event) => setBulkTagId(event.target.value)}>
                    <option value="">{l.chooseTag}</option>
                    {tagOptions.map((tag) => <option key={tag.id} value={tag.id}>{tagPathLabel(tag, tagById)}</option>)}
                  </select>
                  <Button type="button" disabled={bulkBusy || !selectedIds.length || !bulkTagId} onClick={() => void applyBulkTag("add")}>{l.addTag}</Button>
                  <Button type="button" variant="secondary" disabled={bulkBusy || !selectedIds.length || !bulkTagId} onClick={() => void applyBulkTag("remove")}>{l.removeTag}</Button>
                  <details className="bulk-filing-details">
                    <summary>{l.changeFiling}</summary>
                    <div className="bulk-filing">
                    <select aria-label={l.bulkSenderAria} value={bulkSenderId} disabled={bulkBusy} onChange={(event) => setBulkSenderId(event.target.value)}>
                      <option value="">{l.chooseSender}</option>
                      <option value="none">{l.clearSender}</option>
                      {filterOptions.correspondents.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                    </select>
                    <Button type="button" variant="secondary" disabled={bulkBusy || !selectedIds.length || !bulkSenderId} onClick={() => void applyBulkFiling("correspondent")}>{l.setSender}</Button>
                    <select aria-label={l.bulkTypeAria} value={bulkTypeId} disabled={bulkBusy} onChange={(event) => setBulkTypeId(event.target.value)}>
                      <option value="">{l.chooseType}</option>
                      <option value="none">{l.clearType}</option>
                      {filterOptions.document_types.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                    </select>
                    <Button type="button" variant="secondary" disabled={bulkBusy || !selectedIds.length || !bulkTypeId} onClick={() => void applyBulkFiling("document_type")}>{l.setType}</Button>
                    </div>
                  </details>
                  <details className="bulk-filing-details">
                    <summary>{l.learnedSummary}</summary>
                    <div className="bulk-filing">
                      <p>{l.learnedIntro}</p>
                      <Button type="button" variant="secondary" disabled={bulkBusy || !selectedIds.length} onClick={() => void applyBulkLearnedFiling()}><Brain size={16} aria-hidden="true" /> {l.learnedButton(selectedIds.length)}</Button>
                    </div>
                  </details>
                  <details className="bulk-filing-details">
                    <summary>{l.dateSummary}</summary>
                    <div className="bulk-filing">
                      <input type="date" aria-label={l.bulkDateAria} value={bulkDate} disabled={bulkBusy} onChange={(event) => setBulkDate(event.target.value)} />
                      <Button type="button" variant="secondary" disabled={bulkBusy || !selectedIds.length || !bulkDate} onClick={() => void applyBulkDate(false)}>{l.setDate}</Button>
                      <Button type="button" variant="secondary" disabled={bulkBusy || !selectedIds.length} onClick={() => void applyBulkDate(true)}>{l.clearDate}</Button>
                    </div>
                  </details>
                  <details className="bulk-filing-details">
                    <summary>{l.ocrSummary}</summary>
                    <div className="bulk-filing">
                      <Button type="button" variant="secondary" disabled={bulkBusy || !selectedIds.length} onClick={() => void applyBulkOcr("retry")}>
                        <RotateCcw size={16} /> {l.retryFailedOcr}
                      </Button>
                      <Button type="button" variant="secondary" disabled={bulkBusy || !selectedIds.length} onClick={() => void applyBulkOcr("rebuild")}>
                        <RotateCcw size={16} /> {l.rebuildPdfs}
                      </Button>
                    </div>
                  </details>
                  <details className="bulk-filing-details">
                    <summary>{l.mergeSummary}</summary>
                    <div className="bulk-filing">
                      <p>{l.mergeIntro}</p>
                      {selectedIds.length > 1 && <ol className="merge-order">{selectedIds.map((id) => <li key={id}>{documents.find((item) => item.id === id)?.title ?? l.selectedDocumentFallback}</li>)}</ol>}
                      <Button type="button" variant="secondary" disabled={bulkBusy || selectedIds.length < 2 || selectedIds.length > 50} onClick={() => void mergeSelected()}>
                        <Layers size={16} /> {l.mergeButton(selectedIds.length)}
                      </Button>
                    </div>
                  </details>
                  <BundlePanel selectedIds={selectedIds} />
                  <details className="bulk-filing-details">
                    <summary>{l.exportSummary}</summary>
                    <div className="bulk-filing">
                      <p>{l.exportIntro}</p>
                      {selectedIds.length > 20 && <p className="inline-error">{l.exportTooMany}</p>}
                      {selectedIds.length > 0 && selectedIds.length <= 20 && !bulkBusy && <a className="button button-secondary" href={`/api/documents/export?${new URLSearchParams(selectedIds.map((id) => ["document_ids", id]))}`} download="ripiano-documents.zip"><ArrowDownToLine size={16} /> {l.downloadCount(selectedIds.length)}</a>}
                    </div>
                  </details>
                  <details className="bulk-filing-details" open={confirmBulkTrash} onToggle={(event) => setConfirmBulkTrash(event.currentTarget.open)}>
                    <summary>{l.trashSummary}</summary>
                    <div className="bulk-filing">
                      <p>{l.trashIntro}</p>
                      {confirmBulkTrash && <Button type="button" variant="danger" disabled={bulkBusy || !selectedIds.length} onClick={() => void applyBulkTrash()}>
                        <Trash2 size={16} /> {l.confirmTrash(selectedIds.length)}
                      </Button>}
                    </div>
                  </details>
                  </div>
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
                  {query && suggestion && (
                    <p className="search-suggestion">
                      {l.didYouMean}{" "}
                      <button type="button" className="text-action" onClick={() => setQuery(suggestion)}>{suggestion}</button>
                    </p>
                  )}
                  <p>
                    {query || activeFilterCount
                      ? l.tryAnotherSearch
                      : l.addSearchable}
                  </p>
                  {(query || activeFilterCount) ? <p className="search-hint">{l.searchHint}</p> : null}
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
                {/* A real list, so screen readers announce "list, N items"; each row stays an article. */}
                <ul className="document-list library-list" role="list" aria-label={l.resultsList}>
                  {documents.map((doc, index) => (
                    <li key={doc.id}>
                    <article className={`document-row${activeRow === index ? " keyboard-active" : ""}`} data-document-id={doc.id} aria-current={activeRow === index ? "true" : undefined}>
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
                            <span className="document-title-text">{doc.title}</span>
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
                      <div className="document-row-actions">
                      <span className={`status status-${doc.status}`}>
                        {doc.status === "ready"
                          ? l.ready
                          : doc.status === "failed"
                            ? l.needsAttention
                            : l.processing}
                      </span>
                      <div className="document-row-links">
                      {doc.status === "failed" && (
                        <button
                          className="download-link"
                          onClick={() => void retryDocument(doc.id)}
                          aria-label={l.retryNamed(doc.original_name)}
                          title={l.retryOcr}
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
                      </div>
                      </div>
                    </article>
                    </li>
                  ))}
                </ul>
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
              aria-hidden="true"
              aria-label={l.takePhoto}
              type="file"
              accept="image/*"
              capture="environment"
              onChange={(event: ChangeEvent<HTMLInputElement>) => void upload(event.target.files)}
            />
            <input
              ref={galleryRef}
              className="visually-hidden"
              tabIndex={-1}
              aria-hidden="true"
              aria-label={l.choosePhotos}
              type="file"
              accept="image/*"
              multiple
              onChange={(event) => void upload(event.target.files)}
            />
            <input
              ref={fileRef}
              className="visually-hidden"
              tabIndex={-1}
              aria-hidden="true"
              aria-label={l.browseFiles}
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
          onSaved={(saved, closing) => {
            void loadDocuments(query); void loadFilterOptions(); setActionRefresh((value) => value + 1); setInboxRefresh((value) => value + 1);
            // The dialog closes on save: say so, since nothing else on screen changes visibly.
            if (closing) setAppAnnouncement(l.documentSaved(saved.title));
          }}
          onTrashed={(trashed) => void documentTrashed(trashed)}
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
