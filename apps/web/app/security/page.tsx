"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  confirm2fa,
  disable2fa,
  getLoginHistory,
  getSecuritySummary,
  getToken,
  setup2fa,
  type LoginEvent,
} from "../lib/api";

export default function SecurityPage() {
  const [summary, setSummary] = useState<Awaited<ReturnType<typeof getSecuritySummary>> | null>(null);
  const [events, setEvents] = useState<LoginEvent[]>([]);
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  async function refresh() {
    const [sum, hist] = await Promise.all([getSecuritySummary(), getLoginHistory()]);
    setSummary(sum);
    setEvents(hist.events);
  }

  useEffect(() => {
    if (!getToken()) return;
    refresh().catch((e) => setError(String(e)));
  }, []);

  if (!getToken()) {
    return (
      <main className="container">
        <p>Please <Link href="/login">sign in</Link> to manage security.</p>
      </main>
    );
  }

  return (
    <main className="container" style={{ maxWidth: 720 }}>
      <h1>Sign-in security</h1>
      <p className="muted">Two-factor auth, passkeys, and recent sign-in locations to spot suspicious activity.</p>
      {error && <p style={{ color: "#f87171" }}>{error}</p>}
      {msg && <p className="muted">{msg}</p>}

      {summary && (
        <section className="card">
          <h2 style={{ marginTop: 0 }}>Two-factor authentication</h2>
          <p>{summary.totp_enabled ? "2FA is ON for your account." : "2FA is off — enable an authenticator app."}</p>
          {!summary.totp_enabled && !setup && (
            <button type="button" onClick={async () => {
              try { setSetup(await setup2fa()); } catch (e) { setError(String(e)); }
            }}>Set up 2FA</button>
          )}
          {setup && !summary.totp_enabled && (
            <div style={{ marginTop: 8 }}>
              <p className="muted" style={{ fontSize: 13, wordBreak: "break-all" }}>Secret: {setup.secret}</p>
              <input placeholder="6-digit code" value={code} onChange={(e) => setCode(e.target.value)}
                style={{ padding: 8, marginRight: 8 }} />
              <button type="button" onClick={async () => {
                try {
                  await confirm2fa(code);
                  setMsg("2FA enabled.");
                  setSetup(null);
                  await refresh();
                } catch (e) { setError(String(e)); }
              }}>Confirm</button>
            </div>
          )}
          {summary.totp_enabled && (
            <div style={{ marginTop: 8 }}>
              <input placeholder="Code to disable" value={code} onChange={(e) => setCode(e.target.value)}
                style={{ padding: 8, marginRight: 8 }} />
              <button type="button" onClick={async () => {
                try {
                  await disable2fa(code);
                  setMsg("2FA disabled.");
                  setCode("");
                  await refresh();
                } catch (e) { setError(String(e)); }
              }}>Disable 2FA</button>
            </div>
          )}
          <p className="muted" style={{ marginTop: 12, fontSize: 13 }}>
            Passkeys: register from the login page after signing in once. OAuth: use Google/Facebook on the login page.
          </p>
        </section>
      )}

      <section className="card" style={{ marginTop: "1rem" }}>
        <h2 style={{ marginTop: 0 }}>Recent sign-ins</h2>
        {events.length === 0 && <p className="muted">No sign-in history yet.</p>}
        <ul style={{ fontSize: 14 }}>
          {events.map((e, i) => (
            <li key={i} style={{ marginBottom: 6 }}>
              {e.success ? "✓" : "✗"} {new Date(e.ts * 1000).toLocaleString()}
              {" · "}{e.method || "password"}
              {e.ip && <> · IP {e.ip}</>}
              {e.country_hint && <> · {e.country_hint}</>}
              {e.user_agent && <div className="muted" style={{ fontSize: 12 }}>{e.user_agent}</div>}
            </li>
          ))}
        </ul>
        <Link href="/account">Back to account</Link>
      </section>
    </main>
  );
}
