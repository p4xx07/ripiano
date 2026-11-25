import { FormEvent, useEffect, useState } from "react";
import { Mail } from "lucide-react";
import { request } from "./api";
import { Button, Field, Segmented, type SegmentedOption } from "./ui";
import { useMessages } from "./i18n";
import messages from "./locales/EmailDocumentPanel";

type Send = { id: string; recipients: string; status: "queued" | "sent" | "failed"; detail: string; created_at: string };

export default function EmailDocumentPanel({ documentId, searchableReady }: { documentId: string; searchableReady: boolean }) {
  const m = useMessages(messages);
  const [opened, setOpened] = useState(false);
  const [configured, setConfigured] = useState(true);
  const [fromEmail, setFromEmail] = useState("");
  const [sends, setSends] = useState<Send[]>([]);
  const [to, setTo] = useState("");
  const [message, setMessage] = useState("");
  const [attachment, setAttachment] = useState<"original" | "searchable">("original");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    try {
      const result = await request<{ configured: boolean; from_email: string; sends: Send[] }>(`/api/documents/${documentId}/email`);
      setConfigured(result.configured);
      setFromEmail(result.from_email);
      setSends(result.sends);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.loadError);
    }
  }

  const [polls, setPolls] = useState(0);
  useEffect(() => {
    if (!sends.some((item) => item.status === "queued") || polls > 30) return;
    setPolls((value) => value + 1);
    const timer = window.setTimeout(() => void load(), 2000);
    return () => window.clearTimeout(timer);
  }, [sends]);

  async function send(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await request(`/api/documents/${documentId}/email`, { method: "POST", body: JSON.stringify({ to, message, attachment }) });
      setNotice(m.sendingNow);
      setTo("");
      setMessage("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.sendError);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="pages-section email-document" aria-labelledby="email-document-heading">
      <h3 id="email-document-heading"><Mail size={17} aria-hidden="true" /> {m.heading}</h3>
      {!opened ? (
        <Button type="button" variant="secondary" onClick={() => { setOpened(true); void load(); }}>{m.write}</Button>
      ) : !configured ? (
        <p>{m.notConfigured}</p>
      ) : (
        <form onSubmit={send} aria-label={m.formLabel}>
          {error && <div className="inline-error" role="alert">{error}</div>}
          {notice && <p className="bulk-notice" role="status">{notice}</p>}
          {fromEmail && <p className="email-from">{m.from}: <strong>{fromEmail}</strong></p>}
          <Field label={m.to} hint={m.toHint} className="detail-label">
            <input value={to} onChange={(event) => setTo(event.target.value)} autoCapitalize="none" inputMode="email" maxLength={500} required />
          </Field>
          <Field label={m.message} hint={m.optional} className="detail-label">
            <textarea value={message} onChange={(event) => setMessage(event.target.value)} maxLength={2000} rows={3} />
          </Field>
          <Segmented label={m.attach} className="detail-label" value={attachment} onChange={setAttachment} options={[
            { value: "original", label: m.original },
            { value: "searchable", label: `${m.searchable}${searchableReady ? "" : m.notReadyYet}`, disabled: !searchableReady },
          ] satisfies SegmentedOption<"original" | "searchable">[]} />
          <p className="email-hint">{m.hint}</p>
          <Button disabled={busy}>{m.send}</Button>
        </form>
      )}
      {sends.length > 0 && (
        <ul className="email-sends">
          {sends.map((item) => (
            <li key={item.id}>{m.sendStatus(item.status, item.recipients)} · {new Date(item.created_at).toLocaleString()}{item.detail ? ` · ${item.detail}` : ""}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
