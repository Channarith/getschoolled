"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import AppBadges from "./components/AppBadges";
import { PublicCourses } from "./components/PublicCourses";
import AdSlot from "./components/AdSlot";
import { Rail, Tile } from "./components/CourseRail";
import MascotImage from "./components/MascotImage";
import LandingAuthPanel from "./components/LandingAuthPanel";
import { DemoOnlyLanding } from "./components/DemoOnly";
import { useFlag, useFlags } from "./lib/flags";
import { SALES_DEMO_FLAGS } from "./lib/salesDemo";
import {
  AUTH_EVENT,
  getHomeFeed,
  getMe,
  getToken,
  type HomeRail,
} from "./lib/api";
import { friendlyError } from "./lib/errors";
import { useT } from "./lib/i18n";

export default function HomePage() {
  const { t, locale } = useT();
  const carousels = useFlag<boolean>("ux.netflix_carousels", true);
  const demoOnly = useFlag<boolean>(SALES_DEMO_FLAGS.exclusive, false);
  const { ready: flagsReady } = useFlags();
  const [rails, setRails] = useState<HomeRail[] | null>(null);
  const [error, setError] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);
  const [authResolved, setAuthResolved] = useState(false);
  const [tier, setTier] = useState("free");

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

  if (!authResolved || (!loggedIn && !flagsReady)) {
    return (
      <main className="landing-hero">
        <p className="muted" style={{ textAlign: "center", paddingTop: 80 }}>{t("home.loading")}</p>
      </main>
    );
  }

  // Unauthenticated visitors must sign in — show social + email options inline.
  if (!loggedIn) {
    if (demoOnly) return <DemoOnlyLanding />;

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
          <PublicCourses />
          <LandingAuthPanel />
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
