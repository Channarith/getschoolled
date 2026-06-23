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
            <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
              minLength={mode === "signup" ? 8 : undefined}
              style={{ width: "100%", padding: 8 }} />
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
