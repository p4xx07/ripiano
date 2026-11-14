import { FormEvent, useState } from "react";
import { KeyRound } from "lucide-react";
import { request } from "./api";
import { Button, Field } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/PasswordPanel";

export default function PasswordPanel() {
  const m = useMessages(messages);
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
      setError(m.mismatch);
      return;
    }
    setBusy(true);
    try {
      await request("/api/account/password", { method: "POST", body: JSON.stringify({ current_password: current, new_password: next }) });
      setCurrent("");
      setNext("");
      setRepeat("");
      setNotice(m.changed);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.changeError);
    } finally {
      setBusy(false);
    }
  }

  return <form className="password-panel" aria-labelledby="password-heading" onSubmit={(event) => void submit(event)}>
    <h2 id="password-heading"><KeyRound size={18} /> {m.heading}</h2>
    {error && <p className="inline-error" role="alert">{error}</p>}
    {notice && <p className="bulk-notice" role="status">{notice}</p>}
    <Field label={m.current}><input type="password" autoComplete="current-password" required value={current} onChange={(event) => setCurrent(event.target.value)} /></Field>
    <Field label={m.next} hint={m.nextHint}><input type="password" autoComplete="new-password" minLength={12} required value={next} onChange={(event) => setNext(event.target.value)} /></Field>
    <Field label={m.repeat}><input type="password" autoComplete="new-password" minLength={12} required value={repeat} onChange={(event) => setRepeat(event.target.value)} /></Field>
    <Button disabled={busy || !current || next.length < 12 || !repeat}>{busy ? m.changing : m.change}</Button>
  </form>;
}
