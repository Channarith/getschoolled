"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import AppBadges from "./AppBadges";
import { GoogleIcon, FacebookIcon, AppleIcon } from "./BrandIcons";
import {
  AUTH_EVENT,
  login,
  signup,
  setToken,
  submitOnboardingProfile,
} from "../lib/api";
import { signInWithSocial } from "../lib/socialAuth";
import { friendlyError } from "../lib/errors";
import { useT } from "../lib/i18n";

/** Landing-style sign-in box: social buttons, email/password, and the get-the-app line. */
export default function LandingAuthPanel({ onSignedIn }: { onSignedIn?: () => void }) {
  const { t } = useT();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [emailMode, setEmailMode] = useState<"login" | "signup">("login");
  const [emailBusy, setEmailBusy] = useState(false);
  const [emailError, setEmailError] = useState("");
  const [socialBusy, setSocialBusy] = useState(false);
  const [socialError, setSocialError] = useState("");

  function signedIn() {
    window.dispatchEvent(new Event(AUTH_EVENT));
    onSignedIn?.();
  }

  async function handleEmailSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email || !password) return;
    setEmailBusy(true);
    setEmailError("");
    try {
      const displayName = email.split("@")[0].replace(/[^a-zA-Z0-9]/g, " ").trim() || email;
      const res = emailMode === "login"
        ? await login(email, password)
        : await signup(email, password, displayName);
      setToken(res.token);
      if (emailMode === "signup") {
        try {
          await submitOnboardingProfile({ display_name: displayName });
        } catch { /* non-critical — onboarding page handles this */ }
        router.push("/onboarding");
      } else {
        signedIn();
      }
    } catch (e: any) {
      const msg = e?.message || String(e);
      if (emailMode === "signup" && /already exists/i.test(msg)) {
        setEmailMode("login");
        setEmailError("Email already registered — signing you in instead.");
      } else {
        const cleanMsg = msg.replace(/^\d{3}\s+/, "");
        setEmailError(friendlyError(cleanMsg, cleanMsg));
      }
    } finally {
      setEmailBusy(false);
    }
  }

  const handleSocial = async (provider: "google" | "facebook" | "apple") => {
    setSocialBusy(true); setSocialError("");
    try {
      const res = await signInWithSocial(provider);
      setToken(res.token);
      signedIn();
    } catch (e: any) {
      if (e?.error !== "popup_closed_by_user") setSocialError(String(e?.message || e));
    } finally { setSocialBusy(false); }
  };

  return (
    <>
      {/* Social sign-in — right on the page, no redirect needed */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10, marginTop: 28, width: "100%", maxWidth: 340, margin: "28px auto 0" }}>
        <button disabled={socialBusy} onClick={() => void handleSocial("google")}
          style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, width: "100%", padding: "13px 20px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.2)", background: "#fff", color: "#111", fontWeight: 700, fontSize: 15, cursor: "pointer" }}>
          <GoogleIcon /> Continue with Google
        </button>
        <button disabled={socialBusy} onClick={() => void handleSocial("facebook")}
          style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, width: "100%", padding: "13px 20px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.2)", background: "#1877F2", color: "#fff", fontWeight: 700, fontSize: 15, cursor: "pointer" }}>
          <FacebookIcon /> Continue with Facebook
        </button>
        <button disabled={socialBusy} onClick={() => void handleSocial("apple")}
          style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, width: "100%", padding: "13px 20px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.2)", background: "#000", color: "#fff", fontWeight: 700, fontSize: 15, cursor: "pointer" }}>
          <AppleIcon color="#fff" /> Continue with Apple
        </button>
        {socialError && <p style={{ color: "#f87171", fontSize: 13, margin: 0 }}>{socialError}</p>}

        {/* Divider */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, width: "100%", margin: "4px 0" }}>
          <div style={{ flex: 1, height: 1, background: "rgba(255,255,255,0.2)" }} />
          <span style={{ color: "rgba(255,255,255,0.5)", fontSize: 13 }}>or</span>
          <div style={{ flex: 1, height: 1, background: "rgba(255,255,255,0.2)" }} />
        </div>

        {/* Inline email / password form */}
        <form onSubmit={(e) => void handleEmailSubmit(e)} style={{ width: "100%", display: "flex", flexDirection: "column", gap: 8 }}>
          <input
            type="text"
            placeholder="Email or username"
            value={email}
            onChange={e => setEmail(e.target.value)}
            autoComplete="username"
            required
            style={{ width: "100%", padding: "12px 14px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.25)", background: "rgba(255,255,255,0.1)", color: "#fff", fontSize: 15, outline: "none", boxSizing: "border-box" }}
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            autoComplete={emailMode === "signup" ? "new-password" : "current-password"}
            required
            style={{ width: "100%", padding: "12px 14px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.25)", background: "rgba(255,255,255,0.1)", color: "#fff", fontSize: 15, outline: "none", boxSizing: "border-box" }}
          />
          {emailMode === "signup" && password.length > 0 && (password.length < 8 || !/[0-9]/.test(password)) && (
            <p style={{ color: "#fca5a5", fontSize: 12, margin: "4px 0 0", textAlign: "left" }}>
              {password.length < 8 ? "At least 8 characters required" : "Must include at least one number"}
            </p>
          )}
          {emailMode === "signup" && password.length >= 8 && /[0-9]/.test(password) && /[a-zA-Z]/.test(password) && (
            <p style={{ fontSize: 12, color: "#10b981", marginTop: 2 }}>✓ Password looks good</p>
          )}
          {emailError && <p style={{ color: "#f87171", fontSize: 13, margin: 0 }}>{emailError}</p>}
          <button
            type="submit"
            disabled={emailBusy || !email || !password}
            style={{ width: "100%", padding: "13px 20px", borderRadius: 10, border: "none", background: emailBusy ? "rgba(99,102,241,0.5)" : "#6366f1", color: "#fff", fontWeight: 700, fontSize: 15, cursor: emailBusy ? "default" : "pointer" }}
          >
            {emailBusy ? "Signing in…" : emailMode === "login" ? "Sign in" : "Create account"}
          </button>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8, marginTop: 2 }}>
            <button
              type="button"
              onClick={() => { setEmailMode(emailMode === "login" ? "signup" : "login"); setEmailError(""); }}
              style={{ background: "none", border: "none", color: "rgba(255,255,255,0.55)", fontSize: 13, cursor: "pointer", padding: 0, whiteSpace: "normal", textAlign: "left" }}
            >
              {emailMode === "login" ? "New here? Create account" : "Already have an account? Sign in"}
            </button>
            <Link href="/forgot-password" style={{ color: "rgba(255,255,255,0.55)", fontSize: 13, textDecoration: "none" }}>
              Forgot password?
            </Link>
          </div>
        </form>
      </div>

      <p className="glow" style={{ marginTop: 28, marginBottom: 0, opacity: 0.95 }}>
        {t("hero.getAppTitle")}
      </p>
      <AppBadges center />
    </>
  );
}
