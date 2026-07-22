"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import AppBadges from "./components/AppBadges";
import AdSlot from "./components/AdSlot";
import { Rail, Tile } from "./components/CourseRail";
import MascotImage from "./components/MascotImage";
import { GoogleIcon, FacebookIcon, AppleIcon } from "./components/BrandIcons";
import { useFlag } from "./lib/flags";
import {
  AUTH_EVENT,
  getHomeFeed,
  getMe,
  getToken,
  loginWithGoogle,
  loginWithFacebook,
  loginWithApple,
  setToken,
  type HomeRail,
} from "./lib/api";
import { friendlyError } from "./lib/errors";
import { useT } from "./lib/i18n";

export default function HomePage() {
  const { t, locale } = useT();
  const carousels = useFlag<boolean>("ux.netflix_carousels", true);
  const router = useRouter();
  const [rails, setRails] = useState<HomeRail[] | null>(null);
  const [error, setError] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);
  const [authResolved, setAuthResolved] = useState(false);
  const [email, setEmail] = useState("");
  const [tier, setTier] = useState("free");
  const [socialBusy, setSocialBusy] = useState(false);
  const [socialError, setSocialError] = useState("");
  const gisRef = useRef(false);

  useEffect(() => {
    let alive = true;
    let feedController = new AbortController();
    const sync = () => {
      feedController.abort();
      feedController = new AbortController();
      const signal = feedController.signal;
      const authed = Boolean(getToken());
      setLoggedIn(authed);
      setAuthResolved(true);
      if (authed) {
        getHomeFeed(false, locale, signal)
          .then((r) => { if (!alive) return; setRails(r); })
          .catch((e) => { if (!alive || signal.aborted) return; setError(String(e)); });
        getMe()
          .then((m) => { if (!alive) return; setTier(m.tier || "free"); })
          .catch(() => { if (!alive) return; setTier("free"); });
      } else {
        setRails(null);
        setError("");
      }
    };
    sync();
    window.addEventListener(AUTH_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      alive = false;
      feedController.abort();
      window.removeEventListener(AUTH_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, [locale]);

  function onGetStarted(e: React.FormEvent) {
    e.preventDefault();
    router.push(`/login?mode=signup${email ? `&email=${encodeURIComponent(email)}` : ""}`);
  }

  if (!authResolved) {
    return (
      <main className="landing-hero">
        <p className="muted" style={{ textAlign: "center", paddingTop: 80 }}>{t("home.loading")}</p>
      </main>
    );
  }

  // Unauthenticated visitors must sign in — show social + email options inline.
  if (!loggedIn) {
    const handleSocial = async (provider: "google" | "facebook" | "apple") => {
      setSocialBusy(true); setSocialError("");
      try {
        let res: { token: string };
        if (provider === "google") {
          const GOOGLE_CLIENT_ID = "647091395717-scfbmvsudec5t9vqukk2h8k732bgd3kp.apps.googleusercontent.com";
          if (!gisRef.current) {
            await new Promise<void>((resolve, reject) => {
              const s = document.createElement("script");
              s.src = "https://accounts.google.com/gsi/client";
              s.onload = () => resolve(); s.onerror = () => reject(new Error("Failed to load Google"));
              document.head.appendChild(s);
            });
            gisRef.current = true;
          }
          res = await new Promise((resolve, reject) => {
            (window as any).google.accounts.id.initialize({
              client_id: GOOGLE_CLIENT_ID,
              callback: async (r: { credential: string }) => {
                try { resolve(await loginWithGoogle(r.credential)); } catch (e) { reject(e); }
              },
            });
            (window as any).google.accounts.id.prompt((n: any) => {
              if (n.isNotDisplayed() || n.isSkippedMoment()) reject(new Error("Google sign-in dismissed"));
            });
          });
        } else if (provider === "facebook") {
          const FACEBOOK_APP_ID = "1071803295271778";
          if (!(window as any).FB) {
            await new Promise<void>((resolve, reject) => {
              (window as any).fbAsyncInit = () => {
                (window as any).FB.init({ appId: FACEBOOK_APP_ID, version: "v19.0", cookie: true, xfbml: false });
                resolve();
              };
              const s = document.createElement("script");
              s.src = "https://connect.facebook.net/en_US/sdk.js";
              s.onerror = () => reject(new Error("Failed to load Facebook")); document.head.appendChild(s);
            });
          }
          const token = await new Promise<string>((resolve, reject) => {
            (window as any).FB.login((r: any) => {
              if (r.authResponse?.accessToken) resolve(r.authResponse.accessToken);
              else reject(new Error("Facebook sign-in cancelled"));
            }, { scope: "email,public_profile" });
          });
          res = await loginWithFacebook(token);
        } else {
          const APPLE_SERVICES_ID = "com.aiclassroom.web";
          if (!(window as any).AppleID) {
            await new Promise<void>((resolve, reject) => {
              const s = document.createElement("script");
              s.src = "https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js";
              s.onload = () => resolve(); s.onerror = () => reject(new Error("Failed to load Apple")); document.head.appendChild(s);
            });
          }
          (window as any).AppleID.auth.init({ clientId: APPLE_SERVICES_ID, scope: "name email", redirectURI: window.location.origin, usePopup: true });
          const data = await (window as any).AppleID.auth.signIn();
          res = await loginWithApple(data?.authorization?.id_token);
        }
        setToken(res.token);
        window.dispatchEvent(new Event(AUTH_EVENT));
      } catch (e: any) {
        if (e?.error !== "popup_closed_by_user") setSocialError(String(e?.message || e));
      } finally { setSocialBusy(false); }
    };

    return (
      <main className="landing-hero">
        <div
          className="landing-hero-bg site-bg-layer site-bg-kenburns site-bg-motion-2"
          style={{
            backgroundImage:
              "linear-gradient(0deg, rgba(11,16,32,.94) 0%, rgba(11,16,32,.35) 45%, rgba(11,16,32,.85) 100%), url(/wallpapers/wisdom_bodhi.webp)",
            backgroundSize: "cover", backgroundPosition: "center",
          }}
          aria-hidden
        />
        <div className="landing-inner">
          <MascotImage width={140} className="landing-mascot" alt="Salareen mascot" />
          <span className="theme-badge">{t("hero.kicker")}</span>
          <h1 className="theme-title glow" style={{ fontSize: 44, maxWidth: "22ch", margin: "12px auto 10px" }}>
            {t("hero.title")}
          </h1>
          <p className="theme-subtitle glow" style={{ margin: "0 auto" }}>{t("hero.subLoggedOut")}</p>

          {/* Social sign-in — right on the landing page, no redirect needed */}
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
            <div style={{ display: "flex", alignItems: "center", gap: 10, width: "100%", margin: "4px 0" }}>
              <div style={{ flex: 1, height: 1, background: "rgba(255,255,255,0.2)" }} />
              <span style={{ color: "rgba(255,255,255,0.5)", fontSize: 13 }}>or</span>
              <div style={{ flex: 1, height: 1, background: "rgba(255,255,255,0.2)" }} />
            </div>
            <Link href="/login" style={{ width: "100%" }}>
              <button style={{ width: "100%", padding: "13px 20px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.3)", background: "rgba(255,255,255,0.08)", color: "#fff", fontWeight: 700, fontSize: 15, cursor: "pointer" }}>
                Sign in with email / password
              </button>
            </Link>
          </div>

          <p className="glow" style={{ marginTop: 28, marginBottom: 0, opacity: 0.95 }}>
            {t("hero.getAppTitle")}
          </p>
          <AppBadges center />
        </div>
      </main>
    );
  }

  return (
    <main>
      <section className="theme-hero" style={{
        backgroundImage:
          "linear-gradient(120deg, rgba(11,16,32,.82) 0%, rgba(67,56,202,.55) 60%, rgba(124,58,237,.5) 100%), url(/wallpapers/wisdom_bodhi.webp)",
        backgroundSize: "cover", backgroundPosition: "center",
        color: "#fff", padding: "40px 24px 44px",
      }}>
        <div className="theme-hero-inner"
             style={{ display: "flex", gap: 32, alignItems: "center", flexWrap: "wrap" }}>
          <MascotImage
            width={200}
            alt="Salareen Bayon Buddy mascot holding the Bodhi-leaf S mark"
            style={{ flex: "0 0 auto", width: 200, height: "auto",
                      filter: "drop-shadow(0 16px 28px rgba(2,6,23,.55))" }}
          />
          <div style={{ flex: "1 1 320px", minWidth: 0 }}>
          <span className="theme-badge">{t("hero.kicker")}</span>
          <h1 className="theme-title glow" style={{ marginTop: 14 }}>
            {t("hero.title")}
          </h1>
          <p className="theme-subtitle glow">{t("hero.subLoggedIn")}</p>
          <div className="hero-cta">
            <Link href="/class"><button className="theme-btn">{t("hero.trySample")}</button></Link>
            <Link href="/browse"><button className="theme-btn" style={{ background: "#e50914", color: "#fff" }}>{t("hero.browseAll")}</button></Link>
            <Link href="/arcade"><button className="theme-btn" style={{ background: "#7c3aed", color: "#fff" }}>{t("hero.arcade")}</button></Link>
            <Link href="/languages"><button className="theme-btn" style={{ background: "#0ea5e9", color: "#fff" }}>{t("hero.languages")}</button></Link>
            <Link href="/jobs"><button className="theme-btn" style={{ background: "#16a34a", color: "#fff" }}>{t("hero.careers")}</button></Link>
            <Link href="/kids"><button className="theme-btn" style={{ background: "#f59e0b" }}>{t("hero.kids")}</button></Link>
            <Link href="/corporate"><button className="theme-btn" style={{ background: "#0ea5e9", color: "#fff" }}>{t("hero.corporate")}</button></Link>
            <Link href="/recommended"><button className="theme-btn" style={{ background: "#16a34a", color: "#fff" }}>{t("hero.forYou")}</button></Link>
          </div>
          <p className="muted" style={{ marginTop: 16, marginBottom: 0 }}>{t("hero.getAppTitle")}</p>
          <AppBadges />
          </div>
        </div>
      </section>

      <div className="feed">
        <AdSlot slotId="home-banner" tier={tier} />
        {error && (
          <div className="card" style={{ borderColor: "#ff6b6b" }}>
            <strong>{t("home.error")}</strong>
            <div className="muted" style={{ marginTop: 4 }}>{friendlyError(error, t("error.offline"))}</div>
          </div>
        )}
        {rails === null && !error && <p className="muted">{t("home.loading")}</p>}
        {rails && rails.length === 0 && (
          <p className="muted">{t("home.empty")} <Link href="/browse">{t("home.browse")}</Link> {t("home.toGetStarted")}</p>
        )}
        {rails && (carousels
          ? rails.map((r) => <Rail key={r.key} rail={r} />)
          : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
                gap: 16,
                marginTop: 12,
              }}
            >
              {rails.flatMap((r) => r.courses ?? []).map((c) => (
                <Tile key={c.course_id} course={c} />
              ))}
            </div>
          ))}
      </div>
    </main>
  );
}
