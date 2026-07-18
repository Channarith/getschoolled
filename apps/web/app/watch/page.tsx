"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { getAdBreaks, getMe, getToken, searchCourses, type AdBreak, type AdPlan, type CatalogCourse } from "../lib/api";
import { useT } from "../lib/i18n";
import { useFlag } from "../lib/flags";
import { effectiveAdTier } from "../lib/useCourseAds";
import VideoAdBreak from "../components/VideoAdBreak";

const COURSE_SECONDS = 60; // compressed demo runtime for the simulated player
const AD_FREE_TIERS = new Set(["pro", "premium"]);

function WatchInner() {
  const { t } = useT();
  const watchEnabled = useFlag<boolean>("engagement.watch_window", false);
  const adsEnabled = useFlag<boolean>("monetization.video_ads", false);
  const params = useSearchParams();
  const [courses, setCourses] = useState<CatalogCourse[]>([]);
  const [courseId, setCourseId] = useState(params.get("course") ?? "");
  const [tier, setTier] = useState("basic");
  const [tierLabel, setTierLabel] = useState("standard");
  const [plan, setPlan] = useState<AdPlan | null>(null);
  const [error, setError] = useState("");

  // Player state
  const [playing, setPlaying] = useState(false);
  const [contentTime, setContentTime] = useState(0);
  const [ad, setAd] = useState<AdBreak | null>(null);
  const playedMidrolls = useRef<Set<number>>(new Set());
  const log = useRef<string[]>([]);
  const [, force] = useState(0);

  useEffect(() => {
    if (!watchEnabled) return;
    searchCourses({}).then((c) => {
      setCourses(c);
      if (!courseId && c.length) setCourseId(c[0].course_id);
    }).catch((e) => setError(String(e)));
  }, [watchEnabled]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!getToken()) {
      setTier("basic");
      setTierLabel("standard (sign in for your tier)");
      return;
    }
    getMe()
      .then((acct) => {
        const t = (acct.tier || "basic").toLowerCase();
        setTier(t);
        setTierLabel(AD_FREE_TIERS.has(t) ? "VIP (ad-free)" : "standard (ads)");
      })
      .catch(() => {
        setTier("basic");
        setTierLabel("standard");
      });
  }, []);

  function note(msg: string) {
    log.current = [`${new Date().toLocaleTimeString()}  ${msg}`, ...log.current].slice(0, 8);
    force((n) => n + 1);
  }

  async function start() {
    if (!courseId) return;
    setError(""); setContentTime(0); playedMidrolls.current = new Set(); log.current = [];
    // monetization.video_ads off => no ad breaks for anyone, regardless of tier.
    if (!adsEnabled) {
      setPlan({ course_id: courseId, tier, ad_free: true, breaks: [] });
      note("Ads disabled platform-wide (monetization.video_ads off)");
      setPlaying(true);
      return;
    }
    const p = await getAdBreaks(courseId, effectiveAdTier(tier)).catch((e) => { setError(String(e)); return null; });
    if (!p) return;
    setPlan(p);
    note(p.ad_free ? `Ad-free playback (${tierLabel})` : `Loaded ${p.breaks.length} ad break(s)`);
    const pre = p.breaks.find((b) => b.position === "preroll");
    if (pre) { startAd(pre); } else { setPlaying(true); }
  }

  function startAd(b: AdBreak) {
    setAd(b); setPlaying(false);
    note(`${b.position} ad: "${b.ads[0]?.title}" (${b.ads[0]?.advertiser})`);
  }
  function endAd() {
    if (ad) note(`ad complete: ${ad.ads[0]?.title}`);
    setAd(null); setPlaying(true);
  }

  // Content ticker + mid-roll cue detection
  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => setContentTime((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [playing]);
  useEffect(() => {
    if (!plan || !playing) return;
    // Compress real cue points onto the short demo timeline.
    const scale = COURSE_SECONDS / Math.max(1, ...plan.breaks.map((b) => b.offset_s), 1);
    for (const b of plan.breaks) {
      if (b.position !== "midroll") continue;
      const cue = Math.round(b.offset_s * scale);
      if (contentTime >= cue && !playedMidrolls.current.has(b.offset_s)) {
        playedMidrolls.current.add(b.offset_s);
        startAd(b);
        break;
      }
    }
    if (contentTime >= COURSE_SECONDS) { setPlaying(false); note("course finished"); }
  }, [contentTime, plan, playing]); // eslint-disable-line react-hooks/exhaustive-deps

  const adFree = AD_FREE_TIERS.has(tier);

  if (!watchEnabled) {
    return (
      <main style={{ maxWidth: 720, margin: "0 auto", padding: 24 }}>
        <h1>Watch is temporarily unavailable</h1>
        <p className="muted">This experimental window is disabled while testing is completed.</p>
        <Link href="/browse">Browse courses</Link>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 860, margin: "0 auto", padding: 24 }}>
      <h1 style={{ marginBottom: 4 }}>{t("watch.title")}</h1>
      <p style={{ color: "#666", marginTop: 0 }}>{t("watch.intro")}</p>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", margin: "12px 0" }}>
        <select value={courseId} onChange={(e) => setCourseId(e.target.value)}
          style={{ padding: 8, minWidth: 220 }}>
          {courses.map((c) => <option key={c.course_id} value={c.course_id}>{c.title}</option>)}
        </select>
        <span style={{ padding: "8px 12px", borderRadius: 8, background: adFree ? "#14532d" : "#1e293b", color: "#e2e8f0", fontSize: 13 }}>
          {t("watch.plan")} <strong>{tierLabel}</strong>
        </span>
        <button onClick={start} disabled={!courseId}
          style={{ padding: "8px 18px", background: "#e50914", color: "#fff", border: 0, borderRadius: 6, cursor: "pointer" }}>
          {t("watch.play")}
        </button>
        {!adFree && <Link href="/account" style={{ marginLeft: "auto", fontSize: 13 }}>{t("watch.goAdFree")}</Link>}
      </div>

      {error && <p style={{ color: "#e11d48" }}>{error}</p>}

      <div style={{ position: "relative", background: "#000", borderRadius: 12, aspectRatio: "16/9", display: "flex",
        alignItems: "center", justifyContent: "center", color: "#888", marginTop: 16 }}>
        {playing ? (
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 28, color: "#fff" }}>▶ Playing course</div>
            <div style={{ color: "#aaa", marginTop: 8 }}>{contentTime}s / {COURSE_SECONDS}s</div>
          </div>
        ) : !ad ? (
          <div>Press Play to start</div>
        ) : null}
        {ad && (
          <VideoAdBreak
            adBreak={ad}
            placement={`watch-${ad.position}`}
            tier={effectiveAdTier(tier)}
            mode="inline"
            onDone={endAd}
          />
        )}
      </div>

      {log.current.length > 0 && (
        <div style={{ marginTop: 16, fontSize: 12, color: "#666", fontFamily: "monospace" }}>
          {log.current.map((l, i) => <div key={i}>{l}</div>)}
        </div>
      )}
    </main>
  );
}

export default function WatchPage() {
  return (
    <Suspense fallback={<main style={{ padding: 24 }}>Loading…</main>}>
      <WatchInner />
    </Suspense>
  );
}
