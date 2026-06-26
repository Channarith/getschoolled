"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { login, signup, setToken, verify2faLogin, loginWithGoogle, loginWithFacebook } from "../lib/api";
import { useT } from "../lib/i18n";

function passwordProblems(pw: string, t: (k: string) => string): string[] {
  const problems: string[] = [];
  if (pw.length < 8) problems.push(t("login.pwMin8"));
  if (!/[a-zA-Z]/.test(pw)) problems.push(t("login.pwLetter"));
  if (!/[0-9]/.test(pw)) problems.push(t("login.pwNumber"));
  return problems;
}

export default function LoginPage() {
  const { t } = useT();
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [mfaToken, setMfaToken] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [oauthEmail, setOauthEmail] = useState("");

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
      const problems = passwordProblems(password, t);
      if (problems.length) {
        setError(t("login.pwMust", { rules: problems.join(", ") }));
        return;
      }
    }
    setBusy(true);
    try {
      if (mfaToken) {
        const res = await verify2faLogin(mfaToken, mfaCode);
        setToken(res.token);
        router.push("/");
        return;
      }
      const res = mode === "login"
        ? await login(email, password)
        : await signup(email, password, displayName);
      if (res.requires_2fa && res.mfa_token) {
        setMfaToken(res.mfa_token);
        return;
      }
      setToken(res.token);
      router.push("/");
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="container" style={{ maxWidth: 460 }}>
      <h1>{mode === "login" ? t("login.titleSignIn") : t("login.titleSignUp")}</h1>
      <div className="card">
        <form onSubmit={onSubmit}>
          {mode === "signup" && (
            <label style={{ display: "block", marginBottom: 8 }}>
              {t("login.name")}
              <input value={displayName} onChange={(e) => setDisplayName(e.target.value)}
                style={{ width: "100%", padding: 8 }} />
            </label>
          )}
          <label style={{ display: "block", marginBottom: 8 }}>
            {mode === "login" ? t("login.emailOrUsername") : t("login.email")}
            <input type={mode === "login" ? "text" : "email"} required value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoCapitalize="none" autoCorrect="off"
              style={{ width: "100%", padding: 8 }} />
          </label>
          <label style={{ display: "block", marginBottom: 8 }}>
            {t("login.password")}
            <span style={{ position: "relative", display: "block" }}>
              <input type={showPassword ? "text" : "password"} required value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={mode === "signup" ? 8 : undefined}
                autoCapitalize="none" autoCorrect="off"
                style={{ width: "100%", padding: 8, paddingRight: 42 }} />
              <button type="button" onClick={() => setShowPassword((s) => !s)}
                aria-label={showPassword ? t("login.hidePassword") : t("login.showPassword")}
                aria-pressed={showPassword}
                title={showPassword ? t("login.hidePassword") : t("login.showPassword")}
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
          {mfaToken && (
            <label style={{ display: "block", marginBottom: 8 }}>
              2FA code
              <input required value={mfaCode} onChange={(e) => setMfaCode(e.target.value)}
                inputMode="numeric" autoComplete="one-time-code"
                style={{ width: "100%", padding: 8 }} />
            </label>
          )}
          {mode === "signup" && (
            <p className="muted" style={{ fontSize: 12, marginTop: -2, marginBottom: 8 }}>
              {t("login.passwordHint")}
            </p>
          )}
          <button type="submit" disabled={busy}>
            {busy ? t("login.busy") : mfaToken ? "Verify 2FA" : mode === "login" ? t("login.submitSignIn") : t("login.submitSignUp")}
          </button>
        </form>
        {mode === "login" && !mfaToken && (
          <>
            <p className="muted" style={{ margin: "12px 0 8px", fontSize: 13 }}>Or continue with</p>
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <button type="button" disabled={busy} onClick={async () => {
                setBusy(true); setError("");
                try {
                  const em = oauthEmail || window.prompt("Email for sandbox Google login") || "";
                  const res = await loginWithGoogle(`sandbox_google_${em}`);
                  setToken(res.token);
                  router.push("/");
                } catch (e) { setError(String(e)); } finally { setBusy(false); }
              }}>Google</button>
              <button type="button" disabled={busy} onClick={async () => {
                setBusy(true); setError("");
                try {
                  const em = oauthEmail || window.prompt("Email for sandbox Facebook login") || "";
                  const res = await loginWithFacebook(`sandbox_facebook_${em}`);
                  setToken(res.token);
                  router.push("/");
                } catch (e) { setError(String(e)); } finally { setBusy(false); }
              }}>Facebook</button>
            </div>
            <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
              <a href="/forgot-password">Forgot password?</a>
              {" · "}
              <a href="/security">Sign-in security</a>
            </p>
          </>
        )}
        {error && <p className="muted" style={{ color: "#ff6b6b" }}>{error}</p>}
        <p className="muted" style={{ marginTop: 12 }}>
          {mode === "login" ? t("login.newHere") + " " : t("login.alreadyHave") + " "}
          <button
            onClick={() => { setMode(mode === "login" ? "signup" : "login"); setError(""); }}
            style={{ background: "none", border: "none", color: "#6ea8fe", cursor: "pointer", padding: 0 }}
          >
            {mode === "login" ? t("login.createAccount") : t("login.signInLink")}
          </button>
        </p>
      </div>
    </main>
  );
}

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
