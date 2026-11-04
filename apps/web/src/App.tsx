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
  Camera,
  Check,
  Clock3,
  DatabaseBackup,
  Eye,
  FileText,
  FolderOpen,
  ImagePlus,
  LockKeyhole,
  LogOut,
  Menu,
  Plus,
  RotateCcw,
  Search,
  Tag as TagIcon,
  UploadCloud,
  X,
} from "lucide-react";
import { Document, formatDate, request, Session } from "./api";
import DocumentPanel from "./DocumentPanel";
import TagPanel from "./TagPanel";

type BackupRun = {
  id: string;
  status: "pending" | "running" | "complete" | "failed";
  trigger: string;
  snapshot_name: string;
  error: string;
  created_at: string;
};

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
          <label>
            Username
            <input
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete={setup ? "new-password" : "current-password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={setup ? 12 : undefined}
              required
            />
          </label>
          {setup && (
            <label>
              Setup key
              <input
                type="password"
                value={setupKey}
                onChange={(event) => setSetupKey(event.target.value)}
                required
              />
            </label>
          )}
          {error && (
            <div className="form-error" role="alert">
              {error}
            </div>
          )}
          <button className="button button-primary auth-submit" disabled={busy}>
            {busy ? "Please wait…" : setup ? "Create archive" : "Sign in"}{" "}
            <ArrowRight size={18} />
          </button>
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
        <button
          className="button button-primary"
          onClick={start}
          disabled={busy}
        >
          <DatabaseBackup size={18} /> {busy ? "Starting…" : "Back up now"}
        </button>
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
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [dropActive, setDropActive] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<"documents" | "tags" | "backups">(
    "documents",
  );
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(
    null,
  );
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadDocuments = useCallback(async (search: string) => {
    try {
      const result = await request<{ documents: Document[] }>(
        `/api/documents?q=${encodeURIComponent(search)}`,
      );
      setDocuments(result.documents);
      setError("");
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not load documents",
      );
    }
  }, []);

  useEffect(() => {
    request<Session>("/api/session")
      .then(setSession)
      .catch((cause) => setError(cause.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!session?.authenticated || view !== "documents") return;
    const timer = window.setTimeout(() => loadDocuments(query), 200);
    return () => window.clearTimeout(timer);
  }, [session?.authenticated, query, view, loadDocuments]);

  useEffect(() => {
    if (
      !session?.authenticated ||
      !documents.some(
        (doc) => doc.status === "pending" || doc.status === "processing",
      )
    )
      return;
    const timer = window.setInterval(() => loadDocuments(query), 5000);
    return () => window.clearInterval(timer);
  }, [session?.authenticated, documents, query, loadDocuments]);

  async function upload(files: FileList | File[] | null) {
    if (!files?.length) return;
    setUploading(true);
    setShowAdd(false);
    setError("");
    try {
      for (const file of Array.from(files)) {
        const form = new FormData();
        form.append("document", file);
        await request<Document>("/api/documents", {
          method: "POST",
          body: form,
        });
      }
      await loadDocuments(query);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Upload failed");
    } finally {
      setUploading(false);
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

  const ready = documents.filter((doc) => doc.status === "ready").length;
  const waiting = documents.filter(
    (doc) => doc.status === "pending" || doc.status === "processing",
  ).length;
  const isEmpty = documents.length === 0;

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
          className={`nav-link ${view === "documents" ? "active" : ""}`}
          onClick={() => {
            setView("documents");
            setQuery("");
            setMenuOpen(false);
          }}
        >
          <FolderOpen size={18} /> All documents
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
              : view === "tags"
                ? "Tags & filing"
                : "Backups"}
          </div>
          <div className="topbar-right">
            <span className="private-dot" /> Private & yours
          </div>
        </header>
        <section className="page-content">
          {view === "backups" ? (
            <BackupPanel />
          ) : view === "tags" ? (
            <TagPanel />
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
                <button
                  className="button button-primary desktop-add"
                  onClick={() => setShowAdd(true)}
                >
                  <Plus size={19} /> Add document
                </button>
              </div>

              <div className="summary-row">
                <div className="summary-card">
                  <span className="summary-icon">
                    <FileText size={20} />
                  </span>
                  <div>
                    <strong>{documents.length}</strong>
                    <span>{query ? "Matching documents" : "Documents"}</span>
                  </div>
                </div>
                <div className="summary-card">
                  <span className="summary-icon green">
                    <Check size={20} />
                  </span>
                  <div>
                    <strong>{ready}</strong>
                    <span>Ready to find</span>
                  </div>
                </div>
                <div className="summary-card">
                  <span className="summary-icon amber">
                    <Clock3 size={20} />
                  </span>
                  <div>
                    <strong>{waiting}</strong>
                    <span>Being processed</span>
                  </div>
                </div>
              </div>

              <div className="section-heading">
                <div>
                  <h2>Your documents</h2>
                  <p>Find a file in seconds, whenever you need it.</p>
                </div>
              </div>
              <div className="toolbar">
                <div className="search-box">
                  <Search size={19} />
                  <input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Search titles or document text…"
                    aria-label="Search documents"
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
                <button
                  className="button button-secondary mobile-add"
                  onClick={() => setShowAdd(true)}
                >
                  <Plus size={18} /> Add
                </button>
              </div>
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
              {uploading && (
                <div className="upload-progress">
                  <UploadCloud size={19} /> Adding your document…
                </div>
              )}

              {isEmpty ? (
                <div className="empty-state">
                  <div className="empty-icon">
                    <FileText size={33} strokeWidth={1.5} />
                  </div>
                  <h3>
                    {query
                      ? "Nothing found yet"
                      : "A fresh shelf, ready for you."}
                  </h3>
                  <p>
                    {query
                      ? "Try another word from the title or the document."
                      : "Add a document and Ripiano will make its text searchable."}
                  </p>
                  {!query && (
                    <button
                      className="button button-primary"
                      onClick={() => setShowAdd(true)}
                    >
                      <Plus size={18} /> Add your first document
                    </button>
                  )}
                </div>
              ) : (
                <div className="document-list">
                  {documents.map((doc) => (
                    <article className="document-row" key={doc.id}>
                      <div className="document-icon">
                        <FileText size={21} />
                      </div>
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
                          {doc.source === "telegram" && (
                            <>
                              {" "}
                              <span>·</span> via Telegram
                            </>
                          )}
                        </div>
                        {doc.snippet && <p>{doc.snippet}</p>}
                        {doc.tags.length > 0 && (
                          <div className="document-tags">
                            {doc.tags.map((tag) => (
                              <span key={tag.id}>
                                <i style={{ background: tag.color }} />
                                {tag.name}
                              </span>
                            ))}
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
      <input
        ref={cameraRef}
        className="visually-hidden"
        type="file"
        accept="image/*"
        capture="environment"
        onChange={(event: ChangeEvent<HTMLInputElement>) =>
          void upload(event.target.files)
        }
      />
      <input
        ref={galleryRef}
        className="visually-hidden"
        type="file"
        accept="image/*"
        multiple
        onChange={(event) => void upload(event.target.files)}
      />
      <input
        ref={fileRef}
        className="visually-hidden"
        type="file"
        accept="application/pdf,image/jpeg,image/png"
        multiple
        onChange={(event) => void upload(event.target.files)}
      />
      {showAdd && (
        <div
          className="modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setShowAdd(false);
          }}
        >
          <div
            className="add-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="add-heading"
          >
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
              <button onClick={() => cameraRef.current?.click()}>
                <span className="add-option-icon">
                  <Camera size={23} />
                </span>
                <span>
                  <strong>Take a photo</strong>
                  <small>Open your device camera</small>
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
              Camera behavior depends on your browser. A native Android scanner
              is planned for multi-page capture.
            </div>
          </div>
        </div>
      )}
      {selectedDocument && (
        <DocumentPanel
          initial={selectedDocument}
          onClose={() => setSelectedDocument(null)}
          onSaved={() => void loadDocuments(query)}
          onOpenTags={() => {
            setSelectedDocument(null);
            setView("tags");
          }}
        />
      )}
    </div>
  );
}

export default App;
