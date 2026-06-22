"use client";

import { useEffect, useRef, useState } from "react";
import {
  advance,
  ask,
  getDisclosure,
  getPostClassSurvey,
  listLessons,
  reportIssue,
  startSession,
  submitPostClassSurvey,
  type Answer,
  type Disclosure,
  type Lesson,
  type SessionView,
  type Slide,
  type SurveyTemplate,
} from "../lib/api";

export default function ClassPage() {
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [lessonId, setLessonId] = useState<string>("");
  const [classType, setClassType] = useState<string>("group");
  const [view, setView] = useState<SessionView | null>(null);
  const [slide, setSlide] = useState<Slide | null>(null);
  const [question, setQuestion] = useState("");
  const [chat, setChat] = useState<
    {
      role: string;
      text: string;
      citations?: string[];
      grounded?: boolean;
      confidence?: number;
      unsupported?: string[];
    }[]
  >([]);
  const [error, setError] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [disclosure, setDisclosure] = useState<Disclosure | null>(null);
  const [survey, setSurvey] = useState<SurveyTemplate | null>(null);
  const [surveyAnswers, setSurveyAnswers] = useState<Record<string, string | number | boolean>>({});
  const [surveyDone, setSurveyDone] = useState(false);
  const [speakAnswers, setSpeakAnswers] = useState(true);
  const [speaking, setSpeaking] = useState(false);
  const speechRef = useRef<SpeechSynthesisUtterance | null>(null);

  useEffect(() => {
    listLessons()
      .then((ls) => {
        setLessons(ls);
        if (ls.length) setLessonId(ls[0].lesson_id);
      })
      .catch((e) => setError(String(e)));
    getDisclosure()
      .then(setDisclosure)
      .catch(() => setDisclosure(null));
    return () => stopSpeaking();
  }, []);

  function stopSpeaking() {
    try { window.speechSynthesis.cancel(); } catch { /* no browser TTS */ }
    speechRef.current = null;
    setSpeaking(false);
  }

  function speak(text: string) {
    if (!speakAnswers || typeof window === "undefined" || !("speechSynthesis" in window)) return;
    stopSpeaking();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    speechRef.current = utterance;
    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }

  async function onStart() {
    setError("");
    setBusy(true);
    try {
      const v = await startSession(lessonId, classType);
      setView(v);
      setSlide(v.slide);
      setChat([]);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onAdvance() {
    if (!view) return;
    setBusy(true);
    try {
      const s = await advance(view.session.session_id);
      setSlide(s);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  // End the class: if the post-class survey flag is on, prompt the survey.
  async function onFinish() {
    if (!view) return;
    setBusy(true);
    try {
      const res = await getPostClassSurvey();
      if (res.enabled && res.template) {
        setSurvey(res.template);
        setSurveyAnswers({});
        setSurveyDone(false);
      } else {
        window.alert("Class complete. Thanks for attending!");
        setView(null);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onSubmitSurvey() {
    if (!view) return;
    const overall = Number(surveyAnswers["overall"] ?? 0);
    if (!overall) {
      setError("Please give an overall rating.");
      return;
    }
    setBusy(true);
    try {
      await submitPostClassSurvey({
        course_id: lessonId,
        class_type: classType,
        overall,
        clarity: surveyAnswers["clarity"] != null ? Number(surveyAnswers["clarity"]) : null,
        pace: (surveyAnswers["pace"] as string) ?? null,
        would_recommend:
          surveyAnswers["would_recommend"] != null ? Boolean(surveyAnswers["would_recommend"]) : null,
        suggestion: (surveyAnswers["suggestion"] as string) ?? "",
      });
      setSurveyDone(true);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onDispute(text: string) {
    const issue = window.prompt("What seems wrong with this answer? A human will review it.");
    if (!issue) return;
    try {
      const r = await reportIssue({
        target_kind: "claim",
        target_id: view?.session.session_id ?? "",
        locator: text,
        issue,
        author: "student",
      });
      window.alert(`Reported for human review (id ${r.id}, status: ${r.status}).`);
    } catch (e) {
      setError(String(e));
    }
  }

  async function onAsk() {
    if (!view || !question.trim()) return;
    const q = question.trim();
    setQuestion("");
    setChat((c) => [...c, { role: "student", text: q }]);
    setBusy(true);
    try {
      const a: Answer = await ask(view.session.session_id, q);
      speak(a.text);
      setChat((c) => [
        ...c,
        {
          role: "teacher",
          text: a.text,
          citations: a.citations,
          grounded: a.grounded,
          confidence:
            a.hallucination_risk !== undefined
              ? Math.round((1 - a.hallucination_risk) * 100)
              : undefined,
          unsupported: a.unsupported,
        },
      ]);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="container">
      <h1>Live Class</h1>
      {disclosure && (
        <div className="card" style={{ borderColor: "#6ea8fe" }}>
          <strong>AI disclosure</strong>
          <div className="muted">{disclosure.line}</div>
        </div>
      )}
      {error && (
        <div className="card" style={{ borderColor: "#ff6b6b" }}>
          <strong>Could not reach the orchestrator.</strong>
          <div className="muted">{error}</div>
        </div>
      )}

      {!view && (
        <div className="card">
          <h3>Start a session</h3>
          <div className="row">
            <select value={lessonId} onChange={(e) => setLessonId(e.target.value)}>
              {lessons.map((l) => (
                <option key={l.lesson_id} value={l.lesson_id}>
                  {l.title}
                </option>
              ))}
            </select>
            <select value={classType} onChange={(e) => setClassType(e.target.value)}>
              <option value="group">Group class</option>
              <option value="solo">Solo (1:1)</option>
            </select>
            <button onClick={onStart} disabled={busy || !lessonId}>
              Start class
            </button>
          </div>
        </div>
      )}

      {view && slide && (
        <>
          <div className="slide">
            <div className="muted">
              {view.lesson.title} · Slide {slide.index + 1} of {view.lesson.slides.length}
            </div>
            <h2>{slide.title}</h2>
            <p>{slide.body}</p>
            <p className="muted">🔊 {slide.narration}</p>
            <div className="row">
              <button onClick={onAdvance} disabled={busy}>
                Next slide →
              </button>
              <button onClick={onFinish} disabled={busy}
                style={{ background: "#111", color: "#fff" }}>
                Finish class
              </button>
              <span className="muted">Session {view.session.session_id}</span>
            </div>
          </div>

          <div className="card">
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0 }}>Ask the AI teacher</h3>
              <label className="muted" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <input
                  type="checkbox"
                  checked={speakAnswers}
                  onChange={(e) => {
                    setSpeakAnswers(e.target.checked);
                    if (!e.target.checked) stopSpeaking();
                  }}
                />
                Speak answers
              </label>
            </div>
            <div className="chat">
              {chat.map((m, i) => (
                <div key={i} className={`bubble ${m.role}`}>
                  {m.text}
                  {m.role === "teacher" && m.grounded !== undefined && (
                    <div className="cite" style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                      <span
                        title="Whether the answer is supported by the course material"
                        style={{
                          padding: "1px 8px",
                          borderRadius: 999,
                          border: "1px solid currentColor",
                          color: m.grounded ? "#16a34a" : "#d97706",
                        }}
                      >
                        {m.grounded ? "Grounded ✓" : "Unverified ⚠"}
                      </span>
                      {m.confidence !== undefined && (
                        <span title="Confidence = 1 - hallucination risk">
                          confidence {m.confidence}%
                        </span>
                      )}
                      {m.citations && m.citations.length > 0 && (
                        <span>· verified against {m.citations.length} source{m.citations.length > 1 ? "s" : ""}</span>
                      )}
                    </div>
                  )}
                  {m.citations && m.citations.length > 0 && (
                    <div className="cite">Sources: {m.citations.join(" | ")}</div>
                  )}
                  {m.unsupported && m.unsupported.length > 0 && (
                    <div className="cite" style={{ color: "#d97706" }}>
                      Unsupported claims flagged: {m.unsupported.join("; ")}
                    </div>
                  )}
                  {m.role === "teacher" && (
                    <div style={{ marginTop: 6, display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <button
                        onClick={() => speak(m.text)}
                        style={{ fontSize: 12, padding: "2px 10px", color: "#075985", background: "#e0f2fe", border: "1px solid #0ea5e9", borderRadius: 999, cursor: "pointer" }}
                        title="Speak this answer aloud"
                      >
                        🔊 Speak
                      </button>
                      {speaking && (
                        <button
                          onClick={stopSpeaking}
                          style={{ fontSize: 12, padding: "2px 10px", color: "#334155", background: "#f1f5f9", border: "1px solid #94a3b8", borderRadius: 999, cursor: "pointer" }}
                          title="Stop speaking"
                        >
                          Stop audio
                        </button>
                      )}
                      <button
                        onClick={() => onDispute(m.text)}
                        style={{ fontSize: 12, padding: "2px 10px", color: "#b45309", background: "#fff7ed", border: "1px solid #f59e0b", borderRadius: 999, cursor: "pointer" }}
                        title="Dispute this answer; a human reviews it"
                      >
                        Report / dispute
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
            <div className="row" style={{ marginTop: 12 }}>
              <input
                style={{ flex: 1, minWidth: 240 }}
                placeholder="e.g. What gas do plants release?"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && onAsk()}
              />
              <button onClick={onAsk} disabled={busy || !question.trim()}>
                Ask
              </button>
            </div>
          </div>
        </>
      )}

      {survey && (
        <div role="dialog" aria-modal="true"
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)",
            display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50, padding: 16 }}>
          <div className="card" style={{ maxWidth: 520, width: "100%", background: "#fff" }}>
            {!surveyDone ? (
              <>
                <h3 style={{ marginTop: 0 }}>{survey.title}</h3>
                <p className="muted">Optional · helps us improve this course.</p>
                {survey.questions.map((q) => (
                  <div key={q.id} style={{ margin: "14px 0" }}>
                    <label style={{ fontWeight: 600, display: "block", marginBottom: 6 }}>
                      {q.prompt}{q.required ? " *" : ""}
                    </label>
                    {q.type === "rating" && (
                      <div style={{ display: "flex", gap: 6 }}>
                        {[1, 2, 3, 4, 5].map((n) => (
                          <button key={n} onClick={() => setSurveyAnswers((a) => ({ ...a, [q.id]: n }))}
                            style={{ fontSize: 22, lineHeight: 1, padding: "2px 6px", cursor: "pointer",
                              background: "transparent", border: 0,
                              filter: Number(surveyAnswers[q.id] ?? 0) >= n ? "none" : "grayscale(1) opacity(0.4)" }}>
                            ⭐
                          </button>
                        ))}
                      </div>
                    )}
                    {q.type === "choice" && (
                      <select value={(surveyAnswers[q.id] as string) ?? ""}
                        onChange={(e) => setSurveyAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                        style={{ padding: 6 }}>
                        <option value="">—</option>
                        {q.options.map((o) => <option key={o} value={o}>{o}</option>)}
                      </select>
                    )}
                    {q.type === "bool" && (
                      <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
                        <input type="checkbox" checked={Boolean(surveyAnswers[q.id])}
                          onChange={(e) => setSurveyAnswers((a) => ({ ...a, [q.id]: e.target.checked }))} />
                        Yes
                      </label>
                    )}
                    {q.type === "text" && (
                      <textarea rows={2} style={{ width: "100%" }}
                        placeholder="Your suggestion…"
                        value={(surveyAnswers[q.id] as string) ?? ""}
                        onChange={(e) => setSurveyAnswers((a) => ({ ...a, [q.id]: e.target.value }))} />
                    )}
                  </div>
                ))}
                <div className="row" style={{ marginTop: 12 }}>
                  <button onClick={onSubmitSurvey} disabled={busy}
                    style={{ background: "#111", color: "#fff" }}>
                    Submit feedback
                  </button>
                  <button onClick={() => { setSurvey(null); setView(null); }} disabled={busy}>
                    Skip
                  </button>
                </div>
              </>
            ) : (
              <>
                <h3 style={{ marginTop: 0 }}>Thank you! 🙌</h3>
                <p className="muted">Your feedback helps us improve this course.</p>
                <button onClick={() => { setSurvey(null); setView(null); }}
                  style={{ background: "#111", color: "#fff" }}>
                  Close
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
