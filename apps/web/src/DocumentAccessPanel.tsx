import { useEffect, useState } from "react";
import { UserMinus, Users } from "lucide-react";
import { People, Session, request } from "./api";
import { Button, Field } from "./ui";

type Grant = {
  id: string;
  level: "view" | "edit";
  target: { kind: "person" | "group"; id: number; name: string; active: boolean };
};

type Wording = { heading: string; intro: string; empty: string; editLabel: string; removed: string; granted: string };
const documentWording: Wording = {
  heading: "People with access",
  intro: "Share this document with people who sign in to this Ripiano. They see it under Shared with me. Filing, files, links, and Trash stay with you.",
  empty: "Only you can open this document.",
  editLabel: "Can edit details",
  removed: "can no longer open this document.",
  granted: "view and edit details",
};

/** Who may open a document, or (with endpoint and wording) use a tag, sender, type, or saved view. */
export type { Wording };
export default function DocumentAccessPanel({ documentId, endpoint, wording = documentWording, startOpen = false }: { documentId?: string; endpoint?: string; wording?: Wording; startOpen?: boolean }) {
  const base = endpoint ?? `/api/documents/${documentId}/access`;
  const levelLabel = { view: "Can view", edit: wording.editLabel };
  const [opened, setOpened] = useState(startOpen);
  const [loaded, setLoaded] = useState(false);
  const [grants, setGrants] = useState<Grant[]>([]);
  const [directory, setDirectory] = useState<People | null>(null);
  const [ownerName, setOwnerName] = useState<string | null>(null);
  const [target, setTarget] = useState("");
  const [level, setLevel] = useState<Grant["level"]>("view");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    try {
      const [access, people, session] = await Promise.all([
        request<{ grants: Grant[] }>(base),
        request<People>("/api/people"),
        request<Session>("/api/session"),
      ]);
      setOwnerName(session.username);
      setGrants(access.grants);
      setDirectory(people);
      setLoaded(true);
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load who can open this document");
    }
  }

  useEffect(() => {
    if (startOpen) void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function run(action: () => Promise<unknown>, message: string): Promise<boolean> {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      const access = await request<{ grants: Grant[] }>(base);
      setGrants(access.grants);
      setNotice(message);
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not change access");
      return false;
    } finally {
      setBusy(false);
    }
  }

  function add() {
    const [kind, raw] = target.split(":");
    const id = Number(raw);
    if (!id) return;
    const label = kind === "group"
      ? directory?.groups.find((group) => group.id === id)?.name
      : directory?.people.find((person) => person.id === id)?.username;
    void run(() => request(base, {
      method: "POST",
      body: JSON.stringify({ [kind === "group" ? "group_id" : "user_id"]: id, level }),
    }), `${label ?? "They"} ${kind === "group" ? "members " : ""}can now ${level === "edit" ? wording.granted : "view"}.`).then((ok) => { if (ok) setTarget(""); });
  }

  const people = (directory?.people ?? []).filter((person) => person.username !== ownerName && person.is_active !== false);
  const groups = directory?.groups ?? [];

  return <section className="share-panel access-panel" aria-labelledby="access-heading">
    <h3 id="access-heading"><Users size={17} /> {wording.heading}</h3>
    <p>{wording.intro}</p>
    <details open={opened} onToggle={(event) => {
      const next = event.currentTarget.open;
      setOpened(next);
      if (next && !loaded) void load();
    }}>
      <summary>Manage access</summary>
      <div className="share-body">
        {error && <p className="inline-error" role="alert">{error}</p>}
        {notice && <p className="bulk-notice" role="status">{notice}</p>}
        {!loaded && !error && <p>Loading…</p>}
        {loaded && <>
          {people.length + groups.length === 0 ? <p>No one else has an account yet. An admin can add people under People.</p> : <div className="share-controls">
            <Field label="Person or group">
              <select value={target} onChange={(event) => setTarget(event.target.value)} disabled={busy}>
                <option value="">Choose…</option>
                {people.length > 0 && <optgroup label="People">
                  {people.map((person) => <option key={person.id} value={`person:${person.id}`}>{person.name ? `${person.name} (${person.username})` : person.username}</option>)}
                </optgroup>}
                {groups.length > 0 && <optgroup label="Groups">
                  {groups.map((group) => <option key={group.id} value={`group:${group.id}`}>{group.name}</option>)}
                </optgroup>}
              </select>
            </Field>
            <Field label="Access">
              <select value={level} onChange={(event) => setLevel(event.target.value as Grant["level"])} disabled={busy}>
                <option value="view">Can view</option>
                <option value="edit">{wording.editLabel}</option>
              </select>
            </Field>
            <Button type="button" disabled={busy || !target} onClick={add}>Share</Button>
          </div>}
          {!grants.length && <p>{wording.empty}</p>}
          {grants.length > 0 && <ul className="share-list">
            {grants.map((grant) => <li key={grant.id}>
              <span>
                <strong>{grant.target.name}</strong>{grant.target.kind === "group" ? " · group" : ""}{!grant.target.active ? " · account off" : ""}
              </span>
              <span className="access-actions">
                <select aria-label={`Access for ${grant.target.name}`} value={grant.level} disabled={busy} onChange={(event) => {
                  const next = event.target.value as Grant["level"];
                  void run(() => request(`${base}/${grant.id}`, { method: "PATCH", body: JSON.stringify({ level: next }) }), `${grant.target.name}: ${levelLabel[next]}.`);
                }}>
                  <option value="view">Can view</option>
                  <option value="edit">{wording.editLabel}</option>
                </select>
                <button type="button" disabled={busy} aria-label={`Remove access for ${grant.target.name}`} onClick={() => void run(() => request(`${base}/${grant.id}`, { method: "DELETE" }), `${grant.target.name} ${wording.removed}`)}>
                  <UserMinus size={15} /> Remove
                </button>
              </span>
            </li>)}
          </ul>}
        </>}
      </div>
    </details>
  </section>;
}
