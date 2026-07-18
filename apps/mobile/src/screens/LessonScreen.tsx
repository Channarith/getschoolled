import * as Speech from "expo-speech";
import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";

import {
  advanceLessonSession, askLessonSession, directorLxTick, enrollCourse,
  getPostClassSurvey, getPulseSurvey, getQuiz, getRewards, gradeQuiz,
  reengageLessonSession, setEnrollmentStatus, startLessonSession,
  submitPostClassSurvey, submitPulseSurvey,
  type LessonAnswer, type LessonSessionView, type LessonSlide,
  type QuizGrade, type QuizItemView, type SurveyTemplate,
} from "../api";
import AnimatedPressable from "../components/AnimatedPressable";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import SurveySheet from "../components/SurveySheet";
import { useInterstitial } from "../ads/interstitial";
import { useAuth } from "../auth/AuthContext";
import { useT } from "../i18n";
import { getSettings } from "../storage";
import { theme } from "../theme";
import { speakNatural } from "../tts";
import { buildNarrationSpeakOptions } from "../narrationTts";

type Props = {
  lessonId: string;
  title: string;
  preview?: string;
  classType?: "solo" | "group";
  onBack: () => void;
};

type FinishState = {
  kind: "earned" | "complete" | "guest";
  earned?: number;
  balance?: number;
};

export default function LessonScreen({
  lessonId, title, preview, classType = "group", onBack,
}: Props) {
  const { t, locale } = useT();
  const { account } = useAuth();
  const [view, setView] = useState<LessonSessionView | null>(null);
  const [slide, setSlide] = useState<LessonSlide | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [advancing, setAdvancing] = useState(false);
  const [atEnd, setAtEnd] = useState(false);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState<LessonAnswer | null>(null);
  const [narrating, setNarrating] = useState(false);
  const [lxHint, setLxHint] = useState("");
  const [quiz, setQuiz] = useState<QuizItemView[] | null>(null);
  const [quizIdx, setQuizIdx] = useState(0);
  const [quizPick, setQuizPick] = useState<number | null>(null);
  const [quizGrade, setQuizGrade] = useState<QuizGrade | null>(null);
  const [finish, setFinish] = useState<FinishState | null>(null);
  const [surveyTpl, setSurveyTpl] = useState<SurveyTemplate | null>(null);
  const [surveyBusy, setSurveyBusy] = useState(false);
  const slideRef = useRef<LessonSlide | null>(null);
  const studentIdRef = useRef("guest");
  const interstitial = useInterstitial(account?.tier);
  const advanceCountRef = useRef(0);
  const MIDROLL_EVERY_ADVANCES = 4;

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      setError("");
      try {
        const settings = await getSettings();
        studentIdRef.current = settings.studentId;
        const v = await startLessonSession(lessonId, settings.studentId, classType);
        if (!alive) return;
        setView(v);
        setSlide(v.slide);
        slideRef.current = v.slide;
      } catch (e) {
        if (!alive) return;
        setError((e as Error).message);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
      Speech.stop();
    };
  }, [lessonId, classType]);

  function stopNarration() {
    Speech.stop();
    setNarrating(false);
  }

  function narrate() {
    const s = slideRef.current;
    if (!s) return;
    Speech.stop();
    const text = s.narration || s.body || s.title;
    if (!text) return;
    setNarrating(true);
    void buildNarrationSpeakOptions(locale).then((base) => {
      speakNatural(text, {
        ...base,
        onDone: () => setNarrating(false),
        onStopped: () => setNarrating(false),
        onError: () => setNarrating(false),
      });
    });
  }

  async function tickLx(s: LessonSlide) {
    if (!view) return;
    try {
      const r = await directorLxTick({
        session_id: view.session.session_id,
        student_id: studentIdRef.current,
        slide_index: s.index,
        class_type: classType,
      });
      const hint = r.wellness_nudge || r.pacing || r.strategy || "";
      if (hint) setLxHint(hint);
    } catch { /* optional */ }
  }

  async function maybePulse(s: LessonSlide) {
    if (!view || s.index % 3 !== 2) return;
    try {
      const res = await getPulseSurvey(view.lesson.lesson_id, account?.tier);
      if (res.enabled && res.template) setSurveyTpl(res.template);
    } catch { /* optional */ }
  }

  async function next() {
    if (!view) return;
    stopNarration();
    // Mid-lesson interstitial for ad-supported tiers (best-effort; proceeds if
    // no ad is loaded). show() presents the full-screen AdMob ad on iOS/Android.
    advanceCountRef.current += 1;
    if (advanceCountRef.current % MIDROLL_EVERY_ADVANCES === 0) {
      interstitial.show();
    }
    setAdvancing(true);
    setError("");
    try {
      const s = await advanceLessonSession(view.session.session_id);
      const prevIdx = slideRef.current?.index ?? -1;
      if (s.index <= prevIdx) setAtEnd(true);
      setSlide(s);
      slideRef.current = s;
      void tickLx(s);
      void maybePulse(s);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAdvancing(false);
    }
  }

  async function onReengage() {
    if (!view) return;
    setError("");
    try {
      const r = await reengageLessonSession(view.session.session_id);
      void buildNarrationSpeakOptions(locale).then((base) => {
        speakNatural(r.text, base);
      });
      if (r.prompt) setQuestion(r.prompt);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function onQuiz() {
    if (!view) return;
    setError("");
    try {
      const passages = view.lesson.slides.map((sl) => `${sl.title}: ${sl.body}`);
      const res = await getQuiz({
        topic: view.lesson.lesson_id,
        passages,
        studentId: studentIdRef.current,
        classType,
        maxItems: 3,
      });
      setQuiz(res.items);
      setQuizIdx(0);
      setQuizPick(null);
      setQuizGrade(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function onQuizAnswer(idx: number) {
    if (!view || !quiz || quizGrade) return;
    setQuizPick(idx);
    try {
      const g = await gradeQuiz({
        item: quiz[quizIdx],
        chosenIndex: idx,
        studentId: studentIdRef.current,
        topic: view.lesson.lesson_id,
      });
      setQuizGrade(g);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function onQuizNext() {
    if (!quiz) return;
    if (quizIdx + 1 < quiz.length) {
      setQuizIdx(quizIdx + 1);
      setQuizPick(null);
      setQuizGrade(null);
    } else {
      void onQuiz();
    }
  }

  async function awardCompletion() {
    if (!view) return;
    if (!account) {
      setFinish({ kind: "guest" });
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
          : { kind: "complete", balance: res.points_balance },
      );
    } catch {
      setFinish({ kind: "complete" });
    }
  }

  async function onFinish() {
    if (!view) return;
    await awardCompletion();
    try {
      const res = await getPostClassSurvey(view.lesson.lesson_id, account?.tier);
      if (res.enabled && res.template) {
        setSurveyTpl(res.template);
        return;
      }
    } catch { /* optional */ }
    onBack();
  }

  async function onSurveySubmit(answers: Record<string, string | number | boolean>) {
    if (!view) return;
    setSurveyBusy(true);
    try {
      const overall = Number(answers.overall ?? answers.rating ?? 0);
      if (overall) {
        await submitPostClassSurvey({
          course_id: lessonId,
          class_type: classType,
          overall,
          clarity: answers.clarity != null ? Number(answers.clarity) : null,
          pace: (answers.pace as string) ?? null,
          would_recommend: answers.would_recommend != null ? Boolean(answers.would_recommend) : null,
          suggestion: String(answers.suggestion ?? ""),
          student_id: studentIdRef.current,
        });
      } else {
        const goingWell = Number(answers.going_well ?? 0);
        if (goingWell) {
          await submitPulseSurvey({
            course_id: lessonId,
            going_well: goingWell,
            pace: String(answers.pace ?? "ok"),
            class_type: classType,
            student_id: studentIdRef.current,
            slide_index: slide?.index ?? 0,
          });
        }
      }
      setSurveyTpl(null);
      if (finish) onBack();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSurveyBusy(false);
    }
  }

  async function ask() {
    const text = question.trim();
    if (!text || !view) return;
    setAsking(true);
    setAnswer(null);
    setError("");
    try {
      const a = await askLessonSession(view.session.session_id, text, locale);
      setAnswer(a);
      setQuestion("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAsking(false);
    }
  }

  const total = view?.lesson.slides.length ?? 0;
  const idx = slide?.index ?? 0;

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <PrimaryButton label={t("lesson.back")} onPress={() => { stopNarration(); onBack(); }} variant="ghost" />
        <View style={styles.headerText}>
          <Text style={styles.title} numberOfLines={1}>{view?.lesson.title || title}</Text>
          <Text style={styles.classBadge}>
            {classType === "solo" ? t("liveClass.soloBadge") : t("liveClass.groupBadge")}
          </Text>
        </View>
      </View>

      {loading ? (
        <ActivityIndicator color={theme.colors.accent} style={{ marginTop: 24 }} />
      ) : error && !slide ? (
        <ScrollView contentContainerStyle={styles.body}>
          <GlassPanel style={styles.card}>
            <Text style={styles.slideTitle}>{title}</Text>
            {preview ? <Text style={styles.slideBody}>{preview}</Text> : null}
            <Text style={styles.meta}>{t("lesson.noSession")}</Text>
          </GlassPanel>
        </ScrollView>
      ) : (
        <ScrollView contentContainerStyle={styles.body} showsVerticalScrollIndicator={false}>
          {error ? <Text style={styles.error}>{error}</Text> : null}
          {lxHint ? <Text style={styles.lx}>{lxHint}</Text> : null}
          {finish ? (
            <GlassPanel style={styles.card}>
              {finish.kind === "earned" ? (
                <Text style={styles.finishText}>{t("lesson.earned", { n: finish.earned ?? 0, balance: finish.balance ?? 0 })}</Text>
              ) : finish.kind === "guest" ? (
                <Text style={styles.finishText}>{t("lesson.guestFinish")}</Text>
              ) : (
                <Text style={styles.finishText}>{t("lesson.complete")}</Text>
              )}
            </GlassPanel>
          ) : null}

          {total > 0 ? (
            <Text style={styles.progress}>
              {t("lesson.slide")} {Math.min(idx + 1, total)}/{total}
            </Text>
          ) : null}

          {slide ? (
            <GlassPanel style={styles.card}>
              <Text style={styles.slideTitle}>{slide.title}</Text>
              <Text style={styles.slideBody}>{slide.body}</Text>
              <View style={styles.slideActions}>
                <PrimaryButton
                  label={narrating ? t("lesson.stopNarration") : t("lesson.narrate")}
                  onPress={() => (narrating ? stopNarration() : narrate())}
                  variant="ghost"
                />
                <PrimaryButton label={t("lesson.reengage")} onPress={() => void onReengage()} variant="ghost" />
                <PrimaryButton label={t("lesson.quiz")} onPress={() => void onQuiz()} variant="ghost" />
                {!atEnd ? (
                  <PrimaryButton
                    label={t("lesson.next")}
                    onPress={() => void next()}
                    loading={advancing}
                    disabled={advancing}
                    variant="netflix"
                  />
                ) : (
                  <PrimaryButton label={t("lesson.finish")} onPress={() => void onFinish()} variant="netflix" />
                )}
              </View>
            </GlassPanel>
          ) : null}

          {quiz && quiz[quizIdx] ? (
            <GlassPanel style={styles.card}>
              <Text style={styles.cardTitle}>{t("lesson.quizTitle")}</Text>
              <Text style={styles.slideBody}>{quiz[quizIdx].prompt}</Text>
              {quiz[quizIdx].options.map((opt, i) => (
                <AnimatedPressable
                  key={opt}
                  onPress={() => void onQuizAnswer(i)}
                  style={[styles.quizOpt, quizPick === i && styles.quizOptOn]}
                  disabled={quizGrade != null}
                >
                  <Text style={styles.quizOptText}>{opt}</Text>
                </AnimatedPressable>
              ))}
              {quizGrade ? (
                <>
                  <Text style={styles.meta}>
                    {quizGrade.correct ? t("lesson.correct") : t("lesson.incorrect")}
                    {quizGrade.explanation ? ` — ${quizGrade.explanation}` : ""}
                  </Text>
                  <PrimaryButton label={t("lesson.quizNext")} onPress={onQuizNext} variant="brand" />
                </>
              ) : null}
            </GlassPanel>
          ) : null}

          <GlassPanel style={styles.card}>
            <Text style={styles.cardTitle}>{t("lesson.askTitle")}</Text>
            <TextInput
              style={styles.input}
              placeholder={t("lesson.askPlaceholder")}
              placeholderTextColor={theme.colors.muted}
              value={question}
              onChangeText={setQuestion}
              multiline
            />
            <PrimaryButton
              label={t("lesson.ask")}
              onPress={() => void ask()}
              loading={asking}
              disabled={asking || !question.trim()}
              variant="brand"
            />
            {answer ? (
              <View style={styles.answerBox}>
                <Text style={styles.answerText}>{answer.text}</Text>
                {answer.citations.length ? (
                  <Text style={styles.meta}>
                    {t("lesson.sources")}: {answer.citations.join(" · ")}
                  </Text>
                ) : null}
              </View>
            ) : null}
          </GlassPanel>
        </ScrollView>
      )}

      <SurveySheet
        visible={Boolean(surveyTpl)}
        template={surveyTpl}
        busy={surveyBusy}
        onSubmit={(a) => void onSurveySubmit(a)}
        onClose={() => { setSurveyTpl(null); if (finish) onBack(); }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, paddingHorizontal: 16, paddingTop: 56, gap: 8 },
  header: { flexDirection: "row", alignItems: "center", gap: 8 },
  headerText: { flex: 1, gap: 2 },
  title: { color: theme.colors.text, fontSize: 18, fontWeight: "700" },
  classBadge: {
    color: theme.colors.accent,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 0.4,
  },
  body: { gap: 12, paddingBottom: 32 },
  progress: { color: theme.colors.muted, fontSize: 12, fontWeight: "700" },
  lx: { color: theme.colors.accent, fontSize: 12, fontStyle: "italic" },
  card: { gap: 10 },
  cardTitle: { color: theme.colors.text, fontSize: 16, fontWeight: "700" },
  slideTitle: { color: theme.colors.text, fontSize: 19, fontWeight: "800", lineHeight: 25 },
  slideBody: { color: theme.colors.text, fontSize: 15, lineHeight: 23 },
  slideActions: { flexDirection: "row", flexWrap: "wrap", gap: 8, alignItems: "center", marginTop: 4 },
  quizOpt: {
    borderRadius: theme.radius.md, borderWidth: 1, borderColor: theme.colors.border, padding: 12,
  },
  quizOptOn: { borderColor: theme.colors.accent, backgroundColor: "rgba(110,168,254,0.12)" },
  quizOptText: { color: theme.colors.text, fontSize: 14 },
  finishText: { color: theme.colors.accent, fontSize: 16, fontWeight: "800" },
  input: {
    borderWidth: 1, borderColor: theme.colors.border, borderRadius: 10,
    padding: 12, color: theme.colors.text, backgroundColor: "rgba(0,0,0,0.2)",
    minHeight: 44, textAlignVertical: "top",
  },
  answerBox: { gap: 6, marginTop: 4, padding: 10, borderRadius: 10, backgroundColor: "rgba(110,168,254,0.12)" },
  answerText: { color: theme.colors.text, fontSize: 14, lineHeight: 21 },
  meta: { color: theme.colors.muted, fontSize: 13, lineHeight: 18 },
  error: { color: "#f87171", fontSize: 13 },
});
