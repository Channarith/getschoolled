"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Rail } from "./components/CourseRail";
import { getHomeFeed, getToken, type HomeRail } from "./lib/api";
import { useT } from "./lib/i18n";

export default function HomePage() {
  const { t } = useT();
  const [rails, setRails] = useState<HomeRail[] | null>(null);
  const [error, setError] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    setLoggedIn(Boolean(getToken()));
    getHomeFeed().then(setRails).catch((e) => setError(String(e)));
  }, []);

  return (
    <main>
      <section className="theme-hero" style={{
        color: "#fff", padding: "40px 24px 44px",
      }}>
        <div className="theme-hero-inner"
             style={{ display: "flex", gap: 32, alignItems: "center",
                      flexWrap: "wrap" }}>
          {/* Realistic Bodhi-leaf medallion + Khmer wordmark
              (សាលារៀន, sala-rean) lockup. Decorative; the brand
              text is owned by the nav and the title below. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-realistic-lockup-512.webp"
               alt="Salarean - សាលារៀន"
               width={220} height={275}
               style={{ flex: "0 0 auto", borderRadius: 18,
                        boxShadow: "0 16px 40px rgba(2,6,23,.45)",
                        background: "#0b1020" }} />
          <div style={{ flex: "1 1 320px", minWidth: 0 }}>
          <span className="theme-badge">{t("hero.kicker")}</span>
          <h1 className="theme-title" style={{ marginTop: 14 }}>
            {t("hero.title")}
          </h1>
          <p className="theme-subtitle">
            {loggedIn ? t("hero.subLoggedIn") : t("hero.subLoggedOut")}
          </p>
          <div className="hero-cta">
            <Link href="/class"><button className="theme-btn">{t("hero.trySample")}</button></Link>
            <Link href="/browse"><button className="theme-btn" style={{ background: "#e50914", color: "#fff" }}>{t("hero.browseAll")}</button></Link>
            <Link href="/arcade"><button className="theme-btn" style={{ background: "#7c3aed", color: "#fff" }}>{t("hero.arcade")}</button></Link>
            <Link href="/languages"><button className="theme-btn" style={{ background: "#0ea5e9", color: "#fff" }}>{t("hero.languages")}</button></Link>
            <Link href="/kids"><button className="theme-btn" style={{ background: "#f59e0b" }}>{t("hero.kids")}</button></Link>
            <Link href="/corporate"><button className="theme-btn" style={{ background: "#0ea5e9", color: "#fff" }}>{t("hero.corporate")}</button></Link>
            {loggedIn
              ? <Link href="/recommended"><button className="theme-btn" style={{ background: "#16a34a", color: "#fff" }}>{t("hero.forYou")}</button></Link>
              : <Link href="/login"><button className="theme-btn" style={{ background: "#111827", color: "#fff" }}>{t("nav.signin")}</button></Link>}
          </div>
          </div>
        </div>
      </section>

      <div className="feed">
        {error && <p style={{ color: "#b00" }}>{t("home.error")} {error}</p>}
        {rails === null && !error && <p className="muted">{t("home.loading")}</p>}
        {rails && rails.length === 0 && (
          <p className="muted">{t("home.empty")} <Link href="/browse">{t("home.browse")}</Link> {t("home.toGetStarted")}</p>
        )}
        {rails?.map((r) => <Rail key={r.key} rail={r} />)}
      </div>
    </main>
  );
}
