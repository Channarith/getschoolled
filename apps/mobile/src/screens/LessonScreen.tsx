import * as Speech from "expo-speech";
import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";

import {
  advanceLessonSession, askLessonSession, directorLxTick, enrollCourse,
  getAssessmentPolicy, getPostClassSurvey, getPulseSurvey, getQuiz, getRewards, gradeQuiz,
  listStudents, reengageLessonSession, recordAssessmentAttempt, recordAssessmentPass,
  setEnrollmentStatus, startAssessmentCheckpoint, startLessonSession,
  submitPostClassSurvey, submitPulseSurvey,
  type AssessmentCheckpointSpec, type AssessmentRun, type AssessmentSubmitResult,
  type LessonAnswer, type LessonSessionView, type LessonSlide,
  type QuizGrade, type QuizItemView, type StudentProfile, type SurveyTemplate,
} from "../api";
import {
  canAwardCourseCompletion,
  findDueFormativeCheckpoint,
  findDueSummativeCheckpoint,
  shouldOpenSummativeOnAdvance,
} from "../assessmentFlow";
import AnimatedPressable from "../components/AnimatedPressable";
import AssessmentCheckpointCard from "../components/AssessmentCheckpointCard";
import CameraLightingScreener from "../components/CameraLightingScreener";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import SurveySheet from "../components/SurveySheet";
import { useInterstitial } from "../ads/interstitial";
import { useAuth } from "../auth/AuthContext";
import { useAndroidBackTo } from "../hooks/useAndroidBack";
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
  useAndroidBackTo(() => { Speech.stop(); onBack(); });
  const { account } = useAuth();
  const [view, setView] = useState<LessonSessionView | null>(null);
  const [slide, setSlide] = useState<LessonSlide | null>(null);
  const [loading, setLoading] = useState(false);
  const [lightingReady, setLightingReady] = useState(false);
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
  const [studentProfile, setStudentProfile] = useState<StudentProfile | null>(null);
  const [assessmentPolicy, setAssessmentPolicy] = useState<AssessmentCheckpointSpec[]>([]);
  const [assessmentRun, setAssessmentRun] = useState<AssessmentRun | null>(null);
  const [assessmentResult, setAssessmentResult] = useState<AssessmentSubmitResult | null>(null);
  const [passDecisionToken, setPassDecisionToken] = useState<string | null>(null);
  const slideRef = useRef<LessonSlide | null>(null);
  const studentIdRef = useRef("guest");
  const completedCheckpointsRef = useRef<Set<string>>(new Set());
  const assessmentStartingRef = useRef(false);
  const finishingRef = useRef(false);
  const submittingRef = useRef(false);
  const quizSubmittingRef = useRef(false);
  const mountedRef = useRef(true);
  const interstitial = useInterstitial(account?.tier);
  const advanceCountRef = useRef(0);
  const MIDROLL_EVERY_ADVANCES = 4;

  useEffect(() => {
    if (!lightingReady) return;
    let alive = true;
    (async () => {
      setLoading(true);
      setError("");
      try {
        const settings = await getSettings();
        studentIdRef.current = settings.studentId;
        if (account) {
          try {
            const listed = await listStudents();
            const first = listed.students[0] ?? null;
            if (first) {
              studentIdRef.current = first.id;
              if (alive) setStudentProfile(first);
            }
          } catch { /* optional */ }
        }
        const v = await startLessonSession(lessonId, studentIdRef.current, classType);
        if (!alive) return;
        setView(v);
        setSlide(v.slide);
        slideRef.current = v.slide;
        completedCheckpointsRef.current = new Set();
        setAssessmentRun(null);
        setAssessmentResult(null);
        setPassDecisionToken(null);
        try {
          const policy = await getAssessmentPolicy(v.session.session_id);
          if (alive) setAssessmentPolicy(policy.checkpoints);
        } catch {
          if (alive) setAssessmentPolicy([]);
        }
      } catch (e) {
        if (!alive) return;
        setError((e as Error).message);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
      mountedRef.current = false;
      Speech.stop();
    };
  }, [lessonId, classType, account, lightingReady]);

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
        onDone: () => { if (mountedRef.current) setNarrating(false); },
        onStopped: () => { if (mountedRef.current) setNarrating(false); },
        onError: () => { if (mountedRef.current) setNarrating(false); },
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

  async function openCheckpoint(cp: AssessmentCheckpointSpec) {
    if (!view || assessmentStartingRef.current || assessmentRun) return;
    assessmentStartingRef.current = true;
    stopNarration();
    setError("");
    try {
      const acc = studentProfile?.accessibility || {};
      const run = await startAssessmentCheckpoint({
        studentId: studentIdRef.current,
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
      completedCheckpointsRef.current = new Set(completedCheckpointsRef.current).add(cp.checkpoint_id);
      setError((e as Error).message);
    } finally {
      assessmentStartingRef.current = false;
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

  async function awardVerifiedPass(token: string) {
    if (!view) return;
    if (!account) {
      setFinish({ kind: "guest" });
      return;
    }
    try {
      await enrollCourse(lessonId, view.lesson.title, "enrolled");
      const before = await getRewards().then((r) => r.balance).catch(() => 0);
      const res = await recordAssessmentPass(studentIdRef.current, token);
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

  async function onAssessmentSubmitted(result: AssessmentSubmitResult) {
    if (submittingRef.current) return;
    submittingRef.current = true;
    try {
      const checkpointId = result.attempt.checkpoint_id;
      if (result.attempt.passed || result.attempt.stage === "formative") {
        completedCheckpointsRef.current = new Set(completedCheckpointsRef.current).add(checkpointId);
      }
      setAssessmentResult(result);
      if (result.attempt_result_token && account) {
        recordAssessmentAttempt(studentIdRef.current, result.attempt_result_token).catch(() => {});
      }
      if (result.pass_decision_token) setPassDecisionToken(result.pass_decision_token);
      if (result.attempt.stage === "summative" && result.course_decision?.passed && result.pass_decision_token) {
        completedCheckpointsRef.current = new Set(completedCheckpointsRef.current).add(checkpointId);
        await awardVerifiedPass(result.pass_decision_token);
        try {
          const surveyRes = await getPostClassSurvey(view?.lesson.lesson_id, account?.tier);
          if (surveyRes.enabled && surveyRes.template) setSurveyTpl(surveyRes.template);
        } catch { /* optional */ }
      }
      setAssessmentRun(null);
    } finally {
      submittingRef.current = false;
    }
  }

  async function next() {
    if (!view || assessmentRun) return;
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
      const openFinal = shouldOpenSummativeOnAdvance(
        s.index, view.lesson.slides.length,
      );
      if (await maybeOpenDueCheckpoint(s.index, openFinal)) return;
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
      if (r.prompt && mountedRef.current) setQuestion(r.prompt);
    } catch (e) {
      if (mountedRef.current) setError((e as Error).message);
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
    if (quizSubmittingRef.current) return;
    quizSubmittingRef.current = true;
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
    } finally {
      quizSubmittingRef.current = false;
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
    if (passDecisionToken) {
      await awardVerifiedPass(passDecisionToken);
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
    if (finishingRef.current) return;
    finishingRef.current = true;
    try {
      if (!view || assessmentRun) { return; }
      const idx = slide?.index ?? view.lesson.slides.length - 1;
      if (await maybeOpenDueCheckpoint(idx, true)) return;
      // Mobile professional courses: prefer verified pass when policy has a summative.
      const hasSummative = assessmentPolicy.some((cp) => cp.stage === "summative");
      if (
        hasSummative
        && !canAwardCourseCompletion({
          requireVerifiedPass: true,
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
        const finalCp = assessmentPolicy.find((cp) => cp.stage === "summative");
        if (finalCp) {
          completedCheckpointsRef.current = new Set(
            [...completedCheckpointsRef.current].filter((id) => id !== finalCp.checkpoint_id),
          );
          await openCheckpoint(finalCp as AssessmentCheckpointSpec);
          return;
        }
        setError("Pass the end-of-course assessment to finish this course.");
        return;
      }
      if (passDecisionToken && account) {
        await awardVerifiedPass(passDecisionToken);
      } else {
        await awardCompletion();
      }
      try {
        const res = await getPostClassSurvey(view.lesson.lesson_id, account?.tier);
        if (res.enabled && res.template) {
          setSurveyTpl(res.template);
          return;
        }
      } catch { /* optional */ }
      onBack();
    } finally {
      finishingRef.current = false;
    }
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

      {!lightingReady ? (
        <ScrollView contentContainerStyle={styles.body}>
          <CameraLightingScreener onReady={() => setLightingReady(true)} />
        </ScrollView>
      ) : loading ? (
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

          {assessmentRun ? (
            <AssessmentCheckpointCard
              run={assessmentRun}
              busy={advancing}
              onError={setError}
              onSubmitted={(result) => { void onAssessmentSubmitted(result); }}
              onDismiss={() => {
                if (assessmentRun) {
                  completedCheckpointsRef.current = new Set(completedCheckpointsRef.current)
                    .add(assessmentRun.checkpoint.checkpoint_id);
                }
                setAssessmentRun(null);
              }}
            />
          ) : null}

          {assessmentResult && !assessmentRun ? (
            <GlassPanel style={styles.card}>
              <Text style={styles.cardTitle}>
                {assessmentResult.attempt.passed ? "Checkpoint passed" : "Checkpoint not yet passed"}
                {" — "}
                {Math.round(assessmentResult.attempt.score * 100)}%
              </Text>
              {assessmentResult.attempt.stage === "summative" && !assessmentResult.course_decision?.passed ? (
                <PrimaryButton
                  label="Retry assessment"
                  onPress={() => {
                    setAssessmentResult(null);
                    const summative = findDueSummativeCheckpoint(
                      assessmentPolicy, slide?.index ?? 0, completedCheckpointsRef.current,
                    );
                    if (summative) void openCheckpoint(summative);
                  }}
                  variant="brand"
                />
              ) : (
                <PrimaryButton
                  label="Continue"
                  onPress={() => setAssessmentResult(null)}
                  variant="ghost"
                />
              )}
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
