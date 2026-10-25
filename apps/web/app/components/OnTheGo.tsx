"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import {
  getAdPlan,
  getAudioCourse,
  getMe,
  getToken,
  listAudioCourses,
  listStudents,
  searchAudioCourses,
  SPEECH_URL,
  type AdBreak,
  type AudioCourse,
  type AudioCourseRow,
} from "../lib/api";
import DriveStageLook from "./DriveStageLook";
import OnTheGoPresence from "./OnTheGoPresence";
import OnTheGoCourseSearch from "./OnTheGoCourseSearch";
import OnTheGoAvatar, { type AvatarState } from "./OnTheGoAvatar";
import OnTheGoConsent, { type ConsentChoice } from "./OnTheGoConsent";
import OnTheGoTrialEnd from "./OnTheGoTrialEnd";
import { CAMERA_PREF_KEY } from "../lib/facePresence";
import SignInToUse from "./SignInToUse";
import VideoAdBreak from "./VideoAdBreak";
import { effectiveAdTier } from "../lib/useCourseAds";
import { useDemoOnlyAnonymous, useFlag } from "../lib/flags";
import { friendlyError } from "../lib/errors";
import { useT } from "../lib/i18n";
import { getVoicePrefs } from "../lib/voicePrefs";
import { applyVoicePrefsToTts, accentFromPrefs, loadVoiceCatalog } from "../lib/narrationTts";
import { cancelSpeech, configureServerTts, ensureVoices, localeToBcp47, setServerInstructor, speakNaturally } from "../lib/tts";
import { clampPlaybackRate, extractAfterWake, hasWakeWord, isLikelyEcho, isQuestion, normalizeVoicePauseSubmitMs, parsePlaybackCommand, stripWakeWords } from "../lib/voiceCommands";
import { startDriveVoice, type DriveVoiceSession } from "../lib/driveVoiceAgent";
import {
  setTrainingLocale,
  TRAINING_LOCALE_LABELS,
  trainingLocaleFromUi,
  type TrainingLocale,
} from "../lib/trainingLocale";
import {
  prosodyForStyle, resolveEffectiveVoiceStyle,
  type NarrationVoiceStyle,
} from "../lib/voiceProfiles";
import {
  DEMO_COURSE_ID,
  DEMO_COURSE_TITLE_FALLBACK,
  onTheGoExperience,
  sampleCourses,
  timerLabel,
  type OnTheGoMode,
} from "../lib/onTheGoMode";
import {
  DEMO_COURSE_IDS, DEMO_FULL_SEARCH_FLAG, DEMO_PICKER_FLAG, INCLUDE_ENGLISH_KEY, QuestionLimiter, cleanTitle, curatedRows, neighbourCourse,
  parseCourseCommand, readProgress, resumeSegment, saveProgress, type CourseCommand, type Progress,
} from "../lib/onTheGoCatalog";
import { parseSearchCommand, rankCourses, type SearchCommand, type SearchRow } from "../lib/onTheGoSearch";
import { languageFamily } from "../lib/voiceLanguage";

// Hands-free "Drive Mode": big controls, no required visuals, on-device TTS
// narration with an autoplay queue so learners keep their eyes on the road.
const CONSENT_KEY = "salareen.onTheGo.consent.v1";

export default function OnTheGo({ mode = "full", voiceSlot }: { mode?: OnTheGoMode; voiceSlot?: ReactNode }) {
  const { t } = useT();
  return (
    <Suspense fallback={<main className="container"><p className="muted">{t("drive.loading")}</p></main>}>
      <OnTheGoInner mode={mode} voiceSlot={voiceSlot} />
    </Suspense>
  );
}

function audibleCourse<T extends { segments: { text?: string }[] }>(course: T): T {
  const segments = course.segments.filter((segment) => /[^\W\d_]/u.test(segment.text || ""));
  if (!segments.length || segments.length === course.segments.length) return course;
  return { ...course, segments };
}

function OnTheGoInner({ mode, voiceSlot }: { mode: OnTheGoMode; voiceSlot?: ReactNode }) {
  const curatedFlag = useFlag<boolean>(DEMO_PICKER_FLAG, true);
  const experience = onTheGoExperience(mode, { curatedPicker: curatedFlag });
  const { t, locale } = useT();
  const searchParams = useSearchParams();
  const deepLinkCourse = searchParams.get("course");
  const cat = "";
  const [q, setQ] = useState("");
  const [searchRows, setSearchRows] = useState<SearchRow[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [includeEnglish, setIncludeEnglish] = useState(true);
  const demoFullSearch = useFlag<boolean>(DEMO_FULL_SEARCH_FLAG, false);
  // The picked voice decides the language; courses ready in it come first.
  const searchLanguage = languageFamily(locale) || "en";
  const searchEnabled = experience.showCoursePicker || experience.curatedPicker;
  const allowedIds = experience.showTimer && !demoFullSearch ? DEMO_COURSE_IDS : undefined;
  // One-time consent before the first microphone prompt (what is heard, where it goes; the camera is optional and stays on the device).
  const [consent, setConsent] = useState<ConsentChoice | "">("");
  const [consentOpen, setConsentOpen] = useState(false);
  const consentRef = useRef<ConsentChoice | "">("");
  const [rows, setRows] = useState<AudioCourseRow[]>([]);
  const [coursesLoading, setCoursesLoading] = useState(false);
  const [course, setCourse] = useState<AudioCourse | null>(null);
  const [seg, setSeg] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1);
  const [helpOpen, setHelpOpen] = useState(false);
  const [fill, setFill] = useState(false);
  const [canFullscreen, setCanFullscreen] = useState(false);
  const [error, setError] = useState("");
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [assistantStatus, setAssistantStatus] = useState("");
  const [, setAssistantTranscript] = useState("");
  const [, setAssistantAnswer] = useState("");
  const [listening, setListening] = useState(false);
  // Hands-free Drive Mode: mic stays always-on and wake-word-gated (no button).
  const [autoListen, setAutoListen] = useState(true);
  const [micDenied, setMicDenied] = useState(false);
  const [, setMicGranted] = useState(false);
  const [voiceLive, setVoiceLive] = useState(false);
  const [instructor, setInstructorState] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);
  const [tier, setTier] = useState("basic");
  const [adBreak, setAdBreak] = useState<AdBreak | null>(null);
  const afterAdRef = useRef<null | (() => void)>(null);
  const prerollShown = useRef(false);
  const adsEnabled = useFlag<boolean>("monetization.video_ads", false);
  const demoOnlyAnon = useDemoOnlyAnonymous();
  const pauseSubmitMs = normalizeVoicePauseSubmitMs(
    useFlag<number>("ux.voice_pause_submit_ms", 4500),
  );
  const [trainingLang, setTrainingLang] = useState<TrainingLocale>("en");
  const [pickedId, setPickedId] = useState("");
  const [accountReady, setAccountReady] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(experience.sampleSeconds);
  const [demoEnded, setDemoEnded] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [progress, setProgress] = useState<Progress>({ lastCourseId: "", courses: {} });
  const [speechOk, setSpeechOk] = useState(false);
  const awayPausedRef = useRef(false);
  const limiterRef = useRef(new QuestionLimiter());
  const demoEndedRef = useRef(false);
  const queue = useRef<AudioCourseRow[]>([]);
  const recognitionRef = useRef<any>(null);
  // Sala's easter egg (scrub or say "dance"): loaded from the studio's shared module; absent means no easter egg, nothing breaks.
  const salaModRef = useRef<any>(null);
  const salaDanceRef = useRef<null | (() => void)>(null);
  const pauseSubmitTimerRef = useRef<number | null>(null);
  const pendingTranscriptRef = useRef("");
  const submittedRef = useRef(false);
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
  const driveVoiceRef = useRef<DriveVoiceSession | null>(null);
  const tierRef = useRef("basic");
  const voiceGenRef = useRef(0);
  const playSegRef = useRef<(c: AudioCourse, i: number) => void>(() => {});
  const voicePausedLessonRef = useRef(false);
  courseRef.current = course;
  segRef.current = seg;
  playingRef.current = playing;
  tierRef.current = tier;
  trainingLangRef.current = trainingLang;
  autoListenRef.current = autoListen;

  // Remember where each course was left (only while it is actually playing, so loading the page never overwrites it).
  useEffect(() => {
    if (!course || !playing) return;
    saveProgress(course.id, seg);
    setProgress(readProgress());
  }, [course?.id, seg, playing]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setProgress(readProgress());
    setSpeechOk(supportsSpeechRecognition());
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Camera starts only after the learner has tapped Start; it stays on until the course is stopped or the demo ends.
  useEffect(() => { if (playing) setCameraActive(true); }, [playing]);
  useEffect(() => { if (demoEnded) setCameraActive(false); }, [demoEnded]);

  // Always-on listening: once the lesson plays, keep the ambient recognizer running (wake word or a real question).
  useEffect(() => {
    if (!course || !playing || !autoListen || driveVoiceRef.current) return;
    if ((ambientRef.current as { __running?: boolean } | null)?.__running) return;
    void startAmbientListening();
  }, [course?.id, playing, autoListen]); // eslint-disable-line react-hooks/exhaustive-deps

  // Privacy: a hidden tab, a locked screen or a phone call ends listening; it resumes when the page is visible again.
  useEffect(() => {
    const onVisibility = () => {
      if (document.hidden) {
        try { ambientRef.current?.stop?.(); } catch { /* */ }
        ambientRef.current = null;
        setListening(false);
      } else if (autoListenRef.current && playingRef.current && !driveVoiceRef.current) {
        void startAmbientListening();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
    const genRef = playGenRef;
    return () => {
      genRef.current++;
      clearResumeTimer();
      stopDriveVoice();
      stopAmbientListening();
      stopVoiceRecognition();
      try { cancelSpeech(); } catch { /* */ }
    };
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const signedIn = Boolean(getToken());
    setLoggedIn(signedIn);
    // The lesson language follows the picked voice for everyone, including the anonymous demo.
    const stored = trainingLocaleFromUi(locale);
    setTrainingLang(stored);
    setTrainingLocale(stored);
    if (!signedIn) {
      setAccountReady(true);
      return;
    }
    setAccountReady(false);
    getMe()
      .then((a) => setTier((a.tier || "basic").toLowerCase()))
      .catch(() => setTier("basic"))
      .finally(() => setAccountReady(true));
    ensureVoices();
    configureServerTts(SPEECH_URL);   // use ElevenLabs/edge-tts neural audio when available
    const prefs = getVoicePrefs();
    if (prefs.instructorId) {
      setInstructorState(prefs.instructorId);
      setServerInstructor(prefs.instructorId);
      personaRef.current = prefs.instructorId;
    }
    void refreshVoiceStyle();
  }, [locale]);

  useEffect(() => { personaRef.current = instructor; }, [instructor]);

  const refresh = useCallback(() => {
    // Demo-only mode (sales_demo.exclusive) lets anonymous visitors browse the
    // on-the-go catalog without signing in.
    // The public demo loads the sample without a session. The signed-in tab
    // still requires a token unless the sales demo is open to guests.
    if (!experience.showTimer && !getToken() && !demoOnlyAnon) return;
    setCoursesLoading(true);
    // Public demo: skip the search catalog and pin one curated AI course so
    // the visitor just taps Start. We still back-fill `rows` from
    // listAudioCourses so that if the pinned DEMO_COURSE_ID 404s (e.g. a
    // slug change or a locale with no translation) sampleCourses() can
    // pick a sensible AI fallback instead of leaving the demo blank.
    if (experience.mode === "demo") {
      let cancelled = false;
      (async () => {
        try {
          const pinned = await getAudioCourse(DEMO_COURSE_ID, locale, trainingLang);
          if (cancelled) return;
          const row: AudioCourseRow = {
            id: pinned.id, title: pinned.title, category: pinned.category,
            subject: pinned.subject, level: pinned.level,
            duration_min: pinned.duration_min, tags: pinned.tags,
            format: pinned.format, visual_required: pinned.visual_required,
            drive_safe: pinned.drive_safe, segments: pinned.segments.length,
          };
          setRows([row]);
          queue.current = [row];
          setPickedId(pinned.id);
          setCourse(audibleCourse(pinned));
          setSeg(0);
          if (experience.curatedPicker) {
            try {
              const all = await listAudioCourses({ limit: "300" }, locale, trainingLang);
              if (cancelled) return;
              const cur = curatedRows(all.courses);
              if (cur.length) {
                const merged = cur.some((r) => r.id === row.id) ? cur : [row, ...cur];
                setRows(merged);
                queue.current = merged;
                const last = readProgress().lastCourseId;
                if (last && last !== pinned.id && merged.some((r) => r.id === last)) setPickedId(last);
              }
            } catch { /* the pinned course alone still plays */ }
          }
        } catch {
          // Pinned course failed to load - fall back to the first AI course
          // the catalog returns (or whatever sampleCourses picks last).
          try {
            const r = await listAudioCourses({ limit: "20" }, locale, trainingLang);
            if (cancelled) return;
            const picked = sampleCourses(r.courses);
            setRows(picked);
            queue.current = picked;
            if (picked[0]) setPickedId(picked[0].id);
          } catch (e2) {
            if (!cancelled) setError(String(e2));
          }
        } finally {
          if (!cancelled) setCoursesLoading(false);
        }
      })();
      return () => { cancelled = true; };
    }
    // Signed-in tab: load the full catalog for the picker.
    listAudioCourses({ category: cat, q, limit: experience.fullCatalog ? "60" : "20" }, locale, trainingLang)
      .then((r) => {
        const courses = experience.fullCatalog ? r.courses : sampleCourses(r.courses);
        setRows(courses);
        queue.current = courses;
      })
      .catch((e) => setError(String(e)))
      .finally(() => setCoursesLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cat, q, locale, trainingLang, demoOnlyAnon, experience.showTimer, experience.fullCatalog, experience.mode, experience.curatedPicker]);
  useEffect(() => { refresh(); }, [refresh]);

  // `fresh` = the learner just chose. Restoring a saved choice on load must not overwrite a camera on/off they set later in the widget.
  function applyConsent(choice: ConsentChoice, fresh = false) {
    consentRef.current = choice;
    setConsent(choice);
    if (fresh) {
      try { localStorage.setItem(CAMERA_PREF_KEY, choice === "mic-camera" ? "on" : "off"); } catch { /* private mode */ }
    }
    if (choice === "none") {
      autoListenRef.current = false;
      setAutoListen(false);
    }
  }
  function chooseConsent(choice: ConsentChoice) {
    try { localStorage.setItem(CONSENT_KEY, choice); } catch { /* private mode: the choice lasts for this visit */ }
    applyConsent(choice, true);
    setConsentOpen(false);
    window.setTimeout(() => { void onTransport(); }, 0);   // carry on with the Start tap that asked
  }
  function reopenConsent() {
    try { localStorage.removeItem(CONSENT_KEY); } catch { /* private mode */ }
    consentRef.current = "";
    setConsent("");
    setConsentOpen(true);
  }
  useEffect(() => {
    try {
      const v = localStorage.getItem(CONSENT_KEY);
      if (v === "mic" || v === "mic-camera" || v === "none") applyConsent(v);
    } catch { /* private mode */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Search index: every course with the languages it is READY in. Courses without a shippable translation stay listed as English only.
  useEffect(() => {
    try { if (localStorage.getItem(INCLUDE_ENGLISH_KEY) === "0") setIncludeEnglish(false); } catch { /* private mode */ }
  }, []);
  useEffect(() => {
    if (!searchEnabled) return;
    if (!experience.showTimer && !getToken() && !demoOnlyAnon) return;
    let cancelled = false;
    setSearchLoading(true);
    searchAudioCourses({ language: searchLanguage, limit: 500 })
      .then((r) => { if (!cancelled) setSearchRows(r.courses); })
      .catch(() => { if (!cancelled) setSearchRows([]); })   // the catalog rows still list the English courses
      .finally(() => { if (!cancelled) setSearchLoading(false); });
    return () => { cancelled = true; };
  }, [searchEnabled, searchLanguage, experience.showTimer, demoOnlyAnon]);
  const searchSource: SearchRow[] = useMemo(
    () => (searchRows.length ? searchRows : rows.map((r) => ({ id: r.id, title: r.title, category: r.category, duration_min: r.duration_min, level: r.level }))),
    [searchRows, rows],
  );
  // "next course", "play the Roman Empire course" and the list walk the same order the learner sees (ready in their language first).
  useEffect(() => {
    if (!searchEnabled || !searchRows.length) return;
    const ranked = rankCourses(searchRows, "", { language: searchLanguage, includeEnglish: true, allowedIds });
    if (ranked.length) queue.current = ranked as unknown as AudioCourseRow[];
  }, [searchEnabled, searchRows, searchLanguage, allowedIds]);

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
    const line = `${c.segments[i].heading}. ${c.segments[i].text}`;
    const voice = driveVoiceRef.current;
    if (voice?.speakLesson(line, () => {
      if (playGenRef.current === gen) playSeg(c, i + 1);
    })) return;
    speak(line, () => {
      if (playGenRef.current === gen) playSeg(c, i + 1);
    });
  }, [speak]); // eslint-disable-line react-hooks/exhaustive-deps
  playSegRef.current = playSeg;

  function stopDriveVoice() {
    voiceGenRef.current += 1;
    voicePausedLessonRef.current = false;
    driveVoiceRef.current?.stop();
    driveVoiceRef.current = null;
    setVoiceLive(false);
  }

  async function beginDriveVoice(c: AudioCourse): Promise<boolean> {
    const gen = voiceGenRef.current + 1;
    stopDriveVoice();
    voiceGenRef.current = gen;
    try { ambientRef.current?.stop?.(); } catch { /* browser recognizer yields the mic */ }
    ambientRef.current = null;
    const excerpt = c.segments?.[0]?.text || "";
    try {
      const session = await startDriveVoice(
        {
          category: c.category || cat,
          title: c.title,
          excerpt,
          courseId: c.id,
          language: trainingLangRef.current || locale,
        },
        {
          onStatus: (text) => { if (text) setAssistantStatus(text); },
          onUser: (text) => setAssistantTranscript(text),
          onTutor: (text) => setAssistantAnswer(text),
          onSpeaking: (speaking) => {
            if (!speaking) return;
            cancelSpeech();
            setPlaying(true);
          },
          onAnswerDone: () => {
            const current = courseRef.current;
            if (!current) return;
            playSegRef.current(current, segRef.current);
          },
        },
      );
      if (!session || gen !== voiceGenRef.current) {
        session?.stop();
        return false;
      }
      driveVoiceRef.current = session;
      setVoiceLive(true);
      setAssistantStatus(t("drive.voiceAgentOn"));
      return true;
    } catch {
      return false;
    }
  }

  const replayCurrentSegment = useCallback(() => {
    if (!course) return;
    const gen = ++playGenRef.current;
    cancelSpeech();
    const s = course.segments[seg];
    if (!s) return;
    setPlaying(true);
    const line = `${s.heading}. ${s.text}`;
    const voice = driveVoiceRef.current;
    if (voice?.speakLesson(line, () => {
      if (playGenRef.current === gen) playSeg(course, seg + 1);
    })) return;
    speak(line, () => {
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
        setCourse(audibleCourse(c));
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
    if (demoEndedRef.current) return;
    // Full mode is the paid Sala agent. Demo mode narrates the sample only.
    if (experience.salaAgent && !getToken()) { setLoggedIn(false); return; }
    if (experience.salaAgent && tierRef.current === "free") return;
    setPickedId(id);
    setError("");
    try {
      const c = audibleCourse(await getAudioCourse(id, locale, trainingLang));
      const startAt = resumeSegment(readProgress(), id, c.segments.length);
      setCourse(c); setSeg(startAt);
      awayPausedRef.current = false;
      // The voice agent speaks the class and hears questions. Connect it
      // before the first segment so playback does not fall back to a wake phrase.
      if (experience.salaAgent && autoListenRef.current && micReadyRef.current) {
        const voiced = await beginDriveVoice(c);
        if (!voiced) setAssistantStatus(t("drive.voiceAgentOff"));
      }
      playSeg(c, startAt);
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
    if (demoEndedRef.current) return;
    if (experience.showTimer) {
      await startCourse(id);
      return;
    }
    if (!getToken()) { setLoggedIn(false); return; }
    if (tierRef.current === "free") return;
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
  async function playWithXai() {
    const current = courseRef.current;
    if (!current) return;
    if (!experience.salaAgent) {
      if (playingRef.current) pause();
      else resume();
      return;
    }
    if (playingRef.current && driveVoiceRef.current) {
      pause();
      return;
    }
    if (!driveVoiceRef.current) {
      cancelSpeech();
      const voiced = await beginDriveVoice(current);
      if (voiced) {
        playSegRef.current(current, segRef.current);
        return;
      }
    }
    if (playingRef.current) pause();
    else resume();
  }

  function pause() {
    playGenRef.current++;
    driveVoiceRef.current?.hold();
    cancelSpeech();
    setPlaying(false);
  }
  function resume() { replayCurrentSegment(); }
  function stop() {
    stopDriveVoice();
    clearResumeTimer();
    stopVoiceRecognition();
    stopAmbientListening();
    setAutoListen(false);
    playGenRef.current++;               // stop for good: no auto-advance
    cancelSpeech();
    setPlaying(false);
    setCourse(null);
    setAssistantOpen(false);
    setCameraActive(false);
    awayPausedRef.current = false;
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
    if (!courseRef.current) return;
    clearResumeTimer();
    const go = () => {
      setAssistantOpen(false);
      if (courseRef.current) playSeg(courseRef.current, segRef.current);
    };
    if (delayMs > 0) {
      setAssistantStatus(t("drive.resumingIn", { seconds: Math.round(delayMs / 1000) }));
      resumeTimerRef.current = setTimeout(go, delayMs);
    } else {
      go();
    }
  }

  function stopVoiceRecognition() {
    if (pauseSubmitTimerRef.current) {
      window.clearTimeout(pauseSubmitTimerRef.current);
      pauseSubmitTimerRef.current = null;
    }
    pendingTranscriptRef.current = "";
    submittedRef.current = false;
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
    if (typeof document !== "undefined" && document.hidden) return;
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

  async function startVoiceRecognition(expectWakeWord = false) {
    if (driveVoiceRef.current) {
      pauseForAssistant(t("drive.listenQuestion"));
      driveVoiceRef.current.hold();
      driveVoiceRef.current.setLessonAudible(false);
      return;
    }
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
    pendingTranscriptRef.current = "";
    submittedRef.current = false;
    const recognition = new SpeechRecognition();
    recognition.lang = localeToBcp47(locale);
    recognition.interimResults = true;
    recognition.continuous = true;

    const submitPending = () => {
      if (submittedRef.current) return;
      const text = pendingTranscriptRef.current.trim();
      if (!text) return;
      submittedRef.current = true;
      if (pauseSubmitTimerRef.current) {
        window.clearTimeout(pauseSubmitTimerRef.current);
        pauseSubmitTimerRef.current = null;
      }
      setAssistantTranscript(text);
      try { recognition.stop(); } catch { /* */ }
      handleSpokenInput(text, expectWakeWord);
    };

    recognition.onresult = (event: any) => {
      const text = Array.from(event.results || [])
        .map((result: any) => result?.[0]?.transcript || "")
        .join(" ")
        .trim();
      if (!text) return;
      pendingTranscriptRef.current = text;
      setAssistantTranscript(text);
      if (pauseSubmitTimerRef.current) window.clearTimeout(pauseSubmitTimerRef.current);
      pauseSubmitTimerRef.current = window.setTimeout(submitPending, pauseSubmitMs);
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
      if (pauseSubmitTimerRef.current) {
        window.clearTimeout(pauseSubmitTimerRef.current);
        pauseSubmitTimerRef.current = null;
      }
      // Browser ended early — still auto-submit whatever we captured.
      if (!submittedRef.current && pendingTranscriptRef.current.trim()) {
        submitPending();
      }
      setListening(false);
      oneShotActiveRef.current = false;
      // Resume hands-free ambient listening after the manual one-shot.
      if (autoListenRef.current && courseRef.current && !driveVoiceRef.current && micReadyRef.current) {
        setAssistantStatus(t("drive.voiceAgentOff"));
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

  // Native apps (iOS WKWebView has no SpeechRecognition, Android WebView is inconsistent) can hand recognised text to the page:
  //   window.__salaNativeSpeech.onTranscript("please dance")
  // It goes through the same handler as the browser recognizer, so "dance" requests, course commands and questions all work.
  const spokenInputRef = useRef<(raw: string, wake: boolean) => void>(() => {});
  const canDriveRef = useRef(false);
  useEffect(() => {
    const bridge = {
      onTranscript(text: unknown) {
        if (!canDriveRef.current || demoEndedRef.current) return;
        const clean = String(text ?? "").trim().slice(0, 300);
        if (clean) spokenInputRef.current(clean, false);
      },
    };
    (window as unknown as { __salaNativeSpeech?: typeof bridge }).__salaNativeSpeech = bridge;
    return () => { delete (window as unknown as { __salaNativeSpeech?: typeof bridge }).__salaNativeSpeech; };
  }, []);

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
    // Easter egg: a short "dance" request is a playful reaction, not a question (no model call).
    if (salaModRef.current?.matchDanceIntent?.(cleaned, voiceLocaleRef.current || "en")) {
      salaDanceRef.current?.();
      startVoiceRecognition(false);
      return;
    }
    handleAssistantQuestion(cleaned);
  }

  // Say a short line in the chosen voice, then continue (used for course commands and friendly limits).
  function announceThen(text: string, then?: () => void) {
    setAssistantAnswer(text);
    setAssistantStatus(text);
    setAssistantOpen(true);
    playGenRef.current++;
    cancelSpeech();
    const gen = playGenRef.current;
    speak(text, () => {
      if (playGenRef.current !== gen) return;
      then?.();
    });
  }

  function handleCourseCommand(cmd: CourseCommand) {
    const rows = queue.current;
    const here = courseRef.current?.id || "";
    const go = (id: string, key: "drive.coursePlaying" | "drive.courseNextIs") => {
      const row = rows.find((r) => r.id === id);
      announceThen(t(key, { title: cleanTitle(row?.title || "") }), () => { setAssistantOpen(false); void startCourse(id); });
    };
    switch (cmd.kind) {
      case "play":
        go(cmd.id, "drive.coursePlaying");
        return;
      case "next":
      case "previous": {
        const n = neighbourCourse(rows, here, cmd.kind === "next" ? 1 : -1);
        if (!n || n.id === here) { resumeAfterAssistant(0); return; }
        go(n.id, "drive.courseNextIs");
        return;
      }
      case "list": {
        const titles = rows.slice(0, 5).map((r) => cleanTitle(r.title)).join(", ");
        announceThen(t("drive.courseList", { titles }), () => resumeAfterAssistant(0));
        return;
      }
      case "unknown":
        announceThen(t("drive.courseUnknown", { name: cmd.wanted }), () => resumeAfterAssistant(0));
        return;
    }
  }

  function chooseCourse(id: string) {
    setPickedId(id);
    // Choosing while a lesson plays switches straight away; otherwise Start plays the pick.
    if (courseRef.current && playingRef.current && courseRef.current.id !== id) void startCourse(id);
  }

  function toggleMic() {
    if (autoListenRef.current) {
      stopAmbientListening();            // also clears autoListenRef
      setAutoListen(false);
      setAssistantStatus(t("drive.micMuted"));
    } else {
      autoListenRef.current = true;
      setAutoListen(true);               // the effect restarts the recognizer while a lesson plays
      setAssistantStatus(t("drive.micOnAgain"));
    }
  }

  // Looking away or leaving pauses the lesson; coming back carries on. Only a pause WE made is undone.
  function handleAway() {
    if (!playingRef.current || demoEndedRef.current) return;
    awayPausedRef.current = true;
    pause();
    setAssistantOpen(true);
    setAssistantStatus(t("drive.awayPaused"));
  }
  function handleBack() {
    if (!awayPausedRef.current) return;
    awayPausedRef.current = false;
    setAssistantStatus(t("drive.backResume"));
    resumeAfterAssistant(0);
  }

  // "search for the Roman Empire": filter the list the learner sees, say so, and carry on with the lesson.
  function handleSearchCommand(cmd: SearchCommand) {
    clearResumeTimer();
    if (cmd.kind === "clear") {
      setSearchQuery("");
      announceThen(t("drive.search.cleared"), () => resumeAfterAssistant(0));
      return;
    }
    setSearchQuery(cmd.query);
    const found = rankCourses(searchSource, cmd.query, { language: searchLanguage, includeEnglish, allowedIds });
    announceThen(t(found.length ? "drive.search.spoken" : "drive.search.spokenNone", { q: cmd.query }), () => resumeAfterAssistant(0));
  }

  function handleAssistantQuestion(input: string) {
    const spokenSearch = parseSearchCommand(input.trim());
    if (spokenSearch) { setAssistantTranscript(input.trim()); handleSearchCommand(spokenSearch); return; }
    if (!course) return;
    clearResumeTimer();
    const command = input.trim();
    if (!command) return;
    setAssistantTranscript(command);
    const courseCmd = parseCourseCommand(command, queue.current, course.id);
    if (courseCmd) { handleCourseCommand(courseCmd); return; }
    const playback = parsePlaybackCommand(command);
    if (playback) {
      const say = (key: string, vars?: Record<string, string | number>) => setAssistantAnswer(t(key, vars));
      switch (playback.kind) {
        case "pause":
          say("drive.pausedAnswer");
          setAssistantStatus(t("drive.pausedStatus"));
          setPlaying(false);
          playGenRef.current++;
          driveVoiceRef.current?.hold();
          cancelSpeech();
          return;
        case "resume":
          say("drive.resumingAnswer");
          resumeAfterAssistant(1000);
          return;
        case "next":
          say("drive.skipAnswer");
          playSeg(course, seg + 1);
          return;
        case "previous":
          say("drive.repeatAnswer");
          playSeg(course, Math.max(0, seg - 1));
          return;
        case "repeat":
          say("drive.repeatAnswer");
          playSeg(course, seg);
          return;
        case "restart":
          say("drive.restartAnswer");
          playSeg(course, 0);
          return;
        case "faster":
        case "slower":
        case "speed": {
          const next = clampPlaybackRate(
            playback.kind === "speed" ? playback.rate : rate + (playback.kind === "faster" ? 0.15 : -0.15),
          );
          setRate(next);
          say("drive.speedAnswer", { rate: next });
          setAssistantStatus(t("drive.speedAnswer", { rate: next }));
          return;
        }
      }
    }
    const budget = limiterRef.current.check();
    if (!budget.ok) {
      announceThen(
        budget.reason === "session" ? t("drive.limitSession") : t("drive.limitRate", { seconds: budget.retryAfterS }),
        () => resumeAfterAssistant(0),
      );
      return;
    }
    if (driveVoiceRef.current) {
      playGenRef.current++;
      cancelSpeech();
      setPlaying(false);
      driveVoiceRef.current.ask(command);
      setAssistantStatus(t("drive.voiceAgentOn"));
      return;
    }
    const answer = answerFromCourse(course, seg, command, t);
    setAssistantAnswer(answer);
    setAssistantStatus(t("drive.answeringStatus"));
    playGenRef.current++;
    cancelSpeech();
    const genSnapshot = playGenRef.current;
    speak(answer, () => {
      if (playGenRef.current !== genSnapshot) return;
      // A short pause for a follow-up (tap the mascot), then say so and go back.
      clearResumeTimer();
      setAssistantStatus(t("drive.backToCourse"));
      resumeTimerRef.current = setTimeout(() => {
        if (playGenRef.current !== genSnapshot) return;
        speak(t("drive.backToCourse"), () => {
          if (playGenRef.current !== genSnapshot) return;
          resumeAfterAssistant(0);
        });
      }, 2500);
    });
  }

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 1024px)");
    setFill(mq.matches);
    setCanFullscreen(Boolean(document.fullscreenEnabled && document.documentElement.requestFullscreen));
  }, []);

  function toggleFullscreen() {
    if (document.fullscreenElement) {
      void document.exitFullscreen?.().catch(() => {});
      return;
    }
    setFill(true);
    void document.documentElement.requestFullscreen?.().catch(() => {});
  }

  function leaveStage() {
    if (document.fullscreenElement) void document.exitFullscreen?.().catch(() => {});
    if (window.history.length > 1) window.history.back();
    else window.location.href = "/";
  }

  function onStageDoubleClick(event: React.MouseEvent) {
    if ((event.target as HTMLElement).closest("button, a, input, select, textarea")) return;
    if (canFullscreen) toggleFullscreen();
    else setFill((v) => !v);
  }

  const HELP_KEY = "salareen.onTheGo.voiceTutorial.v1";
  useEffect(() => {
    if (!helpOpen) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") closeHelp(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [helpOpen]);
  function closeHelp() {
    setHelpOpen(false);
    try { localStorage.setItem(HELP_KEY, "1"); } catch { /* private mode */ }
  }
  useEffect(() => {
    if (!course) return;
    try { if (!localStorage.getItem(HELP_KEY)) setHelpOpen(true); } catch { /* private mode */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [Boolean(course)]);

  const paid = accountReady && loggedIn && tier !== "free";
  const canDrive = experience.showTimer || paid;
  canDriveRef.current = canDrive;
  spokenInputRef.current = handleSpokenInput;
  // Sala is always on screen; her state says what the microphone is doing.
  const avatarState: AvatarState = !canDrive ? "signin" : demoEnded ? "ended" : !speechOk ? "unsupported" : micDenied ? "blocked"
    : !autoListen ? "muted" : listening || playing ? "listening" : "idle";
  const avatarLabel = ({
    listening: t("drive.listening.on"), idle: t("drive.listening.idle"), muted: t("drive.listening.muted"),
    blocked: t("drive.listening.blocked"), unsupported: t("drive.listening.unavailable"), signin: t("drive.listening.signIn"), ended: "",
  } as Record<AvatarState, string>)[avatarState];

  useEffect(() => {
    let cancelled = false;
    let handle: { dispose: () => void; dance: (why?: string) => boolean } | null = null;
    (async () => {
      try {
        const url = "/api/studio/voice-overlay/sala_interactions.js";   // same-origin studio asset: a variable keeps the bundler out of it
        const mod: any = await import(/* webpackIgnore: true */ url);
        if (cancelled) return;
        salaModRef.current = mod;
        const node = document.querySelector<HTMLElement>("[data-sala-avatar]");
        if (!node) return;
        handle = mod.attachSalaInteractions(node, {
          ignoreSelector: "a, input, select, textarea",   // the mascot itself is a button
          isNarrating: () => Boolean(currentNarrationRef.current),
          isMicListening: () => true,                       // the always-on mic would hear the music: visual only here
          isMuted: () => false,
        });
        salaDanceRef.current = () => { handle?.dance("voice"); };
      } catch { /* the shared module is optional */ }
    })();
    return () => { cancelled = true; salaDanceRef.current = null; handle?.dispose(); };
  }, [Boolean(course), canDrive, consent]);   // the widget is re-keyed after the consent choice: attach to the new Sala node

  // After the mascot is tapped, tapping anywhere else on the page resumes the lesson.
  useEffect(() => {
    if (!assistantOpen) return;
    const onTap = (event: MouseEvent) => {
      const el = event.target as HTMLElement | null;
      if (el?.closest("[data-testid='on-the-go-mascot'], button, a, input, select, textarea")) return;
      stopVoiceRecognition();
      resumeAfterAssistant(0);
    };
    document.addEventListener("click", onTap);
    return () => document.removeEventListener("click", onTap);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assistantOpen]);

  const langLabel = TRAINING_LOCALE_LABELS[trainingLang] || trainingLang;

  useEffect(() => {
    if (!experience.showTimer || !playing || demoEnded) return;
    if (secondsLeft <= 0) {
      demoEndedRef.current = true;
      setDemoEnded(true);
      pause();
      stopVoiceRecognition();
      stopAmbientListening();
      setAutoListen(false);
      setCameraActive(false);
      return;
    }
    const id = window.setTimeout(() => setSecondsLeft((n) => n - 1), 1000);
    return () => window.clearTimeout(id);
  }, [experience.showTimer, playing, secondsLeft, demoEnded]); // eslint-disable-line react-hooks/exhaustive-deps

  async function onTransport() {
    awayPausedRef.current = false;
    if (demoEndedRef.current) return;
    if (!playingRef.current && !consentRef.current) { setConsentOpen(true); return; }
    if (experience.salaAgent && (!getToken() || tierRef.current === "free")) return;
    if (playingRef.current) {
      pause();
      return;
    }
    const id = pickedId || courseRef.current?.id || "";
    if (!id) return;
    if (!courseRef.current || courseRef.current.id !== id) {
      await startCourseWithAds(id);
      return;
    }
    await playWithXai();
  }

  return (
    <main
      className={fill ? "container otg-stage otg-fill" : "container otg-stage"}
      style={{ maxWidth: fill ? undefined : 720 }}
      data-presence={cameraActive && canDrive ? "on" : "off"}
      onDoubleClick={onStageDoubleClick}
    >
      {/* On a phone the camera widget would sit on top of the search box: leave room for it while it is showing. */}
      <style>{`@media (max-width: 640px) { .otg-stage[data-presence=on] { padding-top: 190px !important; } }`}</style>
      <div className="otg-bar">
        {fill ? (
          <button type="button" data-testid="on-the-go-exit" aria-label={t("drive.leave")} title={t("drive.leave")} onClick={leaveStage}>✕</button>
        ) : null}
      </div>
      <h1>{t("drive.pageTitle")}</h1>
      <p className="muted">{t("drive.pageIntro", { total: Math.max(searchRows.length, rows.length) || 200 })}</p>
      <p className="muted" style={{ fontSize: 14 }}>{t("drive.languageFollowsVoice", { lang: langLabel })}</p>
      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{friendlyError(error, t("error.offline"))}</div></div>}

      {!accountReady && !experience.showTimer && <p className="muted">{t("drive.loading")}</p>}

      {!experience.showTimer && accountReady && !loggedIn && <SignInToUse body={t("drive.signInBody")} />}

      {!experience.showTimer && accountReady && loggedIn && tier === "free" && (
        <div className="card" style={{ borderColor: "#f59e0b" }}>
          <strong>{t("drive.freePlan")}</strong>
          <div className="muted" style={{ marginTop: 4 }}>{t("drive.signInBody")}</div>
          <div className="row" style={{ marginTop: 10 }}>
            <a href="/billing"><button type="button" style={{ background: "#e50914", color: "#fff" }}>{t("drive.upgrade")}</button></a>
          </div>
        </div>
      )}

      {adBreak && canDrive && (
        <VideoAdBreak
          adBreak={adBreak}
          placement={`on-the-go-${adBreak.position}`}
          tier={effectiveAdTier(tier)}
          audioOnly
          onDone={onAdDone}
        />
      )}

      {canDrive && (
        <div className="card" style={{ borderColor: "#0ea5e9", background: "#0b1020", color: "#e8ecf6" }}>
          {searchEnabled ? (
            <OnTheGoCourseSearch
              rows={searchSource}
              language={searchLanguage}
              languageNames={TRAINING_LOCALE_LABELS as Record<string, string>}
              query={searchQuery}
              onQuery={setSearchQuery}
              includeEnglish={includeEnglish}
              onIncludeEnglish={(v) => {
                setIncludeEnglish(v);
                try { localStorage.setItem(INCLUDE_ENGLISH_KEY, v ? "1" : "0"); } catch { /* private mode */ }
              }}
              allowedIds={allowedIds}
              selectedId={pickedId || course?.id || ""}
              loading={coursesLoading || searchLoading}
              progress={progress}
              labels={{
                placeholder: t("drive.search.placeholder"), includeEnglish: t("drive.search.includeEnglish"),
                readyIn: (lang) => t("drive.search.readyIn", { lang }), otherLangs: (langs) => t("drive.search.otherLangs", { langs }),
                englishOnly: t("drive.search.englishOnly"), emptyLang: (lang) => t("drive.search.emptyLang", { lang }),
                noMatch: (q) => t("drive.search.noMatch", { q }), count: (n) => t("drive.search.count", { n }),
                voiceHint: t("drive.search.voiceHint"), loading: t("drive.loadingCourses"), resume: t("drive.pickerResume"), choose: t("drive.chooseCourse"),
              }}
              onSelect={chooseCourse}
            />
          ) : (
            <div
              aria-label={t("drive.courseLabel")}
              style={{ display: "flex", flexDirection: "column", gap: 4, padding: "6px 2px" }}
            >
              <span style={{ fontSize: 13, textTransform: "uppercase", letterSpacing: 1, fontWeight: 600, color: "#9fbac2" }}>
                {t("drive.courseLabel")}
              </span>
              <span style={{ fontSize: 20, fontWeight: 700, color: "#f4fbff" }}>
                {course?.title || rows[0]?.title || DEMO_COURSE_TITLE_FALLBACK}
              </span>
              <span style={{ fontSize: 13, color: "#9fbac2" }}>
                {t("drive.demoCourseHint")}
              </span>
            </div>
          )}
          {coursesLoading && <p className="muted">{t("drive.loadingCourses")}</p>}
          {course?.attribution && (
            <p data-testid="course-attribution" style={{ margin: "6px 2px 0", fontSize: 12, lineHeight: 1.4, color: "#9fbac2" }}>
              {course.attribution}
            </p>
          )}

          {experience.showTimer ? (
            <button
              type="button"
              aria-label={playing ? t("drive.pause") : t("drive.start")}
              onClick={() => { void onTransport(); }}
              disabled={demoEnded || !(pickedId || course)}
              style={{
                display: "grid", placeItems: "center",
                width: "100%", minHeight: 280, margin: "8px 0 12px",
                border: 0, background: "transparent", cursor: "pointer",
              }}
            >
              <span
                aria-hidden
                style={{
                  width: 196, height: 196, borderRadius: "50%",
                  display: "grid", placeItems: "center",
                  border: "2px solid rgba(212,184,138,.85)",
                  boxShadow: playing ? "0 0 0 10px rgba(212,184,138,.18), 0 0 28px rgba(212,184,138,.45)" : "0 0 0 8px rgba(212,184,138,.12)",
                  animation: playing ? "sala-ring 1.1s ease-in-out infinite" : "none",
                }}
              >
                <img src="/mascots/sala-gold-cutout.png" alt="" width={64} height={168} style={{ objectFit: "contain", height: 168, width: "auto" }} />
              </span>
              <style>{`@keyframes sala-ring { 50% { transform: scale(1.06); } }`}</style>
            </button>
          ) : (
            <div
              aria-hidden
              style={{
                display: "flex", alignItems: "center", justifyContent: "center",
                width: "100%", minHeight: 180, margin: "16px 0",
                borderRadius: 16, background: "#070b14",
              }}
            >
              <DriveStageLook look="bars" playing={playing} />
            </div>
          )}

          {!experience.showTimer && (
          <button
            type="button"
            aria-label={playing ? t("drive.pause") : t("drive.start")}
            onClick={() => { void onTransport(); }}
            disabled={demoEnded || !(pickedId || course)}
            style={{
              width: "100%", minHeight: 72, fontSize: 28, fontWeight: 700,
              borderRadius: 16, border: 0, cursor: "pointer",
              background: playing ? "#f59e0b" : "#16a34a", color: "#fff",
            }}
          >
            {playing ? t("drive.pause") : t("drive.start")}
          </button>
          )}
          {voiceLive && (
            <p className="muted" style={{ marginTop: 10, fontSize: 14 }}>{t("drive.voiceAgentOn")}</p>
          )}
        </div>
      )}

      {canDrive && helpOpen && (
        <div role="dialog" aria-modal="true" aria-label={t("drive.tutorialTitle")} data-testid="on-the-go-tutorial"
          onClick={() => closeHelp()}
          style={{ position: "fixed", inset: 0, zIndex: 60, background: "rgba(5,8,20,.82)", display: "grid", placeItems: "center", padding: 16 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ maxWidth: 420, width: "100%", background: "#0b1020", color: "#e8ecf6", borderRadius: 18, padding: 22, border: "2px solid #d4af37" }}>
            <h2 style={{ margin: "0 0 12px", fontSize: 20 }}>{t("drive.tutorialTitle")}</h2>
            <ol style={{ margin: 0, paddingLeft: 20, display: "grid", gap: 8, fontSize: 15 }}>
              <li>{t("drive.tutorialStep1")}</li>
              <li>{t("drive.tutorialStep2")}</li>
              <li>{t("drive.tutorialStep3")}</li>
              <li>{t("drive.tutorialStep4")}</li>
              <li>{t("drive.tutorialStep5")}</li>
            </ol>
            <button type="button" autoFocus data-testid="on-the-go-tutorial-close" onClick={() => closeHelp()}
              style={{ marginTop: 16, width: "100%", padding: "10px 14px", borderRadius: 12, border: 0, background: "#d4af37", color: "#0b1020", fontWeight: 800, cursor: "pointer" }}>
              {t("drive.tutorialDone")}
            </button>
          </div>
        </div>
      )}

      <div style={{ position: "fixed", left: 18, bottom: 18, zIndex: 50, display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 8, pointerEvents: "none" }}>
        {canDrive && assistantOpen && assistantStatus && (
          <div role="status" aria-live="polite" style={{ maxWidth: 240, padding: "8px 12px", borderRadius: 12, background: "#0b1020", color: "#e8ecf6", fontSize: 14, boxShadow: "0 6px 18px rgba(0,0,0,.35)" }}>
            {assistantStatus}
          </div>
        )}
      </div>
      {canDrive && consentOpen && (
        <OnTheGoConsent
          labels={{
            title: t("drive.consent.title"), body: t("drive.consent.body"), headphones: t("drive.useHeadphones"),
            mic: t("drive.consent.mic"), micCamera: t("drive.consent.micCamera"), notNow: t("drive.consent.notNow"),
          }}
          onChoose={chooseConsent}
        />
      )}
      {canDrive && (
        <OnTheGoPresence
          key={consent || "pending"}   // re-reads the camera preference after the learner chooses
          active={cameraActive}
          micOn={autoListen}
          micAvailable={speechOk}
          listening={listening}
          onToggleMic={toggleMic}
          onAway={handleAway}
          onBack={handleBack}
          salaState={avatarState}
          salaLabel={avatarLabel}
          salaAriaLabel={t("drive.askSala")}
          signInHref="/login"
          onSalaActivate={() => {
            if (avatarState === "muted") { toggleMic(); return; }
            if (!oneShotActiveRef.current) void startVoiceRecognition(false);
          }}
          timer={experience.showTimer ? { label: timerLabel(secondsLeft), ended: demoEnded, ariaLabel: demoEnded ? t("drive.demoEnded") : t("drive.freeDemo") } : undefined}
          menu={{
            voiceSlot,
            onFullscreen: canFullscreen || !fill ? () => (canFullscreen ? toggleFullscreen() : setFill(true)) : undefined,
            onHelp: experience.mode !== "demo" ? () => setHelpOpen(true) : undefined,
            onPrivacy: consent && !consentOpen ? reopenConsent : undefined,
            headphoneHint: t("drive.useHeadphones"),
            labels: {
              menu: "Settings", minimize: "Minimise", expand: "Expand", mic: "Microphone", micOn: "On", micMuted: "Muted", camera: "Camera",
              cameraOn: "On", cameraOff: "Off", fullscreen: t("drive.fullscreen"), help: t("drive.helpButton"), privacy: t("drive.consent.reset"),
            },
          }}
        />
      )}
      {!canDrive && (
        // Signed out on the full player: no camera or microphone, just Sala as the sign-in link.
        <div style={{ position: "fixed", right: 14, top: 62, zIndex: 55 }}>
          <OnTheGoAvatar state="signin" label={avatarLabel} ariaLabel={t("drive.askSala")} signInHref="/login" onActivate={() => {}} size={56} showLabel={false} />
        </div>
      )}
      {experience.showTimer && demoEnded && <OnTheGoTrialEnd />}
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
