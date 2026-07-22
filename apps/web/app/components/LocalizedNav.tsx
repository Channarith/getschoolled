"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { AUTH_EVENT, getToken, getFlag } from "../lib/api";
import { useT } from "../lib/i18n";
import ProfileMenu from "./ProfileMenu";
import NavSearchBox from "./NavSearchBox";

// Top navigation. Content tabs are gated when signed out. On narrow viewports
// links collapse into a menu so the bar stays full-width and readable.
export default function LocalizedNav({ appVersion }: { appVersion: string }) {
  const { t } = useT();
  const pathname = usePathname() ?? "/";

  const [unlocked, setUnlocked] = useState(false);
  const [homeworkOn, setHomeworkOn] = useState(false);
  const [watchOn, setWatchOn] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const sync = () => {
      setUnlocked(Boolean(getToken()));
      getFlag("access.homework_grader")
        .then((v) => setHomeworkOn(Boolean(v)))
        .catch(() => setHomeworkOn(false));
      getFlag("engagement.watch_window")
        .then((v) => setWatchOn(Boolean(v)))
        .catch(() => setWatchOn(false));
    };
    sync();
    window.addEventListener(AUTH_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(AUTH_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, [pathname]);

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  const logoSrc = pathname.startsWith("/kids")
    ? "/logo-cartoon-mark.webp"
    : "/logo-mark.webp";

  const contentLinks = unlocked ? (
    <>
      <Link href="/">{t("nav.home")}</Link>
      <Link href="/browse">{t("nav.browse")}</Link>
      <Link href="/recommended">{t("nav.forYou")}</Link>
      <Link href="/kids">{t("nav.kids")}</Link>
      <Link href="/corporate">{t("nav.corporate")}</Link>
      <Link href="/languages">{t("nav.languages")}</Link>
      <Link href="/drive">{t("nav.drive")}</Link>
      <Link href="/jobs">{t("nav.careers")}</Link>
      <Link href="/arcade">{t("nav.arcade")}</Link>
      <Link href="/worlds">🌍 Worlds</Link>
      {watchOn && <Link href="/watch">{t("nav.watch")}</Link>}
      <Link href="/class">{t("nav.liveClass")}</Link>
      <Link href="/group-classes">{t("nav.groupClasses")}</Link>
      {homeworkOn && <Link href="/homework">{t("nav.homework")}</Link>}
    </>
  ) : (
    <Link href="/login">{t("nav.signin")}</Link>
  );

  return (
    <header className="site-header">
      <nav className="nav" aria-label="Main">
        <div className="nav-top">
          <Link
            href="/"
            className="brand"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              textDecoration: "none",
              color: "inherit",
            }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={logoSrc}
              alt={t("nav.brand")}
              width={30}
              height={30}
              style={{ height: 30, width: 30, borderRadius: "50%", display: "block" }}
            />
            {t("nav.brand")}
          </Link>

          <div className="nav-actions">
            <span
              className="nav-ai-badge"
              title="This platform is AI-instructed; see the Transparency page."
            >
              {t("nav.aiInstructed")}
            </span>
            <NavSearchBox />
            <ProfileMenu />
            <span className="version" title="App version">
              v{appVersion}
            </span>
            <button
              type="button"
              className="nav-toggle"
              aria-expanded={menuOpen}
              aria-controls="site-nav-menu"
              aria-label={menuOpen ? t("nav.closeMenu") : t("nav.openMenu")}
              onClick={() => setMenuOpen((o) => !o)}
            >
              {menuOpen ? "✕" : "☰"}
            </button>
          </div>
        </div>

        <div id="site-nav-menu" className={`nav-menu${menuOpen ? " open" : ""}`}>
          <Link href="/our-story">{t("nav.ourStory")}</Link>
          {contentLinks}
        </div>
      </nav>
    </header>
  );
}
