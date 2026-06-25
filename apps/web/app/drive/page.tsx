"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  getAudioCategories,
  getAudioCourse,
  getToken,
  listAudioCourses,
  type AudioCourse,
  type AudioCourseRow,
} from "../lib/api";
import SignInToUse from "../components/SignInToUse";
import { friendlyError } from "../lib/errors";
import { useT } from "../lib/i18n";
import { ensureVoices, localeToBcp47, speakNaturally } from "../lib/tts";

// Hands-free "Drive Mode": big controls, no required visuals, on-device TTS
// narration with an autoplay queue so learners keep their eyes on the road.
export default function DrivePage() {
  return (
    <Suspense fallback={<main className="container"><p className="muted">Loading Drive Mode…</p></main>}>
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
  const [assistantStatus, setAssistantStatus] = useState("Say Hey Sala or Salareen to ask a question.");
  const [assistantTranscript, setAssistantTranscript] = useState("");
  const [assistantAnswer, setAssistantAnswer] = useState("");
  const [typedQuestion, setTypedQuestion] = useState("");
  const [listening, setListening] = useState(false);
  const [loggedIn, setLoggedIn] = useState(true);   // resolved on mount
  const queue = useRef<AudioCourseRow[]>([]);
  const recognitionRef = useRef<any>(null);
  const resumeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setLoggedIn(Boolean(getToken()));
    getAudioCategories().then(setCats).catch(() => setCats([]));
    // Warm the voice list so the first segment already uses the natural voice.
    ensureVoices();
  }, []);
  const refresh = useCallback(() => {
    listAudioCourses({ category: cat, q, limit: "60" })
      .then((r) => { setRows(r.courses); setTotal(r.total); queue.current = r.courses; })
      .catch((e) => setError(String(e)));
  }, [cat, q]);
  useEffect(() => { refresh(); }, [refresh]);

  const speak = useCallback((text: string, onEnd?: () => void) => {
    try {
      // Pick the best natural/neural voice for the current language + lifelike
      // prosody (see lib/tts) instead of the default robotic voice.
      speakNaturally(text, { locale, rate, onend: onEnd });
    } catch { onEnd?.(); }
  }, [rate, locale]);

  const playSeg = useCallback((c: AudioCourse, i: number) => {
    window.speechSynthesis.cancel();
    if (i >= c.segments.length) { setPlaying(false); playNextCourse(); return; }
    setSeg(i); setPlaying(true);
    speak(`${c.segments[i].heading}. ${c.segments[i].text}`, () => playSeg(c, i + 1));
  }, [speak]); // eslint-disable-line react-hooks/exhaustive-deps

  async function startCourse(id: string) {
    if (!getToken()) { setLoggedIn(false); return; }   // preview is view-only (no audio)
    setError("");
    try {
      const c = await getAudioCourse(id);
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

  function pauseForAssistant(status = "Listening. Say Hey Sala or Salareen, then ask your question.") {
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
      setAssistantStatus(`Resuming in ${Math.round(delayMs / 1000)} seconds. Say or tap pause to stay paused.`);
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

  function startVoiceRecognition(expectWakeWord = true) {
    pauseForAssistant(expectWakeWord
      ? "Listening for Hey Sala or Salareen..."
      : "Listening for your question or command...");
    const root = window as any;
    const SpeechRecognition = root.SpeechRecognition || root.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setAssistantStatus("Voice recognition is unavailable in this browser. Type your question or use the controls.");
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
      setAssistantStatus("I could not hear that. Try again, or type your question.");
      setListening(false);
    };
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    setListening(true);
    recognition.start();
  }

  function handleSpokenInput(raw: string, expectWakeWord: boolean) {
    stopVoiceRecognition();
    const text = raw.trim();
    const hasWake = /\b(hey\s+sala|sala|salareen)\b/i.test(text);
    if (expectWakeWord && !hasWake) {
      setAssistantStatus("Wake word not detected. Say Hey Sala or Salareen before your question.");
      return;
    }
    const cleaned = text
      .replace(/\bhey\s+sala\b/ig, "")
      .replace(/\bsalareen\b/ig, "")
      .replace(/\bsala\b/ig, "")
      .trim();
    if (!cleaned) {
      setAssistantStatus("I heard you. Ask a question, say pause, resume, next, or previous.");
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
      setAssistantAnswer("Paused. Say or tap Resume when you want to continue.");
      setAssistantStatus("Paused for you.");
      setPlaying(false);
      window.speechSynthesis.cancel();
      return;
    }
    if (/\b(resume|continue|carry on|keep going)\b/.test(lower)) {
      setAssistantAnswer("Resuming the lesson.");
      resumeAfterAssistant(1000);
      return;
    }
    if (/\b(next|skip ahead)\b/.test(lower)) {
      setAssistantAnswer("Skipping to the next segment.");
      playSeg(course, Math.min(seg + 1, course.segments.length - 1));
      return;
    }
    if (/\b(previous|back|repeat)\b/.test(lower)) {
      setAssistantAnswer("Going back so you can hear that part again.");
      playSeg(course, Math.max(0, seg - 1));
      return;
    }
    const answer = answerFromCourse(course, seg, command);
    setAssistantAnswer(answer);
    setAssistantStatus("Answering your question. I will resume automatically unless you pause.");
    window.speechSynthesis.cancel();
    speak(`${answer} Would you like to resume? Say resume, or I will continue shortly.`, () => {
      resumeAfterAssistant(6500);
    });
  }

  function submitTypedQuestion() {
    const q = typedQuestion.trim();
    if (!q) return;
    setTypedQuestion("");
    pauseForAssistant("Answering your typed question.");
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
      <h1>🚗 Drive Mode — audio classes</h1>
      <p className="muted">
        {total}+ audio-only, eyes-free classes for the road. Tap a class and it
        plays hands-free with on-device narration, auto-advancing to the next.
        Keep your eyes on the road. 🛣️
      </p>
      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{friendlyError(error, t("error.offline"))}</div></div>}

      {!loggedIn && !course && <SignInToUse />}

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
          <div style={{ marginTop: 14, padding: 14, borderRadius: 14, background: "#151c34" }}>
            <strong>Say “Hey Sala” or “Salareen”</strong>
            <p className="muted" style={{ margin: "4px 0 10px" }}>
              Interrupt safely to ask a question, pause, resume, repeat, or skip.
            </p>
            <div className="row" style={{ gap: 8 }}>
              <button onClick={() => startVoiceRecognition(true)}>
                {listening ? "Listening..." : "🎙 Ask"}
              </button>
              <button onClick={() => pauseForAssistant("Paused. Ask a question or resume when ready.")}>
                Pause + Ask
              </button>
            </div>
          </div>
        </div>
      )}

      {assistantOpen && (
        <div role="dialog" aria-modal="true"
          style={{ position: "fixed", inset: 0, background: "rgba(3,7,18,0.68)",
            display: "flex", alignItems: "flex-end", justifyContent: "center", zIndex: 60 }}>
          <div className="card" style={{ width: "min(760px, 100%)", margin: 0, borderRadius: "24px 24px 0 0",
            background: "#0b1020", color: "#e8ecf6" }}>
            <h3 style={{ marginTop: 0 }}>Sala Drive Assistant</h3>
            <p className="muted">{assistantStatus}</p>
            {assistantTranscript && <p style={{ color: "#bae6fd" }}>You: {assistantTranscript}</p>}
            {assistantAnswer && <p style={{ lineHeight: 1.6 }}>{assistantAnswer}</p>}
            <input
              placeholder="Ask a question or say pause/resume..."
              value={typedQuestion}
              onChange={(e) => setTypedQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submitTypedQuestion()}
              style={{ width: "100%", padding: 12, borderRadius: 10, background: "#151c34",
                color: "#e8ecf6", border: "1px solid #23304f" }}
            />
            <div className="row" style={{ gap: 8, marginTop: 12 }}>
              <button onClick={() => startVoiceRecognition(false)}>{listening ? "Listening..." : "Mic"}</button>
              <button onClick={submitTypedQuestion}>Ask</button>
              <button onClick={() => resumeAfterAssistant()} style={{ background: "#16a34a", color: "#fff" }}>
                Resume
              </button>
              <button onClick={() => { clearResumeTimer(); setAssistantOpen(false); }}>Stay paused</button>
            </div>
          </div>
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

function answerFromCourse(course: AudioCourse, seg: number, question: string): string {
  const words = question.toLowerCase().split(/[^a-z0-9]+/).filter((w) => w.length > 3);
  const candidates = course.segments.map((segment, i) => ({
    segment,
    score: scoreSegment(segment.text, words) + (i === seg ? 2 : 0),
  })).sort((a, b) => b.score - a.score);
  const best = candidates[0]?.segment || course.segments[seg] || course.segments[0];
  const source = (best.text || "").replace(/\s+/g, " ").trim();
  const snippet = source.length > 420 ? `${source.slice(0, 420)}...` : source;
  return `Here is the course-grounded answer: ${snippet}`;
}

function scoreSegment(text: string, words: string[]): number {
  const lower = text.toLowerCase();
  return words.reduce((score, word) => score + (lower.includes(word) ? 1 : 0), 0);
}
