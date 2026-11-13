import { FormEvent, useEffect, useState } from "react";
import { Mail } from "lucide-react";
import { request } from "./api";
import { Button, Field } from "./ui";

type Send = { id: string; recipients: string; status: "queued" | "sent" | "failed"; detail: string; created_at: string };

export default function EmailDocumentPanel({ documentId, searchableReady }: { documentId: string; searchableReady: boolean }) {
  const [opened, setOpened] = useState(false);
  const [configured, setConfigured] = useState(true);
  const [sends, setSends] = useState<Send[]>([]);
  const [to, setTo] = useState("");
  const [message, setMessage] = useState("");
  const [attachment, setAttachment] = useState<"original" | "searchable">("original");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    try {
      const result = await request<{ configured: boolean; sends: Send[] }>(`/api/documents/${documentId}/email`);
      setConfigured(result.configured);
      setSends(result.sends);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load email history");
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
      setNotice("Sending now. The result appears below.");
      setTo("");
      setMessage("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not send the email");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="pages-section email-document" aria-labelledby="email-document-heading">
      <h3 id="email-document-heading"><Mail size={17} aria-hidden="true" /> Email this document</h3>
      {!opened ? (
        <Button type="button" variant="secondary" onClick={() => { setOpened(true); void load(); }}>Write an email</Button>
      ) : !configured ? (
        <p>Emailing documents is not turned on for this server. The administrator can enable it with RIPIANO_DOCUMENT_EMAIL=1 and the RIPIANO_SMTP settings. You can share a link instead.</p>
      ) : (
        <form onSubmit={send} aria-label="Email this document">
          {error && <div className="inline-error" role="alert">{error}</div>}
          {notice && <p className="bulk-notice" role="status">{notice}</p>}
          <Field label="To" hint="Up to 10 addresses, separated by commas">
            <input value={to} onChange={(event) => setTo(event.target.value)} autoCapitalize="none" inputMode="email" maxLength={500} required />
          </Field>
          <Field label="Message" hint="Optional">
            <textarea value={message} onChange={(event) => setMessage(event.target.value)} maxLength={2000} rows={3} />
          </Field>
          <Field label="Attach">
            <select value={attachment} onChange={(event) => setAttachment(event.target.value as "original" | "searchable")}>
              <option value="original">The original file</option>
              <option value="searchable" disabled={!searchableReady}>The searchable PDF{searchableReady ? "" : " (not ready yet)"}</option>
            </select>
          </Field>
          <p className="email-hint">The subject is the document title, and the message says it comes from you through Ripiano. Replies go to your account’s email address, if it has one.</p>
          <Button disabled={busy}>Send email</Button>
        </form>
      )}
      {sends.length > 0 && (
        <ul className="email-sends">
          {sends.map((item) => (
            <li key={item.id}>{item.status === "sent" ? "Sent" : item.status === "failed" ? "Not sent" : "Sending"} to {item.recipients} · {new Date(item.created_at).toLocaleString()}{item.detail ? ` · ${item.detail}` : ""}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
