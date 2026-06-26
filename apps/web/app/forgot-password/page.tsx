"use client";

import { useState } from "react";
import Link from "next/link";
import { forgotPassword, resetPassword } from "../lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState<"request" | "reset">("request");

  async function onRequest(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMsg("");
    try {
      const out = await forgotPassword(email);
      setMsg("If that email exists, we sent reset instructions.");
      if (out.reset_token) {
        setToken(out.reset_token);
        setStep("reset");
        setMsg("Local mode: use the reset form below with the token we returned.");
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onReset(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await resetPassword(token, password);
      setMsg("Password updated. You can sign in now.");
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="container" style={{ maxWidth: 460 }}>
      <h1>Forgot password</h1>
      <div className="card">
        {step === "request" ? (
          <form onSubmit={onRequest}>
            <label style={{ display: "block", marginBottom: 8 }}>
              Email
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                style={{ width: "100%", padding: 8 }} />
            </label>
            <button type="submit" disabled={busy}>{busy ? "…" : "Send reset link"}</button>
          </form>
        ) : (
          <form onSubmit={onReset}>
            <label style={{ display: "block", marginBottom: 8 }}>
              Reset token
              <input required value={token} onChange={(e) => setToken(e.target.value)}
                style={{ width: "100%", padding: 8 }} />
            </label>
            <label style={{ display: "block", marginBottom: 8 }}>
              New password
              <input type="password" required minLength={8} value={password}
                onChange={(e) => setPassword(e.target.value)} style={{ width: "100%", padding: 8 }} />
            </label>
            <button type="submit" disabled={busy}>{busy ? "…" : "Set new password"}</button>
          </form>
        )}
        {msg && <p className="muted" style={{ marginTop: 12 }}>{msg}</p>}
        {error && <p style={{ color: "#f87171" }}>{error}</p>}
        <p className="muted" style={{ marginTop: 12 }}>
          <Link href="/login">Back to sign in</Link>
        </p>
      </div>
    </main>
  );
}
