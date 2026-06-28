"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { login, signup, setToken, verify2faLogin, loginWithGoogle, loginWithFacebook, getOnboardingStatus } from "../lib/api";
import { useT } from "../lib/i18n";
import { EyeIcon } from "../components/EyeIcon";
import { useFlag } from "../lib/flags";

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
  const signupsOpen = useFlag<boolean>("ops.new_signups", true);
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

  // ops.new_signups kill-switch: if registration is paused, force the form back to
  // sign-in so nobody can land on (or stay in) the signup view.
  useEffect(() => {
    if (!signupsOpen && mode === "signup") setMode("login");
  }, [signupsOpen, mode]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (mode === "signup" && !signupsOpen) {
      setError("New account sign-ups are temporarily paused. Please check back soon.");
      return;
    }
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
      if ("requires_2fa" in res && res.requires_2fa && "mfa_token" in res && res.mfa_token) {
        setMfaToken(res.mfa_token as string);
        return;
      }
      setToken(res.token);
      if (mode === "signup") {
        router.push("/onboarding");
      } else {
        try {
          const st = await getOnboardingStatus();
          router.push(st.completed ? "/" : "/onboarding");
        } catch {
          router.push("/");
        }
      }
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
        {signupsOpen ? (
          <p className="muted" style={{ marginTop: 12 }}>
            {mode === "login" ? t("login.newHere") + " " : t("login.alreadyHave") + " "}
            <button
              onClick={() => { setMode(mode === "login" ? "signup" : "login"); setError(""); }}
              style={{ background: "none", border: "none", color: "#6ea8fe", cursor: "pointer", padding: 0 }}
            >
              {mode === "login" ? t("login.createAccount") : t("login.signInLink")}
            </button>
          </p>
        ) : (
          <p className="muted" style={{ marginTop: 12 }}>
            New account sign-ups are temporarily paused.
          </p>
        )}
      </div>
    </main>
  );
}

