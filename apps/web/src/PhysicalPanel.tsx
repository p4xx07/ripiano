import { FormEvent, useCallback, useEffect, useState } from "react";
import { ArrowRight, Boxes, MapPin, Plus, Printer, ScanLine, X } from "lucide-react";
import { Location, PhysicalCopy, request } from "./api";
import { Button } from "./ui";

type Lookup = { copy: PhysicalCopy; document: { id: string; title: string } };
type LocationLookup = { location: Location; copies: Lookup[]; total: number; next_cursor: string | null };

export default function PhysicalPanel({
  initialSticker,
  initialLocation,
  onOpenDocument,
}: {
  initialSticker: string;
  initialLocation: string;
  onOpenDocument: (id: string) => void;
}) {
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
        cause instanceof Error ? cause.message : "Could not load locations",
      );
    }
  }, []);
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
      setError(cause instanceof Error ? cause.message : "Sticker not found");
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
        cause instanceof Error ? cause.message : "Could not create location",
      );
    } finally {
      setBusy(false);
    }
  }

  async function loadMoreContents() {
    if (!foundLocation?.next_cursor || loadingContents) return;
    setLoadingContents(true);
    setError("");
    try {
      const code = foundLocation.location.sticker_code;
      const next = await request<LocationLookup>(`/api/locations/lookup/${code}?cursor=${encodeURIComponent(foundLocation.next_cursor)}`);
      setFoundLocation((current) => current?.location.sticker_code === code ? {
        ...current,
        copies: [...current.copies, ...next.copies],
        next_cursor: next.next_cursor,
      } : current);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load more contents");
    } finally {
      setLoadingContents(false);
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            <span className="eyebrow-line" /> PAPER, FOUND
          </div>
          <h1>
            Your paper archive<span className="heading-period">.</span>
          </h1>
          <p>Give paper a place, then find a copy or box by its sticker.</p>
        </div>
      </div>
      {error && (
        <div className="inline-error" role="alert">
          {error}
          <button onClick={() => setError("")} aria-label="Dismiss error">
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
            <h2>Find a sticker</h2>
            <p>Scan a QR code or type the code printed on a paper copy, shelf, or box.</p>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void findSticker(code);
              }}
            >
              <input
                value={code}
                onChange={(event) => setCode(event.target.value.toUpperCase())}
                placeholder="R-XXXXXXXX or L-XXXXXXXX"
                aria-label="Sticker code"
                required
              />
              <Button>Find</Button>
            </form>
          </div>
          {found && (
            <div className="sticker-result">
              <div className="sticker-code">{found.copy.sticker_code}</div>
              <h3>{found.document.title}</h3>
              {found.copy.missing_at && <p className="copy-missing-label">This paper copy was reported missing.</p>}
              <p>
                <MapPin size={16} />{" "}
                {found.copy.missing_at ? "Last known: " : ""}{found.copy.location_path.join(" / ") ||
                  "Location not assigned yet"}
              </p>
              <Button
                variant="secondary"
                onClick={() => onOpenDocument(found.document.id)}
              >
                Open document <ArrowRight size={16} />
              </Button>
            </div>
          )}
          {foundLocation && <div className="sticker-result location-result">
            <div className="sticker-code">{foundLocation.location.sticker_code}</div>
            <h3>{foundLocation.location.name}</h3>
            <p><MapPin size={16} /> {foundLocation.location.path.join(" / ")}</p>
            <strong>{foundLocation.total} {foundLocation.total === 1 ? "paper copy" : "paper copies"} recorded here or inside nested locations</strong>
            {foundLocation.copies.length > 0 && <ul className="location-contents">{foundLocation.copies.map((item) => <li key={item.copy.id}>
              <button type="button" onClick={() => onOpenDocument(item.document.id)}>{item.document.title} <ArrowRight size={15} /></button>
              <small>{item.copy.sticker_code} · {item.copy.location_path.join(" / ")}{item.copy.missing_at ? " · Reported missing" : ""}</small>
            </li>)}</ul>}
            {foundLocation.next_cursor && <Button type="button" variant="secondary" disabled={loadingContents} onClick={() => void loadMoreContents()}>{loadingContents ? "Loading…" : "Show more copies"}</Button>}
          </div>}
          <div className="section-heading location-heading">
            <div>
              <h2>Locations</h2>
              <p>Create shelves and boxes that match your real space.</p>
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
                  <button type="button" className="text-action" onClick={() => { setCode(location.sticker_code); void findSticker(location.sticker_code); }}>View contents</button>
                  <a className="text-action" href={`/api/locations/${location.id}/label`} target="_blank" rel="noreferrer"><Printer size={15} /> Print label</a>
                </div>
              ))}
            </div>
          ) : (
            <div className="tag-empty">
              <Boxes size={27} />
              <strong>No locations yet</strong>
              <p>Add a shelf or box to begin tracking paper copies.</p>
            </div>
          )}
        </section>
        <section className="tag-create-card">
          <div className="tag-create-icon">
            <MapPin size={21} />
          </div>
          <h2>Add a location</h2>
          <p>Start broad, then add boxes inside shelves or cabinets.</p>
          <form onSubmit={createLocation}>
            <label>
              Name
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. Filing cabinet"
                maxLength={100}
                required
              />
            </label>
            <label>
              Inside <small>Optional</small>
              <select
                value={parent}
                onChange={(event) => setParent(event.target.value)}
              >
                <option value="">Top level</option>
                {locations.map((location) => (
                  <option key={location.id} value={location.id}>
                    {location.path.join(" / ")}
                  </option>
                ))}
              </select>
            </label>
            <Button disabled={busy}>
              <Plus size={17} /> {busy ? "Adding…" : "Add location"}
            </Button>
          </form>
          <div className="tag-tip">
            A sticker belongs to the paper copy. Moving it changes the recorded
            location without changing the sticker.
          </div>
        </section>
      </div>
    </>
  );
}
