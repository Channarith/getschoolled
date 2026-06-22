import * as Speech from "expo-speech";
import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator, Modal, Pressable, StyleSheet, Text, TextInput, View,
} from "react-native";

import { getAudioCourse, type AudioCourse } from "../api";
import {
  bumpStreak, clearProgress, getMyList, getSettings,
  recordProgress, toggleMyList,
} from "../storage";
import { fireCompletionAlert } from "../notifications";
import { useT } from "../i18n";

// Hands-free audio player: large controls, on-device TTS narration, auto-advance,
// progress persisted to AsyncStorage so Continue Listening works.
export default function DriveModeScreen({ courseId, onBack }: { courseId: string; onBack: () => void }) {
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
  const segRef = useRef(0);
  const resumeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    getAudioCourse(courseId, locale)
      .then((c) => { setCourse(c); playFrom(c, 0); })
      .catch(() => {});
    void getMyList().then((ids) => setSaved(ids.includes(courseId)));
    return () => {
      Speech.stop();
      stopVoiceRecognition();
      clearResumeTimer();
    };
  }, [courseId, locale]);

  function playFrom(c: AudioCourse, i: number) {
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
    Speech.speak(`${s.heading}. ${s.text}`, {
      onDone: () => { if (segRef.current === i) playFrom(c, i + 1); },
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
    const resume = () => {
      setAssistantOpen(false);
      playFrom(course, seg);
    };
    if (delayMs > 0) {
      setAssistantStatus(`Resuming in ${Math.round(delayMs / 1000)} seconds. Say or tap Pause to stay paused.`);
      resumeTimerRef.current = setTimeout(resume, delayMs);
    } else {
      resume();
    }
  }

  function stopVoiceRecognition() {
    try { recognitionRef.current?.stop?.(); } catch {}
    recognitionRef.current = null;
    setListening(false);
  }

  function startVoiceRecognition(expectWakeWord = true) {
    pauseForAssistant(expectWakeWord
      ? "Listening for Hey Sala or Salareen..."
      : "Listening for your question or command...");
    const root = globalThis as any;
    const SpeechRecognition = root.SpeechRecognition || root.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setAssistantStatus("Voice recognition is unavailable here. Type your question or use the controls.");
      return;
    }
    stopVoiceRecognition();
    const recognition = new SpeechRecognition();
    recognition.lang = locale || "en";
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.onresult = (event: any) => {
      const text = Array.from(event.results || [])
        .map((result: any) => result?.[0]?.transcript || "")
        .join(" ")
        .trim();
      setAssistantTranscript(text);
      void handleSpokenInput(text, expectWakeWord);
    };
    recognition.onerror = () => {
      setAssistantStatus("I could not hear that. Try again, or type your question.");
      setListening(false);
    };
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    setListening(true);
    recognition.start();
  }

  async function handleSpokenInput(raw: string, expectWakeWord: boolean) {
    stopVoiceRecognition();
    const text = raw.trim();
    if (!text) {
      setAssistantStatus("I did not catch that. Say Hey Sala, then ask again.");
      return;
    }
    const lower = text.toLowerCase();
    const hasWake = /\b(hey\s+sala|sala|salareen)\b/i.test(lower);
    if (expectWakeWord && !hasWake) {
      setAssistantStatus("Wake word not detected. Say Hey Sala or Salareen before your question.");
      return;
    }
    const cleaned = text
      .replace(/\bhey\s+sala\b/ig, "")
      .replace(/\bsalareen\b/ig, "")
      .replace(/\bsala\b/ig, "")
      .trim();
    if (!cleaned) {
      setAssistantStatus("I heard you. Ask a question, say pause, resume, next, or previous.");
      startVoiceRecognition(false);
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
      Speech.stop();
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
    const answer = answerFromCourse(course, seg, command);
    setAssistantAnswer(answer);
    setAssistantStatus("Answering your question. I will resume automatically unless you pause.");
    Speech.stop();
    Speech.speak(`${answer} Would you like to resume? Say resume, or I will continue shortly.`, {
      onDone: () => resumeCourse(6500),
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

  if (!course) return <View style={styles.c}><ActivityIndicator color="#0ea5e9" /></View>;
  const pct = Math.round(((seg + 1) / course.segments.length) * 100);

  return (
    <View style={styles.c}>
      <View style={styles.topRow}>
        <Pressable onPress={() => { Speech.stop(); onBack(); }}><Text style={styles.back}>{t("drive.back")}</Text></Pressable>
        <Pressable onPress={() => void onToggleSave()} hitSlop={12}>
          <Text style={[styles.star, saved && styles.starOn]}>{saved ? "★" : "☆"}</Text>
        </Pressable>
      </View>
      <Text style={styles.cat}>
        {course.category} · {course.duration_min} {t("meta.min")} · {t("meta.audio")}
      </Text>
      <Text style={styles.title}>{course.title}</Text>
      <Text style={styles.seg}>▶ {course.segments[seg]?.heading}</Text>
      <Text style={styles.prog}>{seg + 1} / {course.segments.length}  ({pct}%)</Text>
      <View style={styles.progressTrack}>
        <View style={[styles.progressBar, { width: `${pct}%` }]} />
      </View>
      <View style={styles.row}>
        <Pressable style={styles.btn} onPress={() => playFrom(course, Math.max(0, seg - 1))}><Text style={styles.btnT}>⏮</Text></Pressable>
        {playing
          ? <Pressable style={[styles.btn, styles.pause]} onPress={() => { Speech.stop(); setPlaying(false); }}><Text style={styles.btnT}>⏸</Text></Pressable>
          : <Pressable style={[styles.btn, styles.play]} onPress={() => playFrom(course, seg)}><Text style={styles.btnT}>▶</Text></Pressable>}
        <Pressable style={styles.btn} onPress={() => playFrom(course, seg + 1)}><Text style={styles.btnT}>⏭</Text></Pressable>
      </View>
      <View style={styles.assistantBar}>
        <Text style={styles.assistantWake}>Say “Hey Sala” or “Salareen”</Text>
        <View style={styles.assistantActions}>
          <Pressable style={styles.assistantBtn} onPress={() => startVoiceRecognition(true)}>
            <Text style={styles.assistantBtnText}>{listening ? "Listening..." : "🎙 Ask"}</Text>
          </Pressable>
          <Pressable style={styles.assistantBtn} onPress={() => pauseForAssistant("Paused. Ask a question or tap Resume.")}>
            <Text style={styles.assistantBtnText}>Pause + Ask</Text>
          </Pressable>
        </View>
      </View>
      <Text style={styles.hint}>{t("drive.hint")}</Text>
      <Modal
        animationType="slide"
        transparent
        visible={assistantOpen}
        onRequestClose={() => setAssistantOpen(false)}
      >
        <View style={styles.modalScrim}>
          <View style={styles.assistantCard}>
            <Text style={styles.assistantTitle}>Sala Drive Assistant</Text>
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
              placeholderTextColor="#7f8aaa"
              selectionColor="#e8ecf6"
              value={typedQuestion}
              onChangeText={setTypedQuestion}
              onSubmitEditing={submitTypedQuestion}
            />
            <View style={styles.modalActions}>
              <Pressable style={styles.modalBtn} onPress={() => startVoiceRecognition(false)}>
                <Text style={styles.modalBtnText}>{listening ? "Listening..." : "Mic"}</Text>
              </Pressable>
              <Pressable style={styles.modalBtn} onPress={submitTypedQuestion}>
                <Text style={styles.modalBtnText}>Ask</Text>
              </Pressable>
              <Pressable style={[styles.modalBtn, styles.resume]} onPress={() => resumeCourse()}>
                <Text style={styles.modalBtnText}>Resume</Text>
              </Pressable>
              <Pressable style={styles.modalBtn} onPress={() => { clearResumeTimer(); setAssistantOpen(false); }}>
                <Text style={styles.modalBtnText}>Stay paused</Text>
              </Pressable>
            </View>
          </View>
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
  c: { flex: 1, backgroundColor: "#0b1020", padding: 24, paddingTop: 56 },
  topRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 16 },
  back: { color: "#0ea5e9", fontSize: 16 },
  star: { color: "#5d6890", fontSize: 28, fontWeight: "800" },
  starOn: { color: "#fbbf24" },
  cat: { color: "#9aa6c2" },
  title: { color: "#e8ecf6", fontSize: 26, fontWeight: "800", marginVertical: 8 },
  seg: { color: "#e8ecf6", fontSize: 20, marginTop: 20 },
  prog: { color: "#9aa6c2", marginTop: 6, marginBottom: 8 },
  progressTrack: { height: 4, backgroundColor: "#23304f", borderRadius: 2, marginBottom: 22, overflow: "hidden" },
  progressBar: { height: 4, backgroundColor: "#0ea5e9" },
  row: { flexDirection: "row", justifyContent: "center", gap: 18 },
  btn: { backgroundColor: "#1d2746", width: 84, height: 84, borderRadius: 42, alignItems: "center", justifyContent: "center" },
  play: { backgroundColor: "#16a34a" }, pause: { backgroundColor: "#f59e0b" },
  btnT: { color: "#fff", fontSize: 34 },
  assistantBar: { backgroundColor: "#151c34", borderRadius: 16, marginTop: 22, padding: 14 },
  assistantWake: { color: "#e8ecf6", fontSize: 14, fontWeight: "800", textAlign: "center" },
  assistantActions: { flexDirection: "row", gap: 10, justifyContent: "center", marginTop: 10 },
  assistantBtn: { backgroundColor: "#0ea5e9", borderRadius: 999, paddingHorizontal: 16, paddingVertical: 9 },
  assistantBtnText: { color: "#001022", fontWeight: "900" },
  hint: { color: "#9aa6c2", textAlign: "center", marginTop: 16 },
  modalScrim: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(3,7,18,0.68)" },
  assistantCard: { backgroundColor: "#0b1020", borderTopLeftRadius: 24, borderTopRightRadius: 24,
                   borderColor: "#23304f", borderWidth: 1, padding: 18 },
  assistantTitle: { color: "#e8ecf6", fontSize: 22, fontWeight: "900" },
  assistantStatus: { color: "#9aa6c2", marginTop: 4 },
  transcript: { color: "#bae6fd", marginTop: 12 },
  answer: { color: "#e8ecf6", fontSize: 15, lineHeight: 21, marginTop: 10 },
  askInput: { backgroundColor: "#151c34", borderColor: "#23304f", borderRadius: 12,
              borderWidth: 1, color: "#e8ecf6", marginTop: 14, padding: 12 },
  modalActions: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 12 },
  modalBtn: { backgroundColor: "#1d2746", borderRadius: 999, paddingHorizontal: 14, paddingVertical: 9 },
  resume: { backgroundColor: "#16a34a" },
  modalBtnText: { color: "#fff", fontWeight: "800" },
});
