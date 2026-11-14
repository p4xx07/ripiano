import { FormEvent, useEffect, useState } from "react";
import { KeyRound, Plus, RotateCcw, Trash2, UserPlus, Users } from "lucide-react";
import { People, Person, PersonGroup, request } from "./api";
import { Button, Field } from "./ui";

export default function PeoplePanel({ currentUsername }: { currentUsername: string | null }) {
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

  async function load() {
    try {
      setData(await request<People>("/api/people"));
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load people");
    }
  }

  useEffect(() => { void load(); }, []);

  async function run(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      await load();
      setNotice(message);
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function addPerson(event: FormEvent) {
    event.preventDefault();
    const added = username.trim();
    if (await run(() => request("/api/people", { method: "POST", body: JSON.stringify({ username: added, name, password, groups: newGroups, current_password: adminPassword }) }), `${added} can now sign in.`)) {
      setUsername("");
      setName("");
      setPassword("");
      setNewGroups([]);
    }
  }

  async function addGroup(event: FormEvent) {
    event.preventDefault();
    const added = groupName.trim();
    if (await run(() => request("/api/groups", { method: "POST", body: JSON.stringify({ name: added }) }), `Group ${added} created.`)) setGroupName("");
  }

  function setMembership(person: Person, group: PersonGroup, member: boolean) {
    const groups = new Set(person.groups ?? []);
    if (member) groups.add(group.id); else groups.delete(group.id);
    void run(() => request(`/api/people/${person.id}`, { method: "PATCH", body: JSON.stringify({ groups: [...groups] }) }),
      `${person.username} ${member ? "joined" : "left"} ${group.name}.`);
  }

  if (!data) return <>
    <Heading onRefresh={() => void load()} />
    {error ? <div className="inline-error" role="alert">{error}</div> : <p>Loading people…</p>}
  </>;

  return <>
    <Heading onRefresh={() => void load()} />
    {error && <div className="inline-error" role="alert">{error}</div>}
    {notice && <p className="bulk-notice" role="status">{notice}</p>}
    <div className="people-confirm">
      <Field label="Your password" hint="Needed to add people, set a password, or turn an account on or off">
        <input type="password" autoComplete="current-password" value={adminPassword} onChange={(event) => setAdminPassword(event.target.value)} />
      </Field>
    </div>
    <section className="people-section" aria-labelledby="people-heading">
      <h2 id="people-heading"><Users size={18} /> People</h2>
      <ul className="people-list">
        {data.people.map((person) => <li key={person.id} className={person.is_active ? "" : "person-off"}>
          <div className="person-head">
            <strong>{person.name || person.username}</strong>
            <small>{person.name ? `${person.username} · ` : ""}{person.is_admin ? "Admin" : "Member"}{person.is_active ? "" : " · Account off"}{person.last_login ? ` · last signed in ${new Date(person.last_login).toLocaleDateString()}` : " · never signed in"}</small>
          </div>
          {data.groups.length > 0 && <fieldset className="person-groups">
            <legend>Groups</legend>
            {data.groups.map((group) => <label key={group.id}>
              <input type="checkbox" disabled={busy} checked={(person.groups ?? []).includes(group.id)} onChange={(event) => setMembership(person, group, event.target.checked)} />
              {group.name}
            </label>)}
          </fieldset>}
          <div className="person-actions">
            {resetFor === person.id ? <form className="person-reset" onSubmit={(event) => {
              event.preventDefault();
              void run(() => request(`/api/people/${person.id}`, { method: "PATCH", body: JSON.stringify({ password: resetPassword, current_password: adminPassword }) }),
                `New password set for ${person.username}. Their other sessions and API tokens ended.`).then((ok) => { if (ok) { setResetFor(null); setResetPassword(""); } });
            }}>
              <Field label={`New password for ${person.username}`} hint="At least 12 characters">
                <input type="password" autoComplete="new-password" minLength={12} required value={resetPassword} onChange={(event) => setResetPassword(event.target.value)} />
              </Field>
              <Button disabled={busy || !adminPassword}>Set password</Button>
              <Button type="button" variant="secondary" onClick={() => { setResetFor(null); setResetPassword(""); }}>Cancel</Button>
            </form> : person.username !== currentUsername && !person.is_admin && <Button type="button" variant="secondary" disabled={busy} onClick={() => setResetFor(person.id)}><KeyRound size={15} /> Reset password</Button>}
            {person.username !== currentUsername && (confirmOffId === person.id ? <span className="note-actions">
              <Button type="button" variant="secondary" disabled={busy || !adminPassword} onClick={() => void run(
                () => request(`/api/people/${person.id}`, { method: "PATCH", body: JSON.stringify({ is_active: !person.is_active, current_password: adminPassword }) }),
                person.is_active ? `${person.username} can no longer sign in. Their documents and what they shared stay as they are.` : `${person.username} can sign in again.`,
              ).then(() => setConfirmOffId(null))}>{person.is_active ? `Confirm: turn off ${person.username}` : `Confirm: turn on ${person.username}`}</Button>
              <Button type="button" variant="secondary" onClick={() => setConfirmOffId(null)}>Cancel</Button>
            </span> : <Button type="button" variant="secondary" disabled={busy} onClick={() => setConfirmOffId(person.id)}>{person.is_active ? "Turn off account" : "Turn on account"}</Button>)}
          </div>
        </li>)}
      </ul>
      <form className="people-form" onSubmit={(event) => void addPerson(event)}>
        <h3><UserPlus size={17} /> Add a person</h3>
        <p>They get their own private archive and see only what is shared with them.</p>
        <Field label="Username"><input required maxLength={150} autoComplete="off" value={username} onChange={(event) => setUsername(event.target.value)} /></Field>
        <Field label="Name" hint="Optional"><input maxLength={150} value={name} onChange={(event) => setName(event.target.value)} /></Field>
        <Field label="Password" hint="At least 12 characters · they can add two-step sign-in later"><input type="password" required minLength={12} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} /></Field>
        {data.groups.length > 0 && <fieldset className="person-groups">
          <legend>Groups</legend>
          {data.groups.map((group) => <label key={group.id}>
            <input type="checkbox" checked={newGroups.includes(group.id)} onChange={(event) => setNewGroups((current) => event.target.checked ? [...current, group.id] : current.filter((id) => id !== group.id))} />
            {group.name}
          </label>)}
        </fieldset>}
        <Button disabled={busy || !username.trim() || password.length < 12 || !adminPassword}><Plus size={16} /> Add person</Button>
        {!adminPassword && <small>Enter your password at the top of this page first.</small>}
      </form>
    </section>
    <section className="people-section" aria-labelledby="groups-heading">
      <h2 id="groups-heading"><Users size={18} /> Groups</h2>
      <p>Share a document with a group to share it with everyone in it, now and later.</p>
      {!data.groups.length && <p>No groups yet.</p>}
      <ul className="share-list">
        {data.groups.map((group) => <li key={group.id}>
          <span><strong>{group.name}</strong> · {(group.member_ids ?? []).length} {(group.member_ids ?? []).length === 1 ? "member" : "members"}</span>
          {deleteGroupId === group.id ? <span className="note-actions">
            <button type="button" disabled={busy} onClick={() => void run(() => request(`/api/groups/${group.id}`, { method: "DELETE" }), `Group ${group.name} deleted. Documents shared only with it are private again.`).then(() => setDeleteGroupId(null))}>Confirm delete</button>
            <button type="button" disabled={busy} onClick={() => setDeleteGroupId(null)}>Cancel</button>
          </span> : <button type="button" disabled={busy} aria-label={`Delete group ${group.name}`} onClick={() => setDeleteGroupId(group.id)}><Trash2 size={15} /> Delete</button>}
        </li>)}
      </ul>
      <form className="filing-create" onSubmit={(event) => void addGroup(event)}>
        <Field label="New group name"><input placeholder="e.g. Family" maxLength={150} value={groupName} onChange={(event) => setGroupName(event.target.value)} /></Field>
        <Button variant="secondary" disabled={busy || !groupName.trim()}><Plus size={16} /> Add group</Button>
      </form>
    </section>
  </>;
}

function Heading({ onRefresh }: { onRefresh: () => void }) {
  return <div className="page-heading">
    <div>
      <div className="eyebrow"><span className="eyebrow-line" /> WHO CAN SIGN IN</div>
      <h1>People<span className="heading-period">.</span></h1>
      <p>Each person has a private archive. Share single documents with people or groups from the document itself.</p>
    </div>
    <Button type="button" variant="secondary" aria-label="Refresh" title="Refresh people" onClick={onRefresh}><RotateCcw size={16} /> <span className="refresh-label">Refresh</span></Button>
  </div>;
}
