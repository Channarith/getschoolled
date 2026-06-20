"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useT } from "../lib/i18n";
import LanguagePicker from "./LanguagePicker";

// Localized version of the top navigation. Each link's label flips to
// the active locale via t(...). Routes themselves are NOT localized
// (e.g. /browse stays /browse) - that's a separate URL-routing-i18n
// piece we can layer on later via Next's built-in i18n routing.
//
// The brand logo also flips to a kid-friendly cartoon variant when
// the current route is under /kids, and to a richly-detailed
// "realistic" variant on the marketing-style /watch + /class hero
// routes. Everywhere else it stays the line-art Bodhi-leaf S mark.
export default function LocalizedNav({ appVersion }: { appVersion: string }) {
  const { t } = useT();
  const pathname = usePathname() ?? "/";
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
      <Link href="/kids">{t("nav.kids")}</Link>
      <Link href="/corporate">{t("nav.corporate")}</Link>
      <Link href="/recommended">{t("nav.forYou")}</Link>
      <Link href="/languages">{t("nav.languages")}</Link>
      <Link href="/drive">{t("nav.drive")}</Link>
      <Link href="/arcade">{t("nav.arcade")}</Link>
      <Link href="/watch">Watch</Link>
      <Link href="/class">Live Class</Link>
      <Link href="/rewards">Rewards</Link>
      <Link href="/account">{t("nav.account")}</Link>
      <Link href="/console">Console</Link>
      <Link href="/admin">Admin</Link>
      <Link href="/dashboard">Dashboard</Link>
      <Link href="/consent">Consent</Link>
      <Link href="/backgrounds">Themes</Link>
      <Link href="/transparency">Transparency</Link>
      <Link href="/legal">Legal</Link>
      <span
        title="This platform is AI-instructed; see the Transparency page."
        style={{ marginLeft: "auto", fontSize: 12, padding: "2px 8px",
                 borderRadius: 999, border: "1px solid currentColor", opacity: 0.85 }}
      >
        AI-instructed
      </span>
      <LanguagePicker compact />
      <span className="version" title="App version"
            style={{ opacity: 0.7, fontSize: 12 }}>
        v{appVersion}
      </span>
    </nav>
  );
}
