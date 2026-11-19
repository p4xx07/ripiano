import { FormEvent, useState } from "react";
import { KeyRound } from "lucide-react";
import { ApiError, isPasswordRefusal, request } from "./api";
import { Button, Field, tooShortMessage, useFieldError } from "./ui";
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
  const invalid = useFieldError<"current" | "next" | "repeat">("password-error");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setError("");
    setNotice("");
    invalid.clear();
    if (next !== repeat) {
      setError(m.mismatch);
      invalid.fail("repeat");
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
      // A wrong current password is about the first field; any other refusal (too short, too common) about the new one.
      if (isPasswordRefusal(cause)) invalid.fail("current");
      else if (cause instanceof ApiError && cause.status === 400) invalid.fail("next");
    } finally {
      setBusy(false);
    }
  }

  return <form className="password-panel" aria-labelledby="password-heading" onSubmit={(event) => void submit(event)}>
    <h2 id="password-heading"><KeyRound size={18} /> {m.heading}</h2>
    {error && <p className="inline-error" role="alert" id="password-error">{error}</p>}
    {notice && <p className="bulk-notice" role="status">{notice}</p>}
    <p className="password-warning" id="password-warning">{m.warning}</p>
    <Field label={m.current}><input type="password" autoComplete="current-password" required {...invalid.props("current")} value={current} onChange={(event) => setCurrent(event.target.value)} /></Field>
    <Field label={m.next} hint={m.nextHint}><input type="password" autoComplete="new-password" minLength={12} required {...tooShortMessage(m.tooShort)} {...invalid.props("next")} value={next} onChange={(event) => setNext(event.target.value)} /></Field>
    <Field label={m.repeat}><input type="password" autoComplete="new-password" minLength={12} required {...tooShortMessage(m.tooShort)} {...invalid.props("repeat")} value={repeat} onChange={(event) => setRepeat(event.target.value)} /></Field>
    <Button aria-describedby="password-warning" pending={busy || !current || next.length < 12 || !repeat}>{busy ? m.changing : m.change}</Button>
  </form>;
}
