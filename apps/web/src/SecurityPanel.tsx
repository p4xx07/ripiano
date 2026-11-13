import { FormEvent, useCallback, useEffect, useState } from "react";
import { KeyRound, ShieldCheck, X } from "lucide-react";
import { request } from "./api";
import { Button, Field } from "./ui";
import TokensPanel from "./TokensPanel";
import PasswordPanel from "./PasswordPanel";

type Status = { two_factor: boolean; recovery_remaining: number };
type Setup = { secret: string; uri: string; qr_svg: string };

export default function SecurityPanel() {
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
      setError(cause instanceof Error ? cause.message : "Could not load security settings");
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "That did not work");
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
      setNotice("Two-step sign-in is on. Save the recovery codes below before you leave this page.");
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
          <div className="eyebrow"><span className="eyebrow-line" /> YOUR ACCOUNT</div>
          <h1>Security<span className="heading-period">.</span></h1>
          <p>Protect your archive with a second step when you sign in.</p>
        </div>
      </div>
      {error && <div className="inline-error" role="alert">{error}<button onClick={() => setError("")} aria-label="Dismiss error"><X size={16} /></button></div>}
      {notice && <p className="bulk-notice" role="status">{notice}</p>}
      <div className="agent-layout">
        <section className="agent-main">
          <article className="agent-card mail-card">
            <span className="agent-avatar"><ShieldCheck size={21} aria-hidden="true" /></span>
            <div className="agent-card-body">
              <strong>Two-step sign-in is {status?.two_factor ? "on" : "off"}</strong>
              <span>{status?.two_factor
                ? `After your password, Ripiano asks for a code from your authenticator app. ${status.recovery_remaining} recovery code${status.recovery_remaining === 1 ? "" : "s"} left.`
                : "Use any authenticator app (for example the one built into your password manager). Agent tokens are not affected."}</span>
            </div>
          </article>
          <TokensPanel />
          <PasswordPanel />
          {recovery.length > 0 && (
            <div className="agent-token-card security-recovery">
              <div className="agent-token-head"><KeyRound size={19} aria-hidden="true" /><strong>Recovery codes</strong></div>
              <p>Each works once if you lose your phone. Store them somewhere safe; they will not be shown again.</p>
              <ol>{recovery.map((item) => <li key={item}><code>{item}</code></li>)}</ol>
            </div>
          )}
        </section>
        <section className="tag-create-card agent-create-card">
          {!status?.two_factor && !setup && (
            <form onSubmit={begin} aria-label="Turn on two-step sign-in">
              <h2>Turn on two-step sign-in</h2>
              <Field label="Your password"><input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></Field>
              <Button disabled={busy}>Continue</Button>
            </form>
          )}
          {setup && (
            <form onSubmit={confirm} aria-label="Confirm authenticator">
              <h2>Scan with your authenticator</h2>
              <div className="security-qr" role="img" aria-label="QR code for your authenticator app" dangerouslySetInnerHTML={{ __html: setup.qr_svg }} />
              <p>Can’t scan? Enter this key: <code className="security-secret">{setup.secret}</code></p>
              <Field label="Code from the app"><input autoComplete="one-time-code" inputMode="numeric" value={code} onChange={(event) => setCode(event.target.value.replace(/\s/g, ""))} maxLength={7} required /></Field>
              <Button disabled={busy}>Turn on</Button>
              <Button type="button" variant="secondary" onClick={() => setSetup(null)}>Cancel</Button>
            </form>
          )}
          {status?.two_factor && (
            <>
              <form onSubmit={confirmed("/api/account/security/recovery-codes", "New recovery codes created. The old ones no longer work.")} aria-label="New recovery codes">
                <h2>Confirm it’s you</h2>
                <Field label="Your password"><input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></Field>
                <Field label="Authenticator or recovery code"><input autoComplete="one-time-code" value={code} onChange={(event) => setCode(event.target.value)} maxLength={32} required /></Field>
                <Button disabled={busy}>Create new recovery codes</Button>
                <Button type="button" variant="danger" disabled={busy || !password || !code}
                  onClick={(event) => { event.preventDefault(); confirmed("/api/account/security/disable", "Two-step sign-in is off.")(event as unknown as FormEvent); }}>
                  Turn off two-step sign-in
                </Button>
              </form>
            </>
          )}
        </section>
      </div>
    </>
  );
}
