"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Rail } from "../components/CourseRail";
import { AUTH_EVENT, getHomeFeed, getToken, type HomeRail } from "../lib/api";
import { useT } from "../lib/i18n";

export default function KidsPage() {
  const { t, locale } = useT();
  const [rails, setRails] = useState<HomeRail[] | null>(null);
  const [error, setError] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);
  const [authResolved, setAuthResolved] = useState(false);

  useEffect(() => {
    const sync = () => {
      const authed = Boolean(getToken());
      setLoggedIn(authed);
      setAuthResolved(true);
      if (authed) {
        getHomeFeed(true, locale).then(setRails).catch((e) => setError(String(e)));
      } else {
        setRails(null);
        setError("");
      }
    };
    sync();
    window.addEventListener(AUTH_EVENT, sync);
    return () => window.removeEventListener(AUTH_EVENT, sync);
  }, [locale]);

  if (!authResolved) {
    return (
      <div className="kids">
        <div className="feed"><p className="muted">{t("kids.loading")}</p></div>
      </div>
    );
  }

  if (!loggedIn) {
    return (
      <div className="kids">
        <div className="feed">
          <div className="kids-hero">
            <h1>{t("kids.title")}</h1>
            <p style={{ color: "#9a3412", fontWeight: 600, fontSize: 18 }}>
              {t("kids.signInSub")}
            </p>
            <div className="hero-cta" style={{ justifyContent: "center" }}>
              <Link href="/login">
                <button className="theme-btn" style={{ background: "#f59e0b" }}>{t("profile.signIn")}</button>
              </Link>
              <Link href="/">
                <button className="theme-btn" style={{ background: "#fff", color: "#9a3412", border: "2px solid #fdba74" }}>
                  {t("kids.backMain")}
                </button>
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="kids">
      <div className="feed">
        <div className="kids-hero">
          <h1>{t("kids.title")}</h1>
          <p style={{ color: "#9a3412", fontWeight: 600, fontSize: 18 }}>
            {t("kids.signedInSub")}
          </p>
          <div className="hero-cta" style={{ justifyContent: "center" }}>
            <Link href="/class">
              <button className="theme-btn" style={{ background: "#f59e0b" }}>{t("kids.startClass")}</button>
            </Link>
            <Link href="/">
              <button className="theme-btn" style={{ background: "#fff", color: "#9a3412", border: "2px solid #fdba74" }}>
                {t("kids.backMain")}
              </button>
            </Link>
          </div>
          <p style={{ color: "#a16207", fontSize: 13, marginTop: 10 }}>
            {t("kids.parentNote")}{" "}
            <Link href="/account">{t("account.title")}</Link>.
          </p>
        </div>

        {error && <p style={{ color: "#b00" }}>{t("kids.loadError")} {error}</p>}
        {rails === null && !error && <p className="muted">{t("kids.loadingClasses")}</p>}
        {rails && rails.length === 0 && <p className="muted">{t("kids.noClasses")}</p>}
        {rails?.map((r) => <Rail key={r.key} rail={r} kids />)}
      </div>
    </div>
  );
}
