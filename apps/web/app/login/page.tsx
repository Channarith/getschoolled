"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { login, signup, setToken } from "../lib/api";

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
    setBusy(true);
    try {
      const res = mode === "login"
        ? await login(email, password)
        : await signup(email, password, displayName);
      setToken(res.token);
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
            Email
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
              style={{ width: "100%", padding: 8 }} />
          </label>
          <label style={{ display: "block", marginBottom: 8 }}>
            Password
            <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
              style={{ width: "100%", padding: 8 }} />
          </label>
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
