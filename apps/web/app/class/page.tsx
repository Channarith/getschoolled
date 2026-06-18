"use client";

import { useEffect, useState } from "react";
import {
  advance,
  ask,
  getDisclosure,
  listLessons,
  startSession,
  type Answer,
  type Disclosure,
  type Lesson,
  type SessionView,
  type Slide,
} from "../lib/api";

export default function ClassPage() {
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [lessonId, setLessonId] = useState<string>("");
  const [classType, setClassType] = useState<string>("group");
  const [view, setView] = useState<SessionView | null>(null);
  const [slide, setSlide] = useState<Slide | null>(null);
  const [question, setQuestion] = useState("");
  const [chat, setChat] = useState<{ role: string; text: string; citations?: string[] }[]>([]);
  const [error, setError] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [disclosure, setDisclosure] = useState<Disclosure | null>(null);

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
  }, []);

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

  async function onAsk() {
    if (!view || !question.trim()) return;
    const q = question.trim();
    setQuestion("");
    setChat((c) => [...c, { role: "student", text: q }]);
    setBusy(true);
    try {
      const a: Answer = await ask(view.session.session_id, q);
      setChat((c) => [...c, { role: "teacher", text: a.text, citations: a.citations }]);
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
              <span className="muted">Session {view.session.session_id}</span>
            </div>
          </div>

          <div className="card">
            <h3>Ask the AI teacher</h3>
            <div className="chat">
              {chat.map((m, i) => (
                <div key={i} className={`bubble ${m.role}`}>
                  {m.text}
                  {m.citations && m.citations.length > 0 && (
                    <div className="cite">Sources: {m.citations.join(" | ")}</div>
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
    </main>
  );
}
