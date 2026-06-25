"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  getAudioCategories,
  getAudioCourse,
  getToken,
  listAudioCourses,
  listStudents,
  type AudioCourse,
  type AudioCourseRow,
} from "../lib/api";
import SignInToUse from "../components/SignInToUse";
import { friendlyError } from "../lib/errors";
import { useT } from "../lib/i18n";
import { getNarrationVoicePref, setNarrationVoicePref } from "../lib/narrationPrefs";
import { ensureVoices, localeToBcp47, speakNaturally } from "../lib/tts";
import {
  NARRATION_VOICE_LABELS, NARRATION_VOICE_STYLES, prosodyForStyle, resolveVoiceStyle,
  type NarrationVoicePref, type NarrationVoiceStyle,
} from "../lib/voiceProfiles";

// Hands-free "Drive Mode": big controls, no required visuals, on-device TTS
// narration with an autoplay queue so learners keep their eyes on the road.
export default function DrivePage() {
  const { t } = useT();
  return (
    <Suspense fallback={<main className="container"><p className="muted">{t("drive.loading")}</p></main>}>
      <DrivePageInner />
    </Suspense>
  );
}

function DrivePageInner() {
  const { t, locale } = useT();
  const searchParams = useSearchParams();
  const deepLinkCourse = searchParams.get("course");
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
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [assistantStatus, setAssistantStatus] = useState("");
  const [assistantTranscript, setAssistantTranscript] = useState("");
  const [assistantAnswer, setAssistantAnswer] = useState("");
  const [typedQuestion, setTypedQuestion] = useState("");
  const [listening, setListening] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);
  const [narrationPref, setNarrationPref] = useState<NarrationVoicePref>("auto");
  const queue = useRef<AudioCourseRow[]>([]);
  const recognitionRef = useRef<any>(null);
  const resumeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const voiceStyleRef = useRef<NarrationVoiceStyle>("standard");

  async function refreshVoiceStyle() {
    setNarrationPref(getNarrationVoicePref());
    let student = null;
    try {
      student = (await listStudents()).students[0] ?? null;
    } catch { /* guest */ }
    voiceStyleRef.current = resolveVoiceStyle(getNarrationVoicePref(), student);
  }

  useEffect(() => {
    setAssistantStatus(t("drive.assistantDefault"));
  }, [t]);

  useEffect(() => {
    setLoggedIn(Boolean(getToken()));
    if (!getToken()) return;
    getAudioCategories(locale).then(setCats).catch(() => setCats([]));
    ensureVoices();
    void refreshVoiceStyle();
  }, [locale]);
  const refresh = useCallback(() => {
    if (!getToken()) return;
    listAudioCourses({ category: cat, q, limit: "60" }, locale)
      .then((r) => { setRows(r.courses); setTotal(r.total); queue.current = r.courses; })
      .catch((e) => setError(String(e)));
  }, [cat, q, locale]);
  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => {
    if (!course || !loggedIn) return;
    getAudioCourse(course.id, locale)
      .then((c) => setCourse(c))
      .catch(() => {});
  }, [locale, course?.id, loggedIn]);

  const speak = useCallback((text: string, onEnd?: () => void) => {
    try {
      const style = voiceStyleRef.current;
      const base = prosodyForStyle(style).rate;
      speakNaturally(text, {
        locale,
        voiceStyle: style,
        rate: base * rate,
        onend: onEnd,
      });
    } catch { onEnd?.(); }
  }, [rate, locale]);

  const playSeg = useCallback((c: AudioCourse, i: number) => {
    window.speechSynthesis.cancel();
    if (i >= c.segments.length) { setPlaying(false); playNextCourse(); return; }
    setSeg(i); setPlaying(true);
    speak(`${c.segments[i].heading}. ${c.segments[i].text}`, () => playSeg(c, i + 1));
  }, [speak]); // eslint-disable-line react-hooks/exhaustive-deps

  const replayCurrentSegment = useCallback(() => {
    if (!course) return;
    window.speechSynthesis.cancel();
    const s = course.segments[seg];
    if (!s) return;
    setPlaying(true);
    speak(`${s.heading}. ${s.text}`, () => playSeg(course, seg + 1));
  }, [course, seg, speak, playSeg]);

  const prevRateRef = useRef(rate);
  const prevNarrationPrefRef = useRef(narrationPref);
  useEffect(() => {
    if (prevRateRef.current === rate && prevNarrationPrefRef.current === narrationPref) return;
    prevRateRef.current = rate;
    prevNarrationPrefRef.current = narrationPref;
    if (!playing || !course) return;
    replayCurrentSegment();
  }, [rate, narrationPref, playing, course, replayCurrentSegment]);

  async function startCourse(id: string) {
    if (!getToken()) { setLoggedIn(false); return; }   // preview is view-only (no audio)
    setError("");
    try {
      const c = await getAudioCourse(id, locale);
      setCourse(c); setSeg(0);
      playSeg(c, 0);
    } catch (e) { setError(String(e)); }
  }

  useEffect(() => {
    if (!deepLinkCourse || !loggedIn) return;
    void startCourse(deepLinkCourse);
  }, [deepLinkCourse, loggedIn]); // eslint-disable-line react-hooks/exhaustive-deps

  function playNextCourse() {
    if (!course) return;
    const idx = queue.current.findIndex((r) => r.id === course.id);
    const next = queue.current[idx + 1];
    if (next) startCourse(next.id);
  }

  function clearResumeTimer() {
    if (resumeTimerRef.current) {
      clearTimeout(resumeTimerRef.current);
      resumeTimerRef.current = null;
    }
  }

  function pause() { window.speechSynthesis.pause(); setPlaying(false); }
  function resume() { window.speechSynthesis.resume(); setPlaying(true); }
  function stop() {
    clearResumeTimer();
    stopVoiceRecognition();
    window.speechSynthesis.cancel();
    setPlaying(false);
    setCourse(null);
    setAssistantOpen(false);
  }

  function pauseForAssistant(status = t("drive.listenStatus")) {
    clearResumeTimer();
    window.speechSynthesis.cancel();
    setPlaying(false);
    setAssistantOpen(true);
    setAssistantStatus(status);
    setAssistantAnswer("");
  }

  function resumeAfterAssistant(delayMs = 0) {
    if (!course) return;
    clearResumeTimer();
    const go = () => {
      setAssistantOpen(false);
      playSeg(course, seg);
    };
    if (delayMs > 0) {
      setAssistantStatus(t("drive.resumingIn", { seconds: Math.round(delayMs / 1000) }));
      resumeTimerRef.current = setTimeout(go, delayMs);
    } else {
      go();
    }
  }

  function stopVoiceRecognition() {
    try { recognitionRef.current?.stop?.(); } catch { /* ignore */ }
    recognitionRef.current = null;
    setListening(false);
  }

  function startVoiceRecognition(expectWakeWord = false) {
    pauseForAssistant(t("drive.listenQuestion"));
    const root = window as any;
    const SpeechRecognition = root.SpeechRecognition || root.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setAssistantStatus(t("drive.voiceUnavailable"));
      return;
    }
    stopVoiceRecognition();
    const recognition = new SpeechRecognition();
    recognition.lang = localeToBcp47(locale);
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.onresult = (event: any) => {
      const text = Array.from(event.results || [])
        .map((result: any) => result?.[0]?.transcript || "")
        .join(" ")
        .trim();
      setAssistantTranscript(text);
      handleSpokenInput(text, expectWakeWord);
    };
    recognition.onerror = () => {
      setAssistantStatus(t("drive.hearRetry"));
      setListening(false);
    };
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    setListening(true);
    recognition.start();
  }

  function handleSpokenInput(raw: string, _expectWakeWord: boolean) {
    stopVoiceRecognition();
    const text = raw.trim();
    const cleaned = text
      .replace(/\bhey\s+sala\b/ig, "")
      .replace(/\bsalareen\b/ig, "")
      .replace(/\bsala\b/ig, "")
      .trim();
    if (!cleaned) {
      setAssistantStatus(t("drive.heardPrompt"));
      startVoiceRecognition(false);
      return;
    }
    handleAssistantQuestion(cleaned);
  }

  function handleAssistantQuestion(input: string) {
    if (!course) return;
    clearResumeTimer();
    const command = input.trim();
    if (!command) return;
    setAssistantTranscript(command);
    const lower = command.toLowerCase();
    if (/\b(pause|stop|hold)\b/.test(lower)) {
      setAssistantAnswer(t("drive.pausedAnswer"));
      setAssistantStatus(t("drive.pausedStatus"));
      setPlaying(false);
      window.speechSynthesis.cancel();
      return;
    }
    if (/\b(resume|continue|carry on|keep going)\b/.test(lower)) {
      setAssistantAnswer(t("drive.resumingAnswer"));
      resumeAfterAssistant(1000);
      return;
    }
    if (/\b(next|skip ahead)\b/.test(lower)) {
      setAssistantAnswer(t("drive.skipAnswer"));
      playSeg(course, Math.min(seg + 1, course.segments.length - 1));
      return;
    }
    if (/\b(previous|back|repeat)\b/.test(lower)) {
      setAssistantAnswer(t("drive.repeatAnswer"));
      playSeg(course, Math.max(0, seg - 1));
      return;
    }
    const answer = answerFromCourse(course, seg, command, t);
    setAssistantAnswer(answer);
    setAssistantStatus(t("drive.answeringStatus"));
    window.speechSynthesis.cancel();
    speak(t("drive.resumePrompt", { answer }), () => {
      resumeAfterAssistant(6500);
    });
  }

  function submitTypedQuestion() {
    const q = typedQuestion.trim();
    if (!q) return;
    setTypedQuestion("");
    pauseForAssistant(t("drive.typedQuestion"));
    handleAssistantQuestion(q);
  }

  useEffect(() => () => {
    clearResumeTimer();
    stopVoiceRecognition();
    try { window.speechSynthesis.cancel(); } catch { /* */ }
  }, []);

  const BIG = { fontSize: 22, padding: "16px 22px", borderRadius: 14 };

  return (
    <main className="container" style={{ maxWidth: 900 }}>
      <h1>{t("drive.pageTitle")}</h1>
      <p className="muted">
        {t("drive.pageIntro", { total })}
      </p>
      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{friendlyError(error, t("error.offline"))}</div></div>}

      {!loggedIn && <SignInToUse body={t("drive.signInBody")} />}

      {/* Now playing */}
      {loggedIn && course && (
        <div className="card" style={{ borderColor: "#0ea5e9", background: "#0b1020", color: "#e8ecf6" }}>
          <div className="muted">{course.category} · {course.duration_min} min · audio</div>
          <h2 style={{ margin: "4px 0" }}>{course.title}</h2>
          <div style={{ fontSize: 18, margin: "8px 0" }}>
            ▶ {course.segments[seg]?.heading} <span className="muted">({seg + 1}/{course.segments.length})</span>
          </div>
          <div style={{ margin: "8px 0 14px" }}>
            <input
              type="range"
              min={0}
              max={Math.max(0, course.segments.length - 1)}
              value={seg}
              onChange={(e) => {
                const i = Number(e.target.value);
                window.speechSynthesis.cancel();
                playSeg(course, i);
              }}
              style={{ width: "100%", accentColor: "#0ea5e9", cursor: "pointer" }}
              aria-label="Course progress"
            />
            <div style={{ height: 4, background: "#1d2746", borderRadius: 6, overflow: "hidden", marginTop: 6 }}>
              <div style={{ height: "100%", width: `${((seg + 1) / course.segments.length) * 100}%`, background: "#0ea5e9" }} />
            </div>
          </div>
          <div className="row" style={{ gap: 12 }}>
            <button onClick={() => playSeg(course, Math.max(0, seg - 1))} style={BIG}>⏮</button>
            {playing
              ? <button onClick={pause} style={{ ...BIG, background: "#f59e0b" }}>{t("drive.pause")}</button>
              : <button onClick={resume} style={{ ...BIG, background: "#16a34a", color: "#fff" }}>{t("drive.play")}</button>}
            <button onClick={() => playSeg(course, seg + 1)} style={BIG}>⏭</button>
            <button onClick={stop} style={{ ...BIG, background: "#e11d48", color: "#fff" }}>⏹</button>
            <button onClick={() => startVoiceRecognition(false)} style={BIG}>🎙 {t("drive.ask")}</button>
            <label style={{ marginLeft: "auto", color: "#9aa6c2" }}>
              {t("drive.speed")}&nbsp;
              <select value={rate} onChange={(e) => setRate(Number(e.target.value))}>
                {[0.5, 1, 2, 3].map((r) => <option key={r} value={r}>{r}x</option>)}
              </select>
            </label>
          </div>
          <div className="row" style={{ gap: 8, marginTop: 10, flexWrap: "wrap", alignItems: "center" }}>
            <span className="muted" style={{ fontSize: 13 }}>{t("drive.narrationVoice")}</span>
            {(["auto", ...NARRATION_VOICE_STYLES] as NarrationVoicePref[]).map((pref) => {
              const on = narrationPref === pref;
              const label = pref === "auto" ? t("drive.autoProfile") : NARRATION_VOICE_LABELS[pref];
              return (
                <button
                  key={pref}
                  type="button"
                  onClick={() => {
                    setNarrationVoicePref(pref);
                    setNarrationPref(pref);
                    void refreshVoiceStyle();
                  }}
                  style={{
                    padding: "6px 10px",
                    borderRadius: 999,
                    border: on ? "1px solid #0ea5e9" : "1px solid #334155",
                    background: on ? "#0ea5e9" : "transparent",
                    color: on ? "#001022" : "#9aa6c2",
                    fontWeight: 700,
                    fontSize: 12,
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>
          <p className="muted" style={{ marginTop: 10, fontSize: 13 }}>
            {t("drive.autoAdvance")}
          </p>
        </div>
      )}

      {loggedIn && assistantOpen && (
        <div role="dialog" aria-modal="true"
          style={{ position: "fixed", inset: 0, background: "rgba(3,7,18,0.68)",
            display: "flex", alignItems: "flex-end", justifyContent: "center", zIndex: 60 }}>
          <div className="card" style={{ width: "min(760px, 100%)", margin: 0, borderRadius: "24px 24px 0 0",
            background: "#0b1020", color: "#e8ecf6" }}>
            <h3 style={{ marginTop: 0 }}>{t("drive.assistantTitle")}</h3>
            <p className="muted">{assistantStatus}</p>
            {assistantTranscript && <p style={{ color: "#bae6fd" }}>{t("drive.youSaid")} {assistantTranscript}</p>}
            {assistantAnswer && <p style={{ lineHeight: 1.6 }}>{assistantAnswer}</p>}
            <input
              placeholder={t("drive.askPlaceholder")}
              value={typedQuestion}
              onChange={(e) => setTypedQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submitTypedQuestion()}
              style={{ width: "100%", padding: 12, borderRadius: 10, background: "#151c34",
                color: "#e8ecf6", border: "1px solid #23304f" }}
            />
            <div className="row" style={{ gap: 8, marginTop: 12 }}>
              <button onClick={() => startVoiceRecognition(false)}>{listening ? t("drive.listening") : t("drive.mic")}</button>
              <button onClick={submitTypedQuestion}>{t("drive.send")}</button>
              <button onClick={() => resumeAfterAssistant()} style={{ background: "#16a34a", color: "#fff" }}>
                {t("drive.resume")}
              </button>
              <button onClick={() => { clearResumeTimer(); setAssistantOpen(false); }}>{t("drive.stayPaused")}</button>
            </div>
          </div>
        </div>
      )}

      {loggedIn && (
      <>
      {/* Browse */}
      <div className="card">
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <input placeholder={t("drive.searchPlaceholder")} value={q} onChange={(e) => setQ(e.target.value)}
            style={{ flex: 1, minWidth: 200, padding: 10 }} />
          <select value={cat} onChange={(e) => setCat(e.target.value)} style={{ padding: 10 }}>
            <option value="">{t("drive.allCategories")}</option>
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
              {r.category} · {r.duration_min} min · {r.segments} {t("drive.segments")}
            </div>
            <span className="pill" style={{ color: "#16a34a", fontSize: 11 }}>{t("drive.eyesFree")}</span>
          </button>
        ))}
        {rows.length === 0 && <div className="muted">{t("drive.noMatch")}</div>}
      </div>
      </>
      )}
    </main>
  );
}

function answerFromCourse(
  course: AudioCourse,
  seg: number,
  question: string,
  t: (key: string, vars?: Record<string, string | number>) => string,
): string {
  const words = question.toLowerCase().split(/[^a-z0-9]+/).filter((w) => w.length > 3);
  const candidates = course.segments.map((segment, i) => ({
    segment,
    score: scoreSegment(segment.text, words) + (i === seg ? 2 : 0),
  })).sort((a, b) => b.score - a.score);
  const best = candidates[0]?.segment || course.segments[seg] || course.segments[0];
  const source = (best.text || "").replace(/\s+/g, " ").trim();
  const snippet = source.length > 420 ? `${source.slice(0, 420)}...` : source;
  return t("drive.groundedAnswer", { snippet });
}

function scoreSegment(text: string, words: string[]): number {
  const lower = text.toLowerCase();
  return words.reduce((score, word) => score + (lower.includes(word) ? 1 : 0), 0);
}
