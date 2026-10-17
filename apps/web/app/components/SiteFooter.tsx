"use client";

import Link from "next/link";

import { usePathname } from "next/navigation";

import { isImmersiveSetupPath } from "../lib/layoutWidth";
import { useDemoOnlyAnonymous, useSignedIn } from "../lib/flags";
import { useT } from "../lib/i18n";
import LanguagePicker from "./LanguagePicker";

// Localized site footer (shared on every page). Client component so the labels
// respond to the language picker instead of being hardcoded English.
export default function SiteFooter() {
  const { t } = useT();
  const pathname = usePathname() ?? "/";
  const demoOnlyAnon = useDemoOnlyAnonymous();
  const signedIn = useSignedIn();
  if (
    demoOnlyAnon
    || isImmersiveSetupPath(pathname)
    || pathname.startsWith("/home-concepts")
    || (pathname === "/" && signedIn !== true)
  ) return null;
  return (
    <footer className="site-footer" style={{ marginTop: 40, padding: "16px 24px", borderTop: "1px solid #333",
      fontSize: 12, opacity: 0.85, display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
      <span>© 2026 Salareen ·</span>
      <Link href="/privacy">{t("footer.privacy")}</Link>
      <Link href="/terms">{t("footer.terms")}</Link>
      <Link href="/data-deletion">{t("footer.dataDeletion")}</Link>
      <Link href="/legal">{t("footer.legal")}</Link>
      <span>· {t("footer.disclaimer")}</span>
      <Link href="/transparency">{t("footer.transparency")}</Link>
      <Link href="/consent">{t("footer.consent")}</Link>
      <Link href="/contact">{t("footer.contact")}</Link>
      <Link href="/download">{t("footer.getApp")}</Link>
      <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 6 }}>
        {t("footer.language")}: <LanguagePicker compact />
      </span>
    </footer>
  );
}
