"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useT } from "../lib/i18n";
import {
  advance,
  ask,
  askStream,
  type AskDone,
  enrollCourse,
  getAssessmentPolicy,
  getDisclosure,
  getQuiz,
  grantReward,
  getPostClassSurvey,
  getRewards,
  getStudentId,
  getToken,
  gradeQuiz,
  listLessons,
  listStudents,
  getMe,
  pronounce,
  reengage,
  recordAssessmentAttempt,
  recordAssessmentPass,
  reportIssue,
  setEnrollmentStatus,
  startAssessmentCheckpoint,
  startSession,
  startSoloLiveRoom,
  submitPostClassSurvey,
  type AdBreak,
  type Answer,
  type AssessmentCheckpointSpec,
  type AssessmentRun,
  type AssessmentSubmitResult,
  type Disclosure,
  type Lesson,
  type Pronounce,
  type QuizGrade,
  type QuizItemView,
  type Reengagement,
  type SessionView,
  type Slide,
  type StudentProfile,
  type SurveyTemplate,
} from "../lib/api";
import {
  canAwardCourseCompletion,
  findDueFormativeCheckpoint,
  findDueSummativeCheckpoint,
} from "../lib/assessmentFlow";
import SignInToUse from "../components/SignInToUse";
import AiPresenter from "../components/AiPresenter";
import AssessmentCheckpointPanel from "../components/AssessmentCheckpointPanel";
import VideoAdBreak from "../components/VideoAdBreak";
import { useCourseAds, effectiveAdTier } from "../lib/useCourseAds";
import { splitForSpeech, startSpeechKeepAlive, stopSpeechKeepAlive, synthChunk } from "../lib/tts";
import { SpeechChunker, StreamingVoice } from "../lib/voicePipeline";

// Minimal Web Speech API typing for the repeat-after-me checkpoint.
type SpeechRec = {
  lang: string; interimResults: boolean; maxAlternatives: number;
  onresult: (e: { results: { [i: number]: { [j: number]: { transcript: string } } } }) => void;
  onerror: (e: { error?: string }) => void; onend: () => void; start: () => void; stop: () => void;
};

// Color the adaptive difficulty badge so the learner can see it shift.
function difficultyStyle(d: string): { background: string; color: string; border: string } {
  if (d === "hard") return { background: "#fee2e2", color: "#991b1b", border: "1px solid #dc2626" };
  if (d === "easy") return { background: "#dcfce7", color: "#166534", border: "1px solid #16a34a" };
  return { background: "#fef9c3", color: "#854d0e", border: "1px solid #ca8a04" }; // medium / default
}

export default function ClassPage() {
  const router = useRouter();
  const { locale } = useT();
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [lessonId, setLessonId] = useState<string>("");
  // The Live Class page is always a Solo (1:1) live room with the AI. Group
  // classes live under their own "Group Classes" section, so no mode selector
  // is shown here.
  const classType = "solo";
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
    { kind: "earned" | "complete" | "guest"; earned?: number; balance?: number } | null
  >(null);
  const [speakAnswers, setSpeakAnswers] = useState(true);
  const [showChat, setShowChat] = useState(true);
  const [speaking, setSpeaking] = useState(false);
  const [spokenText, setSpokenText] = useState("");   // live caption for the presenter
  const [loggedIn, setLoggedIn] = useState(true);   // assume true until resolved (avoids flash)
  const [tier, setTier] = useState("basic");
  const [adBreak, setAdBreak] = useState<AdBreak | null>(null);
  const afterAdRef = useRef<null | (() => void)>(null);
  const advanceCount = useRef(0);
  const MIDROLL_EVERY_ADVANCES = 5;
  const { preroll, takeNextMidroll } = useCourseAds(lessonId, tier);
  const speechRef = useRef<SpeechSynthesisUtterance | null>(null);
  const voiceRef = useRef<StreamingVoice | null>(null);   // real-time chunked voice
  // Adaptive quiz state (difficulty personalizes via the memory service).
  const [quiz, setQuiz] = useState<QuizItemView[] | null>(null);
  const [quizIdx, setQuizIdx] = useState(0);
  const [quizDifficulty, setQuizDifficulty] = useState<string>("");
  const [quizPick, setQuizPick] = useState<number | null>(null);
  const [quizGrade, setQuizGrade] = useState<QuizGrade | null>(null);
  const [heard, setHeard] = useState("");
  const [pron, setPron] = useState<Pronounce | null>(null);
  const [listening, setListening] = useState(false);
  const [studentProfile, setStudentProfile] = useState<StudentProfile | null>(null);
  const [assessmentPolicy, setAssessmentPolicy] = useState<AssessmentCheckpointSpec[]>([]);
  const [assessmentRun, setAssessmentRun] = useState<AssessmentRun | null>(null);
  const [assessmentResult, setAssessmentResult] = useState<AssessmentSubmitResult | null>(null);
  const [passDecisionToken, setPassDecisionToken] = useState<string | null>(null);
  const completedCheckpointsRef = useRef<Set<string>>(new Set());
  const assessmentStartingRef = useRef(false);

  useEffect(() => {
    setLoggedIn(Boolean(getToken()));
    if (getToken()) {
      getMe().then((a) => setTier((a.tier || "basic").toLowerCase())).catch(() => {});
      listStudents().then((r) => setStudentProfile(r.students[0] ?? null)).catch(() => {});
    }
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
    stopSpeechKeepAlive();
    try { window.speechSynthesis.cancel(); window.speechSynthesis.resume(); } catch { /* no browser TTS */ }
    try { voiceRef.current?.stop(); } catch { /* */ }
    voiceRef.current = null;
    speechRef.current = null;
    setSpeaking(false);
  }

  function speak(text: string) {
    setSpokenText(text);   // caption updates even when muted
    if (!speakAnswers || typeof window === "undefined" || !("speechSynthesis" in window)) return;
    stopSpeaking();
    // Chunk into sentences and queue them. Chrome cuts a single long utterance
    // off after ~15s; short queued utterances play the whole narration without
    // truncation (and pace more naturally).
    const chunks = splitForSpeech(text);
    if (!chunks.length) return;
    setSpeaking(true);
    const finish = () => { stopSpeechKeepAlive(); setSpeaking(false); };
    chunks.forEach((chunk, i) => {
      const u = new SpeechSynthesisUtterance(chunk);
      u.rate = 1;
      if (i === 0) speechRef.current = u;
      if (i === chunks.length - 1) u.onend = finish;
      u.onerror = finish;
      window.speechSynthesis.speak(u);
    });
    // Defeat Chrome's ~15s speechSynthesis auto-stop so the whole answer is read.
    startSpeechKeepAlive();
  }

  // Repeat-after-me checkpoint: listen to the learner and score how closely they
  // said the target phrase (reuses the pronunciation endpoint).
  async function startRepeatAfterMe() {
    const target = slide?.say_aloud;
    if (!target) return;
    setError("");
    // Microphone + speech recognition require a SECURE context (https), except on
    // localhost. On a plain http:// origin (e.g. the raw server IP) the browser
    // blocks the mic outright, which is why the button appeared to do nothing.
    if (typeof window !== "undefined" && !window.isSecureContext) {
      setError(
        "Your mic needs a secure connection. Open Salareen over https:// " +
        "(e.g. https://www.salareen.com) — the browser blocks the microphone on an insecure page."
      );
      return;
    }
    const w = window as unknown as {
      webkitSpeechRecognition?: new () => SpeechRec;
      SpeechRecognition?: new () => SpeechRec;
    };
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!Ctor) {
      setError("Speech recognition isn't available in this browser — try Chrome or Edge.");
      return;
    }
    // Ask for mic permission up front so the browser shows its prompt and we can
    // give a clear message if it's blocked (instead of failing silently).
    try {
      if (navigator.mediaDevices?.getUserMedia) {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach((t) => t.stop());  // only needed the grant
      }
    } catch {
      setError(
        "Microphone access is blocked. Click the site-settings icon in the address " +
        "bar, allow the microphone, then tap 🎤 Speak now again."
      );
      return;
    }
    stopSpeaking();
    let rec: SpeechRec;
    try {
      rec = new Ctor();
    } catch {
      setError("Couldn't start the microphone. Try Chrome over https://.");
      return;
    }
    rec.lang = "en-US";
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    setPron(null);
    setHeard("");
    setListening(true);
    rec.onresult = (e) => {
      const said = e.results[0][0].transcript;
      setHeard(said);
      pronounce(target, said).then(setPron).catch((err) => setError(String(err)));
    };
    rec.onerror = (e) => {
      setListening(false);
      const code = e?.error || "";
      if (code === "not-allowed" || code === "service-not-allowed") {
        setError("Microphone access is blocked — allow the mic for this site (address-bar icon). Voice also needs https://.");
      } else if (code === "no-speech") {
        setError("Didn't catch that — tap 🎤 Speak now and speak clearly.");
      } else if (code === "audio-capture") {
        setError("No microphone found — check your device's mic and try again.");
      } else if (code) {
        setError(`Microphone error (${code}). Try again, or use Chrome over https://.`);
      }
    };
    rec.onend = () => setListening(false);
    try {
      rec.start();
    } catch {
      setListening(false);
      setError("Couldn't start the microphone. Try again, or use Chrome over https://.");
    }
  }

  // The AI presenter narrates each slide as it appears, so the video feed shows
  // the agent actually presenting the lesson (and drives the speaking animation).
  useEffect(() => {
    if (!view || !slide) return;
    speak(`${slide.title}. ${slide.narration || slide.body}`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slide?.index, view?.session.session_id]);

  // Play an ad break, then run `then` when it completes/skips. Used for the
  // pre-roll before a class starts and mid-rolls between slides (ad-supported
  // tiers only; VIP/pro get an empty plan so `preroll`/midrolls are null).
  function runAd(b: AdBreak, then: () => void) {
    stopSpeaking();
    afterAdRef.current = then;
    setAdBreak(b);
  }
  function onAdDone() {
    const fn = afterAdRef.current;
    afterAdRef.current = null;
    setAdBreak(null);
    fn?.();
  }

  async function doStart() {
    setError("");
    setBusy(true);
    try {
      const v = await startSession(lessonId, classType, getStudentId());
      setView(v);
      setSlide(v.slide);
      setChat([]);
      setQuiz(null);
      setAssessmentRun(null);
      setAssessmentResult(null);
      setPassDecisionToken(null);
      completedCheckpointsRef.current = new Set();
      advanceCount.current = 0;
      try {
        const policy = await getAssessmentPolicy(v.session.session_id);
        setAssessmentPolicy(policy.checkpoints);
      } catch {
        setAssessmentPolicy([]);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function openCheckpoint(cp: AssessmentCheckpointSpec) {
    if (!view || assessmentStartingRef.current || assessmentRun) return;
    assessmentStartingRef.current = true;
    stopSpeaking();
    setBusy(true);
    try {
      const acc = studentProfile?.accessibility || {};
      const run = await startAssessmentCheckpoint({
        studentId: studentProfile?.id || getStudentId(),
        sessionId: view.session.session_id,
        checkpointId: cp.checkpoint_id,
        stage: cp.stage,
        profileScore: studentProfile?.profile_score || "",
        needsCaptions: Boolean(acc.needs_captions),
        usesAssistiveTech: Boolean(acc.uses_assistive_tech),
        maxItems: cp.stage === "summative" ? 5 : 3,
      });
      setAssessmentRun(run);
      setAssessmentResult(null);
    } catch (e) {
      const msg = String(e);
      const contentUnavailable = msg.includes("422") || msg.toLowerCase().includes("too little");
      if (contentUnavailable) {
        completedCheckpointsRef.current.add(cp.checkpoint_id);
      }
      setError(msg);
    } finally {
      assessmentStartingRef.current = false;
      setBusy(false);
    }
  }

  // hasSummativePolicy is intentionally used as requireVerifiedPass: any course
  // with a summative checkpoint requires a verified pass token before completion
  // can be awarded. ClassRoom.tsx uses `mustVerifyPass = requireVerifiedPass ?? locked`
  // which falls back to course lock status; here we derive it from the policy
  // directly so even unlocked/free courses with a summative gate are treated correctly.
  const hasSummativePolicy = assessmentPolicy.some((cp) => cp.stage === "summative");

  async function maybeOpenDueCheckpoint(slideIndex: number, includeSummative = false) {
    const formative = findDueFormativeCheckpoint(
      assessmentPolicy, slideIndex, completedCheckpointsRef.current,
    );
    if (formative) {
      await openCheckpoint(formative);
      return true;
    }
    if (includeSummative) {
      const summative = findDueSummativeCheckpoint(
        assessmentPolicy, slideIndex, completedCheckpointsRef.current,
      );
      if (summative) {
        await openCheckpoint(summative);
        return true;
      }
    }
    return false;
  }

  async function awardVerifiedPass(token: string) {
    if (!view) return;
    const sid = studentProfile?.id;
    if (!getToken() || !sid) {
      setFinish({ kind: "guest" });
      return;
    }
    try {
      await enrollCourse(lessonId, view.lesson.title, "enrolled");
      const before = await getRewards().then((r) => r.balance).catch(() => 0);
      const res = await recordAssessmentPass(sid, token);
      const earned = Math.max(0, res.points_balance - before);
      setPassDecisionToken(null);
      setFinish(
        earned > 0
          ? { kind: "earned", earned, balance: res.points_balance }
          : { kind: "complete", balance: res.points_balance },
      );
    } catch {
      setFinish({ kind: "complete" });
    }
  }

  async function onAssessmentSubmitted(result: AssessmentSubmitResult) {
    const checkpointId = result.attempt.checkpoint_id;
    if (result.attempt.passed || result.attempt.stage === "formative") {
      completedCheckpointsRef.current = new Set(completedCheckpointsRef.current).add(checkpointId);
    }
    setAssessmentResult(result);
    setAssessmentRun(null);
    const sid = studentProfile?.id;
    if (result.attempt_result_token && sid && getToken()) {
      recordAssessmentAttempt(sid, result.attempt_result_token).catch(() => {});
    }
    if (result.pass_decision_token) setPassDecisionToken(result.pass_decision_token);
    if (result.attempt.stage === "summative" && !result.course_decision?.passed) {
      // Clear stale token so it can't be re-used on the next finish attempt.
      setPassDecisionToken(null);
    }
    if (result.attempt.stage === "summative" && result.course_decision?.passed && result.pass_decision_token) {
      completedCheckpointsRef.current = new Set(completedCheckpointsRef.current).add(checkpointId);
      await awardVerifiedPass(result.pass_decision_token);
      const surveyRes = await getPostClassSurvey().catch(() => null);
      if (surveyRes?.enabled && surveyRes.template) {
        setSurvey(surveyRes.template);
        setSurveyAnswers({});
        setSurveyDone(false);
      }
    }
  }

  async function onStart() {
    if (!getToken()) { setLoggedIn(false); return; }   // preview is view-only
    // Solo (1:1) uses the SAME Salareen classroom as group classes — just the
    // AI host and you. Open a two-seat live room and hand off to that UI.
    if (classType === "solo") {
      setError("");
      setBusy(true);
      try {
        const { room_id } = await startSoloLiveRoom(lessonId);
        router.push(`/live-room/${encodeURIComponent(room_id)}`);
        return;
      } catch (e) {
        setError(String(e));
        setBusy(false);
        return;
      }
    }
    if (preroll) { runAd(preroll, doStart); return; }
    await doStart();
  }

  async function doAdvance() {
    if (!view || assessmentRun) return;
    setBusy(true);
    try {
      const s = await advance(view.session.session_id);
      setSlide(s);
      await maybeOpenDueCheckpoint(s.index, false);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onAdvance() {
    if (!view) return;
    advanceCount.current += 1;
    if (advanceCount.current % MIDROLL_EVERY_ADVANCES === 0) {
      const mid = takeNextMidroll();
      if (mid) { runAd(mid, () => { void doAdvance(); }); return; }
    }
    await doAdvance();
  }

  // Learner is drifting/lost: ask the teaching brain to re-engage. Renders the
  // Director's REENGAGING beat (a recap of the current slide) into the chat,
  // speaks it, and pre-fills the ask box with its check-in prompt.
  async function onReengage() {
    if (!view) return;
    setBusy(true);
    try {
      const r: Reengagement = await reengage(view.session.session_id);
      speak(r.text);
      setChat((c) => [...c, { role: "reengage", text: r.text, citations: r.citations }]);
      if (r.prompt) setQuestion(r.prompt);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  // Fetch an adaptive quiz built from the lesson's slides. With a student id the
  // orchestrator picks difficulty from this learner's mastery (memory service);
  // topic == lesson_id keeps quiz/grade and the live-loop signals on one key.
  async function onQuiz() {
    if (!view) return;
    setBusy(true);
    try {
      const passages = view.lesson.slides.map((s) => `${s.title}: ${s.body}`);
      const res = await getQuiz({
        topic: view.lesson.lesson_id,
        passages,
        studentId: getStudentId(),
        classType: view.session.class_type,
        maxItems: 3,
      });
      setQuiz(res.items);
      setQuizIdx(0);
      setQuizDifficulty(res.items[0]?.difficulty ?? "");
      setQuizPick(null);
      setQuizGrade(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  // Grade the picked option. The outcome updates mastery server-side, so the
  // NEXT quiz ("Quiz me again") reflects an adapted difficulty.
  async function onAnswer(idx: number) {
    if (!view || !quiz || quizGrade) return; // ignore re-clicks once answered
    setQuizPick(idx);
    setBusy(true);
    try {
      const g = await gradeQuiz({
        item: quiz[quizIdx],
        chosenIndex: idx,
        studentId: getStudentId(),
        topic: view.lesson.lesson_id,
      });
      setQuizGrade(g);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  function onNextQuestion() {
    if (!quiz) return;
    if (quizIdx + 1 < quiz.length) {
      setQuizIdx(quizIdx + 1);
      setQuizPick(null);
      setQuizGrade(null);
    } else {
      onQuiz(); // round done -> refetch; difficulty reflects updated mastery
    }
  }

  // End the class: run summative when due, then reward verified pass.
  async function onFinish() {
    if (!view || assessmentRun) return;
    setBusy(true);
    try {
      const idx = slide?.index ?? view.lesson.slides.length - 1;
      if (await maybeOpenDueCheckpoint(idx, true)) return;
      if (!canAwardCourseCompletion({ requireVerifiedPass: hasSummativePolicy, passDecisionToken })) {
        // Summative policy exists but no verified pass yet — re-open the exam.
        const summative = findDueSummativeCheckpoint(assessmentPolicy, idx, completedCheckpointsRef.current);
        if (summative) { await openCheckpoint(summative); return; }
      }
      if (passDecisionToken && studentProfile?.id && getToken()) {
        await awardVerifiedPass(passDecisionToken);
      } else {
        await awardCompletion();
      }
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
  // (idempotent server-side). Prefer verified assessment-pass when available.
  async function awardCompletion() {
    if (!view) return;
    if (!getToken()) {
      setFinish({ kind: "guest" });
      return;
    }
    if (passDecisionToken && studentProfile?.id) {
      await awardVerifiedPass(passDecisionToken);
      return;
    }
    try {
      await enrollCourse(lessonId, view.lesson.title, "enrolled");
      const before = await getRewards().then((r) => r.balance).catch(() => 0);
      const res = await setEnrollmentStatus(lessonId, "passed");
      const earned = Math.max(0, res.points_balance - before);
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
      // Real-time chunked voice: stream LLM tokens (Nemotron when configured) ->
      // cut into tiny chunks -> synthesize + play each immediately so the first
      // audio is heard within ~a few words. Falls back to a buffered ask.
      let a: Answer | AskDone | null = null;
      try {
        stopSpeaking();
        setChat((c) => [...c, { role: "teacher", text: "" }]);   // grows as tokens stream
        const chunker = new SpeechChunker();
        const voice = new StreamingVoice((t) => synthChunk(t, { locale: "en", voiceStyle: "standard" }));
        voiceRef.current = voice;
        if (speakAnswers) setSpeaking(true);
        let acc = "";
        a = await askStream(view.session.session_id, q, {
          language: locale,
          onDelta: (chunk) => {
            acc += chunk;
            setChat((c) => {
              const copy = [...c];
              for (let i = copy.length - 1; i >= 0; i--) {
                if (copy[i].role === "teacher") { copy[i] = { ...copy[i], text: acc }; break; }
              }
              return copy;
            });
            if (speakAnswers) for (const piece of chunker.feed(chunk)) voice.enqueue(piece);
          },
        });
        if (speakAnswers) {
          const tail = chunker.flush();
          if (tail) voice.enqueue(tail);
          voice.drained().then(() => setSpeaking(false));
        }
        if (a) {
          setChat((c) => {
            const copy = [...c];
            for (let i = copy.length - 1; i >= 0; i--) {
              if (copy[i].role === "teacher") {
                copy[i] = {
                  role: "teacher", text: a!.text, citations: a!.citations, grounded: a!.grounded,
                  confidence: a!.hallucination_risk !== undefined
                    ? Math.round((1 - a!.hallucination_risk) * 100) : undefined,
                  unsupported: a!.unsupported,
                };
                break;
              }
            }
            return copy;
          });
        }
      } catch {
        // Streaming unsupported/failed -> buffered ask.
        const buffered: Answer = await ask(view.session.session_id, q, locale);
        a = buffered;
        speak(buffered.text);
        setChat((c) => [
          ...c,
          {
            role: "teacher", text: buffered.text, citations: buffered.citations,
            grounded: buffered.grounded,
            confidence: buffered.hallucination_risk !== undefined
              ? Math.round((1 - buffered.hallucination_risk) * 100) : undefined,
            unsupported: buffered.unsupported,
          },
        ]);
      }
      const reward = (a as Answer)?.reward;
      if (reward?.grant_token && getToken()) {
        try {
          const r = await grantReward(reward.grant_token);
          if (r.earned > 0) {
            setChat((c) => [
              ...c,
              { role: "reward", text: `🎉 The AI teacher awarded you ${r.earned} points — ${reward.reason} (balance: ${r.balance})` },
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
      {adBreak && (
        <VideoAdBreak
          adBreak={adBreak}
          placement={`class-${adBreak.position}`}
          tier={effectiveAdTier(tier)}
          onDone={onAdDone}
        />
      )}
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

      {finish && (
        <div className="card" style={{ borderColor: "#16a34a" }}>
          {finish.kind === "earned" && (
            <>
              <strong>🎉 Course complete — you earned {finish.earned} reward points!</strong>
              <div className="muted">
                Balance: {finish.balance} points · <a href="/rewards">Redeem for discounts or prizes →</a>
              </div>
            </>
          )}
          {finish.kind === "complete" && (
            <>
              <strong>✅ Course complete!</strong>
              <div className="muted">
                {finish.balance !== undefined
                  ? <>Reward balance: {finish.balance} points · <a href="/rewards">Rewards →</a></>
                  : "Nice work."}
              </div>
            </>
          )}
          {finish.kind === "guest" && (
            <>
              <strong>✅ Course complete!</strong>
              <div className="muted">
                <a href="/login">Sign in</a> to earn reward points for completing courses.
              </div>
            </>
          )}
        </div>
      )}

      {!view && !loggedIn && <SignInToUse />}

      {!view && (
        <div className="card">
          <h3>Start a session</h3>
          <p className="muted" style={{ marginTop: 0 }}>
            Browse the lessons below. Starting a class requires an account.
          </p>
          <div className="row">
            <select value={lessonId} onChange={(e) => setLessonId(e.target.value)}>
              {lessons.map((l) => (
                <option key={l.lesson_id} value={l.lesson_id}>
                  {l.title}
                </option>
              ))}
            </select>
            <button onClick={onStart} disabled={busy || !lessonId || !loggedIn}
              title={!loggedIn ? "Sign in to take classes" : undefined}>
              Start class
            </button>
          </div>
        </div>
      )}

      {view && slide && (
        <>
          <AiPresenter
            speaking={speaking}
            name="Salareen AI Instructor"
            persona={disclosure?.line?.match(/persona:?\s*([a-z]+)/i)?.[1]}
            caption={spokenText || `${slide.title}. ${slide.narration || slide.body}`}
            live
            muted={!speakAnswers}
            onToggleMute={() => {
              const next = !speakAnswers;
              setSpeakAnswers(next);
              if (!next) stopSpeaking();
              else speak(`${slide.title}. ${slide.narration || slide.body}`);
            }}
            messages={chat}
          />
          <div className="slide">
            <div className="muted">
              {view.lesson.title} · Slide {slide.index + 1} of {view.lesson.slides.length}
            </div>
            <h2>{slide.title}</h2>
            <p>{slide.body}</p>
            <p className="muted">🔊 {slide.narration}</p>

            {slide.say_aloud && (
              <div className="card" style={{ borderColor: "#7c3aed", background: "rgba(124,58,237,0.08)", marginTop: 8 }}>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>🎤 Your turn — repeat after me</div>
                <p style={{ fontSize: 18, margin: "4px 0" }}>
                  &ldquo;<strong>{slide.say_aloud}</strong>&rdquo;
                </p>
                <div className="row" style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <button type="button" onClick={startRepeatAfterMe} disabled={listening}
                    style={{ background: listening ? "#94a3b8" : "#7c3aed", color: "#fff" }}>
                    {listening ? "Listening…" : pron ? "🎤 Try again" : "🎤 Speak now"}
                  </button>
                  <button type="button" onClick={() => speak(slide.narration || `Repeat after me: ${slide.say_aloud}`)}
                    style={{ background: "#e0f2fe", color: "#075985", border: "1px solid #0ea5e9" }}>
                    🔊 Hear it
                  </button>
                  {heard && <span className="muted">You said: &ldquo;{heard}&rdquo;</span>}
                </div>
                {pron && (
                  <div style={{ marginTop: 8 }}>
                    <div style={{ fontSize: 20 }}>
                      {"★".repeat(pron.stars)}{"☆".repeat(Math.max(0, 3 - pron.stars))}{" "}
                      <strong style={{ color: pron.passed ? "#16a34a" : "#d97706" }}>{pron.score}%</strong>
                      {pron.passed ? " — nicely said!" : " — give it another go."}
                    </div>
                    {pron.feedback && <div className="muted" style={{ marginTop: 2 }}>{pron.feedback}</div>}
                    {pron.missed_words?.length > 0 && (
                      <div className="muted" style={{ marginTop: 2 }}>Focus on: {pron.missed_words.join(", ")}</div>
                    )}
                  </div>
                )}
              </div>
            )}

            <div className="row">
              <button onClick={onAdvance} disabled={busy}>
                Next slide →
              </button>
              <button onClick={onReengage} disabled={busy}
                title="Lost or distracted? The AI teacher recaps this slide and checks in."
                style={{ background: "#fff7ed", color: "#b45309", border: "1px solid #f59e0b" }}>
                🧭 I&apos;m lost — refocus
              </button>
              <button onClick={onQuiz} disabled={busy}
                title="Take a quick quiz. Difficulty adapts to your mastery."
                style={{ background: "#eef2ff", color: "#4338ca", border: "1px solid #6366f1" }}>
                🎯 Quiz me
              </button>
              <button onClick={onFinish} disabled={busy}
                style={{ background: "#111", color: "#fff" }}>
                Finish class
              </button>
              <span className="muted">Session {view.session.session_id}</span>
            </div>
          </div>

          <div className="card">
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
              <h3 style={{ margin: 0 }}>Ask the AI teacher</h3>
              <div className="row" style={{ gap: 12, alignItems: "center" }}>
                <button
                  type="button"
                  onClick={() => setShowChat((v) => !v)}
                  title={showChat ? "Hide the chat transcript" : "Show the chat transcript"}
                  style={{
                    fontSize: 13, padding: "4px 10px", borderRadius: 8, cursor: "pointer",
                    border: "1px solid #cbd5e1", background: showChat ? "#fff" : "#eef2ff",
                    color: "#334155",
                  }}
                >
                  {showChat ? "💬 Hide chat" : "💬 Show chat"}
                </button>
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
            </div>
            {showChat && (
            <div className="chat">
              {chat.map((m, i) => (
                <div key={i} className={`bubble ${m.role}`}
                  style={m.role === "reward"
                    ? { background: "#052e16", color: "#bbf7d0", border: "1px solid #16a34a", fontWeight: 600 }
                    : m.role === "reengage"
                    ? { background: "#fff7ed", color: "#7c2d12", border: "1px solid #f59e0b" }
                    : undefined}>
                  {m.role === "reengage" && <strong>🧭 Let&apos;s refocus. </strong>}
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
            )}
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

          {assessmentRun && (
            <AssessmentCheckpointPanel
              run={assessmentRun}
              busy={busy}
              onBusy={setBusy}
              onError={(msg) => setError(msg)}
              onSubmitted={(result) => { void onAssessmentSubmitted(result); }}
              onDismiss={
                hasSummativePolicy && assessmentRun?.checkpoint.stage === "summative" && !passDecisionToken
                  ? undefined
                  : () => {
                      if (assessmentRun) completedCheckpointsRef.current.add(assessmentRun.checkpoint.checkpoint_id);
                      setAssessmentRun(null);
                    }
              }
            />
          )}

          {assessmentResult && !assessmentRun && (
            <div
              className="card"
              style={{ borderColor: assessmentResult.attempt.passed ? "#16a34a" : "#d97706" }}
            >
              <strong>
                {assessmentResult.attempt.passed ? "Checkpoint passed" : "Checkpoint not yet passed"}
                {" — "}
                {Math.round(assessmentResult.attempt.score * 100)}%
              </strong>
              {assessmentResult.attempt.stage === "summative" && !assessmentResult.course_decision?.passed ? (
                <button
                  type="button"
                  style={{ marginTop: 8 }}
                  onClick={() => {
                    setAssessmentResult(null);
                    // Use the last known slide index; fall back to total-1 so the
                    // summative (due at the final slide) is never gated out by a 0 fallback.
                    const idx = slide?.index ?? (view?.lesson.slides.length ?? 1) - 1;
                    const summative = findDueSummativeCheckpoint(
                      assessmentPolicy, idx, completedCheckpointsRef.current,
                    );
                    if (summative) void openCheckpoint(summative);
                  }}
                >
                  Retry assessment
                </button>
              ) : (
                <button type="button" style={{ marginTop: 8 }} onClick={() => setAssessmentResult(null)}>
                  Continue
                </button>
              )}
            </div>
          )}

          {quiz && quiz.length > 0 && (
            <div className="card">
              <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0 }}>Quiz</h3>
                <span
                  title="Difficulty adapts to your mastery via the memory service"
                  style={{
                    padding: "2px 10px", borderRadius: 999, fontWeight: 600, fontSize: 13,
                    ...difficultyStyle(quizDifficulty),
                  }}
                >
                  {quizDifficulty || "medium"} difficulty
                </span>
              </div>
              <div className="muted" style={{ marginTop: 4 }}>
                Question {quizIdx + 1} of {quiz.length} · answer correctly and the next quiz gets harder.
              </div>
              <div style={{ marginTop: 12 }}>
                <p style={{ fontWeight: 600 }}>{quiz[quizIdx].prompt}</p>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {quiz[quizIdx].options.map((opt, i) => {
                    const answered = quizGrade !== null;
                    const isCorrect = i === quiz[quizIdx].answer_index;
                    const isPicked = i === quizPick;
                    const bg = answered && isCorrect ? "#dcfce7" : answered && isPicked ? "#fee2e2" : "#fff";
                    const bd = answered && isCorrect ? "#16a34a" : answered && isPicked ? "#dc2626" : "#cbd5e1";
                    const col = answered && isCorrect ? "#14532d" : answered && isPicked ? "#7f1d1d" : "#0f172a";
                    return (
                      <button
                        key={i}
                        onClick={() => onAnswer(i)}
                        disabled={busy || answered}
                        style={{
                          textAlign: "left", padding: "8px 12px", borderRadius: 8,
                          background: bg, border: `1px solid ${bd}`, color: col,
                          cursor: answered ? "default" : "pointer",
                        }}
                      >
                        {opt}
                        {answered && isCorrect ? "  ✓" : answered && isPicked && !isCorrect ? "  ✗" : ""}
                      </button>
                    );
                  })}
                </div>
                {quizGrade && (
                  <div style={{ marginTop: 10 }}>
                    <div style={{ fontWeight: 600, color: quizGrade.correct ? "#16a34a" : "#dc2626" }}>
                      {quizGrade.correct ? "Correct!" : "Not quite."}
                      <span className="muted" style={{ fontWeight: 400 }}>
                        {" "}· mastery target {Math.round(quizGrade.mastery_target * 100)}%
                      </span>
                    </div>
                    <button onClick={onNextQuestion} disabled={busy} style={{ marginTop: 8 }}>
                      {quizIdx + 1 < quiz.length
                        ? "Next question →"
                        : "Quiz me again (adapts difficulty) ↻"}
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
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
