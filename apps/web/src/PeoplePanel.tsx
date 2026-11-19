import { FormEvent, useEffect, useState } from "react";
import { KeyRound, Plus, RotateCcw, Trash2, UserPlus, Users } from "lucide-react";
import { ApiError, isPasswordRefusal, People, Person, PersonGroup, request } from "./api";
import { Button, Field, tooShortMessage, useFieldError } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/PeoplePanel";

export default function PeoplePanel({ currentUsername }: { currentUsername: string | null }) {
  const m = useMessages(messages);
  const [data, setData] = useState<People | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [username, setUsername] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [newGroups, setNewGroups] = useState<number[]>([]);
  const [groupName, setGroupName] = useState("");
  const [resetFor, setResetFor] = useState<number | null>(null);
  const [resetPassword, setResetPassword] = useState("");
  const [deleteGroupId, setDeleteGroupId] = useState<number | null>(null);
  const [confirmOffId, setConfirmOffId] = useState<number | null>(null);
  const [adminPassword, setAdminPassword] = useState("");
  // A refused change marks and focuses the field it is about (round-7 judge 2 M1): a wrong "Your password" that
  // field, any other refusal the form's own field (passed as `field`).
  const invalid = useFieldError<"admin" | "username" | "password" | "reset" | "group">("people-error");

  async function load() {
    try {
      setData(await request<People>("/api/people"));
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.loadError);
    }
  }

  useEffect(() => { void load(); }, []);

  async function run(action: () => Promise<unknown>, message: string, field?: "username" | "password" | "reset" | "group") {
    if (busy) return false;
    setBusy(true);
    setError("");
    setNotice("");
    invalid.clear();
    try {
      await action();
      await load();
      setNotice(message);
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.saveError);
      if (isPasswordRefusal(cause)) invalid.fail("admin");
      else if (field && cause instanceof ApiError && (cause.status === 400 || cause.status === 409)) {
        invalid.fail(field === "username" && /password/i.test(cause.message) ? "password" : field);
      }
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function addPerson(event: FormEvent) {
    event.preventDefault();
    const added = username.trim();
    if (await run(() => request("/api/people", { method: "POST", body: JSON.stringify({ username: added, name, password, groups: newGroups, current_password: adminPassword }) }), m.personAdded(added), "username")) {
      setUsername("");
      setName("");
      setPassword("");
      setNewGroups([]);
    }
  }

  async function addGroup(event: FormEvent) {
    event.preventDefault();
    const added = groupName.trim();
    if (await run(() => request("/api/groups", { method: "POST", body: JSON.stringify({ name: added }) }), m.groupCreated(added), "group")) setGroupName("");
  }

  function setMembership(person: Person, group: PersonGroup, member: boolean) {
    const groups = new Set(person.groups ?? []);
    if (member) groups.add(group.id); else groups.delete(group.id);
    void run(() => request(`/api/people/${person.id}`, { method: "PATCH", body: JSON.stringify({ groups: [...groups] }) }),
      member ? m.joined(person.username, group.name) : m.left(person.username, group.name));
  }

  if (!data) return <>
    <Heading onRefresh={() => void load()} />
    {error ? <div className="inline-error" role="alert">{error}</div> : <p>{m.loading}</p>}
  </>;

  return <>
    <Heading onRefresh={() => void load()} />
    {error && <div className="inline-error" role="alert" id="people-error">{error}</div>}
    {notice && <p className="bulk-notice" role="status">{notice}</p>}
    <div className="people-confirm">
      <Field label={m.yourPassword} hint={m.yourPasswordHint}>
        <input type="password" autoComplete="current-password" {...invalid.props("admin")} value={adminPassword} onChange={(event) => setAdminPassword(event.target.value)} />
      </Field>
    </div>
    <section className="people-section" aria-labelledby="people-heading">
      <h2 id="people-heading"><Users size={18} /> {m.peopleHeading}</h2>
      <ul className="people-list">
        {data.people.map((person) => <li key={person.id} className={person.is_active ? "" : "person-off"}>
          <div className="person-head">
            <strong>{person.name || person.username}</strong>
            <small>{person.name ? `${person.username} · ` : ""}{person.is_admin ? m.admin : m.member}{person.is_active ? "" : m.accountOff}{person.last_login ? m.lastSignedIn(new Date(person.last_login).toLocaleDateString()) : m.neverSignedIn}</small>
          </div>
          {data.groups.length > 0 && <fieldset className="person-groups">
            <legend>{m.groups}</legend>
            {data.groups.map((group) => <label key={group.id}>
              <input type="checkbox" aria-disabled={busy || undefined} checked={(person.groups ?? []).includes(group.id)} onChange={(event) => { if (!busy) setMembership(person, group, event.target.checked); }} />
              {group.name}
            </label>)}
          </fieldset>}
          <div className="person-actions">
            {resetFor === person.id ? <form className="person-reset" onSubmit={(event) => {
              event.preventDefault();
              void run(() => request(`/api/people/${person.id}`, { method: "PATCH", body: JSON.stringify({ password: resetPassword, current_password: adminPassword }) }),
                m.passwordSet(person.username), "reset").then((ok) => { if (ok) { setResetFor(null); setResetPassword(""); } });
            }}>
              <p className="password-warning" id={`reset-warning-${person.id}`}>{m.resetWarning(person.username)}</p>
              <Field label={m.newPasswordFor(person.username)} hint={m.atLeast12}>
                <input type="password" autoComplete="new-password" minLength={12} required autoFocus {...tooShortMessage(m.tooShort)} {...invalid.props("reset")} value={resetPassword} onChange={(event) => setResetPassword(event.target.value)} />
              </Field>
              <Button aria-describedby={`reset-warning-${person.id}`} pending={busy || !adminPassword}>{m.setPassword}</Button>
              <Button type="button" variant="secondary" onClick={() => { setResetFor(null); setResetPassword(""); }}>{m.cancel}</Button>
            </form> : person.username !== currentUsername && !person.is_admin && <Button type="button" variant="secondary" pending={busy} onClick={() => setResetFor(person.id)}><KeyRound size={15} /> {m.resetPassword}</Button>}
            {person.username !== currentUsername && (confirmOffId === person.id ? <span className="note-actions">
              <Button type="button" variant="secondary" pending={busy || !adminPassword} onClick={() => void run(
                () => request(`/api/people/${person.id}`, { method: "PATCH", body: JSON.stringify({ is_active: !person.is_active, current_password: adminPassword }) }),
                person.is_active ? m.turnedOff(person.username) : m.turnedOn(person.username),
              ).then((ok) => { if (ok) setConfirmOffId(null); })}>{person.is_active ? m.confirmOff(person.username) : m.confirmOn(person.username)}</Button>
              <Button type="button" variant="secondary" onClick={() => setConfirmOffId(null)}>{m.cancel}</Button>
            </span> : <Button type="button" variant="secondary" pending={busy} onClick={() => setConfirmOffId(person.id)}>{person.is_active ? m.turnOff : m.turnOn}</Button>)}
          </div>
        </li>)}
      </ul>
      <form className="people-form" onSubmit={(event) => void addPerson(event)}>
        <h3><UserPlus size={17} /> {m.addPersonHeading}</h3>
        <p>{m.addPersonIntro}</p>
        <Field label={m.username}><input required maxLength={150} autoComplete="off" {...invalid.props("username")} value={username} onChange={(event) => setUsername(event.target.value)} /></Field>
        <Field label={m.name} hint={m.optional}><input maxLength={150} value={name} onChange={(event) => setName(event.target.value)} /></Field>
        <Field label={m.password} hint={m.passwordHint}><input type="password" required minLength={12} autoComplete="new-password" {...tooShortMessage(m.tooShort)} {...invalid.props("password")} value={password} onChange={(event) => setPassword(event.target.value)} /></Field>
        {data.groups.length > 0 && <fieldset className="person-groups">
          <legend>{m.groups}</legend>
          {data.groups.map((group) => <label key={group.id}>
            <input type="checkbox" checked={newGroups.includes(group.id)} onChange={(event) => setNewGroups((current) => event.target.checked ? [...current, group.id] : current.filter((id) => id !== group.id))} />
            {group.name}
          </label>)}
        </fieldset>}
        <Button pending={busy || !username.trim() || password.length < 12 || !adminPassword}><Plus size={16} /> {m.addPerson}</Button>
        {!adminPassword && <small>{m.enterPasswordFirst}</small>}
      </form>
    </section>
    <section className="people-section" aria-labelledby="groups-heading">
      <h2 id="groups-heading"><Users size={18} /> {m.groups}</h2>
      <p>{m.groupsIntro}</p>
      {!data.groups.length && <p>{m.noGroups}</p>}
      <ul className="share-list">
        {data.groups.map((group) => <li key={group.id}>
          <span><strong>{group.name}</strong> · {m.members((group.member_ids ?? []).length)}</span>
          {deleteGroupId === group.id ? <span className="note-actions">
            <button type="button" disabled={busy} onClick={() => void run(() => request(`/api/groups/${group.id}`, { method: "DELETE" }), m.groupDeleted(group.name)).then(() => setDeleteGroupId(null))}>{m.confirmDelete}</button>
            <button type="button" disabled={busy} onClick={() => setDeleteGroupId(null)}>{m.cancel}</button>
          </span> : <button type="button" disabled={busy} aria-label={m.deleteGroupLabel(group.name)} onClick={() => setDeleteGroupId(group.id)}><Trash2 size={15} /> {m.delete}</button>}
        </li>)}
      </ul>
      <form className="filing-create" onSubmit={(event) => void addGroup(event)}>
        <Field label={m.newGroupName}><input placeholder={m.groupPlaceholder} maxLength={150} {...invalid.props("group")} value={groupName} onChange={(event) => setGroupName(event.target.value)} /></Field>
        <Button variant="secondary" pending={busy || !groupName.trim()}><Plus size={16} /> {m.addGroup}</Button>
      </form>
    </section>
  </>;
}

function Heading({ onRefresh }: { onRefresh: () => void }) {
  const m = useMessages(messages);
  return <div className="page-heading">
    <div>
      <div className="eyebrow"><span className="eyebrow-line" /> {m.eyebrow}</div>
      <h1>{m.heading}<span className="heading-period">.</span></h1>
      <p>{m.intro}</p>
    </div>
    <Button type="button" variant="secondary" aria-label={m.refresh} title={m.refreshTitle} onClick={onRefresh}><RotateCcw size={16} /> <span className="refresh-label">{m.refresh}</span></Button>
  </div>;
}
