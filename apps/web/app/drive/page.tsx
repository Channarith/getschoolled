"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  getAdPlan,
  getAudioCategories,
  getAudioCourse,
  getMe,
  getToken,
  getTtsInstructors,
  listAudioCourses,
  listStudents,
  SPEECH_URL,
  type AdBreak,
  type AudioCourse,
  type AudioCourseRow,
  type Instructor,
} from "../lib/api";
import SignInToUse from "../components/SignInToUse";
import VideoAdBreak from "../components/VideoAdBreak";
import { effectiveAdTier } from "../lib/useCourseAds";
import { useFlag } from "../lib/flags";
import { friendlyError } from "../lib/errors";
import { useT } from "../lib/i18n";
import { getVoicePrefs, setVoicePrefs } from "../lib/voicePrefs";
import { applyVoicePrefsToTts, accentFromPrefs, loadVoiceCatalog } from "../lib/narrationTts";
import { cancelSpeech, configureServerTts, ensureVoices, localeToBcp47, setServerInstructor, speakNaturally } from "../lib/tts";
import { extractAfterWake, hasWakeWord, isLikelyEcho, isQuestion, stripWakeWords } from "../lib/voiceCommands";
import {
  setTrainingLocale, trainingLocaleFromUi, type TrainingLocale,
} from "../lib/trainingLocale";
import {
  prosodyForStyle, resolveEffectiveVoiceStyle,
  type NarrationVoiceStyle,
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
  // Hands-free Drive Mode: mic stays always-on and wake-word-gated (no button).
  const [autoListen, setAutoListen] = useState(true);
  const [micDenied, setMicDenied] = useState(false);
  const [micGranted, setMicGranted] = useState(false);
  const [instructors, setInstructors] = useState<Instructor[]>([]);
  const [instructor, setInstructorState] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);
  const [tier, setTier] = useState("basic");
  const [adBreak, setAdBreak] = useState<AdBreak | null>(null);
  const afterAdRef = useRef<null | (() => void)>(null);
  const prerollShown = useRef(false);
  const adsEnabled = useFlag<boolean>("monetization.video_ads", false);
  const [trainingLang, setTrainingLang] = useState<TrainingLocale>("en");
  const queue = useRef<AudioCourseRow[]>([]);
  const recognitionRef = useRef<any>(null);
  // Always-on ambient recognizer (separate from the one-shot button recognizer).
  const ambientRef = useRef<any>(null);
  const autoListenRef = useRef(true);
  const micReadyRef = useRef(false);  // true after getUserMedia grant on a user gesture
  const awaitingQuestionRef = useRef(false);   // heard wake word, waiting for the question
  const oneShotActiveRef = useRef(false);      // manual (button) recognizer is running
  const currentNarrationRef = useRef("");      // text being spoken now (for echo filtering)
  const resumeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const voiceStyleRef = useRef<NarrationVoiceStyle>("standard");
  // Live mirrors of the chosen accent (BCP-47 of the selected voice) and
  // instructor persona, so the browser-voice fallback can honor them too.
  const voiceLocaleRef = useRef<string>("");
  const voiceGenderRef = useRef<string>("");
  const personaRef = useRef<string>("");
  // Live mirrors so callbacks/effects read current values without re-subscribing.
  const courseRef = useRef<AudioCourse | null>(null);
  const segRef = useRef(0);
  const playingRef = useRef(false);
  const trainingLangRef = useRef<TrainingLocale>("en");
  // Monotonic playback token. Any control that cancels speech bumps it so a
  // cancelled utterance's onend/onerror can't advance the queue (which made
  // Stop/skip appear to "keep playing"). Only the still-current generation
  // may auto-advance to the next segment.
  const playGenRef = useRef(0);
  courseRef.current = course;
  segRef.current = seg;
  playingRef.current = playing;
  trainingLangRef.current = trainingLang;
  autoListenRef.current = autoListen;

  async function refreshVoiceStyle() {
    const prefs = getVoicePrefs();
    let student = null;
    try {
      student = (await listStudents()).students[0] ?? null;
    } catch { /* guest */ }
    voiceStyleRef.current = resolveEffectiveVoiceStyle(prefs.instructorId, student);
    applyVoicePrefsToTts(prefs);
    const groups = await loadVoiceCatalog();
    const accent = accentFromPrefs(prefs, groups);
    voiceLocaleRef.current = accent.voiceLocale;
    voiceGenderRef.current = accent.voiceGender;
  }

  useEffect(() => {
    setAssistantStatus(t("drive.assistantDefault"));
  }, [t]);

  // Hard-stop narration + mic when leaving Drive Mode. Bump playGen first —
  // speechSynthesis.cancel() fires utterance onend, which would otherwise
  // auto-advance into the next segment after navigation.
  useEffect(() => {
    return () => {
      playGenRef.current++;
      clearResumeTimer();
      stopAmbientListening();
      stopVoiceRecognition();
      try { cancelSpeech(); } catch { /* */ }
    };
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setLoggedIn(Boolean(getToken()));
    if (!getToken()) return;
    getMe().then((a) => setTier((a.tier || "basic").toLowerCase())).catch(() => {});
    // Lesson language follows the profile Language picker (no duplicate Drive UI).
    const stored = trainingLocaleFromUi(locale);
    setTrainingLang(stored);
    setTrainingLocale(stored);
    getAudioCategories(locale).then(setCats).catch(() => setCats([]));
    ensureVoices();
    configureServerTts(SPEECH_URL);   // use ElevenLabs/edge-tts neural audio when available
    getTtsInstructors().then((r) => setInstructors(r.instructors)).catch(() => setInstructors([]));
    const prefs = getVoicePrefs();
    if (prefs.instructorId) {
      setInstructorState(prefs.instructorId);
      setServerInstructor(prefs.instructorId);
      personaRef.current = prefs.instructorId;
    }
    void refreshVoiceStyle();
  }, [locale]);

  useEffect(() => { personaRef.current = instructor; }, [instructor]);

  function chooseInstructor(id: string) {
    setInstructorState(id);
    setServerInstructor(id);
    personaRef.current = id;
    setVoicePrefs({ instructorId: id });
    void refreshVoiceStyle().then(() => {
      if (playingRef.current && courseRef.current) replayCurrentSegment();
    });
  }
  const refresh = useCallback(() => {
    if (!getToken()) return;
    listAudioCourses({ category: cat, q, limit: "60" }, locale, trainingLang)
      .then((r) => { setRows(r.courses); setTotal(r.total); queue.current = r.courses; })
      .catch((e) => setError(String(e)));
  }, [cat, q, locale, trainingLang]);
  useEffect(() => { refresh(); }, [refresh]);

  const speak = useCallback((text: string, onEnd?: () => void) => {
    try {
      currentNarrationRef.current = text || "";   // for echo filtering of the mic
      const style = voiceStyleRef.current;
      const base = prosodyForStyle(style).rate;
      // Narrate in the language of the actual text (body_locale), which may
      // differ from the requested training locale when it falls back to English.
      const speakLocale = courseRef.current?.body_locale || trainingLangRef.current;
      speakNaturally(text, {
        locale: speakLocale,
        voiceStyle: style,
        rate: base * rate,
        voiceLocale: voiceLocaleRef.current || undefined,
        voiceGender: voiceGenderRef.current || undefined,
        persona: personaRef.current || undefined,
        onend: onEnd,
      });
    } catch { onEnd?.(); }
  }, [rate]);

  const playSeg = useCallback((c: AudioCourse, i: number) => {
    const gen = ++playGenRef.current;   // new playback generation
    cancelSpeech();
    if (i >= c.segments.length) { setPlaying(false); playNextCourse(); return; }
    setSeg(i); setPlaying(true);
    speak(`${c.segments[i].heading}. ${c.segments[i].text}`, () => {
      if (playGenRef.current === gen) playSeg(c, i + 1);
    });
  }, [speak, course]); // eslint-disable-line react-hooks/exhaustive-deps

  const replayCurrentSegment = useCallback(() => {
    if (!course) return;
    const gen = ++playGenRef.current;
    cancelSpeech();
    const s = course.segments[seg];
    if (!s) return;
    setPlaying(true);
    speak(`${s.heading}. ${s.text}`, () => {
      if (playGenRef.current === gen) playSeg(course, seg + 1);
    });
  }, [course, seg, speak, playSeg]);

  // When the profile language changes, refresh the open course's spoken text
  // and continue from the same segment if audio was playing.
  useEffect(() => {
    const id = courseRef.current?.id;
    if (!id || !loggedIn) return;
    let cancelled = false;
    const wasPlaying = playingRef.current;
    const at = segRef.current;
    getAudioCourse(id, locale, trainingLang)
      .then((c) => {
        if (cancelled) return;
        setCourse(c);
        setSeg(at);
        if (wasPlaying) playSeg(c, at);
        else setPlaying(false);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [locale, trainingLang, loggedIn, playSeg]);

  const prevRateRef = useRef(rate);
  const prevInstructorRef = useRef(instructor);
  useEffect(() => {
    if (
      prevRateRef.current === rate &&
      prevInstructorRef.current === instructor
    )
      return;
    prevRateRef.current = rate;
    prevInstructorRef.current = instructor;
    if (!playing || !course) return;
    replayCurrentSegment();
  }, [rate, instructor, playing, course, replayCurrentSegment]);

  async function startCourse(id: string) {
    if (!getToken()) { setLoggedIn(false); return; }   // preview is view-only (no audio)
    setError("");
    try {
      const c = await getAudioCourse(id, locale, trainingLang);
      setCourse(c); setSeg(0);
      playSeg(c, 0);
      // Hands-free Q&A: only start after mic was primed on a user gesture
      // (startCourseWithAds / Enable mic). Auto-start without permission → not-allowed.
      if (autoListenRef.current && micReadyRef.current) {
        void startAmbientListening();
      }
    } catch (e) { setError(String(e)); }
  }

  function onAdDone() {
    const fn = afterAdRef.current;
    afterAdRef.current = null;
    setAdBreak(null);
    fn?.();
  }

  // User-initiated start: play a one-time audio pre-roll (ad-supported tiers)
  // before the first course of the session, then start playback. Auto-advance
  // (playNextCourse) still calls startCourse directly — no ad between queued courses.
  async function startCourseWithAds(id: string) {
    if (!getToken()) { setLoggedIn(false); return; }
    // Prime the mic on this click (user gesture) so ambient listening can run.
    if (autoListenRef.current) {
      const access = await ensureMicAccess();
      if (access !== "ok") {
        setMicDenied(true);
        setAutoListen(false);
        autoListenRef.current = false;
      }
    }
    if (adsEnabled && !prerollShown.current) {
      prerollShown.current = true;
      try {
        const plan = await getAdPlan(effectiveAdTier(tier));
        const pre = plan.breaks.find((b) => b.position === "preroll");
        if (pre && !plan.ad_free) {
          cancelSpeech();
          afterAdRef.current = () => { void startCourse(id); };
          setAdBreak(pre);
          return;
        }
      } catch { /* ads best-effort; fall through to playback */ }
    }
    await startCourse(id);
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

  // Cancel (not just pause) so a language switch while paused can't resume a
  // stale utterance; Resume replays the current segment in the current voice.
  function pause() { playGenRef.current++; cancelSpeech(); setPlaying(false); }
  function resume() { replayCurrentSegment(); }
  function stop() {
    clearResumeTimer();
    stopVoiceRecognition();
    stopAmbientListening();
    playGenRef.current++;               // stop for good: no auto-advance
    cancelSpeech();
    setPlaying(false);
    setCourse(null);
    setAssistantOpen(false);
  }

  function pauseForAssistant(status = t("drive.listenStatus")) {
    clearResumeTimer();
    playGenRef.current++;
    cancelSpeech();
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

  // ---- Hands-free ambient listening (always on; wake-word gated) ---------- //
  function supportsSpeechRecognition(): boolean {
    if (typeof window === "undefined") return false;
    const root = window as any;
    return Boolean(root.SpeechRecognition || root.webkitSpeechRecognition);
  }

  // Browsers require a secure context + an explicit mic grant. Starting the
  // Web Speech API without getUserMedia often yields `not-allowed` with no
  // prompt — which is what showed "Microphone blocked" mid-class.
  async function ensureMicAccess(): Promise<"ok" | "insecure" | "denied" | "unavailable"> {
    if (typeof window === "undefined") return "unavailable";
    if (!window.isSecureContext) return "insecure";
    if (!supportsSpeechRecognition()) return "unavailable";
    if (micReadyRef.current) return "ok";
    try {
      if (navigator.mediaDevices?.getUserMedia) {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach((track) => track.stop());
      }
      micReadyRef.current = true;
      setMicDenied(false);
      setMicGranted(true);
      return "ok";
    } catch {
      micReadyRef.current = false;
      setMicGranted(false);
      return "denied";
    }
  }

  function openTypedAsk(status?: string) {
    pauseForAssistant(status || t("drive.typeQuestion"));
    setAssistantOpen(true);
    setAssistantStatus(status || t("drive.typeQuestion"));
  }

  // Route a final ambient transcript while the course plays. Pauses ONLY for a
  // genuine question (or an explicit "Hey Sala" command) — casual speech, noise,
  // and the narration the mic itself picks up (echo) are filtered out.
  function handleAmbientResult(text: string) {
    const raw = (text || "").trim();
    if (!raw) return;

    // Already heard the wake word: this utterance is the question.
    if (awaitingQuestionRef.current) {
      awaitingQuestionRef.current = false;
      const q = hasWakeWord(raw) ? stripWakeWords(raw) : raw;
      if (q) handleAssistantQuestion(q);
      else awaitingQuestionRef.current = true;
      return;
    }

    // Explicit wake word → honor any command or question after it.
    const after = extractAfterWake(raw);
    if (after !== null) {
      pauseForAssistant(t("drive.listenQuestion"));
      if (after) handleAssistantQuestion(after);
      else awaitingQuestionRef.current = true;
      return;
    }

    // No wake word: pause ONLY for a real question that isn't the narration echo.
    if (isLikelyEcho(raw, currentNarrationRef.current)) return;   // the course's own audio
    if (!isQuestion(raw)) return;                                 // statement / filler / noise
    pauseForAssistant(t("drive.listenQuestion"));
    handleAssistantQuestion(raw);
  }

  async function startAmbientListening() {
    if (!autoListenRef.current || !supportsSpeechRecognition()) return;
    if (!micReadyRef.current) {
      const access = await ensureMicAccess();
      if (access !== "ok") {
        setMicDenied(true);
        setAutoListen(false);
        autoListenRef.current = false;
        setListening(false);
        return;
      }
    }
    const root = window as any;
    const SpeechRecognition = root.SpeechRecognition || root.webkitSpeechRecognition;
    try { ambientRef.current?.stop?.(); } catch { /* */ }
    const rec = new SpeechRecognition();
    rec.lang = localeToBcp47(trainingLangRef.current || locale);
    rec.continuous = true;
    rec.interimResults = false;
    rec.onresult = (event: any) => {
      const results = event.results || [];
      const last = results[results.length - 1];
      if (!last || !last.isFinal) return;
      const text = (last[0]?.transcript || "").trim();
      if (text) handleAmbientResult(text);
    };
    rec.onerror = (event: any) => {
      const err = event?.error || "";
      if (err === "not-allowed" || err === "service-not-allowed") {
        // Mic permission denied — stop ambient; typed Ask stays available.
        micReadyRef.current = false;
        setMicGranted(false);
        setMicDenied(true);
        setAutoListen(false);
        autoListenRef.current = false;
        setListening(false);
      }
      // "no-speech" / "aborted" / "network" are transient → onend restarts.
    };
    rec.onend = () => {
      setListening(false);
      // Browsers end the stream on silence/timeout; restart to stay always-on
      // (unless the manual one-shot recognizer is currently active).
      if (autoListenRef.current && !oneShotActiveRef.current && micReadyRef.current) {
        window.setTimeout(() => {
          if (autoListenRef.current && !oneShotActiveRef.current && !ambientRef.current?.__running) {
            void startAmbientListening();
          }
        }, 500);
      }
    };
    ambientRef.current = rec;
    (rec as any).__running = true;
    const origEnd = rec.onend;
    rec.onend = (e: any) => { (rec as any).__running = false; origEnd(e); };
    setListening(true);
    try { rec.start(); } catch { /* already starting */ }
  }

  function stopAmbientListening() {
    autoListenRef.current = false;
    awaitingQuestionRef.current = false;
    try { ambientRef.current?.stop?.(); } catch { /* */ }
    ambientRef.current = null;
    setListening(false);
  }

  async function toggleAutoListen() {
    if (autoListen) {
      setAutoListen(false);
      stopAmbientListening();
      return;
    }
    const access = await ensureMicAccess();
    if (access === "insecure") {
      setMicDenied(true);
      setAssistantStatus(t("drive.micNeedsHttps"));
      openTypedAsk(t("drive.micNeedsHttps"));
      return;
    }
    if (access !== "ok") {
      setMicDenied(true);
      openTypedAsk(t("drive.micBlocked"));
      return;
    }
    setMicDenied(false);
    setAutoListen(true);
    autoListenRef.current = true;
    void startAmbientListening();
  }

  async function startVoiceRecognition(expectWakeWord = false) {
    pauseForAssistant(t("drive.listenQuestion"));
    const access = await ensureMicAccess();
    if (access === "insecure") {
      setMicDenied(true);
      setAssistantStatus(t("drive.micNeedsHttps"));
      setAssistantOpen(true);
      return;
    }
    if (access !== "ok") {
      setMicDenied(true);
      setAssistantStatus(t("drive.micBlocked"));
      setAssistantOpen(true);
      return;
    }
    const root = window as any;
    const SpeechRecognition = root.SpeechRecognition || root.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setAssistantStatus(t("drive.voiceUnavailable"));
      setAssistantOpen(true);
      return;
    }
    // Suspend ambient listening so only one recognizer is active at a time.
    oneShotActiveRef.current = true;
    try { ambientRef.current?.stop?.(); } catch { /* */ }
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
    recognition.onerror = (event: any) => {
      const err = event?.error || "";
      if (err === "not-allowed" || err === "service-not-allowed") {
        micReadyRef.current = false;
        setMicGranted(false);
        setMicDenied(true);
        setAssistantStatus(t("drive.micBlocked"));
      } else {
        setAssistantStatus(t("drive.hearRetry"));
      }
      setListening(false);
      oneShotActiveRef.current = false;
      setAssistantOpen(true);
    };
    recognition.onend = () => {
      setListening(false);
      oneShotActiveRef.current = false;
      // Resume hands-free ambient listening after the manual one-shot.
      if (autoListenRef.current && courseRef.current && micReadyRef.current) {
        window.setTimeout(() => { if (autoListenRef.current) void startAmbientListening(); }, 500);
      }
    };
    recognitionRef.current = recognition;
    setListening(true);
    setAssistantOpen(true);
    try {
      recognition.start();
    } catch {
      setListening(false);
      oneShotActiveRef.current = false;
      setAssistantStatus(t("drive.hearRetry"));
    }
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
      playGenRef.current++;
      cancelSpeech();
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
    playGenRef.current++;
    cancelSpeech();
    const genSnapshot = playGenRef.current;
    speak(t("drive.resumePrompt", { answer }), () => {
      if (playGenRef.current !== genSnapshot) return;
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

  const BIG = { fontSize: 22, padding: "16px 22px", borderRadius: 14 };

  return (
    <main className="container" style={{ maxWidth: 900 }}>
      {adBreak && (
        <VideoAdBreak
          adBreak={adBreak}
          placement={`on-the-go-${adBreak.position}`}
          tier={effectiveAdTier(tier)}
          audioOnly
          onDone={onAdDone}
        />
      )}
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
                cancelSpeech();
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
            {supportsSpeechRecognition() && !micDenied ? (
              <button
                onClick={() => void toggleAutoListen()}
                title={t("drive.handsFreeHint")}
                style={{ ...BIG, background: autoListen ? (listening ? "#16a34a" : "#0d9488") : "#334155", color: "#fff" }}
              >
                {autoListen ? t("drive.handsFreeOn") : t("drive.handsFreeOff")}
              </button>
            ) : (
              <button
                onClick={() => void toggleAutoListen()}
                style={{ ...BIG, background: "#0d9488", color: "#fff" }}
                title={t("drive.micEnableHint")}
              >
                {t("drive.enableMic")}
              </button>
            )}
            <button
              onClick={() => openTypedAsk(t("drive.typeQuestion"))}
              style={{ ...BIG, background: "#334155", color: "#fff" }}
            >
              {t("drive.askType")}
            </button>
            {instructors.length > 0 && (
              <label style={{ marginLeft: "auto", color: "#9aa6c2" }}>
                {t("drive.instructor")}&nbsp;
                <select value={instructor} onChange={(e) => chooseInstructor(e.target.value)}>
                  <option value="">{t("drive.instructorDefault")}</option>
                  {instructors.map((p) => (
                    <option key={p.id} value={p.id}>{p.emoji} {p.label}</option>
                  ))}
                </select>
              </label>
            )}
            <label style={{ marginLeft: instructors.length ? undefined : "auto", color: "#9aa6c2" }}>
              {t("drive.speed")}&nbsp;
              <select value={rate} onChange={(e) => setRate(Number(e.target.value))}>
                {[0.5, 1, 2, 3].map((r) => <option key={r} value={r}>{r}x</option>)}
              </select>
            </label>
          </div>
          {micDenied ? (
            <div className="muted" style={{ marginTop: 6, color: "#f59e0b", fontSize: 13 }}>{t("drive.micBlocked")}</div>
          ) : autoListen && micGranted && supportsSpeechRecognition() ? (
            <div className="muted" style={{ marginTop: 6, fontSize: 13 }}>{t("drive.handsFreeHint")}</div>
          ) : supportsSpeechRecognition() ? (
            <div className="muted" style={{ marginTop: 6, fontSize: 13 }}>{t("drive.micEnableHint")}</div>
          ) : null}
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
          <button key={r.id} onClick={() => startCourseWithAds(r.id)}
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
