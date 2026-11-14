import { FormEvent, useCallback, useEffect, useState } from "react";
import { ArrowRight, Boxes, MapPin, Plus, Printer, ScanLine, X } from "lucide-react";
import { Location, PhysicalCopy, request } from "./api";
import { Button } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/PhysicalPanel";

type Lookup = { copy: PhysicalCopy; document: { id: string; title: string } };
type LocationLookup = {
  location: Location;
  copies: Lookup[];
  total: number;
  next_cursor: string | null;
  missing_copies: Lookup[];
  missing_count: number;
  missing_next_cursor: string | null;
};

export default function PhysicalPanel({
  initialSticker,
  initialLocation,
  onOpenDocument,
}: {
  initialSticker: string;
  initialLocation: string;
  onOpenDocument: (id: string) => void;
}) {
  const m = useMessages(messages);
  const [locations, setLocations] = useState<Location[]>([]);
  const [name, setName] = useState("");
  const [parent, setParent] = useState("");
  const [code, setCode] = useState(initialSticker || initialLocation);
  const [found, setFound] = useState<Lookup | null>(null);
  const [foundLocation, setFoundLocation] = useState<LocationLookup | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadingContents, setLoadingContents] = useState(false);

  const load = useCallback(async () => {
    try {
      setLocations(
        (await request<{ locations: Location[] }>("/api/locations")).locations,
      );
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : m.loadError,
      );
    }
  }, [m]);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    if (initialLocation || initialSticker) void findSticker(initialLocation || initialSticker);
  }, [initialSticker, initialLocation]);

  async function findSticker(value: string) {
    setError("");
    setFound(null);
    setFoundLocation(null);
    try {
      const normalized = value.trim().toUpperCase();
      if (normalized.startsWith("L-")) {
        setFoundLocation(await request<LocationLookup>(`/api/locations/lookup/${encodeURIComponent(normalized)}`));
      } else {
        setFound(await request<Lookup>(`/api/stickers/${encodeURIComponent(normalized)}`));
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.stickerNotFound);
    }
  }

  async function createLocation(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await request("/api/locations", {
        method: "POST",
        body: JSON.stringify({ name, parent_id: parent || null }),
      });
      setName("");
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : m.createError,
      );
    } finally {
      setBusy(false);
    }
  }

  async function loadMoreContents(kind: "present" | "missing") {
    const location = foundLocation;
    if (!location || loadingContents) return;
    const cursor = kind === "present" ? location.next_cursor : location.missing_next_cursor;
    if (!cursor) return;
    setLoadingContents(true);
    setError("");
    try {
      const code = location.location.sticker_code;
      const parameter = kind === "present" ? "cursor" : "missing_cursor";
      const next = await request<LocationLookup>(`/api/locations/lookup/${code}?${parameter}=${encodeURIComponent(cursor)}`);
      setFoundLocation((current) => current?.location.sticker_code === code ? {
        ...current,
        copies: kind === "present" ? [...current.copies, ...next.copies] : current.copies,
        next_cursor: kind === "present" ? next.next_cursor : current.next_cursor,
        missing_copies: kind === "missing" ? [...current.missing_copies, ...next.missing_copies] : current.missing_copies,
        missing_next_cursor: kind === "missing" ? next.missing_next_cursor : current.missing_next_cursor,
      } : current);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.loadMoreError);
    } finally {
      setLoadingContents(false);
    }
  }

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
      </div>
      {error && (
        <div className="inline-error" role="alert">
          {error}
          <button onClick={() => setError("")} aria-label={m.dismissError}>
            <X size={16} />
          </button>
        </div>
      )}
      <div className="physical-layout">
        <section className="physical-main">
          <div className="sticker-search-card">
            <div className="physical-icon">
              <ScanLine size={22} />
            </div>
            <h2>{m.findHeading}</h2>
            <p>{m.findIntro}</p>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void findSticker(code);
              }}
            >
              <input
                value={code}
                onChange={(event) => setCode(event.target.value.toUpperCase())}
                placeholder={m.codePlaceholder}
                aria-label={m.codeLabel}
                required
              />
              <Button>{m.find}</Button>
            </form>
          </div>
          {found && (
            <div className="sticker-result">
              <div className="sticker-code">{found.copy.sticker_code}</div>
              <h3>{found.document.title}</h3>
              {found.copy.missing_at && <p className="copy-missing-label">{m.copyMissing}</p>}
              <p>
                <MapPin size={16} />{" "}
                {found.copy.missing_at ? m.lastKnown : ""}{found.copy.location_path.join(" / ") ||
                  m.notAssigned}
              </p>
              <Button
                variant="secondary"
                onClick={() => onOpenDocument(found.document.id)}
              >
                {m.openDocument} <ArrowRight size={16} />
              </Button>
            </div>
          )}
          {foundLocation && <div className="sticker-result location-result">
            <div className="sticker-code">{foundLocation.location.sticker_code}</div>
            <h3>{foundLocation.location.name}</h3>
            <p><MapPin size={16} /> {foundLocation.location.path.join(" / ")}</p>
            <strong>{m.presentCount(foundLocation.total)}</strong>
            {foundLocation.missing_count > 0 && <p className="copy-missing-label">
              {m.missingCount(foundLocation.missing_count)}
            </p>}
            {foundLocation.copies.length > 0 && <ul className="location-contents">{foundLocation.copies.map((item) => <li key={item.copy.id}>
              <button type="button" onClick={() => onOpenDocument(item.document.id)}>{item.document.title} <ArrowRight size={15} /></button>
              <small>{item.copy.sticker_code} · {item.copy.location_path.join(" / ")}</small>
            </li>)}</ul>}
            {foundLocation.next_cursor && <Button type="button" variant="secondary" disabled={loadingContents} onClick={() => void loadMoreContents("present")}>{loadingContents ? m.loading : m.showMore}</Button>}
            {foundLocation.missing_copies.length > 0 && <div className="location-missing-contents">
              <h4>{m.missingHeading}</h4>
              <ul className="location-contents">{foundLocation.missing_copies.map((item) => <li key={item.copy.id}>
                <button type="button" onClick={() => onOpenDocument(item.document.id)}>{item.document.title} <ArrowRight size={15} /></button>
                <small>{item.copy.sticker_code} · {m.lastKnown}{item.copy.location_path.join(" / ")}</small>
              </li>)}</ul>
            </div>}
            {foundLocation.missing_next_cursor && <Button type="button" variant="secondary" disabled={loadingContents} onClick={() => void loadMoreContents("missing")}>{loadingContents ? m.loading : m.showMoreMissing}</Button>}
          </div>}
          <div className="section-heading location-heading">
            <div>
              <h2>{m.locationsHeading}</h2>
              <p>{m.locationsIntro}</p>
            </div>
          </div>
          {locations.length ? (
            <div className="location-list">
              {locations.map((location) => (
                <div key={location.id}>
                  <span className="location-marker">
                    <Boxes size={18} />
                  </span>
                  <span className="location-path">{location.path.join(" / ")}</span>
                  <button type="button" className="text-action" onClick={() => { setCode(location.sticker_code); void findSticker(location.sticker_code); }}>{m.viewContents}</button>
                  <a className="text-action" href={`/api/locations/${location.id}/label`} target="_blank" rel="noreferrer"><Printer size={15} /> {m.printLabel}</a>
                </div>
              ))}
            </div>
          ) : (
            <div className="tag-empty">
              <Boxes size={27} />
              <strong>{m.emptyTitle}</strong>
              <p>{m.emptyText}</p>
            </div>
          )}
        </section>
        <section className="tag-create-card">
          <div className="tag-create-icon">
            <MapPin size={21} />
          </div>
          <h2>{m.addHeading}</h2>
          <p>{m.addIntro}</p>
          <form onSubmit={createLocation}>
            <label>
              {m.name}
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder={m.namePlaceholder}
                maxLength={100}
                required
              />
            </label>
            <label>
              {m.inside} <small>{m.optional}</small>
              <select
                value={parent}
                onChange={(event) => setParent(event.target.value)}
              >
                <option value="">{m.topLevel}</option>
                {locations.map((location) => (
                  <option key={location.id} value={location.id}>
                    {location.path.join(" / ")}
                  </option>
                ))}
              </select>
            </label>
            <Button disabled={busy}>
              <Plus size={17} /> {busy ? m.adding : m.addLocation}
            </Button>
          </form>
          <div className="tag-tip">
            {m.tip}
          </div>
        </section>
      </div>
    </>
  );
}
