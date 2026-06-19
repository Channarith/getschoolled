import * as Speech from "expo-speech";
import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { getAudioCourse, type AudioCourse } from "../api";
import {
  bumpStreak, clearProgress, getMyList, getSettings,
  recordProgress, toggleMyList,
} from "../storage";
import { fireCompletionAlert } from "../notifications";

// Hands-free audio player: large controls, on-device TTS narration, auto-advance,
// progress persisted to AsyncStorage so Continue Listening works.
export default function DriveModeScreen({ courseId, onBack }: { courseId: string; onBack: () => void }) {
  const [course, setCourse] = useState<AudioCourse | null>(null);
  const [seg, setSeg] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [saved, setSaved] = useState(false);
  const segRef = useRef(0);

  useEffect(() => {
    getAudioCourse(courseId).then((c) => { setCourse(c); playFrom(c, 0); }).catch(() => {});
    void getMyList().then((ids) => setSaved(ids.includes(courseId)));
    return () => { Speech.stop(); };
  }, [courseId]);

  function playFrom(c: AudioCourse, i: number) {
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
        <Pressable onPress={() => { Speech.stop(); onBack(); }}><Text style={styles.back}>← Back</Text></Pressable>
        <Pressable onPress={() => void onToggleSave()} hitSlop={12}>
          <Text style={[styles.star, saved && styles.starOn]}>{saved ? "★" : "☆"}</Text>
        </Pressable>
      </View>
      <Text style={styles.cat}>{course.category} · {course.duration_min} min · audio</Text>
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
      <Text style={styles.hint}>Keep your eyes on the road — this plays hands-free.</Text>
    </View>
  );
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
  hint: { color: "#9aa6c2", textAlign: "center", marginTop: 28 },
});
