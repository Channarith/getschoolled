"use client";

import Link from "next/link";

import { useT } from "../lib/i18n";

// Store-badge buttons (with icons) for the front page. Targets are configurable
// via NEXT_PUBLIC_* (inlined at build); when a store URL isn't set yet the badge
// links to the in-app /download page (which shows direct APK / TestFlight installs
// and a "coming soon" state) - so the icons are never a dead end.
const PLAY = process.env.NEXT_PUBLIC_PLAY_STORE_URL
  || process.env.NEXT_PUBLIC_ANDROID_APK_URL || "/download";
const APPSTORE = process.env.NEXT_PUBLIC_APP_STORE_URL
  || process.env.NEXT_PUBLIC_IOS_APP_URL || "/download";

function AppleIcon() {
  return (
    <svg viewBox="0 0 24 24" width={26} height={26} fill="#fff" aria-hidden focusable="false">
      <path d="M17.05 12.04c-.03-2.6 2.12-3.85 2.22-3.91-1.21-1.77-3.09-2.01-3.76-2.04-1.6-.16-3.12.94-3.93.94-.81 0-2.06-.92-3.39-.89-1.74.03-3.35 1.01-4.25 2.57-1.81 3.14-.46 7.79 1.3 10.34.86 1.25 1.88 2.65 3.22 2.6 1.29-.05 1.78-.83 3.34-.83 1.56 0 2 .83 3.37.81 1.39-.03 2.27-1.27 3.12-2.53.98-1.45 1.39-2.85 1.41-2.92-.03-.01-2.71-1.04-2.74-4.12zM14.6 4.4c.71-.86 1.19-2.06 1.06-3.25-1.02.04-2.26.68-2.99 1.54-.66.76-1.23 1.98-1.08 3.15 1.14.09 2.3-.58 3.01-1.44z" />
    </svg>
  );
}

function PlayIcon() {
  return (
    <svg viewBox="0 0 24 24" width={24} height={24} aria-hidden focusable="false">
      <path d="M3.6 1.81a1 1 0 0 0-.6.92v18.54a1 1 0 0 0 .6.92l10.19-10.19L3.6 1.81z" fill="#00D4FF" />
      <path d="M3.6 1.81a1 1 0 0 1 1.04.07l11.15 6.32-2 2L3.6 1.81z" fill="#00F076" />
      <path d="M16.79 8.2l2.3 1.31c.86.49.86 1.89 0 2.38l-2.3 1.31-2-2 2-2.99z" fill="#FFC107" />
      <path d="M13.79 12l2 2L4.64 20.32a1 1 0 0 1-1.04.07L13.79 12z" fill="#FF3D44" />
    </svg>
  );
}

function Badge({ href, icon, line1, line2 }: {
  href: string; icon: React.ReactNode; line1: string; line2: string;
}) {
  const external = href.startsWith("http");
  const content = (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 10,
      background: "#000", color: "#fff", border: "1px solid rgba(255,255,255,.25)",
      borderRadius: 12, padding: "8px 16px", textDecoration: "none", minWidth: 168,
    }}>
      {icon}
      <span style={{ display: "flex", flexDirection: "column", lineHeight: 1.15, textAlign: "left" }}>
        <span style={{ fontSize: 10, opacity: 0.85, textTransform: "uppercase", letterSpacing: ".02em" }}>{line1}</span>
        <span style={{ fontSize: 18, fontWeight: 700 }}>{line2}</span>
      </span>
    </span>
  );
  return external
    ? <a href={href} target="_blank" rel="noopener noreferrer" aria-label={`${line1} ${line2}`}>{content}</a>
    : <Link href={href} aria-label={`${line1} ${line2}`}>{content}</Link>;
}

// Row of App Store + Google Play badges. `center` centers them (landing hero).
export default function AppBadges({ center = false }: { center?: boolean }) {
  const { t } = useT();
  return (
    <div style={{
      display: "flex", gap: 12, flexWrap: "wrap", marginTop: 14,
      justifyContent: center ? "center" : "flex-start",
    }}>
      <Badge href={APPSTORE} icon={<AppleIcon />}
        line1={t("download.downloadOn")} line2="App Store" />
      <Badge href={PLAY} icon={<PlayIcon />}
        line1={t("download.getItOn")} line2="Google Play" />
    </div>
  );
}
