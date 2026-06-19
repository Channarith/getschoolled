import * as Speech from "expo-speech";
import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { getAudioCourse, type AudioCourse } from "../api";

// Hands-free audio player: large controls, on-device TTS narration, auto-advance.
export default function DriveModeScreen({ courseId, onBack }: { courseId: string; onBack: () => void }) {
  const [course, setCourse] = useState<AudioCourse | null>(null);
  const [seg, setSeg] = useState(0);
  const [playing, setPlaying] = useState(false);
  const segRef = useRef(0);

  useEffect(() => {
    getAudioCourse(courseId).then((c) => { setCourse(c); playFrom(c, 0); }).catch(() => {});
    return () => { Speech.stop(); };
  }, [courseId]);

  function playFrom(c: AudioCourse, i: number) {
    Speech.stop();
    if (i >= c.segments.length) { setPlaying(false); return; }
    segRef.current = i; setSeg(i); setPlaying(true);
    const s = c.segments[i];
    Speech.speak(`${s.heading}. ${s.text}`, {
      onDone: () => { if (segRef.current === i) playFrom(c, i + 1); },
    });
  }

  if (!course) return <View style={styles.c}><ActivityIndicator color="#0ea5e9" /></View>;
  const pct = Math.round(((seg + 1) / course.segments.length) * 100);

  return (
    <View style={styles.c}>
      <Pressable onPress={() => { Speech.stop(); onBack(); }}><Text style={styles.back}>← Back</Text></Pressable>
      <Text style={styles.cat}>{course.category} · {course.duration_min} min · audio</Text>
      <Text style={styles.title}>{course.title}</Text>
      <Text style={styles.seg}>▶ {course.segments[seg]?.heading}</Text>
      <Text style={styles.prog}>{seg + 1} / {course.segments.length}  ({pct}%)</Text>
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
  back: { color: "#0ea5e9", fontSize: 16, marginBottom: 16 },
  cat: { color: "#9aa6c2" },
  title: { color: "#e8ecf6", fontSize: 26, fontWeight: "800", marginVertical: 8 },
  seg: { color: "#e8ecf6", fontSize: 20, marginTop: 20 },
  prog: { color: "#9aa6c2", marginTop: 6, marginBottom: 28 },
  row: { flexDirection: "row", justifyContent: "center", gap: 18 },
  btn: { backgroundColor: "#1d2746", width: 84, height: 84, borderRadius: 42, alignItems: "center", justifyContent: "center" },
  play: { backgroundColor: "#16a34a" }, pause: { backgroundColor: "#f59e0b" },
  btnT: { color: "#fff", fontSize: 34 },
  hint: { color: "#9aa6c2", textAlign: "center", marginTop: 28 },
});
