import * as Speech from "expo-speech";
import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator, Modal, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";

import {
  askCourseQuestion, getAudioCourse, listStudents, type AudioCourse,
} from "../api";
import AnimatedPressable from "../components/AnimatedPressable";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import {
  bumpStreak, clearProgress, getMyList, getSettings,
  recordProgress, toggleMyList,
} from "../storage";
import { fireCompletionAlert } from "../notifications";
import { useT } from "../i18n";
import { speakNatural, warmVoices } from "../tts";
import { normalizeTrainingLocale, type TrainingLocale } from "../trainingLocale";
import {
  getVoiceEngineDetails, hasWakeWord,
  startVoiceListening, stopVoiceListening, stripWakeWords,
  type VoiceEngineLabel,
} from "../voiceAssistant";
import { resolveVoiceStyle, prosodyForStyle, type NarrationVoiceStyle } from "../voiceProfiles";
import { categoryGradient, theme } from "../theme";

const RESUME_DELAY_MS = 25000;

export default function DriveModeScreen({
  courseId, isDriving = false, onBack,
}: { courseId: string; isDriving?: boolean; onBack: () => void }) {
  const { t, locale } = useT();
  const [course, setCourse] = useState<AudioCourse | null>(null);
  const [seg, setSeg] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [saved, setSaved] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [assistantStatus, setAssistantStatus] = useState("Say Hey Sala or Salareen to ask a question.");
  const [assistantTranscript, setAssistantTranscript] = useState("");
  const [assistantAnswer, setAssistantAnswer] = useState("");
  const [typedQuestion, setTypedQuestion] = useState("");
  const [listening, setListening] = useState(false);
  const [voiceEngine, setVoiceEngine] = useState<VoiceEngineLabel>("System");
  const [rate, setRate] = useState(1);
  const [trainingLang, setTrainingLang] = useState<TrainingLocale>("en");
  const rateRef = useRef(rate);
  rateRef.current = rate;
  const segRef = useRef(0);
  const voiceStyleRef = useRef<NarrationVoiceStyle>("standard");
  const resumeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const expectWakeRef = useRef(false);
  const handsFreeRef = useRef(true);
  const answeringRef = useRef(false);

  useEffect(() => {
    void getVoiceEngineDetails()
      .then((d) => setVoiceEngine(d.label))
      .catch(() => setVoiceEngine("System"));
  }, []);

  async function refreshVoiceStyle() {
    const settings = await getSettings();
    let student = null;
    try {
      student = (await listStudents()).students[0] ?? null;
    } catch { /* offline / guest */ }
    voiceStyleRef.current = resolveVoiceStyle(settings.narrationVoicePref, student);
  }

  useEffect(() => {
    void warmVoices();
    void refreshVoiceStyle();
    void getSettings().then((s) => {
      const tloc = normalizeTrainingLocale(s.trainingLocale || locale);
      setTrainingLang(tloc);
      getAudioCourse(courseId, locale, tloc)
        .then((c) => { setCourse(c); playFrom(c, 0, tloc); })
        .catch(() => {});
    });
    void getMyList().then((ids) => setSaved(ids.includes(courseId)));
    return () => {
      handsFreeRef.current = false;
      Speech.stop();
      stopVoiceRecognition();
      clearResumeTimer();
    };
  }, [courseId, locale]);

  useEffect(() => {
    if (!course || !handsFreeRef.current) return;
    void startHandsFreeListening();
    return () => stopVoiceRecognition();
  }, [course?.id, locale]);

  function playFrom(c: AudioCourse, i: number, tloc: TrainingLocale = trainingLang) {
    clearResumeTimer();
    setAssistantOpen(false);
    Speech.stop();
    if (i >= c.segments.length) {
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
    speakNatural(`${s.heading}. ${s.text}`, {
      locale: tloc,
      voiceStyle: voiceStyleRef.current,
      rate: rateRef.current * prosodyForStyle(voiceStyleRef.current).rate,
      onDone: () => { if (segRef.current === i) playFrom(c, i + 1, tloc); },
    });
  }

  function clearResumeTimer() {
    if (resumeTimerRef.current) {
      clearTimeout(resumeTimerRef.current);
      resumeTimerRef.current = null;
    }
  }

  function pauseForAssistant(status = "Listening. Say Hey Sala or Salareen, then ask your question.") {
    clearResumeTimer();
    segRef.current = -1;
    Speech.stop();
    setPlaying(false);
    setAssistantOpen(true);
    setAssistantStatus(status);
    setAssistantAnswer("");
  }

  function resumeCourse(delayMs = 0) {
    if (!course) return;
    clearResumeTimer();
    stopVoiceRecognition();
    const resume = () => {
      answeringRef.current = false;
      setAssistantOpen(false);
      playFrom(course, seg);
      void startHandsFreeListening();
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

  function scheduleHandsFreeRestart() {
    if (!handsFreeRef.current || answeringRef.current) return;
    setTimeout(() => {
      if (handsFreeRef.current && !assistantOpen && !answeringRef.current) {
        void startHandsFreeListening();
      }
    }, 400);
  }

  async function startHandsFreeListening() {
    if (!handsFreeRef.current || answeringRef.current) return;
    expectWakeRef.current = false;
    const started = await startVoiceListening({
      locale,
      continuous: true,
      onSpeechStart: () => {
        if (playing && !assistantOpen) {
          pauseForAssistant(t("drive.listeningHandsFree", { engine: voiceEngine }));
        }
      },
      onResult: (text) => {
        setListening(false);
        setAssistantTranscript(text);
        void handleSpokenInput(text, false);
      },
      onError: (code) => {
        setListening(false);
        if (code === "permission_denied") {
          setAssistantStatus(t("drive.voicePermissionDenied", { engine: voiceEngine }));
        } else if (code !== "aborted" && code !== "no-speech") {
          scheduleHandsFreeRestart();
        }
      },
      onEnd: () => {
        setListening(false);
        scheduleHandsFreeRestart();
      },
    });
    if (started) setListening(true);
  }

  async function startVoiceRecognition(expectWakeWord = false) {
    expectWakeRef.current = expectWakeWord;
    pauseForAssistant(expectWakeWord
      ? t("drive.listeningWake", { engine: voiceEngine })
      : t("drive.listeningQuestion"));

    const started = await startVoiceListening({
      locale,
      continuous: false,
      onSpeechStart: () => {
        if (playing) pauseForAssistant(t("drive.listeningQuestion"));
      },
      onResult: (text) => {
        setListening(false);
        setAssistantTranscript(text);
        void handleSpokenInput(text, expectWakeRef.current);
      },
      onError: (code) => {
        setListening(false);
        if (code === "permission_denied") {
          setAssistantStatus(t("drive.voicePermissionDenied", { engine: voiceEngine }));
        } else if (code === "unavailable") {
          setAssistantStatus(t("drive.voiceUnavailable", { engine: voiceEngine }));
        } else {
          setAssistantStatus(t("drive.voiceError"));
        }
      },
      onEnd: () => setListening(false),
    });

    if (started) setListening(true);
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
    void runAssistantQuestion(command);
  }

  async function runAssistantQuestion(command: string) {
    if (!course) return;
    clearResumeTimer();
    stopVoiceRecognition();
    answeringRef.current = true;
    setAssistantTranscript(command);
    const lower = command.toLowerCase();
    if (/\b(pause|stop|hold)\b/.test(lower)) {
      Speech.stop();
      setPlaying(false);
      setAssistantAnswer("Paused. Say resume or wait — I will keep listening.");
      setAssistantStatus("Paused for you.");
      answeringRef.current = false;
      void startHandsFreeListening();
      return;
    }
    if (/\b(resume|continue|carry on|keep going)\b/.test(lower)) {
      setAssistantAnswer("Resuming the lesson.");
      answeringRef.current = false;
      resumeCourse(1000);
      return;
    }
    if (/\b(next|skip ahead)\b/.test(lower)) {
      setAssistantAnswer("Skipping to the next segment.");
      answeringRef.current = false;
      playFrom(course, Math.min(seg + 1, course.segments.length - 1));
      return;
    }
    if (/\b(previous|back|repeat)\b/.test(lower)) {
      setAssistantAnswer("Going back so you can hear that part again.");
      answeringRef.current = false;
      playFrom(course, Math.max(0, seg - 1));
      return;
    }

    setAssistantStatus(t("drive.searchingCourse"));
    Speech.stop();
    setPlaying(false);
    let answer = "";
    try {
      answer = await askCourseQuestion(course.id, command, seg, trainingLang);
    } catch { /* offline */ }
    if (!answer) {
      answer = answerFromCourse(course, seg, command);
    }
    setAssistantAnswer(answer);
    setAssistantStatus(t("drive.answeringResume", { seconds: RESUME_DELAY_MS / 1000 }));
    speakNatural(answer, {
      locale: trainingLang,
      voiceStyle: voiceStyleRef.current,
      onDone: () => {
        answeringRef.current = false;
        resumeCourse(RESUME_DELAY_MS);
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
  };

  if (!course) {
    return (
      <View style={styles.c}>
        <ActivityIndicator color={theme.colors.netflix} size="large" />
      </View>
    );
  }
  const pct = Math.round(((seg + 1) / course.segments.length) * 100);
  const [c1, c2] = categoryGradient(course.category);

  return (
    <ScrollView
      style={styles.c}
      contentContainerStyle={styles.scrollContent}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.topRow}>
        <AnimatedPressable onPress={() => { Speech.stop(); onBack(); }}>
          <View style={styles.backRow}>
            <Ionicons name="chevron-back" size={22} color={theme.colors.text} />
            <Text style={styles.back}>{t("drive.back")}</Text>
          </View>
        </AnimatedPressable>
        <AnimatedPressable onPress={() => void onToggleSave()} hitSlop={12}>
          <Ionicons
            name={saved ? "bookmark" : "bookmark-outline"}
            size={26}
            color={saved ? theme.colors.gold : theme.colors.muted}
          />
        </AnimatedPressable>
      </View>

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
        <Ionicons name="headset" size={48} color="rgba(255,255,255,0.9)" />
        <Text style={styles.heroTitle} numberOfLines={2}>{course.title}</Text>
      </LinearGradient>

      <GlassPanel style={styles.playerCard}>
        <Text style={styles.cat}>
          {course.category} · {course.duration_min} {t("meta.min")} · {t("meta.audio")}
        </Text>
        <Text style={styles.seg}>{course.segments[seg]?.heading}</Text>
        <Text style={styles.prog}>{seg + 1} / {course.segments.length} ({pct}%)</Text>
        <View style={styles.progressTrack}>
          <View style={[styles.progressBar, { width: `${pct}%` }]} />
        </View>
        <View style={styles.speedRow}>
          {[0.5, 1, 2, 3].map((r) => (
            <AnimatedPressable
              key={r}
              onPress={() => {
                setRate(r);
                if (course) {
                  Speech.stop();
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
          <AnimatedPressable style={styles.btn} onPress={() => playFrom(course, Math.max(0, seg - 1))}>
            <Ionicons name="play-skip-back" size={28} color="#fff" />
          </AnimatedPressable>
          {playing ? (
            <AnimatedPressable
              style={[styles.btn, styles.pause]}
              onPress={() => { Speech.stop(); setPlaying(false); }}
            >
              <Ionicons name="pause" size={32} color="#fff" />
            </AnimatedPressable>
          ) : (
            <AnimatedPressable style={[styles.btn, styles.play]} onPress={() => playFrom(course, seg)}>
              <Ionicons name="play" size={32} color="#fff" />
            </AnimatedPressable>
          )}
          <AnimatedPressable style={styles.btn} onPress={() => playFrom(course, seg + 1)}>
            <Ionicons name="play-skip-forward" size={28} color="#fff" />
          </AnimatedPressable>
        </View>
      </GlassPanel>

      <GlassPanel style={styles.assistantBar}>
        <View style={styles.listeningRow}>
          <Ionicons
            name={listening ? "radio" : "mic-off"}
            size={18}
            color={listening ? theme.colors.success : theme.colors.muted}
          />
          <Text style={styles.assistantWake}>
            {listening
              ? t("drive.handsFreeOn", { engine: voiceEngine })
              : t("drive.handsFreeOff", { engine: voiceEngine })}
          </Text>
        </View>
        <Text style={styles.assistantEngine}>{t("drive.assistantEngineHint")}</Text>
        <Text style={styles.assistantHint}>{t("drive.handsFreeHint")}</Text>
        <View style={styles.assistantActions}>
          <AnimatedPressable
            style={styles.assistantBtn}
            onPress={() => void startVoiceRecognition(false)}
          >
            <Ionicons name="mic" size={16} color="#001022" />
            <Text style={styles.assistantBtnText}>{t("drive.askNow")}</Text>
          </AnimatedPressable>
          <AnimatedPressable
            style={[styles.assistantBtn, styles.assistantBtnGhost]}
            onPress={() => pauseForAssistant(t("drive.pauseAskStatus"))}
          >
            <Text style={styles.assistantBtnGhostText}>{t("drive.pauseAsk")}</Text>
          </AnimatedPressable>
        </View>
      </GlassPanel>
      <Text style={styles.hint}>{t("drive.hint")}</Text>

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
    </ScrollView>
  );
}

function answerFromCourse(course: AudioCourse, seg: number, question: string): string {
  const lower = question.toLowerCase();
  const lessonMatch = lower.match(/\b(lesson|segment|chapter|part)\s*#?\s*(\d+)\b/);
  if (lessonMatch) {
    const idx = parseInt(lessonMatch[2], 10) - 1;
    if (idx >= 0 && idx < course.segments.length) {
      const s = course.segments[idx];
      const body = (s.text || "").replace(/\s+/g, " ").trim();
      const snippet = body.length > 420 ? `${body.slice(0, 420)}...` : body;
      return `Lesson ${idx + 1} is "${s.heading}". ${snippet}`;
    }
    return `This course has ${course.segments.length} segments. Lesson ${lessonMatch[2]} is not in range.`;
  }
  const words = lower.split(/[^a-z0-9]+/).filter((w) => w.length > 3);
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
  scrollContent: { padding: theme.spacing.screenX, paddingTop: 56, paddingBottom: 32 },
  topRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 16 },
  backRow: { flexDirection: "row", alignItems: "center", gap: 2 },
  back: { color: theme.colors.text, fontSize: 16, fontWeight: "600" },
  heroPoster: {
    height: 160, borderRadius: theme.radius.lg, overflow: "hidden",
    alignItems: "center", justifyContent: "center", marginBottom: 16,
    ...theme.shadow.hero,
  },
  drivingBadge: {
    position: "absolute", top: 12, right: 12, zIndex: 2,
    flexDirection: "row", alignItems: "center", gap: 6,
    backgroundColor: "rgba(229, 9, 20, 0.92)", paddingHorizontal: 10, paddingVertical: 5,
    borderRadius: theme.radius.pill,
  },
  drivingBadgeText: { color: "#fff", fontSize: 12, fontWeight: "800" },
  heroTitle: {
    position: "absolute", bottom: 14, left: 14, right: 14,
    color: "#fff", fontSize: 20, fontWeight: "800",
  },
  playerCard: { marginBottom: 14 },
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
  progressBar: { height: 6, backgroundColor: theme.colors.netflix },
  row: { flexDirection: "row", justifyContent: "center", gap: 18 },
  btn: {
    backgroundColor: "rgba(255,255,255,0.08)",
    width: 72, height: 72, borderRadius: 36,
    alignItems: "center", justifyContent: "center",
    borderWidth: 1, borderColor: theme.colors.border,
  },
  play: { backgroundColor: theme.colors.success, borderColor: theme.colors.success },
  pause: { backgroundColor: theme.colors.gold, borderColor: theme.colors.gold },
  assistantBar: { marginTop: 8 },
  listeningRow: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8 },
  assistantWake: { color: theme.colors.text, fontSize: 14, fontWeight: "800", textAlign: "center", flexShrink: 1 },
  assistantEngine: {
    color: theme.colors.muted, fontSize: 11, textAlign: "center", marginTop: 4, lineHeight: 15,
  },
  assistantHint: {
    color: theme.colors.accent, fontSize: 11, textAlign: "center", marginTop: 6, lineHeight: 15,
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
  transcript: { color: theme.colors.accent, marginTop: 12 },
  answer: { color: theme.colors.text, fontSize: 15, lineHeight: 21, marginTop: 10 },
  askInput: {
    backgroundColor: "rgba(255,255,255,0.06)", borderColor: theme.colors.border,
    borderRadius: theme.radius.md, borderWidth: 1, color: theme.colors.text,
    marginTop: 14, padding: 12,
  },
  modalActions: { marginTop: 14, gap: 10 },
});
