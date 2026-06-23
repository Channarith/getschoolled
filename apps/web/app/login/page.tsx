"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { applyAdmin, login, signup, setToken } from "../lib/api";

// Mirror of aoep_shared.passwords policy for inline (pre-submit) feedback; the
// identity service is the authoritative enforcer.
function passwordProblems(pw: string): string[] {
  const problems: string[] = [];
  if (pw.length < 8) problems.push("at least 8 characters");
  if (!/[a-zA-Z]/.test(pw)) problems.push("at least one letter");
  if (!/[0-9]/.test(pw)) problems.push("at least one number");
  return problems;
}

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Honor ?mode=signup&email=... from the home landing "Get Started" flow.
  // Read from window (not useSearchParams) to avoid a Suspense boundary at build.
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    if (p.get("mode") === "signup") setMode("signup");
    const em = p.get("email");
    if (em) setEmail(em);
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (mode === "signup") {
      const problems = passwordProblems(password);
      if (problems.length) {
        setError("Password must have " + problems.join(", ") + ".");
        return;
      }
    }
    setBusy(true);
    try {
      const res = mode === "login"
        ? await login(email, password)
        : await signup(email, password, displayName);
      setToken(res.token);
      // Admins (e.g. the seeded default account) unlock operator surfaces.
      applyAdmin(Boolean(res.account?.is_admin));
      // Land on the Netflix-style home feed (popular / category / age) on login.
      router.push("/");
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="container" style={{ maxWidth: 460 }}>
      <h1>{mode === "login" ? "Sign in" : "Create your account"}</h1>
      <div className="card">
        <form onSubmit={onSubmit}>
          {mode === "signup" && (
            <label style={{ display: "block", marginBottom: 8 }}>
              Name
              <input value={displayName} onChange={(e) => setDisplayName(e.target.value)}
                style={{ width: "100%", padding: 8 }} />
            </label>
          )}
          <label style={{ display: "block", marginBottom: 8 }}>
            {mode === "login" ? "Email or username" : "Email"}
            <input type={mode === "login" ? "text" : "email"} required value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoCapitalize="none" autoCorrect="off"
              style={{ width: "100%", padding: 8 }} />
          </label>
          <label style={{ display: "block", marginBottom: 8 }}>
            Password
            <span style={{ position: "relative", display: "block" }}>
              <input type={showPassword ? "text" : "password"} required value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={mode === "signup" ? 8 : undefined}
                autoCapitalize="none" autoCorrect="off"
                style={{ width: "100%", padding: 8, paddingRight: 42 }} />
              <button type="button" onClick={() => setShowPassword((s) => !s)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                aria-pressed={showPassword}
                title={showPassword ? "Hide password" : "Show password"}
                style={{
                  position: "absolute", right: 4, top: 0, bottom: 0,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  width: 34, background: "none", border: "none", padding: 0,
                  cursor: "pointer", color: "#9aa4b2",
                }}>
                <EyeIcon off={showPassword} />
              </button>
            </span>
          </label>
          {mode === "signup" && (
            <p className="muted" style={{ fontSize: 12, marginTop: -2, marginBottom: 8 }}>
              At least 8 characters, with a letter and a number.
            </p>
          )}
          <button type="submit" disabled={busy}>
            {busy ? "..." : mode === "login" ? "Sign in" : "Sign up"}
          </button>
        </form>
        {error && <p className="muted" style={{ color: "#ff6b6b" }}>{error}</p>}
        <p className="muted" style={{ marginTop: 12 }}>
          {mode === "login" ? "New here? " : "Already have an account? "}
          <button
            onClick={() => { setMode(mode === "login" ? "signup" : "login"); setError(""); }}
            style={{ background: "none", border: "none", color: "#6ea8fe", cursor: "pointer", padding: 0 }}
          >
            {mode === "login" ? "Create an account" : "Sign in"}
          </button>
        </p>
      </div>
    </main>
  );
}

// Eye / eye-off glyph (inline SVG, no icon dependency). `off` shows the slashed
// variant used while the password is visible (click to hide).
function EyeIcon({ off }: { off: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true" focusable="false">
      {off ? (
        <>
          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
          <line x1="1" y1="1" x2="23" y2="23" />
        </>
      ) : (
        <>
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
          <circle cx="12" cy="12" r="3" />
        </>
      )}
    </svg>
  );
}
