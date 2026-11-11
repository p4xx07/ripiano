import { FormEvent, useCallback, useEffect, useState } from "react";
import { ArrowRight, Boxes, MapPin, Plus, ScanLine, X } from "lucide-react";
import { Location, PhysicalCopy, request } from "./api";
import { Button } from "./ui";

type Lookup = { copy: PhysicalCopy; document: { id: string; title: string } };

export default function PhysicalPanel({
  initialSticker,
  onOpenDocument,
}: {
  initialSticker: string;
  onOpenDocument: (id: string) => void;
}) {
  const [locations, setLocations] = useState<Location[]>([]);
  const [name, setName] = useState("");
  const [parent, setParent] = useState("");
  const [code, setCode] = useState(initialSticker);
  const [found, setFound] = useState<Lookup | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

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
    if (initialSticker) void findSticker(initialSticker);
  }, [initialSticker]);

  async function findSticker(value: string) {
    setError("");
    setFound(null);
    try {
      setFound(
        await request<Lookup>(
          `/api/stickers/${encodeURIComponent(value.trim())}`,
        ),
      );
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
          <p>Give paper a place, then find it by its sticker.</p>
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
            <p>Scan the QR code or type the code printed on a paper copy.</p>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void findSticker(code);
              }}
            >
              <input
                value={code}
                onChange={(event) => setCode(event.target.value.toUpperCase())}
                placeholder="R-XXXXXXXX"
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
                  <span>{location.path.join(" / ")}</span>
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
