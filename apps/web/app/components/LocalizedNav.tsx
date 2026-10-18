"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { AUTH_EVENT, getToken, getFlag } from "../lib/api";
import { useDemoOnlyAnonymous, useFullNavTabs, useSignedIn } from "../lib/flags";
import { useT } from "../lib/i18n";
import { learningHint, useLearningPhrase } from "../lib/learningPhrases";
import { isImmersiveSetupPath } from "../lib/layoutWidth";
import ProfileMenu from "./ProfileMenu";
import NavSearchBox from "./NavSearchBox";
import ThemeToggle from "./ThemeToggle";

// Top navigation. Content tabs are gated when signed out. On narrow viewports
// links collapse into a menu so the bar stays full-width and readable.
export default function LocalizedNav({ appVersion }: { appVersion: string }) {
  const { t, locale } = useT();
  const learnPhrase = useLearningPhrase();
  const pathname = usePathname() ?? "/";

  const demoOnlyAnon = useDemoOnlyAnonymous();
  const fullNavTabs = useFullNavTabs();
  const signedIn = useSignedIn();
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

  // Demo-only mode (sales_demo.exclusive) hides the full site chrome for signed-
  // out visitors so the inverted demo stays focused on the three demo features.
  // The DN landing hero (now the default `/`) expects the dark navy header to
  // sit above it, so we DO show the nav on `/` for signed-out visitors; the
  // old "hide nav on /" branch is removed. `/home-concepts` still gets no
  // nav because its own chrome paints over the top. Immersive setup paths
  // (e.g. onboarding flows) also hide the nav so the setup chrome owns the
  // whole viewport.
  if (
    demoOnlyAnon
    || isImmersiveSetupPath(pathname)
    || pathname.startsWith("/home-concepts")
  ) {
    return null;
  }

  const logoSrc = pathname.startsWith("/kids")
    ? "/logo-cartoon-mark.webp"
    : "/logo-mark.webp";

  // Simplified-nav default (nav.full_tabs_enabled=false). "Our Story" is
  // rendered outside contentLinks already, so the simplified list adds the
  // other 4 tabs: Vision Play, On the Go, Careers, Live Class.
  // Keeping the count small lets the full header fit on ONE row even on
  // narrow laptops. The audio translation lab stays at /audio-lab; it is
  // not a tab.
  const simplifiedLinks = (
    <>
      <Link href="/arcade">{t("nav.arcade")}</Link>
      <Link href="/drive">{t("nav.drive")}</Link>
      <Link href="/jobs">{t("nav.careers")}</Link>
      <Link href="/class">{t("nav.liveClass")}</Link>
    </>
  );

  const fullSignedInLinks = (
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
      {watchOn && <Link href="/watch">{t("nav.watch")}</Link>}
      <Link href="/class">{t("nav.liveClass")}</Link>
      <Link href="/group-classes">{t("nav.groupClasses")}</Link>
      {homeworkOn && <Link href="/homework">{t("nav.homework")}</Link>}
    </>
  );

  // Simplified-nav mode is the DEFAULT for every signed-in account (admin
  // included). Only 5 header items ship by default: Our Story (rendered
  // outside contentLinks) + Vision Play, On the Go, Careers,
  // Live Class. An admin can restore the full nav globally by checking
  // `nav.full_tabs_enabled` in the admin console; the admin UI auto-renders
  // every FlagSpec by category, so the checkbox appears automatically under
  // the "nav" section.
  const contentLinks = unlocked
    ? fullNavTabs
      ? fullSignedInLinks
      : simplifiedLinks
    : <Link href="/login">{t("nav.signin")}</Link>;

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
            <Link
              href="/transparency"
              className="nav-ai-badge"
              title={learningHint(locale)}
            >
              {learnPhrase}
            </Link>
            <NavSearchBox />
            <ThemeToggle />
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
