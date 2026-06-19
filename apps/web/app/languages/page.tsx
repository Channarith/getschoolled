"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  getLangCourse,
  getLearnLanguages,
  getToken,
  languagePractice,
  newLangExercise,
  pronounce,
  type LangCourse,
  type LangExercise,
  type LangInfo,
  type Pronounce,
} from "../lib/api";

// Best-effort BCP-47 for speech synthesis/recognition.
const BCP47: Record<string, string> = {
  en: "en-US", es: "es-ES", fr: "fr-FR", de: "de-DE", it: "it-IT", pt: "pt-PT",
  nl: "nl-NL", pl: "pl-PL", ru: "ru-RU", uk: "uk-UA", tr: "tr-TR", ar: "ar-SA",
  he: "he-IL", hi: "hi-IN", bn: "bn-BD", ur: "ur-PK", fa: "fa-IR", zh: "zh-CN",
  ja: "ja-JP", ko: "ko-KR", vi: "vi-VN", th: "th-TH", id: "id-ID", sw: "sw-KE",
  el: "el-GR", cs: "cs-CZ",
};

type SpeechRec = {
  lang: string; interimResults: boolean; maxAlternatives: number;
  onresult: (e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void;
  onerror: () => void; onend: () => void; start: () => void; stop: () => void;
};

function speak(text: string, code: string) {
  try {
    const u = new SpeechSynthesisUtterance(text);
    u.lang = BCP47[code] ?? code;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  } catch { /* TTS not available */ }
}

function todayStr() { return new Date().toISOString().slice(0, 10); }

export default function LanguagesPage() {
  const [langs, setLangs] = useState<LangInfo[]>([]);
  const [course, setCourse] = useState<LangCourse | null>(null);
  const [skill, setSkill] = useState<string>("");
  const [ex, setEx] = useState<LangExercise | null>(null);
  const [answers, setAnswers] = useState<Record<string, number | string>>({});
  const [selTerm, setSelTerm] = useState("");
  const [done, setDone] = useState<{ correct: number; total: number; xp?: number } | null>(null);
  const [pron, setPron] = useState<Pronounce | null>(null);
  const [heard, setHeard] = useState("");
  const [listening, setListening] = useState(false);
  const [streak, setStreak] = useState(0);
  const [xpTotal, setXpTotal] = useState(0);
  const [error, setError] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    setLoggedIn(Boolean(getToken()));
    getLearnLanguages().then((r) => setLangs(r.languages)).catch((e) => setError(String(e)));
    try {
      const s = JSON.parse(window.localStorage.getItem("aoep-lang-streak") || "{}");
      setStreak(s.count || 0);
    } catch { /* ignore */ }
  }, []);

  const bumpStreak = useCallback(() => {
    try {
      const s = JSON.parse(window.localStorage.getItem("aoep-lang-streak") || "{}");
      const t = todayStr();
      if (s.date === t) return;
      const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
      const count = s.date === yesterday ? (s.count || 0) + 1 : 1;
      window.localStorage.setItem("aoep-lang-streak", JSON.stringify({ date: t, count }));
      setStreak(count);
    } catch { /* ignore */ }
  }, []);

  async function openCourse(code: string) {
    setError(""); setEx(null); setSkill(""); setDone(null); setPron(null);
    try { setCourse(await getLangCourse(code)); } catch (e) { setError(String(e)); }
  }

  async function startSkill(s: string) {
    if (!course) return;
    setSkill(s); setEx(null); setDone(null); setPron(null); setAnswers({});
    setSelTerm(""); setHeard("");
    try { setEx(await newLangExercise(course.code, s, s === "match" ? 4 : 5)); }
    catch (e) { setError(String(e)); }
  }

  function gradeChoice() {
    if (!ex?.items || !course) return;
    const correct = ex.items.filter((it) => answers[it.id] === it.answer_index).length;
    finishSet(correct, ex.items.length);
  }
  function gradeMatch() {
    if (!ex?.pairs || !course) return;
    const correct = ex.pairs.filter((p) => answers[p.id] === p.id).length;
    finishSet(correct, ex.pairs.length);
  }
  async function finishSet(correct: number, total: number) {
    bumpStreak();
    let xp: number | undefined;
    if (loggedIn && course) {
      try {
        const r = await languagePractice(course.code, skill, correct, total);
        xp = r.xp; setXpTotal(r.balance);
      } catch { /* not blocking */ }
    }
    setDone({ correct, total, xp });
  }

  async function checkPronunciation(text: string) {
    if (!ex?.target) return;
    try {
      const r = await pronounce(ex.target, text);
      setPron(r);
      bumpStreak();
      if (loggedIn && course && r.passed) {
        const res = await languagePractice(course.code, "pronunciation", r.stars, 3);
        setXpTotal(res.balance);
      }
    } catch (e) { setError(String(e)); }
  }

  function startSpeaking() {
    const w = window as unknown as { webkitSpeechRecognition?: new () => SpeechRec; SpeechRecognition?: new () => SpeechRec };
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!Ctor || !course) { setError("Speech recognition isn't available in this browser — type what you said instead."); return; }
    const rec = new Ctor();
    rec.lang = BCP47[course.code] ?? course.code;
    rec.interimResults = false; rec.maxAlternatives = 1;
    setListening(true);
    rec.onresult = (e) => { const t = e.results[0][0].transcript; setHeard(t); void checkPronunciation(t); };
    rec.onerror = () => setListening(false);
    rec.onend = () => setListening(false);
    rec.start();
  }

  return (
    <main className="container" style={{ maxWidth: 1040 }}>
      <h1>🌍 Languages</h1>
      <p className="muted">
        Learn 20+ languages by playing - pronunciation (speak &amp; get scored),
        listening, vocabulary, phrases, travel, conversation, grammar, slang &amp;
        more. {streak > 0 && <strong>🔥 {streak}-day streak!</strong>}
        {!loggedIn && <> <Link href="/login">Sign in</Link> to earn points.</>}
      </p>
      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}

      {/* Language picker */}
      {!course && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px,1fr))", gap: 10 }}>
          {langs.map((l) => (
            <button key={l.code} onClick={() => openCourse(l.code)}
              style={{ background: "var(--panel)", color: "var(--text)", border: "1px solid var(--border)",
                borderRadius: 12, padding: 14, textAlign: "left", cursor: "pointer" }}>
              <div style={{ fontSize: 28 }}>{l.flag}</div>
              <div style={{ fontWeight: 700 }}>{l.name}</div>
              <div className="muted" style={{ fontSize: 12 }}>{l.native}</div>
              <span className="pill" style={{ color: l.tier === "rich" ? "#16a34a" : "#b45309", fontSize: 10 }}>
                {l.tier === "rich" ? "full course" : "starter"}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Course view */}
      {course && !skill && (
        <div>
          <button onClick={() => setCourse(null)} style={{ marginBottom: 12 }}>← All languages</button>
          <div className="card">
            <h2 style={{ marginTop: 0 }}>{course.flag} {course.name} <span className="muted" style={{ fontSize: 16 }}>{course.native}</span></h2>
            {course.grammar_tip && <p className="muted">🧩 {course.grammar_tip}</p>}
            {course.culture_note && <p className="muted">🌍 {course.culture_note}</p>}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px,1fr))", gap: 12 }}>
            {course.skills.map((s) => (
              <button key={s.id} onClick={() => startSkill(s.id)}
                style={{ background: "var(--panel)", color: "var(--text)", border: "1px solid var(--border)",
                  borderRadius: 12, padding: 14, textAlign: "left", cursor: "pointer" }}>
                <div style={{ fontSize: 22 }}>{s.icon}</div>
                <div style={{ fontWeight: 700 }}>{s.name}</div>
                <div className="muted" style={{ fontSize: 12 }}>{s.desc}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Exercise */}
      {course && skill && ex && (
        <div className="card">
          <button onClick={() => { setSkill(""); setEx(null); }} style={{ marginBottom: 10 }}>← {course.name} skills</button>

          {/* grammar / culture */}
          {(ex.tip || ex.note) && <p style={{ fontSize: 16 }}>{ex.tip || ex.note}</p>}

          {/* pronunciation / shadowing */}
          {ex.target && (
            <div>
              <h3 style={{ marginTop: 0 }}>Say it: <span style={{ color: "#7c3aed" }}>{ex.target}</span></h3>
              {ex.roman && <div className="muted">/{ex.roman}/</div>}
              <div className="muted">means: {ex.en}</div>
              <p style={{ background: "#ede9fe", color: "#4c1d95", padding: "8px 12px", borderRadius: 8 }}>
                👄 {ex.mouth_tip}
              </p>
              <div className="row" style={{ gap: 8 }}>
                <button onClick={() => speak(ex.target!, course.code)}>🔊 Listen</button>
                <button onClick={startSpeaking} disabled={listening}
                  style={{ background: "#7c3aed", color: "#fff" }}>
                  {listening ? "🎤 Listening…" : "🎤 Speak"}
                </button>
              </div>
              <div className="row" style={{ marginTop: 8 }}>
                <input placeholder="…or type what you said" value={heard}
                  onChange={(e) => setHeard(e.target.value)} style={{ flex: 1, minWidth: 200 }} />
                <button onClick={() => checkPronunciation(heard)} disabled={!heard.trim()}>Check</button>
              </div>
              <p className="muted" style={{ fontSize: 12 }}>
                Camera mouth-shape coaching is available via the perception service; the tip above is your cue.
              </p>
              {pron && (
                <div className="card" style={{ borderColor: pron.passed ? "#16a34a" : "#f59e0b" }}>
                  <strong>{"⭐".repeat(pron.stars)}{"☆".repeat(3 - pron.stars)} {pron.score}%</strong>
                  <div>{pron.feedback}</div>
                  <div className="muted">👄 {pron.mouth_tip}</div>
                  {pron.missed_words.length > 0 && <div className="muted">focus: {pron.missed_words.join(", ")}</div>}
                </div>
              )}
            </div>
          )}

          {/* MCQ (vocabulary / listening) */}
          {ex.items && !done && (
            <div>
              <h3 style={{ marginTop: 0 }}>{skill === "listening" ? "👂 Listening" : "📖 Vocabulary"}</h3>
              {ex.items.map((it, qi) => (
                <div key={it.id} style={{ margin: "12px 0" }}>
                  <div style={{ fontWeight: 600, display: "flex", gap: 8, alignItems: "center" }}>
                    {qi + 1}. {it.prompt}
                    {it.audio_prompt && <button onClick={() => speak(it.audio_prompt!, course.code)}
                      style={{ padding: "2px 8px" }}>🔊</button>}
                  </div>
                  <div className="row" style={{ flexWrap: "wrap", gap: 8, marginTop: 6 }}>
                    {it.options.map((opt, idx) => (
                      <button key={idx} onClick={() => setAnswers((a) => ({ ...a, [it.id]: idx }))}
                        style={{ border: answers[it.id] === idx ? "2px solid #7c3aed" : "1px solid var(--border)",
                          background: answers[it.id] === idx ? "#ede9fe" : "transparent",
                          color: answers[it.id] === idx ? "#4c1d95" : "var(--text)" }}>
                        {opt}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
              <button onClick={gradeChoice} style={{ background: "#16a34a", color: "#fff" }}>Submit</button>
            </div>
          )}

          {/* Match */}
          {ex.pairs && !done && (
            <div>
              <h3 style={{ marginTop: 0 }}>💬 Match the phrase to its meaning</h3>
              <p className="muted">Click a phrase, then its meaning.</p>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                <div>
                  {ex.pairs.map((p) => (
                    <button key={p.id} onClick={() => setSelTerm(p.id)}
                      style={{ display: "block", width: "100%", marginBottom: 8, textAlign: "left",
                        border: selTerm === p.id ? "2px solid #7c3aed" : "1px solid var(--border)",
                        background: answers[p.id] ? "#dcfce7" : "transparent",
                        color: answers[p.id] ? "#166534" : "var(--text)" }}>
                      {p.term} {answers[p.id] ? "✓" : ""}
                    </button>
                  ))}
                </div>
                <div>
                  {ex.pairs.map((p) => {
                    const taken = Object.values(answers).includes(p.id);
                    return (
                      <button key={p.id} onClick={() => { if (selTerm) { setAnswers((a) => ({ ...a, [selTerm]: p.id })); setSelTerm(""); } }}
                        disabled={!selTerm}
                        style={{ display: "block", width: "100%", marginBottom: 8, textAlign: "left",
                          opacity: taken ? 0.5 : 1, border: "1px solid var(--border)",
                          background: "transparent", color: "var(--text)" }}>
                        {p.match}
                      </button>
                    );
                  })}
                </div>
              </div>
              <button onClick={gradeMatch} style={{ background: "#16a34a", color: "#fff", marginTop: 10 }}>Submit</button>
            </div>
          )}

          {/* Result */}
          {done && (
            <div className="card" style={{ borderColor: "#7c3aed" }}>
              <h3 style={{ marginTop: 0 }}>
                {done.correct}/{done.total} correct {done.correct === done.total ? "🎉" : "👍"}
              </h3>
              {done.xp !== undefined && <div className="muted">+{done.xp} XP · 🔥 {streak}-day streak{xpTotal ? ` · balance ${xpTotal} pts` : ""}</div>}
              {!loggedIn && <div className="muted"><Link href="/login">Sign in</Link> to earn points for practice.</div>}
              <div className="row" style={{ marginTop: 8 }}>
                <button onClick={() => startSkill(skill)} style={{ background: "#7c3aed", color: "#fff" }}>Again</button>
                <button onClick={() => { setSkill(""); setEx(null); setDone(null); }}>More skills</button>
              </div>
            </div>
          )}
        </div>
      )}
    </main>
  );
}
