"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  advance,
  ask,
  enrollCourse,
  generateClassQuiz,
  getDisclosure,
  grantReward,
  getPostClassSurvey,
  getRewards,
  getToken,
  listLessons,
  listStudents,
  recordAdaptationEvent,
  recordWellnessCheckIn,
  reportIssue,
  setEnrollmentStatus,
  startSession,
  submitPostClassSurvey,
  type Answer,
  type ClassQuizItem,
  type Disclosure,
  type Lesson,
  type SessionView,
  type Slide,
  type SurveyTemplate,
} from "../lib/api";
import SignInToUse from "./SignInToUse";
import { useT } from "../lib/i18n";
import { speakNaturally } from "../lib/tts";

export type ClassRoomProps = {
  // Page heading (e.g. "Live Class" or "Corporate training").
  title?: string;
  // When set, the room runs ONLY this lesson: no picker, auto-starts on load.
  lockedLessonId?: string;
  // Optional deep-link lesson id (picker mode); preselects without locking.
  initialLessonId?: string;
  // Hide corporate lessons from the picker (Live Class). Ignored when locked.
  hideCorporate?: boolean;
  // Optional "back" link rendered at the top of the page.
  backHref?: string;
  backLabel?: string;
  // Label for the primary start button.
  startLabel?: string;
};

export default function ClassRoom({
  title,
  lockedLessonId,
  initialLessonId,
  hideCorporate = false,
  backHref,
  backLabel,
  startLabel,
}: ClassRoomProps) {
  const { t, locale } = useT();
  const heading = title ?? t("class.title");
  const startBtn = startLabel ?? t("class.startLabel");
  const back = backLabel ?? t("class.back");
  const locked = Boolean(lockedLessonId);
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [lessonId, setLessonId] = useState<string>(lockedLessonId ?? initialLessonId ?? "");
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
  const [finish, setFinish] = useState<
    | { kind: "earned"; earned: number; balance: number }
    | { kind: "complete"; balance?: number }
    | { kind: "guest" }
    | null
  >(null);
  const [speakAnswers, setSpeakAnswers] = useState(true);
  const [speaking, setSpeaking] = useState(false);
  const [loggedIn, setLoggedIn] = useState(true);   // assume true until resolved (avoids flash)
  const [slidesSinceQuiz, setSlidesSinceQuiz] = useState(0);
  const [popQuiz, setPopQuiz] = useState<ClassQuizItem[] | null>(null);
  const [studentId, setStudentId] = useState("");
  const [wellness, setWellness] = useState("ok");
  const sessionStartRef = useRef<number | null>(null);
  const speechRef = useRef<SpeechSynthesisUtterance | null>(null);
  const autoStartedRef = useRef(false);

  useEffect(() => {
    const signedIn = Boolean(getToken());
    setLoggedIn(signedIn);
    if (signedIn) {
      listStudents().then((r) => setStudentId(r.students[0]?.id ?? "")).catch(() => {});
    }
    if (!locked) {
      listLessons()
        .then((ls) => {
          setLessons(ls);
          if (initialLessonId && ls.some((l) => l.lesson_id === initialLessonId)) {
            setLessonId(initialLessonId);
          } else {
            const pickable = hideCorporate
              ? ls.filter((l) => (l.audience ?? "general") !== "corporate")
              : ls;
            if (pickable.length) setLessonId((prev) => prev || pickable[0].lesson_id);
            else if (ls.length) setLessonId((prev) => prev || ls[0].lesson_id);
          }
        })
        .catch((e) => setError(String(e)));
    }
    getDisclosure()
      .then(setDisclosure)
      .catch(() => setDisclosure(null));
    return () => stopSpeaking();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Locked mode (corporate course): start the session automatically once, so the
  // learner lands directly on the slides + AI teacher instead of a picker.
  useEffect(() => {
    if (locked && loggedIn && !view && !busy && !finish && !autoStartedRef.current) {
      autoStartedRef.current = true;
      onStart();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locked, loggedIn, view, busy, finish]);

  function stopSpeaking() {
    try { window.speechSynthesis.cancel(); } catch { /* no browser TTS */ }
    speechRef.current = null;
    setSpeaking(false);
  }

  function speak(text: string) {
    if (!speakAnswers || typeof window === "undefined" || !("speechSynthesis" in window)) return;
    stopSpeaking();
    speakNaturally(text, {
      locale,
      onend: () => setSpeaking(false),
    });
    setSpeaking(true);
  }

  async function onStart() {
    if (!getToken()) { setLoggedIn(false); return; }   // preview is view-only
    setError("");
    setFinish(null);
    setBusy(true);
    try {
      if (studentId && wellness !== "ok") {
        recordWellnessCheckIn(studentId, wellness).catch(() => {});
      }
      const v = await startSession(lessonId, classType);
      sessionStartRef.current = Date.now();
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
    if (!view || popQuiz) return;
    setBusy(true);
    try {
      const s = await advance(view.session.session_id);
      setSlide(s);
      const nextCount = slidesSinceQuiz + 1;
      setSlidesSinceQuiz(nextCount);
      if (nextCount >= 3) {
        const passages = view.lesson.slides
          .slice(Math.max(0, s.index - 3), s.index + 1)
          .map((sl) => `${sl.title}: ${sl.body || sl.narration}`);
        const quiz = await generateClassQuiz(view.lesson.title, passages, 2);
        if (quiz.items?.length) {
          setPopQuiz(quiz.items);
          setSlidesSinceQuiz(0);
        }
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  function dismissPopQuiz() {
    setPopQuiz(null);
  }

  // End the class: reward the completion (logged-in learners earn points), then
  // prompt the post-class survey if enabled.
  async function onFinish() {
    if (!view) return;
    setBusy(true);
    try {
      await awardCompletion();
      const res = await getPostClassSurvey();
      if (res.enabled && res.template) {
        setSurvey(res.template);
        setSurveyAnswers({});
        setSurveyDone(false);
      } else {
        setView(null);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  // Mark this lesson passed so identity awards reward points on the first pass
  // (idempotent server-side). Signed-out learners are nudged to sign in.
  async function awardCompletion() {
    if (!view) return;
    if (!getToken()) {
      setFinish({ kind: "guest" });
      return;
    }
    try {
      await enrollCourse(lessonId, view.lesson.title, "enrolled");
      const before = await getRewards().then((r) => r.balance).catch(() => 0);
      const res = await setEnrollmentStatus(lessonId, "passed");
      const earned = Math.max(0, res.points_balance - before);
      if (studentId) {
        const elapsedMs = sessionStartRef.current ? Date.now() - sessionStartRef.current : 0;
        const mins = Math.max(1, Math.round(elapsedMs / 60_000) || Math.max(20, view.lesson.slides.length * 2));
        const expected = Math.max(20, view.lesson.slides.length * 2);
        const complexity = view.lesson.slides.length > 30 ? 4 : view.lesson.slides.length < 12 ? 2 : 3;
        recordAdaptationEvent(studentId, "course_completion", {
          course_id: lessonId,
          minutes: mins,
          expected_min: expected,
          complexity,
        }).catch(() => {});
      }
      setFinish(
        earned > 0
          ? { kind: "earned", earned, balance: res.points_balance }
          : { kind: "complete", balance: res.points_balance }
      );
    } catch {
      /* not enrollable / offline: don't block finishing the class */
      setFinish({ kind: "complete" });
    }
  }

  async function onSubmitSurvey() {
    if (!view) return;
    const overall = Number(surveyAnswers["overall"] ?? 0);
    if (!overall) {
      setError(t("class.ratingRequired"));
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
      if (studentId && getToken()) {
        const pace = String(surveyAnswers["pace"] ?? "");
        if (overall <= 2) {
          recordWellnessCheckIn(studentId, "stressed", "low post-class rating").catch(() => {});
        } else if (pace.toLowerCase().includes("too fast")) {
          recordAdaptationEvent(studentId, "trigger", {
            trigger: "pace too fast",
            reason: "post-class survey: pacing felt too fast",
            severity: "medium",
          }).catch(() => {});
        }
      }
      setSurveyDone(true);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onDispute(text: string) {
    const issue = window.prompt(t("class.reportPrompt"));
    if (!issue) return;
    try {
      const r = await reportIssue({
        target_kind: "claim",
        target_id: view?.session.session_id ?? "",
        locator: text,
        issue,
        author: "student",
      });
      window.alert(t("class.reported", { id: r.id, status: r.status }));
    } catch (e) {
      setError(String(e));
    }
  }

  async function onAsk() {
    if (!view || !question.trim()) return;
    const q = question.trim();
    setQuestion("");
    const frustration = /(stupid|hate this|confus|frustrat|angry|doesn't work|too fast|too slow)/i.test(q);
    const wellnessCue = /(sick|not feeling|tired|exhausted|stressed|anxious|overwhelmed|bad mood|headache)/i.test(q);
    if (frustration && studentId && getToken()) {
      recordAdaptationEvent(studentId, "trigger", {
        trigger: q.slice(0, 80).toLowerCase(),
        reason: "student expressed frustration during class Q&A",
        severity: "medium",
      }).catch(() => {});
    }
    if (wellnessCue && studentId && getToken()) {
      const state = /(sick|not feeling|ill|headache)/i.test(q) ? "unwell"
        : /(tired|exhausted|no energy)/i.test(q) ? "low_energy" : "stressed";
      recordWellnessCheckIn(studentId, state, q.slice(0, 120)).catch(() => {});
    }
    setChat((c) => [...c, { role: "student", text: q }]);
    setBusy(true);
    try {
      const a: Answer = await ask(view.session.session_id, q, locale);
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
      // The AI teacher may grant points for a good question. Redeem the signed
      // voucher to the learner's account (server-verified) and show it.
      if (a.reward?.grant_token && getToken()) {
        try {
          const r = await grantReward(a.reward.grant_token);
          if (r.earned > 0) {
            setChat((c) => [
              ...c,
              { role: "reward", text: t("class.rewardAwarded", {
                earned: r.earned, reason: a.reward!.reason, balance: r.balance,
              }) },
            ]);
          }
        } catch {
          /* reward grants not configured / offline: skip silently */
        }
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="container">
      {backHref && (
        <div className="row" style={{ marginBottom: 4 }}>
          <Link href={backHref} className="muted" style={{ fontSize: 14 }}>{back}</Link>
        </div>
      )}
      <h1>{heading}</h1>
      {disclosure && (
        <div className="card" style={{ borderColor: "#6ea8fe" }}>
          <strong>{t("class.aiDisclosure")}</strong>
          <div className="muted">{disclosure.line}</div>
        </div>
      )}
      {error && (
        <div className="card" style={{ borderColor: "#ff6b6b" }}>
          <strong>{t("class.orchestratorError")}</strong>
          <div className="muted">{error}</div>
        </div>
      )}

      {finish && (
        <div className="card" style={{ borderColor: "#16a34a" }}>
          {finish.kind === "earned" && (
            <>
              <strong>{t("class.completeEarned", { earned: finish.earned })}</strong>
              <div className="muted">
                {t("class.balanceRedeem", { balance: finish.balance })}{" "}
                <a href="/rewards">{t("class.redeemLink")}</a>
              </div>
            </>
          )}
          {finish.kind === "complete" && (
            <>
              <strong>{t("class.complete")}</strong>
              <div className="muted">
                {finish.balance !== undefined
                  ? <>{t("class.rewardBalance", { balance: finish.balance })} <a href="/rewards">{t("class.rewardsLink")}</a></>
                  : t("class.niceWork")}
              </div>
            </>
          )}
          {finish.kind === "guest" && (
            <>
              <strong>{t("class.complete")}</strong>
              <div className="muted">
                <a href="/login">{t("profile.signIn")}</a> {t("class.guestComplete")}
              </div>
            </>
          )}
          {locked && (
            <div className="row" style={{ marginTop: 10 }}>
              <button onClick={() => { autoStartedRef.current = false; setFinish(null); }}>
                {t("class.takeAgain")}
              </button>
              {backHref && (
                <Link href={backHref}>
                  <button style={{ background: "transparent", border: "1px solid var(--border)" }}>
                    {back}
                  </button>
                </Link>
              )}
            </div>
          )}
        </div>
      )}

      {!view && !loggedIn && <SignInToUse />}

      {/* Picker mode (Live Class): choose a lesson and class type. */}
      {!view && !locked && (
        <div className="card">
          <h3>{t("class.startSession")}</h3>
          <p className="muted" style={{ marginTop: 0 }}>{t("class.startSessionDesc")}</p>
          <div className="row">
            <select value={lessonId} onChange={(e) => setLessonId(e.target.value)}>
              {lessons
                .filter((l) => !hideCorporate || (l.audience ?? "general") !== "corporate" || l.lesson_id === initialLessonId)
                .map((l) => (
                  <option key={l.lesson_id} value={l.lesson_id}>
                    {l.title}
                  </option>
                ))}
            </select>
            <select value={classType} onChange={(e) => setClassType(e.target.value)}>
              <option value="group">{t("class.groupClass")}</option>
              <option value="solo">{t("class.solo")}</option>
            </select>
          </div>
          {loggedIn && (
            <div style={{ marginTop: 12 }}>
              <div className="muted" style={{ marginBottom: 6 }}>{t("class.wellnessPrompt")}</div>
              <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
                {([
                  ["ok", "class.wellnessOk"],
                  ["low_energy", "class.wellnessTired"],
                  ["stressed", "class.wellnessStressed"],
                  ["unwell", "class.wellnessUnwell"],
                ] as const).map(([val, label]) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setWellness(val)}
                    style={{
                      background: wellness === val ? "var(--accent, #6ea8fe)" : "transparent",
                      border: "1px solid var(--border)",
                      color: wellness === val ? "#fff" : "inherit",
                      fontSize: 13,
                    }}
                  >
                    {t(label)}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="row" style={{ marginTop: 12 }}>
            <button onClick={onStart} disabled={busy || !lessonId || !loggedIn}
              title={!loggedIn ? t("class.signInToTake") : undefined}>
              {startBtn}
            </button>
          </div>
        </div>
      )}

      {/* Locked mode (corporate course): auto-starting; show a starting state or
          a manual start button if the learner is signed in but auto-start hasn't
          fired (e.g. they hit "Take it again"). */}
      {!view && locked && loggedIn && !finish && (
        <div className="card">
          {busy ? (
            <p className="muted" style={{ margin: 0 }}>{t("class.startingCourse")}</p>
          ) : (
            <button onClick={onStart} disabled={!lessonId}>{startBtn}</button>
          )}
        </div>
      )}

      {view && slide && (
        <>
          <div className="slide">
            <div className="muted">
              {view.lesson.title} · {t("class.slideOf", {
                current: slide.index + 1,
                total: view.lesson.slides.length,
              })}
            </div>
            <h2>{slide.title}</h2>
            <p>{slide.body}</p>
            <p className="muted">🔊 {slide.narration}</p>
            <div className="row">
              <button onClick={onAdvance} disabled={busy}>
                {t("class.nextSlide")}
              </button>
              <button onClick={onFinish} disabled={busy}
                style={{ background: "#111", color: "#fff" }}>
                {t("class.finishClass")}
              </button>
              <span className="muted">{t("class.session", { id: view.session.session_id })}</span>
            </div>
          </div>

          {popQuiz && popQuiz.length > 0 && (
            <div className="card" style={{ borderColor: "#6ea8fe" }}>
              <h3 style={{ marginTop: 0 }}>Pop quiz — check your understanding</h3>
              {popQuiz.map((item) => (
                <div key={item.item_id} style={{ marginBottom: 12 }}>
                  <p><strong>{item.prompt}</strong></p>
                  <ul>
                    {item.options.map((opt, i) => (
                      <li key={i}>{opt}</li>
                    ))}
                  </ul>
                </div>
              ))}
              <button type="button" onClick={dismissPopQuiz}>Continue lesson</button>
            </div>
          )}

          <div className="card">
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0 }}>{t("class.askTeacher")}</h3>
              <label className="muted" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <input
                  type="checkbox"
                  checked={speakAnswers}
                  onChange={(e) => {
                    setSpeakAnswers(e.target.checked);
                    if (!e.target.checked) stopSpeaking();
                  }}
                />
                {t("class.speakAnswers")}
              </label>
            </div>
            <div className="chat">
              {chat.map((m, i) => (
                <div key={i} className={`bubble ${m.role}`}
                  style={m.role === "reward"
                    ? { background: "#052e16", color: "#bbf7d0", border: "1px solid #16a34a", fontWeight: 600 }
                    : undefined}>
                  {m.text}
                  {m.role === "teacher" && m.grounded !== undefined && (
                    <div className="cite" style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                      <span
                        title={t("class.groundedTitle")}
                        style={{
                          padding: "1px 8px",
                          borderRadius: 999,
                          border: "1px solid currentColor",
                          color: m.grounded ? "#16a34a" : "#d97706",
                        }}
                      >
                        {m.grounded ? t("class.grounded") : t("class.unverified")}
                      </span>
                      {m.confidence !== undefined && (
                        <span title={t("class.confidenceTitle")}>
                          {t("class.confidence", { pct: m.confidence })}
                        </span>
                      )}
                      {m.citations && m.citations.length > 0 && (
                        <span>{m.citations.length > 1
                          ? t("class.verifiedSourcesPlural", { n: m.citations.length })
                          : t("class.verifiedSources", { n: m.citations.length })}</span>
                      )}
                    </div>
                  )}
                  {m.citations && m.citations.length > 0 && (
                    <div className="cite">{t("class.sources")} {m.citations.join(" | ")}</div>
                  )}
                  {m.unsupported && m.unsupported.length > 0 && (
                    <div className="cite" style={{ color: "#d97706" }}>
                      {t("class.unsupportedClaims")} {m.unsupported.join("; ")}
                    </div>
                  )}
                  {m.role === "teacher" && (
                    <div style={{ marginTop: 6, display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <button
                        onClick={() => speak(m.text)}
                        style={{ fontSize: 12, padding: "2px 10px", color: "#075985", background: "#e0f2fe", border: "1px solid #0ea5e9", borderRadius: 999, cursor: "pointer" }}
                        title={t("class.speakTitle")}
                      >
                        {t("class.speak")}
                      </button>
                      {speaking && (
                        <button
                          onClick={stopSpeaking}
                          style={{ fontSize: 12, padding: "2px 10px", color: "#334155", background: "#f1f5f9", border: "1px solid #94a3b8", borderRadius: 999, cursor: "pointer" }}
                          title={t("class.stopTitle")}
                        >
                          {t("class.stopAudio")}
                        </button>
                      )}
                      <button
                        onClick={() => onDispute(m.text)}
                        style={{ fontSize: 12, padding: "2px 10px", color: "#b45309", background: "#fff7ed", border: "1px solid #f59e0b", borderRadius: 999, cursor: "pointer" }}
                        title={t("class.reportTitle")}
                      >
                        {t("class.reportDispute")}
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
            <div className="row" style={{ marginTop: 12 }}>
              <input
                style={{ flex: 1, minWidth: 240 }}
                placeholder={t("class.askPlaceholder")}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && onAsk()}
              />
              <button onClick={onAsk} disabled={busy || !question.trim()}>
                {t("class.ask")}
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
                <p className="muted">{t("class.surveyOptional")}</p>
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
                        {t("class.surveyYes")}
                      </label>
                    )}
                    {q.type === "text" && (
                      <textarea rows={2} style={{ width: "100%" }}
                        placeholder={t("class.surveySuggestion")}
                        value={(surveyAnswers[q.id] as string) ?? ""}
                        onChange={(e) => setSurveyAnswers((a) => ({ ...a, [q.id]: e.target.value }))} />
                    )}
                  </div>
                ))}
                <div className="row" style={{ marginTop: 12 }}>
                  <button onClick={onSubmitSurvey} disabled={busy}
                    style={{ background: "#111", color: "#fff" }}>
                    {t("class.surveySubmit")}
                  </button>
                  <button onClick={() => { setSurvey(null); setView(null); }} disabled={busy}>
                    {t("class.surveySkip")}
                  </button>
                </div>
              </>
            ) : (
              <>
                <h3 style={{ marginTop: 0 }}>{t("class.surveyThanks")}</h3>
                <p className="muted">{t("class.surveyThanksBody")}</p>
                <button onClick={() => { setSurvey(null); setView(null); }}
                  style={{ background: "#111", color: "#fff" }}>
                  {t("class.surveyClose")}
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
