"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getAudioCategories,
  getAudioCourse,
  listAudioCourses,
  type AudioCourse,
  type AudioCourseRow,
} from "../lib/api";

// Hands-free "Drive Mode": big controls, no required visuals, on-device TTS
// narration with an autoplay queue so learners keep their eyes on the road.
export default function DrivePage() {
  const [cats, setCats] = useState<{ category: string; count: number }[]>([]);
  const [cat, setCat] = useState<string>("");
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<AudioCourseRow[]>([]);
  const [total, setTotal] = useState(0);
  const [course, setCourse] = useState<AudioCourse | null>(null);
  const [seg, setSeg] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1);
  const [error, setError] = useState("");
  const queue = useRef<AudioCourseRow[]>([]);

  useEffect(() => {
    getAudioCategories().then(setCats).catch(() => setCats([]));
  }, []);
  const refresh = useCallback(() => {
    listAudioCourses({ category: cat, q, limit: "60" })
      .then((r) => { setRows(r.courses); setTotal(r.total); queue.current = r.courses; })
      .catch((e) => setError(String(e)));
  }, [cat, q]);
  useEffect(() => { refresh(); }, [refresh]);

  const speak = useCallback((text: string, onEnd?: () => void) => {
    try {
      const u = new SpeechSynthesisUtterance(text);
      u.rate = rate;
      u.onend = () => onEnd?.();
      window.speechSynthesis.speak(u);
    } catch { onEnd?.(); }
  }, [rate]);

  const playSeg = useCallback((c: AudioCourse, i: number) => {
    window.speechSynthesis.cancel();
    if (i >= c.segments.length) { setPlaying(false); playNextCourse(); return; }
    setSeg(i); setPlaying(true);
    speak(`${c.segments[i].heading}. ${c.segments[i].text}`, () => playSeg(c, i + 1));
  }, [speak]); // eslint-disable-line react-hooks/exhaustive-deps

  async function startCourse(id: string) {
    setError("");
    try {
      const c = await getAudioCourse(id);
      setCourse(c); setSeg(0);
      playSeg(c, 0);
    } catch (e) { setError(String(e)); }
  }

  function playNextCourse() {
    if (!course) return;
    const idx = queue.current.findIndex((r) => r.id === course.id);
    const next = queue.current[idx + 1];
    if (next) startCourse(next.id);
  }

  function pause() { window.speechSynthesis.pause(); setPlaying(false); }
  function resume() { window.speechSynthesis.resume(); setPlaying(true); }
  function stop() { window.speechSynthesis.cancel(); setPlaying(false); setCourse(null); }

  useEffect(() => () => { try { window.speechSynthesis.cancel(); } catch { /* */ } }, []);

  const BIG = { fontSize: 22, padding: "16px 22px", borderRadius: 14 };

  return (
    <main className="container" style={{ maxWidth: 900 }}>
      <h1>🚗 Drive Mode — audio classes</h1>
      <p className="muted">
        {total}+ audio-only, eyes-free classes for the road. Tap a class and it
        plays hands-free with on-device narration, auto-advancing to the next.
        Keep your eyes on the road. 🛣️
      </p>
      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}

      {/* Now playing */}
      {course && (
        <div className="card" style={{ borderColor: "#0ea5e9", background: "#0b1020", color: "#e8ecf6" }}>
          <div className="muted">{course.category} · {course.duration_min} min · audio</div>
          <h2 style={{ margin: "4px 0" }}>{course.title}</h2>
          <div style={{ fontSize: 18, margin: "8px 0" }}>
            ▶ {course.segments[seg]?.heading} <span className="muted">({seg + 1}/{course.segments.length})</span>
          </div>
          <div style={{ height: 8, background: "#1d2746", borderRadius: 6, overflow: "hidden", margin: "8px 0 14px" }}>
            <div style={{ height: "100%", width: `${((seg + 1) / course.segments.length) * 100}%`, background: "#0ea5e9" }} />
          </div>
          <div className="row" style={{ gap: 12 }}>
            <button onClick={() => playSeg(course, Math.max(0, seg - 1))} style={BIG}>⏮</button>
            {playing
              ? <button onClick={pause} style={{ ...BIG, background: "#f59e0b" }}>⏸ Pause</button>
              : <button onClick={resume} style={{ ...BIG, background: "#16a34a", color: "#fff" }}>▶ Play</button>}
            <button onClick={() => playSeg(course, seg + 1)} style={BIG}>⏭</button>
            <button onClick={stop} style={{ ...BIG, background: "#e11d48", color: "#fff" }}>⏹</button>
            <label style={{ marginLeft: "auto", color: "#9aa6c2" }}>
              Speed&nbsp;
              <select value={rate} onChange={(e) => setRate(Number(e.target.value))}>
                {[0.75, 1, 1.25, 1.5].map((r) => <option key={r} value={r}>{r}x</option>)}
              </select>
            </label>
          </div>
          <p className="muted" style={{ marginTop: 10, fontSize: 13 }}>
            Auto-advances to the next class when this one finishes.
          </p>
        </div>
      )}

      {/* Browse */}
      <div className="card">
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <input placeholder="Search audio classes…" value={q} onChange={(e) => setQ(e.target.value)}
            style={{ flex: 1, minWidth: 200, padding: 10 }} />
          <select value={cat} onChange={(e) => setCat(e.target.value)} style={{ padding: 10 }}>
            <option value="">All categories</option>
            {cats.map((c) => <option key={c.category} value={c.category}>{c.category} ({c.count})</option>)}
          </select>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px,1fr))", gap: 12 }}>
        {rows.map((r) => (
          <button key={r.id} onClick={() => startCourse(r.id)}
            style={{ textAlign: "left", background: "var(--panel)", color: "var(--text)",
              border: course?.id === r.id ? "2px solid #0ea5e9" : "1px solid var(--border)",
              borderRadius: 12, padding: 14, cursor: "pointer" }}>
            <div style={{ fontWeight: 700 }}>🎧 {r.title}</div>
            <div className="muted" style={{ fontSize: 12 }}>
              {r.category} · {r.duration_min} min · {r.segments} segments
            </div>
            <span className="pill" style={{ color: "#16a34a", fontSize: 11 }}>eyes-free</span>
          </button>
        ))}
        {rows.length === 0 && <div className="muted">No audio classes match.</div>}
      </div>
    </main>
  );
}
