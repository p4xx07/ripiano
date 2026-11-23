import { FormEvent, useEffect, useState } from "react";
import { BookmarkPlus, PinOff, X } from "lucide-react";
import { Document, LibraryFilters, request, SavedView, Tag } from "./api";
import { useMessages } from "./i18n";
import messages from "./locales/DashboardCollections";

const filterKeys = ["tag_id", "copy_status", "correspondent_id", "document_type_id", "date_from", "date_to", "custom_field_id", "custom_value", "custom_min", "custom_max"] as const;

function filtersFor(view: SavedView): LibraryFilters {
  return Object.fromEntries(filterKeys.map((key) => [key, view[key] ?? ""])) as LibraryFilters;
}

function CollectionCard({ view, onOpen, onOpenDocument, onUnpin }: {
  view: SavedView;
  onOpen: (view: SavedView) => void;
  onOpenDocument: (id: string) => void;
  onUnpin: (view: SavedView) => void;
}) {
  const m = useMessages(messages);
  const [result, setResult] = useState<{ total: number; documents: Document[] } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    const params = new URLSearchParams({ q: view.query, sort: "newest" });
    for (const [key, value] of Object.entries(filtersFor(view))) if (value) params.set(key, value);
    request<{ counts: { total: number }; documents: Document[] }>(`/api/documents?${params}`).then((response) => {
      if (live) setResult({ total: response.counts.total, documents: response.documents.slice(0, 3) });
    }).catch((cause) => { if (live) setError(cause instanceof Error ? cause.message : m.loadError); });
    return () => { live = false; };
  }, [view, m]);
  return <article className="dashboard-collection">
    <div className="dashboard-collection-head">
      <button type="button" className="dashboard-collection-title" onClick={() => onOpen(view)}>{view.name}</button>
      <button type="button" className="icon-button" aria-label={m.unpin(view.name)} title={m.unpin(view.name)} onClick={() => onUnpin(view)}><PinOff size={16} /></button>
    </div>
    {error ? <p className="inline-error" role="alert">{error}</p> : result ? <>
      <p className="dashboard-collection-count">{m.documentCount(result.total)}</p>
      {result.documents.length ? <ul>{result.documents.map((doc) => <li key={doc.id}><button type="button" onClick={() => onOpenDocument(doc.id)}>{doc.title}</button></li>)}</ul> : <p className="agent-empty-activity">{m.noMatches}</p>}
      <button type="button" className="text-action" onClick={() => onOpen(view)}>{m.openAll}</button>
    </> : <p className="agent-empty-activity">{m.loading}</p>}
  </article>;
}

export default function DashboardCollections({ onOpen, onOpenDocument }: {
  onOpen: (query: string, filters: LibraryFilters) => void;
  onOpenDocument: (id: string) => void;
}) {
  const m = useMessages(messages);
  const [views, setViews] = useState<SavedView[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [name, setName] = useState("");
  const [query, setQuery] = useState("");
  const [tagId, setTagId] = useState("");
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [home, setHome] = useState(() => { try { return localStorage.getItem("ripiano.dashboardHome") === "1"; } catch { return false; } });
  const load = async () => {
    const [saved, labels] = await Promise.all([
      request<{ views: SavedView[] }>("/api/saved-views"), request<{ tags: Tag[] }>("/api/tags"),
    ]);
    setViews(saved.views);
    setTags(labels.tags);
  };
  useEffect(() => { void load().catch((cause) => setError(cause instanceof Error ? cause.message : m.loadError)); }, [m]);
  const pinned = views.filter((view) => view.dashboard_pinned);
  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      await request("/api/saved-views", { method: "POST", body: JSON.stringify({ name, query, tag_id: tagId || null, dashboard_pinned: true }) });
      setName(""); setQuery(""); setTagId("");
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : m.saveError); }
    finally { setBusy(false); }
  }
  async function setPinned(view: SavedView, value: boolean): Promise<boolean> {
    setBusy(true); setError("");
    try {
      await request(`/api/saved-views/${view.id}`, { method: "PATCH", body: JSON.stringify({ dashboard_pinned: value }) });
      await load();
      return true;
    } catch (cause) { setError(cause instanceof Error ? cause.message : m.saveError); return false; }
    finally { setBusy(false); }
  }
  function setAsHome(value: boolean) {
    setHome(value);
    try { if (value) localStorage.setItem("ripiano.dashboardHome", "1"); else localStorage.removeItem("ripiano.dashboardHome"); } catch { /* Device storage may be disabled. */ }
  }
  return <section className="overview-card dashboard-collections" aria-labelledby="dashboard-collections-heading">
    <div className="dashboard-collections-heading">
      <div><h2 id="dashboard-collections-heading">{m.heading}</h2><p>{m.intro}</p></div>
      <label className="dashboard-home-choice"><input type="checkbox" checked={home} onChange={(event) => setAsHome(event.target.checked)} /> {m.useAsHome}</label>
    </div>
    {pinned.length ? <div className="dashboard-collection-grid">{pinned.map((view) => <CollectionCard key={view.id} view={view} onOpen={(item) => onOpen(item.query, filtersFor(item))} onOpenDocument={onOpenDocument} onUnpin={(item) => void setPinned(item, false)} />)}</div> : <p className="agent-empty-activity">{m.empty}</p>}
    {pinned.length < 6 && <div className="dashboard-collection-controls">
      <form onSubmit={(event) => void create(event)} className="dashboard-collection-create">
        <label className="detail-label">{m.name}<input value={name} onChange={(event) => setName(event.target.value)} maxLength={100} required placeholder={m.nameExample} /></label>
        <label className="detail-label">{m.search}<input value={query} onChange={(event) => setQuery(event.target.value)} maxLength={200} placeholder={m.searchExample} /></label>
        <label className="detail-label">{m.tag}<select value={tagId} onChange={(event) => setTagId(event.target.value)}><option value="">{m.anyTag}</option>{tags.map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}</select></label>
        <button type="submit" className="button button-secondary" disabled={busy}><BookmarkPlus size={16} /> {m.addCollection}</button>
      </form>
      {views.some((view) => !view.dashboard_pinned) && <div className="dashboard-collection-pin"><label className="detail-label">{m.pinExisting}<select value={selected} onChange={(event) => setSelected(event.target.value)}><option value="">{m.chooseSaved}</option>{views.filter((view) => !view.dashboard_pinned).map((view) => <option key={view.id} value={view.id}>{view.name}</option>)}</select></label><button type="button" className="text-action" disabled={busy || !selected} onClick={() => { const view = views.find((item) => item.id === selected); if (view) void setPinned(view, true).then((ok) => { if (ok) setSelected(""); }); }}>{m.pin}</button></div>}
    </div>}
    {error && <p className="inline-error" role="alert">{error}<button type="button" aria-label={m.dismissError} onClick={() => setError("")}><X size={16} /></button></p>}
  </section>;
}
