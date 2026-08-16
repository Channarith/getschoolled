"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  advance,
  ask,
  directorLxTick,
  enrollCourse,
  generateClassQuiz,
  getAssessmentPolicy,
  getDisclosure,
  getStudentAdaptation,
  grantReward,
  gradeQuizItem,
  getPostClassSurvey,
  getPulseSurvey,
  getRewards,
  getToken,
  listLessons,
  listStudents,
  pronounce,
  recordAdaptationEvent,
  recordAssessmentAttempt,
  recordAssessmentPass,
  recordBehavior,
  recordWellnessCheckIn,
  reportIssue,
  setEnrollmentStatus,
  startAssessmentCheckpoint,
  startSession,
  submitPostClassSurvey,
  submitPulseSurvey,
  updateTopicMastery,
  type Answer,
  type AssessmentCheckpointSpec,
  type AssessmentRun,
  type AssessmentSubmitResult,
  type ClassQuizItem,
  type Disclosure,
  type Lesson,
  type Pronounce,
  type SessionView,
  type Slide,
  type StudentProfile,
  type SurveyTemplate,
} from "../lib/api";
import {
  canAwardCourseCompletion,
  findDueFormativeCheckpoint,
  findDueSummativeCheckpoint,
  shouldOpenSummativeOnAdvance,
} from "../lib/assessmentFlow";
import SignInToUse from "./SignInToUse";
import AiPresenter from "./AiPresenter";
import AssessmentCheckpointPanel from "./AssessmentCheckpointPanel";
import CameraLightingScreener from "./CameraLightingScreener";
import { useT } from "../lib/i18n";
import { buildNarrationSpeakOptions } from "../lib/narrationTts";
import { cancelSpeech, speakNaturally } from "../lib/tts";
import { useVoicePauseSubmitMs } from "../lib/flags";
import { createVoicePauseSubmitter } from "../lib/voiceCommands";

// Minimal Web Speech API typing for the repeat-after-me checkpoint.
type SpeechRec = {
  lang: string; interimResults: boolean; continuous?: boolean; maxAlternatives: number;
  onresult: (e: {
    resultIndex: number;
    results: { length: number; [i: number]: { [j: number]: { transcript: string } } };
  }) => void;
  onerror: ((e?: { error?: string }) => void) | (() => void); onend: () => void; start: () => void; stop: () => void;
};

const RECOG_LANG: Record<string, string> = {
  en: "en-US", es: "es-ES", fr: "fr-FR", de: "de-DE", it: "it-IT", pt: "pt-BR",
  zh: "zh-CN", ja: "ja-JP", ko: "ko-KR", hi: "hi-IN", ar: "ar-SA", ru: "ru-RU",
};

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
  /**
   * Professional / corporate courses: block silent completion awards until the
   * end-of-course assessment issues a verified pass token. Locked lessons
   * default to true.
   */
  requireVerifiedPass?: boolean;
};

export default function ClassRoom({
  title,
  lockedLessonId,
  initialLessonId,
  hideCorporate = false,
  backHref,
  backLabel,
  startLabel,
  requireVerifiedPass,
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
  const [lightingReady, setLightingReady] = useState(false);
  const [disclosure, setDisclosure] = useState<Disclosure | null>(null);
  const [survey, setSurvey] = useState<SurveyTemplate | null>(null);
  const [surveyAnswers, setSurveyAnswers] = useState<Record<string, string | number | boolean>>({});
  const [surveyDone, setSurveyDone] = useState(false);
  const [pulseEnabled, setPulseEnabled] = useState(false);
  const [pulseTemplate, setPulseTemplate] = useState<SurveyTemplate | null>(null);
  const [showPulse, setShowPulse] = useState(false);
  const [pulseAnswers, setPulseAnswers] = useState<Record<string, string | number>>({});
  const [finish, setFinish] = useState<
    | { kind: "earned"; earned: number; balance: number }
    | { kind: "complete"; balance?: number }
    | { kind: "guest" }
    | null
  >(null);
  const [speakAnswers, setSpeakAnswers] = useState(true);
  const [speaking, setSpeaking] = useState(false);
  // Immersive presenter: the text currently being narrated (for live captions)
  // and a fullscreen "Zoom call" mode for the AI instructor + slide.
  const [spokenText, setSpokenText] = useState("");
  const [isFullscreen, setIsFullscreen] = useState(false);
  const stageRef = useRef<HTMLDivElement | null>(null);
  // Autoplay: the AI presenter narrates a slide, then advances to the next so it
  // teaches the whole course beginning-to-end (pauses on repeat-after-me slides,
  // quizzes, pulse checks, and the last slide). A ref mirrors it for callbacks.
  const [autoplay, setAutoplay] = useState(true);
  const autoplayRef = useRef(true);
  const autoAdvanceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [loggedIn, setLoggedIn] = useState(true);   // assume true until resolved (avoids flash)
  const [slidesSinceQuiz, setSlidesSinceQuiz] = useState(0);
  const [popQuiz, setPopQuiz] = useState<ClassQuizItem[] | null>(null);
  const [popQuizAnswers, setPopQuizAnswers] = useState<Record<string, number>>({});
  const [studentId, setStudentId] = useState("");
  const [studentProfile, setStudentProfile] = useState<StudentProfile | null>(null);
  const [assessmentPolicy, setAssessmentPolicy] = useState<AssessmentCheckpointSpec[]>([]);
  const [assessmentRun, setAssessmentRun] = useState<AssessmentRun | null>(null);
  const [assessmentResult, setAssessmentResult] = useState<AssessmentSubmitResult | null>(null);
  const [passDecisionToken, setPassDecisionToken] = useState<string | null>(null);
  const [heard, setHeard] = useState("");
  const [pron, setPron] = useState<Pronounce | null>(null);
  const [listening, setListening] = useState(false);
  const pauseSubmitMs = useVoicePauseSubmitMs();
  const recognitionRef = useRef<SpeechRec | null>(null);
  const pauseSubmitterRef = useRef<ReturnType<typeof createVoicePauseSubmitter> | null>(null);
  const [adaptationProfile, setAdaptationProfile] = useState<Record<string, unknown>>({});
  const [lxScore, setLxScore] = useState<number | null>(null);
  const [lxTarget, setLxTarget] = useState(75);
  const [lxStrategy, setLxStrategy] = useState("");
  const [wellness, setWellness] = useState("ok");
  const sessionStartRef = useRef<number | null>(null);
  const frustrationCountRef = useRef(0);
  const questionsAskedRef = useRef(0);
  const quizStatsRef = useRef({ correct: 0, total: 0 });
  const declaredPaceRef = useRef("moderate");
  const speechRef = useRef<SpeechSynthesisUtterance | null>(null);
  const autoStartedRef = useRef(false);
  const completedCheckpointsRef = useRef<Set<string>>(new Set());
  const assessmentStartingRef = useRef(false);

  // mustVerifyPass: only enforce the assessment gate when the course actually has
  // a summative checkpoint in its policy. This keeps corporate (requireVerifiedPass)
  // and self-paced (locked) courses consistent with class/page.tsx behaviour:
  // if the server's policy is empty the gate is silently bypassed rather than
  // blocking completion with a confusing "assessment required" error.
  const hasSummativeInPolicy = assessmentPolicy.some((cp) => cp.stage === "summative");
  const mustVerifyPass = (requireVerifiedPass ?? locked) && hasSummativeInPolicy;

  useEffect(() => {
    const signedIn = Boolean(getToken());
    setLoggedIn(signedIn);
    if (signedIn) {
      listStudents().then((r) => {
        const first = r.students[0] ?? null;
        const sid = first?.id ?? "";
        setStudentId(sid);
        setStudentProfile(first);
        if (sid) {
          getStudentAdaptation(sid).then((prof) => {
            setAdaptationProfile(prof.adaptation ?? {});
            declaredPaceRef.current = prof.learning_pace || "moderate";
          }).catch(() => {});
        }
      }).catch(() => {});
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
    getPulseSurvey()
      .then((r) => {
        setPulseEnabled(r.enabled);
        setPulseTemplate(r.template);
      })
      .catch(() => {});
    return () => stopSpeaking();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Locked mode (corporate course): start only after the camera/lighting gate
  // passes, so dark/blurry rooms never land mid-lesson with broken tracking.
  useEffect(() => {
    if (
      locked &&
      loggedIn &&
      lightingReady &&
      !view &&
      !busy &&
      !finish &&
      !autoStartedRef.current
    ) {
      autoStartedRef.current = true;
      onStart();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locked, loggedIn, lightingReady, view, busy, finish]);

  // When the language switches mid-class, cancel any in-flight narration so it
  // doesn't keep talking in the previous language; the next spoken line (slide
  // advance or answer) is then narrated with the newly-selected voice.
  useEffect(() => {
    stopSpeaking();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locale]);

  function stopSpeaking() {
    // cancelSpeech() stops BOTH the on-device voice AND the neural server audio
    // (and aborts any in-flight fetch). Calling only speechSynthesis.cancel()
    // left neural MP3 narration playing — which is why the class "couldn't be
    // stopped". Also clear any pending auto-advance so it doesn't jump ahead.
    cancelSpeech();
    try { window.speechSynthesis.cancel(); } catch { /* no browser TTS */ }
    if (autoAdvanceRef.current) { clearTimeout(autoAdvanceRef.current); autoAdvanceRef.current = null; }
    speechRef.current = null;
    setSpeaking(false);
  }

  function speak(text: string, onDone?: () => void) {
    setSpokenText(text || "");   // live caption, even if audio is muted/unavailable
    if (!speakAnswers || typeof window === "undefined" || !("speechSynthesis" in window)) {
      // No audio: don't auto-advance — the learner reads and taps Next.
      return;
    }
    stopSpeaking();
    void buildNarrationSpeakOptions(locale).then((base) => {
      speakNaturally(text, {
        ...base,
        onend: () => { setSpeaking(false); onDone?.(); },
      });
    });
    setSpeaking(true);
  }

  useEffect(() => { autoplayRef.current = autoplay; }, [autoplay]);

  // Continue the lecture after a quiz / pulse check / assessment closes (autoplay only).
  function resumeAutoplay() {
    if (!autoplayRef.current || !speakAnswers) return;
    if (autoAdvanceRef.current) clearTimeout(autoAdvanceRef.current);
    autoAdvanceRef.current = setTimeout(() => { void onAdvance(); }, 400);
  }

  async function openCheckpoint(cp: AssessmentCheckpointSpec) {
    if (!view || assessmentStartingRef.current || assessmentRun) return;
    const sid = studentId || "guest";
    assessmentStartingRef.current = true;
    stopSpeaking();
    setAutoplay(false);
    setBusy(true);
    try {
      const acc = studentProfile?.accessibility || {};
      const run = await startAssessmentCheckpoint({
        studentId: sid,
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
      // Only permanently skip on content-unavailable (422). Transient network
      // errors (5xx, offline) should remain retryable so a summative exam is
      // not silently bypassed due to a momentary server blip.
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

  async function onAssessmentSubmitted(result: AssessmentSubmitResult) {
    const checkpointId = result.attempt.checkpoint_id;
    const passedOrFormative = result.attempt.passed || result.attempt.stage === "formative";
    if (passedOrFormative) {
      completedCheckpointsRef.current = new Set(completedCheckpointsRef.current).add(checkpointId);
    }
    setAssessmentResult(result);
    setAssessmentRun(null);
    if (result.attempt_result_token && studentId && getToken()) {
      recordAssessmentAttempt(studentId, result.attempt_result_token).catch(() => {});
    }
    if (result.pass_decision_token) {
      setPassDecisionToken(result.pass_decision_token);
    }
    if (result.attempt.stage === "summative" && result.course_decision?.passed && result.pass_decision_token) {
      completedCheckpointsRef.current = new Set(completedCheckpointsRef.current).add(checkpointId);
      await awardVerifiedPass(result.pass_decision_token);
      const surveyRes = await getPostClassSurvey().catch(() => null);
      if (surveyRes?.enabled && surveyRes.template
          && !localStorage.getItem(`survey-done-${lessonId}`)) {
        setSurvey(surveyRes.template);
        setSurveyAnswers({});
        setSurveyDone(false);
      }
      return;
    }
    if (result.attempt.stage === "formative") {
      resumeAutoplay();
    }
  }

  function dismissAssessment() {
    // Professional courses: do not silently skip a required end-of-course exam.
    if (
      mustVerifyPass
      && assessmentRun?.checkpoint.stage === "summative"
      && !passDecisionToken
    ) {
      setError("Complete the end-of-course assessment to finish this professional course.");
      return;
    }
    if (assessmentRun) {
      completedCheckpointsRef.current = new Set(completedCheckpointsRef.current)
        .add(assessmentRun.checkpoint.checkpoint_id);
    }
    setAssessmentRun(null);
    setAssessmentResult(null);
    resumeAutoplay();
  }

  async function awardVerifiedPass(token: string) {
    if (!view) return;
    if (!getToken() || !studentId) {
      setFinish({ kind: "guest" });
      return;
    }
    try {
      await enrollCourse(lessonId, view.lesson.title, "enrolled");
      const before = await getRewards().then((r) => r.balance).catch(() => 0);
      const res = await recordAssessmentPass(studentId, token);
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

  // Fullscreen "Zoom call" mode for the presenter + slide.
  useEffect(() => {
    if (typeof document === "undefined") return;
    const onFs = () => setIsFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", onFs);
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, []);

  function toggleFullscreen() {
    if (typeof document === "undefined") return;
    if (document.fullscreenElement) { void document.exitFullscreen().catch(() => undefined); return; }
    const el = stageRef.current;
    if (el?.requestFullscreen) void el.requestFullscreen().catch(() => undefined);
  }

  // On each slide change, reset any prior speaking-checkpoint result. For a
  // repeat-after-me slide, have the teacher say the phrase so the learner can
  // echo it (the class then pauses here until they speak or advance).
  useEffect(() => {
    setHeard("");
    setPron(null);
    setListening(false);
    if (autoAdvanceRef.current) { clearTimeout(autoAdvanceRef.current); autoAdvanceRef.current = null; }
    if (!slide || !view || assessmentRun || showPulse || popQuiz) return;
    // The AI instructor narrates EVERY slide as it appears (this is what makes it
    // feel driven/immersive) — a repeat-after-me slide leads with its cue. When
    // the narration finishes, auto-advance so it teaches the whole course end to
    // end — pausing on repeat-after-me, quizzes, pulse checks, and the last slide.
    // Narrate the full slide body (a substantive mini-lecture), not just the
    // terse one-line script, so a self-paced course actually teaches in depth.
    const line = slide.say_aloud
      ? (slide.narration || `Repeat after me: ${slide.say_aloud}`)
      : `${slide.title}. ${slide.body || slide.narration || ""}`.trim();
    const isLast = slide.index >= view.lesson.slides.length - 1;
    let advanced = false;
    const goNext = () => {
      if (advanced) return;
      advanced = true;
      if (autoAdvanceRef.current) { clearTimeout(autoAdvanceRef.current); autoAdvanceRef.current = null; }
      // Advance through EVERY slide (including repeat-after-me) so the AI teaches
      // the whole course end-to-end; only stop on the final slide.
      if (autoplayRef.current && !isLast) void onAdvance();
    };
    // Narrate the slide; for a normal slide, advance shortly after it finishes.
    // For a repeat-after-me slide we DON'T advance on narration-end — the dwell
    // timer below gives the learner a beat to speak, then continues.
    speak(line, () => {
      if (!slide.say_aloud) autoAdvanceRef.current = setTimeout(goNext, 500);
    });
    // Also advance after an estimated reading time, so the lecture never stalls
    // even if the browser's speech `onend` doesn't fire (a known long-text quirk)
    // and so repeat-after-me slides continue after a pause. Only when audio is on
    // (muted = the learner reads and taps Next themselves).
    if (autoplayRef.current && speakAnswers && !isLast) {
      const words = line.split(/\s+/).filter(Boolean).length;
      const dwellMs = slide.say_aloud
        ? 15000  // repeat-after-me: give ~15s to echo the phrase, then move on
        : Math.min(90000, Math.max(7000, words * 430));
      autoAdvanceRef.current = setTimeout(goNext, dwellMs);
    }
    return () => { if (autoAdvanceRef.current) { clearTimeout(autoAdvanceRef.current); autoAdvanceRef.current = null; } };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slide?.index]);

  // Stop any pending auto-advance when leaving the class.
  useEffect(() => () => { if (autoAdvanceRef.current) clearTimeout(autoAdvanceRef.current); }, []);

  // Listen to the learner and score how closely they said the target phrase.
  async function startRepeatAfterMe() {
    const target = slide?.say_aloud;
    if (!target) return;
    if (typeof window !== "undefined" && !window.isSecureContext) {
      setError(
        "Your mic needs a secure connection. Open Salareen over https:// — " +
        "the browser blocks the microphone on an insecure page."
      );
      return;
    }
    const w = window as unknown as { webkitSpeechRecognition?: new () => SpeechRec; SpeechRecognition?: new () => SpeechRec };
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!Ctor) { setError("Speech recognition isn't available in this browser — try Chrome."); return; }
    try {
      if (navigator.mediaDevices?.getUserMedia) {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach((track) => track.stop());
      }
    } catch {
      setError(
        "Microphone access is blocked. Click the site-settings icon in the address " +
        "bar, allow the microphone, then tap 🎤 Speak now again."
      );
      return;
    }
    stopSpeaking();   // don't record our own narration
    let rec: SpeechRec;
    try {
      rec = new Ctor();
    } catch {
      setError("Couldn't start the microphone. Try Chrome over https://.");
      return;
    }
    try { recognitionRef.current?.stop(); } catch { /* */ }
    pauseSubmitterRef.current?.cancelPending();
    rec.lang = RECOG_LANG[locale] ?? "en-US";
    rec.interimResults = true;
    rec.continuous = true;
    rec.maxAlternatives = 1;
    setPron(null);
    setHeard("");
    setListening(true);
    const submitter = createVoicePauseSubmitter(pauseSubmitMs, (said) => {
      setHeard(said);
      setListening(false);
      try { rec.stop(); } catch { /* */ }
      pronounce(target, said)
        .then((r) => {
          setPron(r);
          if (studentId) {
            recordBehavior({
              student_id: studentId,
              topic: view?.lesson.title ?? "",
              saw_slide: true,
            }).catch(() => {});
          }
        })
        .catch((err) => setError(String(err)));
    });
    pauseSubmitterRef.current = submitter;
    rec.onresult = (e) => {
      const parts: string[] = [];
      for (let i = 0; i < e.results.length; i++) {
        const chunk = e.results[i]?.[0]?.transcript ?? "";
        if (chunk) parts.push(chunk);
      }
      const said = parts.join(" ").trim();
      if (!said) return;
      setHeard(said);
      submitter.updateTranscript(said);
    };
    rec.onerror = (e) => {
      setListening(false);
      submitter.cancelPending();
      const code = (e as { error?: string })?.error || "";
      if (code === "not-allowed" || code === "service-not-allowed") {
        setError("Microphone access is blocked — allow the mic for this site (address-bar icon).");
      }
    };
    rec.onend = () => {
      submitter.flush();
      setListening(false);
      recognitionRef.current = null;
      pauseSubmitterRef.current = null;
    };
    recognitionRef.current = rec;
    try {
      rec.start();
    } catch {
      setListening(false);
      recognitionRef.current = null;
      pauseSubmitterRef.current = null;
      setError("Couldn't start the microphone. Try Chrome over https://.");
    }
  }

  async function refreshLxTick(slideIndex: number, slidesTotal: number) {
    if (!studentId || !getToken()) return;
    const stats = quizStatsRef.current;
    const quizAccuracy = stats.total > 0 ? stats.correct / stats.total : 0.5;
    try {
      const tick = await directorLxTick({
        class_type: classType,
        slides_total: slidesTotal,
        slide_index: slideIndex,
        pending_questions: 0,
        attention: 0.75,
        slides_since_quiz: slidesSinceQuiz,
        topic_mastery: quizAccuracy,
        quiz_accuracy: quizAccuracy,
        avg_response_latency_s: 8,
        attention_trend: 0.75,
        question_rate: questionsAskedRef.current / Math.max(1, slideIndex + 1),
        declared_pace: declaredPaceRef.current,
        adaptation: adaptationProfile,
        wellness_state: wellness,
        course_complexity: slidesTotal > 30 ? 4 : slidesTotal < 12 ? 2 : 3,
        frustration_events: frustrationCountRef.current,
      });
      setLxScore(tick.lx_score);
      setLxTarget(tick.lx_target);
      setLxStrategy(tick.teaching_strategy);
      recordAdaptationEvent(studentId, "lx_tick", {
        score: tick.lx_score,
        strategy: tick.teaching_strategy,
        success: tick.lx_score >= tick.lx_target,
      }).catch(() => {});
    } catch {
      /* offline: keep teaching */
    }
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
      frustrationCountRef.current = 0;
      questionsAskedRef.current = 0;
      quizStatsRef.current = { correct: 0, total: 0 };
      completedCheckpointsRef.current = new Set();
      setAssessmentRun(null);
      setAssessmentResult(null);
      setPassDecisionToken(null);
      setView(v);
      setSlide(v.slide);
      setChat([]);
      try {
        const policy = await getAssessmentPolicy(v.session.session_id);
        setAssessmentPolicy(policy.checkpoints);
      } catch {
        setAssessmentPolicy([]);
      }
      await refreshLxTick(v.slide.index, v.lesson.slides.length);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onAdvance() {
    if (!view || popQuiz || showPulse || assessmentRun) return;
    setBusy(true);
    try {
      const s = await advance(view.session.session_id);
      setSlide(s);
      if (studentId) {
        recordBehavior({
          student_id: studentId,
          topic: view.lesson.title,
          saw_slide: true,
        }).catch(() => {});
      }
      await refreshLxTick(s.index, view.lesson.slides.length);
      // Policy checkpoints interrupt teaching (including autoplay): mid-course
      // pop quizzes (formative) and the end-of-course exam on the last slide.
      const openFinal = shouldOpenSummativeOnAdvance(s.index, view.lesson.slides.length);
      if (await maybeOpenDueCheckpoint(s.index, openFinal)) return;
      // While autoplay is on, the AI teaches straight through — don't interrupt
      // the lecture with pulse surveys or legacy pop quizzes (they require
      // interaction). They resume in self-paced mode when autoplay is paused.
      // Policy formatives/summatives above still fire under autoplay.
      if (autoplayRef.current) return;
      const interval = pulseTemplate?.interval_slides ?? 5;
      if (pulseEnabled && pulseTemplate && (s.index + 1) % interval === 0) {
        setPulseAnswers({});
        setShowPulse(true);
        return;
      }
      const nextCount = slidesSinceQuiz + 1;
      setSlidesSinceQuiz(nextCount);
      if (nextCount >= 3) {
        const passages = view.lesson.slides
          .slice(Math.max(0, s.index - 3), s.index + 1)
          .map((sl) => `${sl.title}: ${sl.body || sl.narration}`);
        const quiz = await generateClassQuiz(view.lesson.title, passages, 2);
        if (quiz.items?.length) {
          setPopQuiz(quiz.items);
          setPopQuizAnswers({});
          setSlidesSinceQuiz(0);
        }
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function submitPulse() {
    if (!view || !pulseTemplate) {
      setShowPulse(false);
      return;
    }
    const goingWell = Number(pulseAnswers["going_well"] ?? 0);
    const pace = String(pulseAnswers["pace"] ?? "");
    if (!goingWell || !pace) {
      setError(t("class.pulseRequired"));
      return;
    }
    setBusy(true);
    try {
      const workingBest = pulseAnswers["working_best"]
        ? String(pulseAnswers["working_best"]) : null;
      await submitPulseSurvey({
        course_id: lessonId,
        going_well: goingWell,
        pace,
        class_type: classType,
        student_id: studentId || null,
        slide_index: slide?.index ?? 0,
        teaching_strategy: lxStrategy,
        working_best: workingBest,
      });
      if (studentId) {
        const out = await recordAdaptationEvent(studentId, "pulse_survey", {
          course_id: lessonId,
          going_well: goingWell,
          pace,
          working_best: workingBest,
          teaching_strategy: lxStrategy,
        });
        setAdaptationProfile(out.adaptation ?? adaptationProfile);
        if (pace === "too fast") {
          recordAdaptationEvent(studentId, "trigger", {
            trigger: "pace too fast",
            reason: "pulse survey during class",
            severity: "medium",
            allow_retry: true,
          }).catch(() => {});
        }
      }
      await refreshLxTick(slide?.index ?? 0, view.lesson.slides.length);
      setShowPulse(false);
      resumeAutoplay();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  function skipPulse() {
    setShowPulse(false);
    setPulseAnswers({});
    resumeAutoplay();
  }

  async function submitPopQuiz() {
    if (!popQuiz || !view || !studentId) {
      dismissPopQuiz();
      return;
    }
    setBusy(true);
    let correct = 0;
    try {
      for (const item of popQuiz) {
        const chosen = popQuizAnswers[item.item_id];
        if (chosen === undefined) continue;
        const graded = await gradeQuizItem(item, chosen);
        if (graded.correct) correct += 1;
        quizStatsRef.current.total += 1;
        if (graded.correct) quizStatsRef.current.correct += 1;
        await recordBehavior({
          student_id: studentId,
          topic: view.lesson.title,
          quiz_correct: graded.correct,
        }).catch(() => {});
        await updateTopicMastery(studentId, view.lesson.title, graded.correct).catch(() => {});
      }
      if (popQuiz.length > 0) {
        recordAdaptationEvent(studentId, "strategy_success", {
          strategy: lxStrategy || "worked_examples",
        }).catch(() => {});
      }
      await refreshLxTick(slide?.index ?? 0, view.lesson.slides.length);
    } finally {
      setPopQuiz(null);
      setPopQuizAnswers({});
      setBusy(false);
      resumeAutoplay();
    }
  }

  function dismissPopQuiz() {
    setPopQuiz(null);
    setPopQuizAnswers({});
    resumeAutoplay();
  }

  // End the class: run the summative when due, then reward verified pass.
  async function onFinish() {
    if (!view || assessmentRun) return;
    setBusy(true);
    try {
      const idx = slide?.index ?? view.lesson.slides.length - 1;
      if (await maybeOpenDueCheckpoint(idx, true)) return;
      if (
        !canAwardCourseCompletion({
          requireVerifiedPass: mustVerifyPass,
          passDecisionToken,
        })
      ) {
        const summative = findDueSummativeCheckpoint(
          assessmentPolicy, idx, completedCheckpointsRef.current,
        );
        if (summative) {
          await openCheckpoint(summative);
          return;
        }
        // Failed summative without a pass token — reopen final exam for retry.
        const finalCp = assessmentPolicy.find((cp) => cp.stage === "summative");
        if (finalCp) {
          completedCheckpointsRef.current = new Set(
            [...completedCheckpointsRef.current].filter((id) => id !== finalCp.checkpoint_id),
          );
          await openCheckpoint(finalCp);
          return;
        }
        setError(
          "This professional course requires a passing end-of-course assessment before completion credit.",
        );
        return;
      }
      if (passDecisionToken && studentId && getToken()) {
        await awardVerifiedPass(passDecisionToken);
      } else {
        await awardCompletion();
      }
      const res = await getPostClassSurvey();
      if (res.enabled && res.template
          && !localStorage.getItem(`survey-done-${lessonId}`)) {
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
    if (passDecisionToken && studentId) {
      await awardVerifiedPass(passDecisionToken);
      return;
    }
    if (mustVerifyPass) {
      setError(
        "This professional course requires a passing end-of-course assessment before completion credit.",
      );
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
        if (lxScore !== null) {
          recordAdaptationEvent(studentId, "lx_session_end", {
            score: lxScore,
            strategy: lxStrategy,
            success: lxScore >= lxTarget,
          }).catch(() => {});
        }
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
        const clarity = surveyAnswers["clarity"] != null ? Number(surveyAnswers["clarity"]) : null;
        const surveyScore = Math.round((overall / 5) * 100);
        recordAdaptationEvent(studentId, "lx_session_end", {
          score: surveyScore,
          strategy: lxStrategy,
          success: surveyScore >= lxTarget,
        }).catch(() => {});
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
      localStorage.setItem(`survey-done-${lessonId}`, "1");
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
      frustrationCountRef.current += 1;
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
    questionsAskedRef.current += 1;
    if (studentId) {
      recordBehavior({
        student_id: studentId,
        topic: view.lesson.title,
        asked_question: true,
      }).catch(() => {});
    }
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
              <button onClick={() => { autoStartedRef.current = false; setLightingReady(false); setFinish(null); }}>
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

      {!view && loggedIn && !finish && !lightingReady && (
        <CameraLightingScreener
          onReady={() => setLightingReady(true)}
          title="Camera and lighting check"
        />
      )}

      {/* Picker mode (Live Class): choose a lesson and class type. */}
      {!view && !locked && lightingReady && (
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

      {/* Locked mode (corporate course): auto-starting after lighting gate. */}
      {!view && locked && loggedIn && lightingReady && !finish && (
        <div className="card">
          {busy ? (
            <p className="muted" style={{ margin: 0 }}>{t("class.startingCourse")}</p>
          ) : (
            <button
              onClick={() => {
                autoStartedRef.current = false;
                setLightingReady(false);
              }}
            >
              Re-check camera
            </button>
          )}
        </div>
      )}

      {view && slide && (
        <>
          <div
            ref={stageRef}
            style={
              isFullscreen
                ? { background: "#060a17", padding: "24px 16px", minHeight: "100vh", overflowY: "auto", display: "flex", flexDirection: "column", alignItems: "center", gap: 16, justifyContent: "flex-start" }
                : { display: "flex", flexDirection: "column", gap: 12 }
            }
          >
            <div style={isFullscreen ? { width: "100%", maxWidth: 760, alignSelf: "center" } : undefined}>
              <AiPresenter
                speaking={speaking}
                name="Salareen AI Instructor"
                persona={disclosure?.line?.match(/persona:?\s*([a-z]+)/i)?.[1]}
                caption={spokenText || `${slide.title}. ${slide.narration || slide.body}`}
                muted={!speakAnswers}
                onToggleMute={() => {
                  const next = !speakAnswers;
                  setSpeakAnswers(next);
                  if (!next) stopSpeaking();
                  else speak(`${slide.title}. ${slide.body || slide.narration}`);
                }}
                messages={chat}
              />
            </div>
          <div
            className="slide"
            style={isFullscreen
              ? { alignSelf: "center", width: "100%", maxWidth: 980, background: "transparent", border: "none", color: "#e8ecf6" }
              : undefined}
          >
            <div className="muted" style={isFullscreen ? { fontSize: 15, color: "#c7d2fe" } : undefined}>
              {view.lesson.title} · {t("class.slideOf", {
                current: slide.index + 1,
                total: view.lesson.slides.length,
              })}
              {lxScore !== null && (
                <span style={{ marginLeft: 12 }}>
                  · {t("class.lxScore", { score: lxScore, target: lxTarget })}
                  {lxStrategy ? ` · ${lxStrategy.replace(/_/g, " ")}` : ""}
                </span>
              )}
            </div>
            <h2 style={isFullscreen ? { fontSize: "clamp(30px, 4.2vw, 52px)", lineHeight: 1.15, color: "#fff", margin: "6px 0" } : undefined}>{slide.title}</h2>
            <p style={isFullscreen ? { fontSize: "clamp(18px, 2.2vw, 26px)", lineHeight: 1.6, color: "#e8ecf6" } : undefined}>{slide.body}</p>
            <p className="muted" style={isFullscreen ? { fontSize: 16, color: "#9fb4d8" } : undefined}>🔊 {slide.narration}</p>

            {slide.say_aloud && (
              <div className="card" style={{ borderColor: "#7c3aed", background: "rgba(124,58,237,0.08)", marginTop: 8 }}>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>🎤 Your turn — repeat after me</div>
                <p style={{ fontSize: 18, margin: "4px 0" }}>
                  &ldquo;<strong>{slide.say_aloud}</strong>&rdquo;
                </p>
                <div className="row" style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <button
                    type="button"
                    onClick={() => void startRepeatAfterMe()}
                    disabled={listening}
                    style={{ background: listening ? "#94a3b8" : "#7c3aed", color: "#fff" }}
                  >
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
              <button
                type="button"
                onClick={() => {
                  setAutoplay((v) => {
                    const next = !v;
                    // Pausing must actually stop the AI talking now (not just
                    // prevent the next advance) — halt narration + pending timer.
                    if (!next) stopSpeaking();
                    return next;
                  });
                }}
                title="Autoplay: the AI teaches the whole course and advances on its own"
                style={{ background: autoplay ? "#4f46e5" : "transparent", color: autoplay ? "#fff" : "inherit", border: "1px solid var(--border)" }}
              >
                {autoplay ? "⏸ Pause autoplay" : "▶ Autoplay"}
              </button>
              <button onClick={onAdvance} disabled={busy}>
                {t("class.nextSlide")}
              </button>
              <button onClick={onFinish} disabled={busy}
                style={{ background: "#111", color: "#fff" }}>
                {t("class.finishClass")}
              </button>
              <button type="button" onClick={toggleFullscreen}
                style={{ background: "transparent", border: "1px solid var(--border)" }}
                title="Fullscreen the presentation (Esc to exit)">
                {isFullscreen ? "⛶ Exit fullscreen" : "⛶ Fullscreen"}
              </button>
              <span className="muted">{t("class.session", { id: view.session.session_id })}</span>
            </div>
          </div>
          </div>

          {mustVerifyPass && view && !assessmentRun && (
            <div className="card" style={{ borderColor: "#6366f1", background: "rgba(99,102,241,0.06)" }}>
              <strong>Professional course assessments</strong>
              <p className="muted" style={{ marginBottom: 0 }}>
                Expect a mid-course pop quiz while you learn, then an end-of-course assessment.
                Completion credit requires a passing final score.
              </p>
            </div>
          )}

          {assessmentRun && (
            <AssessmentCheckpointPanel
              run={assessmentRun}
              busy={busy}
              onBusy={setBusy}
              onError={(msg) => setError(msg)}
              onSubmitted={(result) => { void onAssessmentSubmitted(result); }}
              onDismiss={
                mustVerifyPass && assessmentRun.checkpoint.stage === "summative"
                  ? undefined
                  : dismissAssessment
              }
              dismissLabel="Continue without submitting"
              headingOverride={
                assessmentRun.checkpoint.stage === "summative"
                  ? "End-of-course assessment"
                  : "Pop quiz"
              }
            />
          )}

          {assessmentResult && !assessmentRun && (
            <div
              className="card"
              style={{
                borderColor: assessmentResult.attempt.passed ? "#16a34a" : "#d97706",
              }}
            >
              <strong>
                {assessmentResult.attempt.passed ? "Checkpoint passed" : "Checkpoint not yet passed"}
                {" — "}
                {Math.round(assessmentResult.attempt.score * 100)}%
              </strong>
              <div className="muted" style={{ marginTop: 4 }}>
                {assessmentResult.attempt.stage === "summative"
                  ? (assessmentResult.course_decision?.passed
                    ? "Course pass verified. Retention checks are scheduled."
                    : "You can retry the course assessment (up to 3 attempts).")
                  : "Keep going — the next slides unlock when you continue."}
              </div>
              {assessmentResult.attempt.stage === "summative" && !assessmentResult.course_decision?.passed ? (
                <button
                  type="button"
                  style={{ marginTop: 8 }}
                  onClick={() => {
                    setAssessmentResult(null);
                    const summative = findDueSummativeCheckpoint(
                      assessmentPolicy,
                      slide?.index ?? (view?.lesson.slides.length ?? 1) - 1,
                      completedCheckpointsRef.current,
                    );
                    if (summative) void openCheckpoint(summative);
                  }}
                >
                  Retry assessment
                </button>
              ) : (
                <button
                  type="button"
                  style={{ marginTop: 8 }}
                  onClick={() => setAssessmentResult(null)}
                >
                  Continue
                </button>
              )}
            </div>
          )}

          {showPulse && pulseTemplate && (
            <div className="card" style={{ borderColor: "#f0ad4e" }}>
              <h3 style={{ marginTop: 0 }}>{pulseTemplate.title}</h3>
              {pulseTemplate.subtitle && (
                <p className="muted" style={{ marginTop: 0 }}>{pulseTemplate.subtitle}</p>
              )}
              {pulseTemplate.questions.map((q) => (
                <div key={q.id} style={{ marginBottom: 12 }}>
                  <p><strong>{q.prompt}</strong></p>
                  {q.type === "rating" && (
                    <div className="row" style={{ gap: 8 }}>
                      {[1, 2, 3, 4, 5].map((n) => (
                        <button
                          key={n}
                          type="button"
                          onClick={() => setPulseAnswers((prev) => ({ ...prev, [q.id]: n }))}
                          style={{
                            background: Number(pulseAnswers[q.id]) === n ? "#f0ad4e" : "transparent",
                            color: Number(pulseAnswers[q.id]) === n ? "#111" : "inherit",
                            border: "1px solid var(--border)",
                            minWidth: 36,
                          }}
                        >
                          {n}
                        </button>
                      ))}
                    </div>
                  )}
                  {q.type === "choice" && (
                    <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
                      {q.options.map((opt) => (
                        <button
                          key={opt}
                          type="button"
                          onClick={() => setPulseAnswers((prev) => ({ ...prev, [q.id]: opt }))}
                          style={{
                            background: pulseAnswers[q.id] === opt ? "#f0ad4e" : "transparent",
                            color: pulseAnswers[q.id] === opt ? "#111" : "inherit",
                            border: "1px solid var(--border)",
                            fontSize: 13,
                          }}
                        >
                          {opt}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              <div className="row">
                <button type="button" onClick={submitPulse} disabled={busy}>
                  {t("class.pulseSubmit")}
                </button>
                <button type="button" onClick={skipPulse} disabled={busy}>
                  {t("class.pulseSkip")}
                </button>
              </div>
            </div>
          )}

          {popQuiz && popQuiz.length > 0 && (
            <div className="card" style={{ borderColor: "#6ea8fe" }}>
              <h3 style={{ marginTop: 0 }}>Pop quiz — check your understanding</h3>
              {popQuiz.map((item) => (
                <div key={item.item_id} style={{ marginBottom: 12 }}>
                  <p><strong>{item.prompt}</strong></p>
                  <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
                    {item.options.map((opt, i) => (
                      <button
                        key={i}
                        type="button"
                        onClick={() => setPopQuizAnswers((prev) => ({ ...prev, [item.item_id]: i }))}
                        style={{
                          background: popQuizAnswers[item.item_id] === i ? "#6ea8fe" : "transparent",
                          color: popQuizAnswers[item.item_id] === i ? "#fff" : "inherit",
                          border: "1px solid var(--border)",
                          fontSize: 13,
                        }}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
              <div className="row">
                <button type="button" onClick={submitPopQuiz} disabled={busy}>
                  Submit quiz
                </button>
                <button type="button" onClick={dismissPopQuiz}>Skip for now</button>
              </div>
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
