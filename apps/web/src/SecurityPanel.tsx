import { FormEvent, useCallback, useEffect, useState } from "react";
import { KeyRound, ShieldCheck, X } from "lucide-react";
import { request } from "./api";
import { Button, Field } from "./ui";
import TokensPanel from "./TokensPanel";
import PasswordPanel from "./PasswordPanel";
import { useMessages } from "./i18n";
import messages from "./locales/SecurityPanel";

type Status = { two_factor: boolean; recovery_remaining: number };
type Setup = { secret: string; uri: string; qr_svg: string };

export default function SecurityPanel() {
  const m = useMessages(messages);
  const [status, setStatus] = useState<Status | null>(null);
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [setup, setSetup] = useState<Setup | null>(null);
  const [recovery, setRecovery] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    try {
      setStatus(await request<Status>("/api/account/security"));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.loadError);
    }
  }, [m]);
  useEffect(() => { void load(); }, [load]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : m.genericError);
    } finally {
      setBusy(false);
    }
  }

  function begin(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      setSetup(await request<Setup>("/api/account/security/setup", { method: "POST", body: JSON.stringify({ password }) }));
      setPassword("");
    });
  }

  function confirm(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      const result = await request<Status & { recovery_codes: string[] }>("/api/account/security/enable", { method: "POST", body: JSON.stringify({ code }) });
      setRecovery(result.recovery_codes);
      setStatus(result);
      setSetup(null);
      setCode("");
      setNotice(m.enabledNotice);
    });
  }

  function confirmed(path: string, message: string) {
    return (event: FormEvent) => {
      event.preventDefault();
      void run(async () => {
        const result = await request<Status & { recovery_codes?: string[] }>(path, { method: "POST", body: JSON.stringify({ password, code }) });
        setStatus(result);
        setRecovery(result.recovery_codes ?? []);
        setPassword("");
        setCode("");
        setNotice(message);
      });
    };
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> {m.eyebrow}</div>
          <h1>{m.heading}<span className="heading-period">.</span></h1>
          <p>{m.intro}</p>
        </div>
      </div>
      {error && <div className="inline-error" role="alert">{error}<button onClick={() => setError("")} aria-label={m.dismissError}><X size={16} /></button></div>}
      {notice && <p className="bulk-notice" role="status">{notice}</p>}
      <div className="agent-layout">
        <section className="agent-main">
          <article className="agent-card mail-card">
            <span className="agent-avatar"><ShieldCheck size={21} aria-hidden="true" /></span>
            <div className="agent-card-body">
              <strong>{m.status(!!status?.two_factor)}</strong>
              <span>{status?.two_factor
                ? m.onDetail(status.recovery_remaining)
                : m.offDetail}</span>
            </div>
          </article>
          <TokensPanel />
          <PasswordPanel />
          {recovery.length > 0 && (
            <div className="agent-token-card security-recovery">
              <div className="agent-token-head"><KeyRound size={19} aria-hidden="true" /><strong>{m.recoveryHeading}</strong></div>
              <p>{m.recoveryText}</p>
              <ol>{recovery.map((item) => <li key={item}><code>{item}</code></li>)}</ol>
            </div>
          )}
        </section>
        <section className="tag-create-card agent-create-card">
          {!status?.two_factor && !setup && (
            <form onSubmit={begin} aria-label={m.turnOnHeading}>
              <h2>{m.turnOnHeading}</h2>
              <Field label={m.yourPassword}><input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></Field>
              <Button disabled={busy}>{m.continue}</Button>
            </form>
          )}
          {setup && (
            <form onSubmit={confirm} aria-label={m.confirmAuthenticator}>
              <h2>{m.scanHeading}</h2>
              <div className="security-qr" role="img" aria-label={m.qrLabel} dangerouslySetInnerHTML={{ __html: setup.qr_svg }} />
              <p>{m.cantScan} <code className="security-secret">{setup.secret}</code></p>
              <Field label={m.appCode}><input autoComplete="one-time-code" inputMode="numeric" value={code} onChange={(event) => setCode(event.target.value.replace(/\s/g, ""))} maxLength={7} required /></Field>
              <Button disabled={busy}>{m.turnOn}</Button>
              <Button type="button" variant="secondary" onClick={() => setSetup(null)}>{m.cancel}</Button>
            </form>
          )}
          {status?.two_factor && (
            <>
              <form onSubmit={confirmed("/api/account/security/recovery-codes", m.newCodesNotice)} aria-label={m.newCodesLabel}>
                <h2>{m.confirmHeading}</h2>
                <Field label={m.yourPassword}><input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></Field>
                <Field label={m.codeLabel}><input autoComplete="one-time-code" value={code} onChange={(event) => setCode(event.target.value)} maxLength={32} required /></Field>
                <Button disabled={busy}>{m.createCodes}</Button>
                <Button type="button" variant="danger" disabled={busy || !password || !code}
                  onClick={(event) => { event.preventDefault(); confirmed("/api/account/security/disable", m.disabledNotice)(event as unknown as FormEvent); }}>
                  {m.turnOff}
                </Button>
              </form>
            </>
          )}
        </section>
      </div>
    </>
  );
}
