"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getOAuthProviderStatus,
  getOnboardingStatus,
  login,
  loginWithApple,
  loginWithFacebook,
  loginWithGoogle,
  setToken,
  signup,
  verify2faLogin,
  type OAuthProviderStatus,
} from "../lib/api";
import { useT } from "../lib/i18n";
import { AppleIcon, FacebookIcon, GoogleIcon } from "../components/BrandIcons";
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
  const [oauthStatus, setOauthStatus] = useState<OAuthProviderStatus | null>(null);
  const gisRef = useRef(false);

  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    if (p.get("mode") === "signup") setMode("signup");
    const em = p.get("email");
    if (em) setEmail(em);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void getOAuthProviderStatus()
      .then((status) => {
        if (!cancelled) setOauthStatus(status);
      })
      .catch(() => {
        if (!cancelled) setOauthStatus(null);
      });
    return () => {
      cancelled = true;
    };
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
      const msg = String(err);
      if (mode === "signup" && /already exists/i.test(msg)) {
        setMode("login");
        setError("That email is already registered. Sign in instead, or use Forgot password.");
      } else {
        setError(msg);
      }
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
                autoComplete="name"
                style={{ width: "100%", padding: 8 }} />
            </label>
          )}
          <label style={{ display: "block", marginBottom: 8 }}>
            {mode === "login" ? t("login.emailOrUsername") : t("login.email")}
            <input type={mode === "login" ? "text" : "email"} required value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete={mode === "login" ? "username" : "email"}
              autoCapitalize="none" autoCorrect="off"
              style={{ width: "100%", padding: 8 }} />
          </label>
          <label style={{ display: "block", marginBottom: 8 }}>
            {t("login.password")}
            <span style={{ position: "relative", display: "block" }}>
              <input type={showPassword ? "text" : "password"} required value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={mode === "signup" ? 8 : undefined}
                autoComplete={mode === "signup" ? "new-password" : "current-password"}
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
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true); setError("");
                  try {
                    if (oauthStatus?.google?.mode === "sandbox") {
                        const em = window.prompt("Sandbox: enter email for Google login") || "";
                        if (!em) { setBusy(false); return; }
                        const res = await loginWithGoogle(`sandbox_google_${em}`);
                        setToken(res.token);
                        router.push("/");
                        return;
                      }
                      // Real Google sign-in via Google Identity Services one-tap
                      const GOOGLE_CLIENT_ID = "647091395717-scfbmvsudec5t9vqukk2h8k732bgd3kp.apps.googleusercontent.com";
                      if (!gisRef.current) {
                        await new Promise<void>((resolve, reject) => {
                          const s = document.createElement("script");
                          s.src = "https://accounts.google.com/gsi/client";
                          s.onload = () => resolve();
                          s.onerror = () => reject(new Error("Failed to load Google GIS"));
                          document.head.appendChild(s);
                        });
                        gisRef.current = true;
                      }
                      await new Promise<void>((resolve, reject) => {
                        (window as any).google.accounts.id.initialize({
                          client_id: GOOGLE_CLIENT_ID,
                          callback: async (resp: { credential: string }) => {
                            try {
                              const res = await loginWithGoogle(resp.credential);
                              setToken(res.token);
                              router.push("/");
                              resolve();
                            } catch (e) { reject(e); }
                          },
                          auto_select: false,
                          cancel_on_tap_outside: true,
                        });
                        (window as any).google.accounts.id.prompt((notification: any) => {
                          if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
                            // Fallback: render a hidden button and click it
                            const div = document.createElement("div");
                            div.style.display = "none";
                            document.body.appendChild(div);
                            (window as any).google.accounts.id.renderButton(div, { type: "standard" });
                            const btn = div.querySelector("div[role=button]") as HTMLElement | null;
                            btn?.click();
                            document.body.removeChild(div);
                          }
                        });
                      });
                  } catch (e) { setError(String(e)); setBusy(false); }
                }}
                style={{ display: "flex", alignItems: "center", gap: 8 }}
              >
                <GoogleIcon /> Google
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true); setError("");
                  try {
                    if (oauthStatus?.facebook?.mode === "sandbox") {
                        const em = window.prompt("Sandbox: enter email for Facebook login") || "";
                        if (!em) { setBusy(false); return; }
                        const res = await loginWithFacebook(`sandbox_facebook_${em}`);
                        setToken(res.token);
                        router.push("/");
                        return;
                      }
                      const FACEBOOK_APP_ID = "1071803295271778";
                      if (!(window as any).FB) {
                        await new Promise<void>((resolve, reject) => {
                          (window as any).fbAsyncInit = () => {
                            (window as any).FB.init({ appId: FACEBOOK_APP_ID, version: "v19.0", cookie: true, xfbml: false });
                            resolve();
                          };
                          const s = document.createElement("script");
                          s.src = "https://connect.facebook.net/en_US/sdk.js";
                          s.onerror = () => reject(new Error("Failed to load Facebook SDK"));
                          document.head.appendChild(s);
                        });
                      }
                      const accessToken = await new Promise<string>((resolve, reject) => {
                        (window as any).FB.login((resp: any) => {
                          if (resp.authResponse?.accessToken) resolve(resp.authResponse.accessToken);
                          else reject(new Error(resp.status === "not_authorized" ? "Facebook login denied" : "Facebook login cancelled"));
                        }, { scope: "email,public_profile" });
                      });
                      const res = await loginWithFacebook(accessToken);
                      setToken(res.token);
                      router.push("/");
                  } catch (e) { setError(String(e)); setBusy(false); }
                }}
                style={{ display: "flex", alignItems: "center", gap: 8 }}
              >
                <FacebookIcon /> Facebook
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true); setError("");
                  try {
                    if (oauthStatus?.apple?.mode === "sandbox") {
                      const em = window.prompt("Sandbox: enter email for Apple login") || "";
                      if (!em) { setBusy(false); return; }
                      const res = await loginWithApple(`sandbox_apple_${em}`);
                      setToken(res.token);
                      router.push("/");
                      return;
                    }
                    // Apple Sign In for web — requires a Services ID registered at
                    // developer.apple.com → Certificates → Identifiers → Services IDs
                    const APPLE_SERVICES_ID = "com.aiclassroom.web";
                    if (!(window as any).AppleID) {
                      await new Promise<void>((resolve, reject) => {
                        const s = document.createElement("script");
                        s.src = "https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js";
                        s.onload = () => resolve();
                        s.onerror = () => reject(new Error("Failed to load Apple JS SDK"));
                        document.head.appendChild(s);
                      });
                    }
                    (window as any).AppleID.auth.init({
                      clientId: APPLE_SERVICES_ID,
                      scope: "name email",
                      redirectURI: window.location.origin + "/login",
                      usePopup: true,
                    });
                    const data = await (window as any).AppleID.auth.signIn();
                    const identityToken = data?.authorization?.id_token;
                    if (!identityToken) throw new Error("Apple sign-in did not return an identity token");
                    const res = await loginWithApple(identityToken);
                    setToken(res.token);
                    router.push("/");
                  } catch (e: any) {
                    if (e?.error !== "popup_closed_by_user") setError(String(e?.message || e));
                    setBusy(false);
                  }
                }}
                style={{ display: "flex", alignItems: "center", gap: 8 }}
              >
                <AppleIcon /> Apple
              </button>
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

