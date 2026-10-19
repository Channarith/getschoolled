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
      {/* Legal is the single destination for Privacy, Terms, Data Deletion,
          and Rewards & Sweepstakes rules — users asked for one link, one page.
          Consent is no longer a footer link; it moved into onboarding so new
          users tick it once at sign-up and don't need to hunt it down later. */}
      <Link href="/legal" title="Privacy, Terms, Data Deletion, Sweepstakes Rules">
        {t("footer.legal")}
      </Link>
      <Link href="/transparency">{t("footer.transparency")}</Link>
      <Link href="/contact">{t("footer.contact")}</Link>
      <Link href="/download">{t("footer.getApp")}</Link>
      <span>· {t("footer.disclaimer")}</span>
      <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 6 }}>
        {t("footer.language")}: <LanguagePicker compact />
      </span>
    </footer>
  );
}
