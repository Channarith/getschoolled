"use client";

import Link from "next/link";
import { useState } from "react";
import { setToken, signup } from "../lib/api";
import { friendlyError } from "../lib/errors";
import styles from "./Onboarding.module.css";

type Props = {
  onDone: () => void;
};

function passwordHint(password: string): string {
  if (password.length < 8) return "At least 8 characters.";
  if (!/[a-zA-Z]/.test(password)) return "Include at least one letter.";
  if (!/[0-9]/.test(password)) return "Include at least one number.";
  return "";
}

/** New Salareen accounts are created here with email. Existing accounts log in elsewhere. */
export default function AccountStep({ onDone }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const hint = passwordHint(password);
  const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const ready = emailOk && password.length > 0 && !hint;

  async function submitEmail(event: React.FormEvent) {
    event.preventDefault();
    if (!ready || busy) return;
    setBusy(true);
    setError("");
    try {
      const trimmed = email.trim();
      const displayName = trimmed.split("@")[0].replace(/[^a-zA-Z0-9]/g, " ").trim() || trimmed;
      const result = await signup(trimmed, password, displayName);
      setToken(result.token);
      onDone();
    } catch (reason) {
      const message = String((reason as Error)?.message || reason);
      if (/already exists/i.test(message)) {
        setError("That email already has a Salareen account. Log in instead.");
      } else {
        setError(friendlyError(message.replace(/^\d{3}\s+/, ""), message));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={styles.panel}>
      <span className={styles.eyebrow}>New account</span>
      <h1>Create your account.</h1>
      <p className={styles.lede}>
        The setup assistant is for new accounts. Use your email as your username and choose a password.
      </p>
      <form onSubmit={(event) => void submitEmail(event)}>
        <label className={styles.field}>
          <span>Email</span>
          <input
            type="email"
            autoComplete="username"
            value={email}
            placeholder="you@email.com"
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <label className={styles.field}>
          <span>Password</span>
          <input
            type="password"
            autoComplete="new-password"
            value={password}
            placeholder="At least 8 characters"
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {hint && password.length > 0 && <p className={styles.note}>{hint}</p>}
        {error && <p className={styles.error} role="alert">{error}</p>}
        <div className={styles.actions}>
          <button className={styles.primary} type="submit" disabled={busy || !ready}>
            {busy ? "Creating…" : "Create account"}
          </button>
          <Link className={styles.ghost} href="/login">
            I already have an account
          </Link>
        </div>
      </form>
      <p className={styles.footnote}>
        Already on Salareen? Log in with your email, Google, Apple, or Facebook. You will not go through this assistant again.
      </p>
    </section>
  );
}
