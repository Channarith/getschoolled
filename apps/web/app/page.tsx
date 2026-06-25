"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import AppBadges from "./components/AppBadges";
import { Rail } from "./components/CourseRail";
import MascotImage from "./components/MascotImage";
import {
  AUTH_EVENT,
  getHomeFeed,
  getToken,
  type HomeRail,
} from "./lib/api";
import { friendlyError } from "./lib/errors";
import { useT } from "./lib/i18n";

export default function HomePage() {
  const { t } = useT();
  const router = useRouter();
  const [rails, setRails] = useState<HomeRail[] | null>(null);
  const [error, setError] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);
  const [authResolved, setAuthResolved] = useState(false);
  const [email, setEmail] = useState("");

  useEffect(() => {
    const sync = () => {
      const authed = Boolean(getToken());
      setLoggedIn(authed);
      setAuthResolved(true);
      if (authed) {
        getHomeFeed().then(setRails).catch((e) => setError(String(e)));
      } else {
        setRails(null);
        setError("");
      }
    };
    sync();
    window.addEventListener(AUTH_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(AUTH_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

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

  // Signed-out visitors see the marketing landing only — no catalog rails.
  if (!loggedIn) {
    return (
      <main className="landing-hero">
        <div
          className="landing-hero-bg site-bg-layer site-bg-kenburns site-bg-motion-2"
          style={{
            backgroundImage:
              "linear-gradient(0deg, rgba(11,16,32,.94) 0%, rgba(11,16,32,.35) 45%, rgba(11,16,32,.85) 100%), url(/wallpapers/wisdom_bodhi.webp)",
            backgroundSize: "cover",
            backgroundPosition: "center",
          }}
          aria-hidden
        />
        <div className="landing-inner">
          <MascotImage width={160} className="landing-mascot" alt="Salareen mascot" />
          <span className="theme-badge">{t("hero.kicker")}</span>
          <h1 className="theme-title glow" style={{ fontSize: 52, maxWidth: "20ch", margin: "14px auto 12px" }}>
            {t("hero.title")}
          </h1>
          <p className="theme-subtitle glow" style={{ margin: "0 auto" }}>{t("hero.subLoggedOut")}</p>
          <p className="glow" style={{ marginTop: 18, opacity: 0.95 }}>{t("landing.emailCta")}</p>
          <form onSubmit={onGetStarted} className="row" style={{ justifyContent: "center", gap: 8, marginTop: 8 }}>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                   placeholder={t("landing.email")} aria-label={t("landing.email")}
                   style={{ minWidth: 260, padding: "14px 12px" }} />
            <button type="submit" className="theme-btn"
                    style={{ background: "#e50914", color: "#fff", fontSize: 18, padding: "13px 22px" }}>
              {t("landing.getStarted")} →
            </button>
          </form>
          <div className="hero-cta" style={{ justifyContent: "center", marginTop: 18 }}>
            <Link href="/login"><button className="theme-btn" style={{ background: "#111827", color: "#fff" }}>{t("landing.signIn")}</button></Link>
          </div>
          <p className="glow" style={{ marginTop: 22, marginBottom: 0, opacity: 0.95 }}>
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
        {rails?.map((r) => <Rail key={r.key} rail={r} />)}
      </div>
    </main>
  );
}
