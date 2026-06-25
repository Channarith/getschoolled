"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { AUTH_EVENT, getToken, getFlag } from "../lib/api";
import { useT } from "../lib/i18n";
import ProfileMenu from "./ProfileMenu";

// Top navigation. Content tabs (Browse, For You, Kids, Corporate, … Homework)
// are GATED: signed-out visitors only see the brand, Our Story, and Sign in.
// Personal/settings surfaces live in the ProfileMenu dropdown on the right.
export default function LocalizedNav({ appVersion }: { appVersion: string }) {
  const { t } = useT();
  const pathname = usePathname() ?? "/";

  const [unlocked, setUnlocked] = useState(false);
  const [homeworkOn, setHomeworkOn] = useState(false);
  useEffect(() => {
    const sync = () => {
      setUnlocked(Boolean(getToken()));
      getFlag("access.homework_grader")
        .then((v) => setHomeworkOn(Boolean(v)))
        .catch(() => setHomeworkOn(false));
    };
    sync();
    window.addEventListener(AUTH_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(AUTH_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
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
      <Link href="/our-story">{t("nav.ourStory")}</Link>

      {unlocked ? (
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
          <Link href="/watch">{t("nav.watch")}</Link>
          <Link href="/class">{t("nav.liveClass")}</Link>
          <Link href="/group-classes">{t("nav.groupClasses")}</Link>
          {/* Homework grader: hidden unless the access.homework_grader flag is on. */}
          {homeworkOn && <Link href="/homework">{t("nav.homework")}</Link>}
        </>
      ) : (
        <Link href="/login">{t("nav.signin")}</Link>
      )}

      <span
        title="This platform is AI-instructed; see the Transparency page."
        style={{ marginLeft: "auto", fontSize: 12, padding: "2px 8px",
                 borderRadius: 999, border: "1px solid currentColor", opacity: 0.85 }}
      >
        AI-instructed
      </span>
      <ProfileMenu />
      <span className="version" title="App version"
            style={{ opacity: 0.7, fontSize: 12 }}>
        v{appVersion}
      </span>
    </nav>
  );
}
