"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { clearToken, getToken } from "../lib/api";
import { useT } from "../lib/i18n";
import LanguagePicker from "./LanguagePicker";

// Netflix-style profile dropdown: a single avatar button on the right of the nav
// that opens a menu with the user's personal surfaces (profile/account, rewards,
// themes, language, get the app, sign out) when signed in, or sign in / create
// account when signed out. Keeps the top nav focused on content tabs.
export default function ProfileMenu() {
  const { t } = useT();
  const router = useRouter();
  const pathname = usePathname() ?? "/";
  const [loggedIn, setLoggedIn] = useState(false);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLoggedIn(Boolean(getToken()));
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onEsc);
    };
  }, []);

  function signOut() {
    clearToken();
    setLoggedIn(false);
    setOpen(false);
    router.push("/");
  }

  const itemStyle: React.CSSProperties = {
    display: "block", padding: "9px 14px", color: "var(--text)",
    textDecoration: "none", fontSize: 14, borderRadius: 8,
  };

  return (
    <div ref={ref} style={{ position: "relative", marginLeft: 8 }}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t("profile.menu")}
        style={{
          display: "inline-flex", alignItems: "center", gap: 6,
          background: "transparent", border: "1px solid var(--border)",
          borderRadius: 999, padding: "4px 8px 4px 4px", cursor: "pointer",
          color: "var(--text)",
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/logo-mark.webp" alt="" width={26} height={26}
             style={{ borderRadius: "50%", display: "block" }} />
        <span aria-hidden style={{ fontSize: 10, opacity: 0.8 }}>▾</span>
      </button>

      {open && (
        <div
          role="menu"
          style={{
            position: "absolute", right: 0, top: "calc(100% + 8px)", minWidth: 240,
            background: "var(--panel)", border: "1px solid var(--border)",
            borderRadius: 12, boxShadow: "0 12px 36px rgba(0,0,0,.45)",
            padding: 8, zIndex: 1000,
          }}
        >
          {loggedIn ? (
            <>
              <Link role="menuitem" href="/account" style={itemStyle}>👤 {t("profile.account")}</Link>
              <Link role="menuitem" href="/rewards" style={itemStyle}>⭐ {t("profile.rewards")}</Link>
              <Link role="menuitem" href="/backgrounds" style={itemStyle}>🎨 {t("profile.themes")}</Link>
              <Link role="menuitem" href="/download" style={itemStyle}>📱 {t("profile.getApp")}</Link>
            </>
          ) : (
            <>
              <Link role="menuitem" href="/login" style={{ ...itemStyle, fontWeight: 700 }}>{t("profile.signIn")}</Link>
              <Link role="menuitem" href="/login" style={itemStyle}>{t("profile.createAccount")}</Link>
              <Link role="menuitem" href="/download" style={itemStyle}>📱 {t("profile.getApp")}</Link>
            </>
          )}

          <div style={{ borderTop: "1px solid var(--border)", margin: "8px 0", paddingTop: 8 }}>
            <div style={{ padding: "0 14px 6px", fontSize: 12, color: "var(--muted)" }}>
              🌐 {t("profile.language")}
            </div>
            <div style={{ padding: "0 10px" }}>
              <LanguagePicker />
            </div>
          </div>

          {loggedIn && (
            <div style={{ borderTop: "1px solid var(--border)", marginTop: 8, paddingTop: 8 }}>
              <button onClick={signOut}
                style={{ ...itemStyle, width: "100%", textAlign: "left",
                         background: "transparent", border: 0, cursor: "pointer" }}>
                ⏻ {t("profile.signOut")}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
