import { FormEvent, useState } from "react";
import { KeyRound } from "lucide-react";
import { request } from "./api";
import { Button, Field } from "./ui";

export default function PasswordPanel() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setNotice("");
    if (next !== repeat) {
      setError("The two new passwords are different");
      return;
    }
    setBusy(true);
    try {
      await request("/api/account/password", { method: "POST", body: JSON.stringify({ current_password: current, new_password: next }) });
      setCurrent("");
      setNext("");
      setRepeat("");
      setNotice("Password changed. Your other devices and API tokens were signed out.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not change your password");
    } finally {
      setBusy(false);
    }
  }

  return <form className="password-panel" aria-labelledby="password-heading" onSubmit={(event) => void submit(event)}>
    <h2 id="password-heading"><KeyRound size={18} /> Password</h2>
    {error && <p className="inline-error" role="alert">{error}</p>}
    {notice && <p className="bulk-notice" role="status">{notice}</p>}
    <Field label="Current password"><input type="password" autoComplete="current-password" required value={current} onChange={(event) => setCurrent(event.target.value)} /></Field>
    <Field label="New password" hint="At least 12 characters"><input type="password" autoComplete="new-password" minLength={12} required value={next} onChange={(event) => setNext(event.target.value)} /></Field>
    <Field label="Repeat new password"><input type="password" autoComplete="new-password" minLength={12} required value={repeat} onChange={(event) => setRepeat(event.target.value)} /></Field>
    <Button disabled={busy || !current || next.length < 12 || !repeat}>{busy ? "Changing…" : "Change password"}</Button>
  </form>;
}
