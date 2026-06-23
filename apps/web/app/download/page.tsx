"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useT } from "../lib/i18n";

// Cross-platform "Get the app" page: direct Android APK + iOS install today,
// with Google Play / App Store badges that light up once published. All target
// URLs are configurable via NEXT_PUBLIC_* (inlined at web build time); when a URL
// is unset the button shows a "Coming soon" disabled state instead of a dead link.
const ANDROID_APK_URL = process.env.NEXT_PUBLIC_ANDROID_APK_URL ?? "";
const PLAY_STORE_URL = process.env.NEXT_PUBLIC_PLAY_STORE_URL ?? "";
const IOS_APP_URL = process.env.NEXT_PUBLIC_IOS_APP_URL ?? ""; // TestFlight / install
const APP_STORE_URL = process.env.NEXT_PUBLIC_APP_STORE_URL ?? "";

function StoreButton({ href, label, sublabel, bg }: {
  href: string; label: string; sublabel: string; bg: string;
}) {
  const enabled = Boolean(href);
  const style: React.CSSProperties = {
    display: "inline-flex", flexDirection: "column", alignItems: "flex-start",
    padding: "10px 18px", borderRadius: 12, minWidth: 200,
    background: enabled ? bg : "#1d2746", color: "#fff",
    border: "1px solid rgba(255,255,255,.15)", textDecoration: "none",
    opacity: enabled ? 1 : 0.6, cursor: enabled ? "pointer" : "default",
  };
  const inner = (
    <>
      <span style={{ fontSize: 11, opacity: 0.8 }}>{sublabel}</span>
      <span style={{ fontSize: 17, fontWeight: 700 }}>{label}</span>
    </>
  );
  return enabled
    ? <a href={href} style={style} target="_blank" rel="noopener noreferrer">{inner}</a>
    : <span style={style} aria-disabled title="Coming soon">{inner}</span>;
}

export default function DownloadPage() {
  const { t } = useT();
  const [qr, setQr] = useState("");

  // Build a QR (rendered client-side only) pointing at this page so a desktop
  // visitor can scan it and open the download page on their phone.
  useEffect(() => {
    const target = ANDROID_APK_URL || PLAY_STORE_URL || window.location.href;
    setQr(`https://api.qrserver.com/v1/create-qr-code/?size=200x200&margin=8&data=${encodeURIComponent(target)}`);
  }, []);

  return (
    <main className="container" style={{ maxWidth: 880 }}>
      <h1>{t("download.title")}</h1>
      <p className="muted" style={{ fontSize: 18 }}>{t("download.subtitle")}</p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16, marginTop: 16 }}>
        {/* Android */}
        <div className="card">
          <h2 style={{ marginTop: 0 }}>🤖 {t("download.android")}</h2>
          <p className="muted">{t("download.androidNote")}</p>
          <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
            <StoreButton href={ANDROID_APK_URL} bg="#16a34a"
              sublabel={t("download.directDownload")} label={t("download.apk")} />
            <StoreButton href={PLAY_STORE_URL} bg="#000"
              sublabel={t("download.getItOn")} label="Google Play" />
          </div>
        </div>

        {/* iOS */}
        <div className="card">
          <h2 style={{ marginTop: 0 }}>🍎 {t("download.ios")}</h2>
          <p className="muted">{t("download.iosNote")}</p>
          <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
            <StoreButton href={IOS_APP_URL} bg="#0ea5e9"
              sublabel={t("download.beta")} label="TestFlight" />
            <StoreButton href={APP_STORE_URL} bg="#000"
              sublabel={t("download.downloadOn")} label="App Store" />
          </div>
        </div>
      </div>

      <div className="card" style={{ display: "flex", gap: 20, alignItems: "center", flexWrap: "wrap", marginTop: 16 }}>
        {qr && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={qr} alt={t("download.qrAlt")} width={140} height={140}
               style={{ borderRadius: 12, background: "#fff", padding: 6 }}
               onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }} />
        )}
        <div style={{ flex: "1 1 280px", minWidth: 0 }}>
          <h3 style={{ marginTop: 0 }}>{t("download.scanTitle")}</h3>
          <p className="muted">{t("download.scanNote")}</p>
          <ul style={{ lineHeight: 1.8, margin: 0 }}>
            <li>{t("download.feat1")}</li>
            <li>{t("download.feat2")}</li>
            <li>{t("download.feat3")}</li>
          </ul>
        </div>
      </div>

      <p className="muted" style={{ marginTop: 16, fontSize: 13 }}>
        {t("download.legal")} <Link href="/legal">{t("download.legalLink")}</Link>.
      </p>
    </main>
  );
}
