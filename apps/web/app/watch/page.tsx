"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { getAdBreaks, searchCourses, type AdBreak, type AdPlan, type CatalogCourse } from "../lib/api";

const COURSE_SECONDS = 60; // compressed demo runtime for the simulated player

function WatchInner() {
  const params = useSearchParams();
  const [courses, setCourses] = useState<CatalogCourse[]>([]);
  const [courseId, setCourseId] = useState(params.get("course") ?? "");
  const [tier, setTier] = useState("free");
  const [plan, setPlan] = useState<AdPlan | null>(null);
  const [error, setError] = useState("");

  // Player state
  const [playing, setPlaying] = useState(false);
  const [contentTime, setContentTime] = useState(0);
  const [ad, setAd] = useState<AdBreak | null>(null);
  const [adTime, setAdTime] = useState(0);
  const playedMidrolls = useRef<Set<number>>(new Set());
  const log = useRef<string[]>([]);
  const [, force] = useState(0);

  useEffect(() => {
    searchCourses({}).then((c) => {
      setCourses(c);
      if (!courseId && c.length) setCourseId(c[0].course_id);
    }).catch((e) => setError(String(e)));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function note(msg: string) {
    log.current = [`${new Date().toLocaleTimeString()}  ${msg}`, ...log.current].slice(0, 8);
    force((n) => n + 1);
  }

  async function start() {
    if (!courseId) return;
    setError(""); setContentTime(0); playedMidrolls.current = new Set(); log.current = [];
    const p = await getAdBreaks(courseId, tier).catch((e) => { setError(String(e)); return null; });
    if (!p) return;
    setPlan(p);
    note(p.ad_free ? `Ad-free playback (${tier} member)` : `Loaded ${p.breaks.length} ad break(s)`);
    const pre = p.breaks.find((b) => b.position === "preroll");
    if (pre) { startAd(pre); } else { setPlaying(true); }
  }

  function startAd(b: AdBreak) {
    setAd(b); setAdTime(0); setPlaying(false);
    note(`${b.position} ad: "${b.ads[0]?.title}" (${b.ads[0]?.advertiser})`);
  }
  function endAd() {
    if (ad) note(`ad complete: ${ad.ads[0]?.title}`);
    setAd(null); setPlaying(true);
  }

  // Ad ticker
  useEffect(() => {
    if (!ad) return;
    const t = setInterval(() => setAdTime((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [ad]);
  useEffect(() => {
    const dur = ad?.ads[0]?.duration_s ?? 0;
    if (ad && adTime >= dur) endAd();
  }, [adTime, ad]); // eslint-disable-line react-hooks/exhaustive-deps

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

  const skipIn = ad ? Math.max(0, (ad.ads[0]?.skippable_after_s ?? 9999) - adTime) : 0;
  const canSkip = ad ? adTime >= (ad.ads[0]?.skippable_after_s ?? Infinity) : false;

  return (
    <main style={{ maxWidth: 860, margin: "0 auto", padding: 24 }}>
      <h1 style={{ marginBottom: 4 }}>Watch</h1>
      <p style={{ color: "#666", marginTop: 0 }}>
        Course playback with monetized video ads (IAB VAST/VMAP). Paid tiers are ad-free.
      </p>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", margin: "12px 0" }}>
        <select value={courseId} onChange={(e) => setCourseId(e.target.value)}
          style={{ padding: 8, minWidth: 220 }}>
          {courses.map((c) => <option key={c.course_id} value={c.course_id}>{c.title}</option>)}
        </select>
        <label>Tier:&nbsp;
          <select value={tier} onChange={(e) => setTier(e.target.value)} style={{ padding: 8 }}>
            <option value="free">free (ads)</option>
            <option value="basic">basic (ads)</option>
            <option value="pro">pro (ad-free)</option>
            <option value="premium">premium (ad-free)</option>
          </select>
        </label>
        <button onClick={start} disabled={!courseId}
          style={{ padding: "8px 18px", background: "#e50914", color: "#fff", border: 0, borderRadius: 6, cursor: "pointer" }}>
          ▶ Play
        </button>
        <Link href="/account" style={{ marginLeft: "auto", fontSize: 13 }}>Go ad-free →</Link>
      </div>

      {error && <p style={{ color: "#b00" }}>{error}</p>}

      <div style={{ position: "relative", background: "#000", borderRadius: 10, aspectRatio: "16 / 9",
        display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", overflow: "hidden" }}>
        {ad ? (
          <div style={{ textAlign: "center" }}>
            <div style={{ position: "absolute", top: 10, left: 10, background: "#facc15", color: "#000",
              fontWeight: 700, fontSize: 12, padding: "2px 8px", borderRadius: 4 }}>
              Ad · {ad.position}
            </div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{ad.ads[0]?.title}</div>
            <div style={{ opacity: 0.7, marginTop: 6 }}>{ad.ads[0]?.advertiser} · {ad.ads[0]?.duration_s}s</div>
            <div style={{ marginTop: 16 }}>
              <button onClick={endAd} disabled={!canSkip}
                style={{ padding: "8px 16px", borderRadius: 6, border: 0, cursor: canSkip ? "pointer" : "not-allowed",
                  background: canSkip ? "#fff" : "#555", color: canSkip ? "#000" : "#aaa" }}>
                {canSkip ? "Skip Ad ⏭" : `Skip in ${skipIn}s`}
              </button>
            </div>
          </div>
        ) : playing ? (
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 20, fontWeight: 700 }}>▶ Now playing</div>
            <div style={{ opacity: 0.8 }}>{courses.find((c) => c.course_id === courseId)?.title}</div>
            <div style={{ opacity: 0.6, marginTop: 8 }}>{contentTime}s / {COURSE_SECONDS}s</div>
          </div>
        ) : (
          <div style={{ opacity: 0.6 }}>Press Play to start</div>
        )}
        {/* progress bar */}
        <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 5, background: "#333" }}>
          <div style={{ height: "100%", width: `${Math.min(100, (contentTime / COURSE_SECONDS) * 100)}%`,
            background: "#e50914" }} />
        </div>
      </div>

      {plan && (
        <p style={{ marginTop: 10, fontSize: 13, color: plan.ad_free ? "#16a34a" : "#666" }}>
          {plan.ad_free
            ? "✓ Ad-free experience for this membership tier."
            : `Monetized: ${plan.breaks.length} ad break(s) scheduled (pre-roll + mid-rolls).`}
        </p>
      )}

      {log.current.length > 0 && (
        <pre style={{ background: "#0b1020", color: "#9ee", padding: 12, borderRadius: 8, fontSize: 12,
          marginTop: 12, whiteSpace: "pre-wrap" }}>{log.current.join("\n")}</pre>
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
