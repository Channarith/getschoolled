import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";

import {
  getLangCourse, getLearnLanguages, languagePractice, newLangExercise,
  pronounce, type LangCourse, type LangExercise, type LangInfo, type Pronounce,
} from "../api";
import AnimatedPressable from "../components/AnimatedPressable";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { useT } from "../i18n";
import { theme } from "../theme";

export default function LanguagesScreen({ onBack }: { onBack: () => void }) {
  const { t } = useT();
  const [langs, setLangs] = useState<LangInfo[]>([]);
  const [course, setCourse] = useState<LangCourse | null>(null);
  const [skill, setSkill] = useState("");
  const [ex, setEx] = useState<LangExercise | null>(null);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [done, setDone] = useState<{ correct: number; total: number; xp?: number } | null>(null);
  const [pron, setPron] = useState<Pronounce | null>(null);
  const [heard, setHeard] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    void getLearnLanguages()
      .then((r) => setLangs(r.languages))
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, []);

  const openCourse = useCallback(async (code: string) => {
    setError("");
    setEx(null);
    setDone(null);
    setPron(null);
    try {
      setCourse(await getLangCourse(code));
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  async function startSkill(s: string) {
    if (!course) return;
    setSkill(s);
    setEx(null);
    setDone(null);
    setPron(null);
    setAnswers({});
    try {
      setEx(await newLangExercise(course.code, s, s === "match" ? 4 : 5));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function finishExercise(correct: number, total: number) {
    if (!course) return;
    setDone({ correct, total });
    try {
      const r = await languagePractice(course.code, skill, correct, total);
      setDone({ correct, total, xp: r.xp });
    } catch { /* offline ok */ }
  }

  function gradeQuiz() {
    if (!ex?.items || !course) return;
    const correct = ex.items.filter((it) => answers[it.id] === it.answer_index).length;
    void finishExercise(correct, ex.items.length);
  }

  async function checkPronunciation() {
    if (!ex?.target) return;
    setError("");
    try {
      setPron(await pronounce(ex.target, heard.trim()));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <ScrollView style={styles.bg} contentContainerStyle={styles.scroll}>
      <PrimaryButton label={t("languages.back")} onPress={onBack} variant="ghost" />
      <Text style={styles.title}>{t("languages.title")}</Text>
      <Text style={styles.sub}>{t("languages.sub")}</Text>
      {loading ? <ActivityIndicator color={theme.colors.netflix} /> : null}
      {error ? <Text style={styles.err}>{error}</Text> : null}
      {!course ? (
        <View style={styles.grid}>
          {langs.map((l) => (
            <AnimatedPressable key={l.code} onPress={() => void openCourse(l.code)} style={styles.langChip}>
              <Text style={styles.flag}>{l.flag}</Text>
              <Text style={styles.langName}>{l.native}</Text>
            </AnimatedPressable>
          ))}
        </View>
      ) : (
        <>
          <Text style={styles.courseTitle}>{course.flag} {course.name}</Text>
          <Text style={styles.tip}>{course.grammar_tip}</Text>
          {!skill ? (
            <View style={styles.grid}>
              {course.skills.map((s) => (
                <PrimaryButton key={s.id} label={s.name} onPress={() => void startSkill(s.id)} variant="brand" />
              ))}
            </View>
          ) : null}
          {ex?.items ? (
            <GlassPanel style={styles.card}>
              {ex.items.map((it) => (
                <View key={it.id} style={{ gap: 6 }}>
                  <Text style={styles.prompt}>{it.prompt}</Text>
                  {it.options.map((opt, i) => (
                    <AnimatedPressable
                      key={opt}
                      onPress={() => setAnswers((a) => ({ ...a, [it.id]: i }))}
                      style={[styles.opt, answers[it.id] === i && styles.optOn]}
                    >
                      <Text style={styles.optText}>{opt}</Text>
                    </AnimatedPressable>
                  ))}
                </View>
              ))}
              <PrimaryButton label={t("languages.grade")} onPress={gradeQuiz} variant="netflix" />
            </GlassPanel>
          ) : null}
          {ex?.target ? (
            <GlassPanel style={styles.card}>
              <Text style={styles.prompt}>{ex.target}</Text>
              {ex.roman ? <Text style={styles.meta}>{ex.roman}</Text> : null}
              <TextInput style={styles.input} value={heard} onChangeText={setHeard}
                placeholder={t("languages.heard")} placeholderTextColor={theme.colors.muted} />
              <PrimaryButton label={t("languages.check")} onPress={() => void checkPronunciation()} variant="brand" />
              {pron ? (
                <Text style={styles.meta}>{pron.feedback} ({pron.score}%)</Text>
              ) : null}
            </GlassPanel>
          ) : null}
          {done ? (
            <GlassPanel>
              <Text style={styles.done}>{t("languages.done", { correct: done.correct, total: done.total, xp: done.xp ?? 0 })}</Text>
            </GlassPanel>
          ) : null}
          <PrimaryButton label={t("languages.pickLang")} onPress={() => { setCourse(null); setSkill(""); setEx(null); }} variant="ghost" />
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  bg: { flex: 1 },
  scroll: { paddingHorizontal: theme.spacing.screenX, paddingTop: 56, paddingBottom: 32, gap: 10 },
  title: { color: theme.colors.text, fontSize: 26, fontWeight: "800" },
  sub: { color: theme.colors.muted, fontSize: 14, lineHeight: 20 },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  langChip: {
    width: "30%", minWidth: 100, alignItems: "center", padding: 12,
    borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.colors.border,
    backgroundColor: "rgba(255,255,255,0.04)",
  },
  flag: { fontSize: 28 },
  langName: { color: theme.colors.text, fontSize: 12, fontWeight: "700", marginTop: 4, textAlign: "center" },
  courseTitle: { color: theme.colors.text, fontSize: 20, fontWeight: "800" },
  tip: { color: theme.colors.muted, fontSize: 13, lineHeight: 18 },
  card: { gap: 10 },
  prompt: { color: theme.colors.text, fontSize: 15, fontWeight: "700" },
  opt: {
    borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.colors.border, padding: 10,
  },
  optOn: { borderColor: theme.colors.accent, backgroundColor: "rgba(110,168,254,0.12)" },
  optText: { color: theme.colors.text, fontSize: 14 },
  input: {
    borderWidth: 1, borderColor: theme.colors.border, borderRadius: 10,
    padding: 12, color: theme.colors.text, backgroundColor: "rgba(0,0,0,0.2)",
  },
  meta: { color: theme.colors.muted, fontSize: 13 },
  done: { color: theme.colors.accent, fontWeight: "700" },
  err: { color: theme.colors.netflix, fontSize: 13 },
});
