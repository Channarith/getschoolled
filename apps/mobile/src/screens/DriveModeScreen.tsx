import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator, Animated, Easing, Image, Modal, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";

import { getAudioCourse, getTtsVoices, listStudents, SPEECH_URL, syncMyListToggle, type AudioCourse, type VoiceGroup } from "../api";
import AnimatedPressable from "../components/AnimatedPressable";
import CornerChip from "../components/CornerChip";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { useVoicePauseSubmitMs } from "../featureFlags";
import {
  bumpStreak, clearProgress, getMyList, getSettings, setSettings,
  recordProgress, toggleMyList,
} from "../storage";
import { fireCompletionAlert } from "../notifications";
import { useAndroidBackTo } from "../hooks/useAndroidBack";
import { useT } from "../i18n";
import { configureServerTts, speakNatural, stopSpeech as stopAllTts, warmVoices, setServerVoice, setServerInstructor } from "../tts";
import {
  normalizeTrainingLocale, type TrainingLocale,
} from "../trainingLocale";
import {
  checkHandsFreeReadiness, getVoiceEngineDetails, hasWakeWord,
  openHandsFreeSettings, openWakeAssistantSetupGuide,
  startVoiceListening, stopVoiceListening, stripWakeWords,
  startAmbientListening, stopAmbientListening, isQuestion, isLikelyEcho,
  type HandsFreeReadiness, type VoiceEngineLabel,
} from "../voiceAssistant";
import {
  resolveEffectiveVoiceStyle, prosodyForStyle, type NarrationVoiceStyle,
} from "../voiceProfiles";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { categoryGradient, theme } from "../theme";
import { useXaiClassVoice } from "../useXaiClassVoice";

export default function DriveModeScreen({
  courseId, isDriving = false, onBack,
}: { courseId: string; isDriving?: boolean; onBack: () => void }) {
  const { t, locale } = useT();
  const insets = useSafeAreaInsets();
  const pauseSubmitMs = useVoicePauseSubmitMs();
  useAndroidBackTo(() => { stopAllTts(); onBack(); });
  useEffect(() => { return () => { stopAllTts(); }; }, []);
  const [course, setCourse] = useState<AudioCourse | null>(null);
  const [loadError, setLoadError] = useState("");
  const [seg, setSeg] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [saved, setSaved] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [assistantStatus, setAssistantStatus] = useState("Voice agent is starting.");
  const [assistantTranscript, setAssistantTranscript] = useState("");
  const [assistantAnswer, setAssistantAnswer] = useState("");
  const [typedQuestion, setTypedQuestion] = useState("");
  const [listening, setListening] = useState(false);
  // Ambient hands-free and a deliberate tap-to-speak are different things. One
  // shared flag made "Ask" claim it was listening before you ever tapped it.
  const [capturing, setCapturing] = useState(false);
  const [partialTranscript, setPartialTranscript] = useState("");
  const micPulse = useRef(new Animated.Value(0)).current;
  const [autoListen, setAutoListen] = useState(true);   // hands-free: mic always on
  const [voiceGroups, setVoiceGroups] = useState<VoiceGroup[]>([]);
  const [voiceId, setVoiceId] = useState("");
  const [voiceEngine, setVoiceEngine] = useState<VoiceEngineLabel>("System");
  const [voiceSetupOpen, setVoiceSetupOpen] = useState(false);
  const [voiceSetupChecking, setVoiceSetupChecking] = useState(true);
  const [voiceReadiness, setVoiceReadiness] = useState<HandsFreeReadiness | null>(null);
  const [rate, setRate] = useState(1);
  const [trainingLang, setTrainingLang] = useState<TrainingLocale>("en");
  const rateRef = useRef(rate);
  rateRef.current = rate;
  const segRef = useRef(0);
  const voiceStyleRef = useRef<NarrationVoiceStyle>("standard");
  // Live mirrors of the chosen accent (BCP-47) / gender / instructor so the
  // on-device voice fallback honors them too — not only the neural server path.
  const voiceLocaleRef = useRef<string>("");
  const voiceGenderRef = useRef<string>("");
  const instructorRef = useRef<string>("");
  const resumeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const expectWakeRef = useRef(true);
  const autoListenRef = useRef(true);
  const awaitingQuestionRef = useRef(false);
  const currentNarrationRef = useRef("");
  autoListenRef.current = autoListen;
  // Monotonic playback token: any stop/pause/back bumps it so a stopped
  // utterance's onDone can't re-speak the next segment (which made audio keep
  // playing after Stop / leaving the screen).
  const playGenRef = useRef(0);
  const setupStartedRef = useRef(false);
  const agentStartedRef = useRef(false);
  const xai = useXaiClassVoice(Boolean(course), {
    mode: "drive",
    context: course?.segments?.[0]?.text || course?.title || "",
    language: course?.body_locale || trainingLang,
    category: course?.category || "",
    topic: course?.title || "",
    courseId: course?.id || courseId,
  });
  const speakAgentRef = useRef(xai.speakLatest);
  const interruptAgentRef = useRef(xai.interrupt);
  speakAgentRef.current = xai.speakLatest;
  interruptAgentRef.current = xai.interrupt;

  function stopSpeech() {
    playGenRef.current++;
    interruptAgentRef.current();
    stopAllTts();   // stops device voice AND server neural audio
  }

  useEffect(() => {
    configureServerTts(SPEECH_URL);   // use ElevenLabs/edge-tts neural audio when available
    void getTtsVoices().then((r) => setVoiceGroups(r.groups)).catch(() => setVoiceGroups([]));
    void getVoiceEngineDetails()
      .then((d) => setVoiceEngine(d.label))
      .catch(() => setVoiceEngine("System"));
  }, []);

  useEffect(() => {
    if (!voiceId || !voiceGroups.length) return;
    syncVoiceRefsFromCatalog(voiceId);
  }, [voiceId, voiceGroups]);

  async function refreshVoiceStyle() {
    const settings = await getSettings();
    let student = null;
    try {
      student = (await listStudents()).students[0] ?? null;
    } catch { /* offline / guest */ }
    voiceStyleRef.current = resolveEffectiveVoiceStyle(settings.instructorId, student);
  }

  function syncVoiceRefsFromCatalog(vid: string) {
    const v = voiceGroups.flatMap((g) => g.voices).find((x) => x.id === vid);
    voiceLocaleRef.current = v?.locale || "";
    voiceGenderRef.current = v?.gender || "";
  }

  useEffect(() => {
    void warmVoices();
    void refreshVoiceStyle();
    void getSettings().then((s) => {
      setVoiceId(s.voiceId || "");
      setServerVoice(s.voiceId || "");
      setServerInstructor(s.instructorId || "");
      instructorRef.current = s.instructorId || "";
      const tloc = normalizeTrainingLocale(s.trainingLocale || locale);
      setTrainingLang(tloc);
      setCourse(null);
      setLoadError("");
      getAudioCourse(courseId, locale, tloc)
        .then((c) => {
          agentStartedRef.current = false;
          setCourse(c);
          void prepareHandsFree(c, tloc);
        })
        .catch((e) => setLoadError((e as Error).message || "This course could not be opened."));
    });
    void getMyList().then((ids) => setSaved(ids.includes(courseId)));
    return () => {
      playGenRef.current++;
      stopSpeech();
      stopVoiceRecognition();
      stopAmbient();
      clearResumeTimer();
    };
  }, [courseId, locale]);

  async function prepareHandsFree(_c: AudioCourse, _tloc: TrainingLocale) {
    if (setupStartedRef.current) return;
    setupStartedRef.current = true;
    setVoiceSetupChecking(true);
    const readiness = await checkHandsFreeReadiness(true);
    setVoiceReadiness(readiness);
    setVoiceEngine(readiness.engine);
    setVoiceSetupChecking(false);
    setVoiceSetupOpen(false);
    if (!readiness.permissionGranted) {
      setAssistantStatus(t("drive.voicePermissionDenied", { engine: readiness.engine }));
      return;
    }
    autoListenRef.current = true;
    setAutoListen(true);
    void startAmbient();
  }

  function playFrom(c: AudioCourse, i: number, tloc: TrainingLocale = trainingLang) {
    clearResumeTimer();
    setAssistantOpen(false);
    const gen = ++playGenRef.current;   // new playback generation
    stopAllTts();
    if (i < 0 || i >= c.segments.length) {
      setPlaying(false);
      void onCompleted(c);
      return;
    }
    segRef.current = i; setSeg(i); setPlaying(true);
    void recordProgress({
      id: c.id, title: c.title, category: c.category,
      segment: i, total: c.segments.length,
    });
    const s = c.segments[i];
    // Narrate in the language of the actual text (body_locale), which may
    // differ from the requested training locale when it falls back to English.
    const speakLocale = c.body_locale || tloc;
    const script = `${s.heading}. ${s.text}`;
    currentNarrationRef.current = script;   // for echo filtering
    const advance = () => {
      if (playGenRef.current === gen && segRef.current === i) playFrom(c, i + 1, tloc);
    };
    speakAgentRef.current(
      `drive-${c.id}-${i}-${gen}`,
      `Read this lesson segment aloud, then stop. Do not ask a question.\n\n${script}`,
      {
        onDone: advance,
        fallback: () => {
          speakNatural(script, {
            locale: speakLocale,
            voiceStyle: voiceStyleRef.current,
            rate: rateRef.current * prosodyForStyle(voiceStyleRef.current).rate,
            voiceLocale: voiceLocaleRef.current || undefined,
            voiceGender: voiceGenderRef.current || undefined,
            persona: instructorRef.current || undefined,
            onDone: advance,
          });
        },
      },
    );
  }

  useEffect(() => {
    if (!course || agentStartedRef.current) return;
    if (xai.phase !== "live" && xai.phase !== "unavailable") return;
    agentStartedRef.current = true;
    playFrom(course, segRef.current, trainingLang);
  }, [course, xai.phase, trainingLang]);

  function clearResumeTimer() {
    if (resumeTimerRef.current) {
      clearTimeout(resumeTimerRef.current);
      resumeTimerRef.current = null;
    }
  }

  function pauseForAssistant(status = "Voice agent is listening. Ask your question.") {
    clearResumeTimer();
    stopSpeech();
    setPlaying(false);
    setAssistantOpen(true);
    setAssistantStatus(status);
    setAssistantAnswer("");
  }

  function resumeCourse(delayMs = 0) {
    if (!course) return;
    clearResumeTimer();
    const resume = () => {
      setAssistantOpen(false);
      playFrom(course, segRef.current);
    };
    if (delayMs > 0) {
      setAssistantStatus(`Resuming in ${Math.round(delayMs / 1000)} seconds. Say or tap Pause to stay paused.`);
      resumeTimerRef.current = setTimeout(resume, delayMs);
    } else {
      resume();
    }
  }

  function stopVoiceRecognition() {
    stopVoiceListening();
    setListening(false);
  }

  // ---- Hands-free ambient listening (always on; wake-word gated) ---------- //
  function handleAmbientResult(text: string) {
    const raw = (text || "").trim();
    if (!raw) return;
    // Already heard the wake word: this utterance is the question.
    if (awaitingQuestionRef.current) {
      awaitingQuestionRef.current = false;
      const q = hasWakeWord(raw) ? stripWakeWords(raw) : raw;
      if (q) { setAssistantTranscript(q); handleAssistantQuestion(q); }
      else awaitingQuestionRef.current = true;
      return;
    }
    // Explicit wake word → honor command/question after it.
    if (hasWakeWord(raw)) {
      const after = stripWakeWords(raw);
      pauseForAssistant("Listening. Ask your question.");
      if (after) { setAssistantTranscript(after); handleAssistantQuestion(after); }
      else awaitingQuestionRef.current = true;
      return;
    }
    // No wake word: pause ONLY for a real question that isn't the narration echo.
    if (isLikelyEcho(raw, currentNarrationRef.current)) return;
    if (!isQuestion(raw)) return;   // statement / filler / noise → keep playing
    setAssistantTranscript(raw);
    pauseForAssistant("Answering your question.");
    handleAssistantQuestion(raw);
  }

  async function startAmbient(): Promise<boolean> {
    if (!autoListenRef.current) return false;
    const ok = await startAmbientListening({
      locale,
      pauseSubmitMs,
      onResult: (text) => handleAmbientResult(text),
      onError: (code) => {
        setListening(false);
        if (code === "permission_denied") {
          setAutoListen(false); autoListenRef.current = false;
          setAssistantStatus(t("drive.voicePermissionDenied", { engine: voiceEngine }));
        }
      },
    });
    setListening(ok);
    return ok;
  }

  function stopAmbient() {
    autoListenRef.current = false;
    awaitingQuestionRef.current = false;
    stopAmbientListening();
    setListening(false);
  }

  // A visible heartbeat while the mic is open: text alone was too easy to miss,
  // which is why the device looked like it was not listening.
  const micLive = capturing || (autoListen && listening);
  useEffect(() => {
    if (!micLive) {
      micPulse.stopAnimation();
      micPulse.setValue(0);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(micPulse, {
          toValue: 1,
          duration: 700,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true,
        }),
        Animated.timing(micPulse, {
          toValue: 0,
          duration: 700,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [micLive, micPulse]);

  /** Cancel a deliberate capture without waiting for the silence timer. */
  function stopCapture() {
    stopVoiceRecognition();
    setCapturing(false);
    setPartialTranscript("");
    setAssistantStatus("");
    if (autoListenRef.current) setTimeout(() => { void startAmbient(); }, 300);
  }

  function toggleAutoListen() {
    if (autoListen) { setAutoListen(false); stopAmbient(); }
    else { setAutoListen(true); autoListenRef.current = true; void startAmbient(); }
  }

  async function startVoiceRecognition(expectWakeWord = false) {
    // Tapping the mic IS the wake signal, so a spoken wake word is never
    // Tapping Ask is the signal. The voice agent does not need a wake phrase.
    expectWakeRef.current = expectWakeWord;
    // Suspend ambient so only one recognizer is active during the manual capture.
    stopAmbientListening();
    setPartialTranscript("");
    pauseForAssistant(t("drive.listeningQuestion"));

    const started = await startVoiceListening({
      // Recognise in the language the lesson is taught in, not the UI language.
      locale: trainingLang || locale,
      pauseSubmitMs,
      autoSubmitOnPause: true,
      onPartial: (text) => setPartialTranscript(text),
      onResult: (text) => {
        setCapturing(false);
        setPartialTranscript("");
        setAssistantTranscript(text);
        void handleSpokenInput(text, expectWakeRef.current);
      },
      onError: (code) => {
        setCapturing(false);
        setPartialTranscript("");
        if (code === "permission_denied") {
          setAssistantStatus(t("drive.voicePermissionDenied", { engine: voiceEngine }));
        } else if (code === "no_speech") {
          setAssistantStatus(t("drive.noSpeechHeard"));
        } else if (code === "unavailable") {
          setAssistantStatus(t("drive.voiceUnavailable", { engine: voiceEngine }));
        } else {
          setAssistantStatus(t("drive.voiceError"));
        }
      },
      onEnd: () => {
        setCapturing(false);
        setPartialTranscript("");
        // Resume hands-free ambient listening after the manual one-shot.
        if (autoListenRef.current) setTimeout(() => { void startAmbient(); }, 500);
      },
    });

    setCapturing(started);
  }

  async function handleSpokenInput(raw: string, expectWakeWord: boolean) {
    stopVoiceRecognition();
    const text = raw.trim();
    if (!text) {
      setAssistantStatus(t("drive.voiceNoInput"));
      return;
    }
    if (expectWakeWord && !hasWakeWord(text)) {
      setAssistantStatus(t("drive.wakeNotDetected"));
      return;
    }
    const cleaned = stripWakeWords(text);
    if (!cleaned) {
      setAssistantStatus(t("drive.heardWakeOnly"));
      void startVoiceRecognition(false);
      return;
    }
    handleAssistantQuestion(cleaned);
  }

  function handleAssistantQuestion(input: string) {
    if (!course) return;
    const command = input.trim();
    if (!command) return;
    clearResumeTimer();
    setAssistantTranscript(command);
    const lower = command.toLowerCase();
    if (/\b(pause|stop|hold)\b/.test(lower)) {
      stopSpeech();
      setPlaying(false);
      setAssistantAnswer("Paused. Say or tap Resume when you want to continue.");
      setAssistantStatus("Paused for you.");
      return;
    }
    if (/\b(resume|continue|carry on|keep going)\b/.test(lower)) {
      setAssistantAnswer("Resuming the lesson.");
      resumeCourse(1000);
      return;
    }
    if (/\b(next|skip ahead)\b/.test(lower)) {
      setAssistantAnswer("Skipping to the next segment.");
      playFrom(course, Math.min(seg + 1, course.segments.length - 1));
      return;
    }
    if (/\b(previous|back|repeat)\b/.test(lower)) {
      setAssistantAnswer("Going back so you can hear that part again.");
      playFrom(course, Math.max(0, seg - 1));
      return;
    }
    stopSpeech();
    setAssistantStatus("Voice agent is answering.");
    const askedAt = segRef.current;
    speakAgentRef.current(`ask-${Date.now()}`, command, {
      onDone: () => {
        if (segRef.current < 0) segRef.current = Math.max(0, askedAt);
        resumeCourse(1200);
      },
      fallback: () => {
        const answer = answerFromCourse(course, seg, command);
        setAssistantAnswer(answer);
        setAssistantStatus("Answering your question. I will resume automatically unless you pause.");
        speakNatural(`${answer} Would you like to resume? Say resume, or I will continue shortly.`, {
          locale: course.body_locale || trainingLang,
          voiceStyle: voiceStyleRef.current,
          onDone: () => resumeCourse(6500),
        });
      },
    });
  }

  function submitTypedQuestion() {
    const q = typedQuestion.trim();
    if (!q) return;
    setTypedQuestion("");
    pauseForAssistant("Answering your typed question.");
    handleAssistantQuestion(q);
  }

  async function onCompleted(c: AudioCourse) {
    await clearProgress(c.id);
    await bumpStreak();
    const settings = await getSettings();
    if (settings.notificationsEnabled && settings.completionAlerts) {
      try { await fireCompletionAlert(c.title, c.id); } catch {}
    }
  }

  const onToggleSave = async () => {
    const next = await toggleMyList(courseId);
    setSaved(next);
    // Best-effort server sync so the save appears on other devices.
    void syncMyListToggle(courseId, next, course?.title ?? courseId);
  };

  if (!course) {
    return (
      <View style={styles.c}>
        {loadError ? (
          <>
            <Text style={{ color: theme.colors.text, textAlign: "center", marginBottom: 16 }}>
              {loadError}
            </Text>
            <AnimatedPressable onPress={onBack}>
              <Text style={{ color: theme.colors.accent }}>{t("liveClass.back")}</Text>
            </AnimatedPressable>
          </>
        ) : (
          <ActivityIndicator color={theme.colors.netflix} size="large" />
        )}
      </View>
    );
  }
  const [c1, c2] = categoryGradient(course.category);

  return (
    <View style={styles.c}>
      <LinearGradient colors={[c1, c2]} style={styles.heroPoster}>
        <LinearGradient
          colors={["transparent", "rgba(0,0,0,0.75)"]}
          style={StyleSheet.absoluteFill}
        />
        {isDriving ? (
          <View style={styles.drivingBadge}>
            <Ionicons name="car" size={14} color="#fff" />
            <Text style={styles.drivingBadgeText}>{t("drive.drivingBadge")}</Text>
          </View>
        ) : null}
        <View style={[styles.salaRing, playing && styles.salaRingLive]}>
          <Image source={require("../../assets/sala-gold.png")} style={styles.salaGold} accessibilityIgnoresInvertColors />
        </View>
        <Text style={styles.heroTitle} numberOfLines={2}>{course.title}</Text>
      </LinearGradient>

      <View style={[styles.corner, { top: insets.top + 8 }]} pointerEvents="box-none">
        <CornerChip>
          <AnimatedPressable onPress={() => { stopSpeech(); onBack(); }} hitSlop={8} accessibilityLabel={t("drive.back")}>
            <Ionicons name="chevron-back" size={16} color={theme.colors.goldTrim} />
          </AnimatedPressable>
          <AnimatedPressable onPress={() => void onToggleSave()} hitSlop={8} accessibilityLabel={saved ? "Saved" : "Save"}>
            <Ionicons
              name={saved ? "bookmark" : "bookmark-outline"}
              size={15}
              color={saved ? theme.colors.goldTrim : theme.colors.muted}
            />
          </AnimatedPressable>
        </CornerChip>
      </View>

      <GlassPanel style={[styles.playerCard, { marginBottom: Math.max(insets.bottom, 10) }]}>
        <Text testID="drive-segment-heading" style={styles.cat} numberOfLines={1}>
          {course.segments[seg]?.heading} · {seg + 1}/{course.segments.length}
        </Text>
        <View style={styles.speedRow}>
          {[0.5, 1, 2, 3].map((r) => (
            <AnimatedPressable
              key={r}
              testID={`drive-speed-${r}`}
              onPress={() => {
                setRate(r);
                rateRef.current = r;
                if (course) {
                  stopAllTts();
                  playFrom(course, seg);
                }
              }}
              style={[styles.speedChip, rate === r && styles.speedChipOn]}
            >
              <Text style={[styles.speedChipText, rate === r && styles.speedChipTextOn]}>{r}x</Text>
            </AnimatedPressable>
          ))}
        </View>

        <View style={styles.row}>
          <AnimatedPressable testID="drive-prev" style={styles.btn} onPress={() => playFrom(course, Math.max(0, seg - 1))}>
            <Ionicons name="play-skip-back" size={28} color="#fff" />
          </AnimatedPressable>
          {playing ? (
            <AnimatedPressable
              testID="drive-pause"
              style={[styles.btn, styles.pause]}
              onPress={() => { stopSpeech(); setPlaying(false); }}
            >
              <Ionicons name="pause" size={32} color="#fff" />
            </AnimatedPressable>
          ) : (
            <AnimatedPressable testID="drive-play" style={[styles.btn, styles.play]} onPress={() => playFrom(course, seg)}>
              <Ionicons name="play" size={32} color="#fff" />
            </AnimatedPressable>
          )}
          <AnimatedPressable testID="drive-next" style={styles.btn} onPress={() => playFrom(course, seg + 1)}>
            <Ionicons name="play-skip-forward" size={22} color="#fff" />
          </AnimatedPressable>
          <AnimatedPressable
            testID="drive-ask"
            style={styles.btn}
            accessibilityLabel={capturing ? t("drive.stopListening") : t("drive.ask")}
            onPress={() => (capturing ? stopCapture() : void startVoiceRecognition(false))}
          >
            <Ionicons name={capturing ? "stop" : "mic"} size={20} color={theme.colors.goldTrim} />
          </AnimatedPressable>
          <AnimatedPressable
            style={styles.btn}
            accessibilityLabel={t("drive.setupButton")}
            onPress={() => setVoiceSetupOpen(true)}
          >
            <Ionicons name="options-outline" size={18} color={theme.colors.goldTrim} />
          </AnimatedPressable>
        </View>
        {micLive ? (
          <Text style={styles.micLiveText} numberOfLines={1} testID="drive-listening-indicator">
            {partialTranscript || (capturing ? t("drive.listeningQuestion") : t("drive.handsFreeListening"))}
          </Text>
        ) : null}
      </GlassPanel>

      <Modal
        animationType="slide"
        transparent
        visible={voiceSetupOpen}
        onRequestClose={onBack}
      >
        <View style={styles.modalScrim}>
          <GlassPanel style={styles.assistantCard} padded={false}>
            <ScrollView contentContainerStyle={{ padding: 18 }}>
              <Text style={styles.assistantTitle}>{t("drive.setupTitle")}</Text>
              <Text style={styles.setupSafety}>{t("drive.setupSafety")}</Text>
              <View style={styles.setupStatus}>
                <Ionicons
                  name={voiceReadiness?.available ? "checkmark-circle" : "alert-circle"}
                  size={20}
                  color={voiceReadiness?.available ? theme.colors.success : theme.colors.netflix}
                />
                <Text style={styles.assistantStatus}>
                  {voiceReadiness?.available
                    ? t("drive.setupRecognitionReady", { engine: voiceReadiness.engine })
                    : t("drive.setupRecognitionMissing", { engine: voiceEngine })}
                </Text>
              </View>
              <View style={styles.setupStatus}>
                <Ionicons
                  name={voiceReadiness?.permissionGranted ? "checkmark-circle" : "mic-off"}
                  size={20}
                  color={voiceReadiness?.permissionGranted ? theme.colors.success : theme.colors.gold}
                />
                <Text style={styles.assistantStatus}>
                  {voiceReadiness?.permissionGranted
                    ? t("drive.setupPermissionReady")
                    : t("drive.setupPermissionNeeded")}
                </Text>
              </View>
              <Text style={styles.setupNotice}>
                {t("drive.setupWakeNotice", { engine: voiceEngine })}
              </Text>
              <Text style={styles.setupSteps}>
                {voiceEngine === "Siri"
                  ? t("drive.setupSiriSteps")
                  : t("drive.setupGoogleSteps")}
              </Text>
              <View style={styles.modalActions}>
                {voiceReadiness?.available && voiceReadiness.permissionGranted ? (
                  <PrimaryButton
                    label={t("drive.setupContinue")}
                    onPress={() => setVoiceSetupOpen(false)}
                    variant="brand"
                  />
                ) : (
                  <PrimaryButton
                    label={voiceSetupChecking ? t("drive.setupChecking") : t("drive.setupEnable")}
                    disabled={voiceSetupChecking}
                    onPress={() => {
                      if (!course) return;
                      setupStartedRef.current = false;
                      void prepareHandsFree(course, trainingLang);
                    }}
                    variant="brand"
                  />
                )}
                <PrimaryButton
                  label={t("drive.setupSettings")}
                  onPress={() => void openHandsFreeSettings()}
                  variant="ghost"
                />
                <PrimaryButton
                  label={t("drive.setupGuide", { engine: voiceEngine })}
                  onPress={() => void openWakeAssistantSetupGuide()}
                  variant="ghost"
                />
                <PrimaryButton
                  label={t("drive.setupListenAnyway")}
                  onPress={() => setVoiceSetupOpen(false)}
                  variant="ghost"
                />
                <PrimaryButton label={t("drive.back")} onPress={onBack} variant="ghost" />
              </View>
            </ScrollView>
          </GlassPanel>
        </View>
      </Modal>

      <Modal animationType="slide" transparent visible={assistantOpen} onRequestClose={() => setAssistantOpen(false)}>
        <View style={styles.modalScrim}>
          <GlassPanel style={styles.assistantCard} padded={false}>
            <View style={{ padding: 18 }}>
              <Text style={styles.assistantTitle}>{t("drive.assistantTitle")}</Text>
              <Text style={styles.assistantStatus}>{assistantStatus}</Text>
              {assistantTranscript ? (
                <Text style={styles.transcript}>You: {assistantTranscript}</Text>
              ) : null}
              {assistantAnswer ? (
                <Text style={styles.answer}>{assistantAnswer}</Text>
              ) : null}
              <TextInput
                style={styles.askInput}
                placeholder="Ask a question or say pause/resume..."
                placeholderTextColor={theme.colors.muted}
                selectionColor={theme.colors.text}
                value={typedQuestion}
                onChangeText={setTypedQuestion}
                onSubmitEditing={submitTypedQuestion}
              />
              <View style={styles.modalActions}>
                <PrimaryButton
                  label={listening ? t("drive.listening") : t("drive.mic")}
                  onPress={() => void startVoiceRecognition(false)}
                  variant="ghost"
                />
                <PrimaryButton label={t("drive.ask")} onPress={submitTypedQuestion} variant="brand" />
                <PrimaryButton label={t("drive.resume")} onPress={() => resumeCourse()} variant="netflix" />
                <PrimaryButton
                  label={t("drive.stayPaused")}
                  onPress={() => { clearResumeTimer(); setAssistantOpen(false); }}
                  variant="ghost"
                />
              </View>
            </View>
          </GlassPanel>
        </View>
      </Modal>
    </View>
  );
}

function answerFromCourse(course: AudioCourse, seg: number, question: string): string {
  const words = question.toLowerCase().split(/[^a-z0-9]+/).filter((w) => w.length > 3);
  const candidates = course.segments.map((s, i) => ({
    segment: s,
    score: scoreSegment(s.text, words) + (i === seg ? 2 : 0),
  })).sort((a, b) => b.score - a.score);
  const best = candidates[0]?.segment || course.segments[seg] || course.segments[0];
  const current = course.segments[seg] || best;
  const source = (best.text || current.text || "").replace(/\s+/g, " ").trim();
  const snippet = source.length > 360 ? `${source.slice(0, 360)}...` : source;
  return `Here is the course-grounded answer: ${snippet}`;
}

function scoreSegment(text: string, words: string[]): number {
  const lower = text.toLowerCase();
  return words.reduce((score, word) => score + (lower.includes(word) ? 1 : 0), 0);
}

const styles = StyleSheet.create({
  c: { flex: 1, backgroundColor: "transparent" },
  corner: { position: "absolute", left: 10, zIndex: 4 },
  topRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 16 },
  backRow: { flexDirection: "row", alignItems: "center", gap: 2 },
  back: { color: theme.colors.text, fontSize: 16, fontWeight: "600" },
  heroPoster: {
    flex: 1, overflow: "hidden",
    alignItems: "center", justifyContent: "center",
  },
  drivingBadge: {
    position: "absolute", top: 12, right: 12, zIndex: 2,
    flexDirection: "row", alignItems: "center", gap: 6,
    backgroundColor: "rgba(229, 9, 20, 0.92)", paddingHorizontal: 10, paddingVertical: 5,
    borderRadius: theme.radius.pill,
  },
  drivingBadgeText: { color: "#fff", fontSize: 12, fontWeight: "800" },
  salaRing: {
    width: 92, height: 92, borderRadius: 46, borderWidth: 2, borderColor: "rgba(212,184,138,.9)",
    alignItems: "center", justifyContent: "center", marginBottom: 8,
  },
  salaRingLive: { borderColor: "#e8d5b0", transform: [{ scale: 1.06 }] },
  salaGold: { width: 54, height: 72, resizeMode: "contain" },
  heroTitle: {
    position: "absolute", bottom: 14, left: 14, right: 14,
    color: "#fff", fontSize: 20, fontWeight: "800", lineHeight: 26,
  },
  playerCard: { marginHorizontal: 10, marginTop: -18 },
  cat: { color: theme.colors.muted, ...theme.typography.caption },
  seg: { color: theme.colors.text, fontSize: 18, fontWeight: "700", marginTop: 10 },
  prog: { color: theme.colors.muted, marginTop: 6, marginBottom: 8, ...theme.typography.caption },
  progressTrack: {
    height: 6,
    backgroundColor: "rgba(255,255,255,0.15)",
    borderRadius: 4,
    overflow: "hidden",
    marginBottom: 10,
  },
  speedRow: { flexDirection: "row", gap: 8, marginBottom: 12, justifyContent: "center" },
  speedChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: theme.radius.pill,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.35)",
    backgroundColor: "rgba(255,255,255,0.1)",
  },
  speedChipOn: { backgroundColor: theme.colors.netflix, borderColor: theme.colors.netflix },
  speedChipText: { color: theme.colors.muted, fontWeight: "700", fontSize: 13 },
  speedChipTextOn: { color: "#fff" },
  langLabel: { color: theme.colors.muted, marginBottom: 8, ...theme.typography.caption },
  langRow: { flexDirection: "row", gap: 8, paddingBottom: 4, marginBottom: 4 },
  micLiveRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 8,
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 10,
    backgroundColor: "rgba(46,204,113,0.12)",
    borderWidth: 1,
    borderColor: "rgba(46,204,113,0.45)",
  },
  micDot: { width: 10, height: 10, borderRadius: 999, backgroundColor: "#2ecc71" },
  micLiveText: {
    flex: 1,
    minWidth: 0,
    color: "#d6f5e3",
    fontSize: 12,
    fontWeight: "600",
    lineHeight: 16,
    includeFontPadding: false,
  },
  langChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: theme.radius.pill,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.35)",
    backgroundColor: "rgba(255,255,255,0.1)",
  },
  langChipOn: { backgroundColor: theme.colors.success, borderColor: theme.colors.success },
  langChipText: { color: theme.colors.muted, fontWeight: "700", fontSize: 13 },
  langChipTextOn: { color: "#fff" },
  progressBar: { height: 6, backgroundColor: theme.colors.netflix },
  row: { flexDirection: "row", justifyContent: "center", alignItems: "center", gap: 8 },
  btn: {
    backgroundColor: "rgba(255,255,255,0.08)",
    width: 44, height: 44, borderRadius: 22,
    alignItems: "center", justifyContent: "center",
    borderWidth: 1, borderColor: "rgba(232, 200, 114, 0.55)",
  },
  play: { backgroundColor: theme.colors.success, borderColor: theme.colors.success },
  pause: { backgroundColor: theme.colors.gold, borderColor: theme.colors.gold },
  assistantBar: { marginTop: 8 },
  assistantWake: { color: theme.colors.text, fontSize: 14, fontWeight: "800", textAlign: "center" },
  assistantEngine: {
    color: theme.colors.muted, fontSize: 11, textAlign: "center", marginTop: 4, lineHeight: 15,
  },
  assistantActions: { flexDirection: "row", gap: 10, justifyContent: "center", marginTop: 12, flexWrap: "wrap" },
  assistantBtn: {
    flexDirection: "row", alignItems: "center", gap: 6,
    backgroundColor: theme.colors.brand, borderRadius: theme.radius.pill,
    paddingHorizontal: 16, paddingVertical: 10,
  },
  assistantBtnText: { color: "#001022", fontWeight: "900" },
  assistantBtnGhost: { backgroundColor: "transparent", borderWidth: 1, borderColor: theme.colors.border },
  assistantBtnGhostText: { color: theme.colors.text, fontWeight: "700" },
  hint: { color: theme.colors.muted, textAlign: "center", marginTop: 16, ...theme.typography.caption },
  modalScrim: { flex: 1, justifyContent: "flex-end", backgroundColor: theme.colors.scrimHeavy },
  assistantCard: { borderBottomLeftRadius: 0, borderBottomRightRadius: 0 },
  assistantTitle: { color: theme.colors.text, fontSize: 22, fontWeight: "900" },
  assistantStatus: { color: theme.colors.muted, marginTop: 4 },
  setupSafety: {
    color: theme.colors.text, fontSize: 15, lineHeight: 21, marginTop: 10,
    fontWeight: "700",
  },
  setupStatus: { flexDirection: "row", alignItems: "center", gap: 9, marginTop: 12 },
  setupNotice: { color: theme.colors.gold, lineHeight: 20, marginTop: 14 },
  setupSteps: { color: theme.colors.text, lineHeight: 20, marginTop: 10 },
  transcript: { color: theme.colors.accent, marginTop: 12 },
  answer: { color: theme.colors.text, fontSize: 15, lineHeight: 21, marginTop: 10 },
  askInput: {
    backgroundColor: "rgba(255,255,255,0.06)", borderColor: theme.colors.border,
    borderRadius: theme.radius.md, borderWidth: 1, color: theme.colors.text,
    marginTop: 14, padding: 12,
  },
  modalActions: { marginTop: 14, gap: 10 },
});
