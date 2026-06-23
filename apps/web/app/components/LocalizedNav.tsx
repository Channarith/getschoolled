"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { getToken } from "../lib/api";
import { useT } from "../lib/i18n";
import LanguagePicker from "./LanguagePicker";

// Top navigation. Every label is localized via t(...) so switching language
// updates the whole bar. Account-area surfaces (Dashboard, Console, Admin) and
// the legal/consent/transparency notices are intentionally NOT top-level tabs -
// they live under Account (the profile hub) and the footer. The brand mark flips
// to the kid-friendly cartoon variant on /kids.
export default function LocalizedNav({ appVersion }: { appVersion: string }) {
  const { t } = useT();
  const pathname = usePathname() ?? "/";
  const [loggedIn, setLoggedIn] = useState(false);

  // Re-check auth on every route change so the bar updates right after
  // login/logout (both navigate, changing the pathname).
  useEffect(() => {
    setLoggedIn(Boolean(getToken()));
  }, [pathname]);

  const logoSrc = pathname.startsWith("/kids")
    ? "/logo-cartoon-mark.webp"
    : "/logo-mark.webp";

  return (
    <nav className="nav">
      <Link href="/" className="brand"
            style={{ display: "inline-flex", alignItems: "center", gap: 8,
                     textDecoration: "none", color: "inherit" }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={logoSrc} alt={t("nav.brand")} height={30}
             style={{ height: 30, width: "auto", borderRadius: 6 }} />
        {t("nav.brand")}
      </Link>
      <Link href="/">{t("nav.home")}</Link>
      <Link href="/browse">{t("nav.browse")}</Link>
      <Link href="/recommended">{t("nav.forYou")}</Link>
      <Link href="/kids">{t("nav.kids")}</Link>
      <Link href="/corporate">{t("nav.corporate")}</Link>
      <Link href="/languages">{t("nav.languages")}</Link>
      <Link href="/drive">{t("nav.drive")}</Link>
      <Link href="/jobs">{t("nav.careers")}</Link>
      <Link href="/arcade">{t("nav.arcade")}</Link>
      <Link href="/watch">{t("nav.watch")}</Link>
      <Link href="/class">{t("nav.liveClass")}</Link>
      <Link href="/homework">{t("nav.homework")}</Link>
      <Link href="/rewards">{t("nav.rewards")}</Link>
      <Link href="/backgrounds">{t("nav.themes")}</Link>
      <span
        title="This platform is AI-instructed; see the Transparency page."
        style={{ marginLeft: "auto", fontSize: 12, padding: "2px 8px",
                 borderRadius: 999, border: "1px solid currentColor", opacity: 0.85 }}
      >
        AI-instructed
      </span>
      {loggedIn
        ? <Link href="/account">{t("nav.account")}</Link>
        : <Link href="/login">{t("nav.signin")}</Link>}
      <LanguagePicker compact />
      <span className="version" title="App version"
            style={{ opacity: 0.7, fontSize: 12 }}>
        v{appVersion}
      </span>
    </nav>
  );
}
