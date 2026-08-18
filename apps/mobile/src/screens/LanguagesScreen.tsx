import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator, Linking, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";

import {
  explainLangWord, getLangCourse, getLearnLanguages, languagePractice,
  newLangExercise, pronounce, scoreMusicVideoTranslation,
  type LangCourse, type LangExercise, type LangInfo,
  type LangWordExplanation, type MusicVideoScore, type Pronounce,
} from "../api";
import AnimatedPressable from "../components/AnimatedPressable";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { useVoicePauseSubmitMs } from "../featureFlags";
import { useAndroidBackTo } from "../hooks/useAndroidBack";
import { useT } from "../i18n";
import { speakNatural, stopSpeech } from "../tts";
import { startVoiceListening, stopVoiceListening } from "../voiceAssistant";
import { theme } from "../theme";

export default function LanguagesScreen({ onBack }: { onBack: () => void }) {
  const { t } = useT();
  const pauseSubmitMs = useVoicePauseSubmitMs();
  useAndroidBackTo(onBack);
  const [langs, setLangs] = useState<LangInfo[]>([]);
  const [course, setCourse] = useState<LangCourse | null>(null);
  const [skill, setSkill] = useState("");
  const [ex, setEx] = useState<LangExercise | null>(null);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [done, setDone] = useState<{ correct: number; total: number; xp?: number } | null>(null);
  const [pron, setPron] = useState<Pronounce | null>(null);
  const [heard, setHeard] = useState("");
  const [listening, setListening] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [verseIndex, setVerseIndex] = useState(0);
  const [mediaSegmentIndex, setMediaSegmentIndex] = useState(0);
  const [mediaPlaying, setMediaPlaying] = useState(false);
  const [mediaAnswer, setMediaAnswer] = useState("");
  const [mediaResults, setMediaResults] = useState<Record<string, boolean>>({});
  const [mvIndex, setMvIndex] = useState(0);
  const [mvDraft, setMvDraft] = useState("");
  const [mvScore, setMvScore] = useState<MusicVideoScore | null>(null);
  const [mvResults, setMvResults] = useState<Record<string, boolean>>({});
  const [mvScoring, setMvScoring] = useState(false);
  const mediaTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [storyPageIndex, setStoryPageIndex] = useState(0);
  const [wordHelp, setWordHelp] = useState<LangWordExplanation | null>(null);
  const [wordHelpLoading, setWordHelpLoading] = useState(false);
  // Guards callbacks after unmount so stale STT/TTS closures don't update state.
  const mountedRef = useRef(true);
  // Latest passing target/course for the STT result callback (avoids stale closure).
  const targetRef = useRef<string>("");
  const codeRef = useRef<string>("");
  targetRef.current = ex?.target ?? "";
  codeRef.current = course?.code ?? "";

  useEffect(() => {
    void getLearnLanguages()
      .then((r) => setLangs(r.languages))
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, []);

  // Stop mic + narration when leaving the screen; mark unmounted so stale
  // voice callbacks (onResult/onEnd/onError) don't fire into unmounted state.
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      stopVoiceListening();
      stopSpeech();
      if (mediaTimerRef.current) clearTimeout(mediaTimerRef.current);
    };
  }, []);

  const openCourseGenRef = useRef(0);
  const openCourse = useCallback(async (code: string) => {
    setError("");
    setEx(null);
    setDone(null);
    setPron(null);
    // Generation guard: tapping two languages quickly must not let the slower
    // response overwrite the newer course.
    const gen = ++openCourseGenRef.current;
    try {
      const c = await getLangCourse(code);
      if (gen === openCourseGenRef.current) setCourse(c);
    } catch (e) {
      if (gen === openCourseGenRef.current) setError((e as Error).message);
    }
  }, []);

  async function startSkill(s: string) {
    if (!course) return;
    setSkill(s);
    setEx(null);
    setDone(null);
    setPron(null);
    setAnswers({});
    setVerseIndex(0);
    setMediaSegmentIndex(0);
    setMediaPlaying(false);
    setMediaAnswer("");
    setMediaResults({});
    setStoryPageIndex(0);
    setWordHelp(null);
    setMvIndex(0);
    setMvDraft("");
    setMvScore(null);
    setMvResults({});
    setMvScoring(false);
    const n = s === "conversation" || s === "story" ? 20
      : s === "slang" || s === "idioms" ? 60
      : s === "media-listening" || s === "music-video" ? 10
      : s === "match" ? 4 : 5;
    try {
      setEx(await newLangExercise(course.code, s, n));
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

  async function checkPronunciation(said: string) {
    const target = targetRef.current;
    const text = (said || "").trim();
    if (!target || !text) return;
    setError("");
    try {
      const r = await pronounce(target, text);
      setPron(r);
      if (r.passed && codeRef.current) {
        try { await languagePractice(codeRef.current, "pronunciation", r.stars, 3); } catch { /* offline ok */ }
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }

  // Speak the target phrase aloud so the learner can hear it before repeating.
  function listenToTarget() {
    const target = targetRef.current;
    if (!target) return;
    stopSpeech();
    speakNatural(target, { locale: codeRef.current || "en" });
  }

  function stopMediaClip() {
    if (mediaTimerRef.current) clearTimeout(mediaTimerRef.current);
    mediaTimerRef.current = null;
    stopSpeech();
    setMediaPlaying(false);
  }

  function playMediaClip(text: string, durationSec: number) {
    stopMediaClip();
    setMediaAnswer("");
    setMediaPlaying(true);
    speakNatural(text, { locale: codeRef.current || "km" });
    mediaTimerRef.current = setTimeout(stopMediaClip, durationSec * 1000);
  }

  async function explainClickedWord(wordId: string) {
    if (!course) return;
    stopSpeech();
    setWordHelpLoading(true);
    setError("");
    try {
      setWordHelp(await explainLangWord(course.code, wordId));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setWordHelpLoading(false);
    }
  }

  async function checkMusicVideoGist() {
    if (!course || !ex?.sections?.length) return;
    const section = ex.sections[Math.min(mvIndex, ex.sections.length - 1)];
    const text = mvDraft.trim();
    if (!text) {
      setError("Type the gist of this section in English first.");
      return;
    }
    setError("");
    setMvScoring(true);
    try {
      const result = await scoreMusicVideoTranslation(
        course.code, ex.video_id || "", section.id, text,
      );
      if (!mountedRef.current) return;
      setMvScore(result);
      setMvResults((prev) => ({ ...prev, [section.id]: result.passed }));
    } catch (e) {
      if (mountedRef.current) setError((e as Error).message);
    } finally {
      if (mountedRef.current) setMvScoring(false);
    }
  }

  // Record the learner via native speech recognition (Siri/Google STT on device,
  // Web Speech in Expo web), transcribe, then auto-score against the target.
  async function startSpeaking() {
    if (!targetRef.current) return;
    setError("");
    setPron(null);
    setHeard("");
    stopSpeech();
    setListening(true);
    const ok = await startVoiceListening({
      locale: codeRef.current || "en",
      pauseSubmitMs,
      autoSubmitOnPause: true,
      onResult: (transcript) => {
        if (!mountedRef.current) return;
        setHeard(transcript);
        void checkPronunciation(transcript);
      },
      onError: (code) => {
        if (!mountedRef.current) return;
        setListening(false);
        if (code === "permission_denied") setError(t("languages.micDenied"));
        else if (code === "unavailable") setError(t("languages.micUnavailable"));
        else if (code === "no-speech") setError(t("languages.micNoSpeech"));
      },
      onEnd: () => {
        if (!mountedRef.current) return;
        setListening(false);
      },
    });
    if (!ok) setListening(false);
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
          <Text style={styles.meta}>
            📖 {course.vocabulary_count ?? 0} vocabulary words · 💬 {course.phrase_count} phrases ·
            {" "}🗨️ {course.dialogue_count ?? 0} conversations
          </Text>
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
              {ex.mouth_tip ? <Text style={styles.tip}>👄 {ex.mouth_tip}</Text> : null}
              <View style={styles.row}>
                <PrimaryButton label={t("languages.listen")} onPress={listenToTarget} variant="ghost" />
                <PrimaryButton
                  label={listening ? t("languages.listening") : t("languages.speak")}
                  onPress={() => void startSpeaking()}
                  variant="brand"
                />
              </View>
              {pron ? (
                <Text style={styles.meta}>
                  {"⭐".repeat(pron.stars)}{"☆".repeat(Math.max(0, 3 - pron.stars))} {pron.score}% — {pron.feedback}
                </Text>
              ) : null}
              <Text style={styles.fallbackLabel}>{t("languages.typeInstead")}</Text>
              <View style={styles.row}>
                <TextInput
                  style={[styles.input, { flex: 1 }]}
                  value={heard}
                  onChangeText={setHeard}
                  placeholder={t("languages.heard")}
                  placeholderTextColor={theme.colors.muted}
                  onSubmitEditing={() => void checkPronunciation(heard)}
                />
                <PrimaryButton label={t("languages.check")} onPress={() => void checkPronunciation(heard)} variant="netflix" />
              </View>
            </GlassPanel>
          ) : null}
          {ex?.pages ? (() => {
            const page = ex.pages[Math.min(storyPageIndex, ex.pages.length - 1)];
            return (
              <GlassPanel style={styles.card}>
                <Text style={styles.sectionTitle}>📖 {ex.title}</Text>
                <Text style={styles.tip}>{ex.instructions}</Text>
                <Text style={styles.meta}>Page {page.page_number} of {ex.pages.length}</Text>
                <Text style={styles.prompt}>{page.title}</Text>
                <Text style={styles.storyText}>
                  {page.runs.map((run, index) => (
                    <Text
                      key={`${run.word_id ?? "text"}-${index}`}
                      onPress={run.word_id ? () => void explainClickedWord(run.word_id!) : undefined}
                      style={run.word_id ? styles.storyWord : undefined}
                    >
                      {run.text}
                    </Text>
                  ))}
                </Text>
                <View style={styles.row}>
                  <PrimaryButton label="🔊 Read page aloud" onPress={() => {
                    stopSpeech();
                    speakNatural(page.text, { locale: course.code });
                  }} variant="brand" />
                  <PrimaryButton label="⏸ Pause" onPress={stopSpeech} variant="ghost" />
                </View>
                <Text style={styles.translation}>English</Text>
                <Text style={styles.meta}>{page.translation_en}</Text>
                {wordHelpLoading ? <ActivityIndicator color={theme.colors.accent} /> : null}
                {wordHelp ? (
                  <View style={styles.wordCoach}>
                    <Text style={styles.sectionTitle}>✨ AI Word Coach: {wordHelp.target}</Text>
                    {wordHelp.roman ? <Text style={styles.meta}>/{wordHelp.roman}/</Text> : null}
                    <Text style={styles.translation}>Meaning: {wordHelp.meaning}</Text>
                    <Text style={styles.optText}>{wordHelp.explanation}</Text>
                    <Text style={styles.tip}>🗣️ {wordHelp.pronunciation_tip}</Text>
                    <PrimaryButton label="🔊 Hear this word" onPress={() => {
                      stopSpeech();
                      speakNatural(wordHelp.target, { locale: course.code });
                    }} variant="ghost" />
                    {wordHelp.examples.map((example) => (
                      <View key={example.page} style={styles.turn}>
                        <Text style={styles.prompt}>Example from page {example.page}</Text>
                        <Text style={styles.optText}>{example.target}</Text>
                        <Text style={styles.meta}>{example.en}</Text>
                      </View>
                    ))}
                    <PrimaryButton label="Close coach" onPress={() => setWordHelp(null)} variant="ghost" />
                  </View>
                ) : null}
                <View style={styles.row}>
                  {storyPageIndex > 0 ? (
                    <PrimaryButton label="← Previous page" onPress={() => {
                      stopSpeech(); setWordHelp(null);
                      setStoryPageIndex((index) => Math.max(0, index - 1));
                    }} variant="ghost" />
                  ) : null}
                  {storyPageIndex < ex.pages.length - 1 ? (
                    <PrimaryButton label="Next page →" onPress={() => {
                      stopSpeech(); setWordHelp(null);
                      setStoryPageIndex((index) => Math.min(ex.pages!.length - 1, index + 1));
                    }} variant="netflix" />
                  ) : (
                    <PrimaryButton label="Finish story" onPress={() => void finishExercise(1, 1)} variant="netflix" />
                  )}
                </View>
              </GlassPanel>
            );
          })() : null}
          {ex?.study_words && ex.segments ? (() => {
            const segment = ex.segments[Math.min(mediaSegmentIndex, ex.segments.length - 1)];
            const correct = mediaResults[segment.id];
            return (
              <GlassPanel style={styles.card}>
                <Text style={styles.sectionTitle}>🎧 {ex.title}</Text>
                <Text style={styles.tip}>{ex.instructions}</Text>
                <Text style={styles.prompt}>Study these {ex.study_words.length} words</Text>
                <View style={styles.studyGrid}>
                  {ex.study_words.map((word) => (
                    <View key={word.id} style={styles.studyWord}>
                      <Text style={styles.optText}>{word.target}</Text>
                      {word.roman ? <Text style={styles.meta}>/{word.roman}/</Text> : null}
                      <Text style={styles.meta}>{word.en}</Text>
                    </View>
                  ))}
                </View>
                <Text style={styles.meta}>
                  Clip {mediaSegmentIndex + 1} of {ex.segments.length} ·
                  {" "}{segment.start_sec}–{segment.end_sec} seconds
                </Text>
                <PrimaryButton
                  label={mediaPlaying ? "▶ Playing 10 seconds…" : "▶ Play 10-second clip"}
                  onPress={() => playMediaClip(segment.tts_text, segment.duration_sec)}
                  disabled={mediaPlaying}
                  variant="brand"
                />
                {mediaPlaying ? (
                  <PrimaryButton label="⏸ Pause now & answer" onPress={stopMediaClip} variant="ghost" />
                ) : null}
                <Text style={styles.prompt}>{segment.question}</Text>
                <View style={styles.grid}>
                  {segment.options.map((option) => (
                    <AnimatedPressable
                      key={option.id}
                      disabled={mediaPlaying || Boolean(mediaAnswer)}
                      onPress={() => {
                        setMediaAnswer(option.id);
                        setMediaResults((results) => ({
                          ...results,
                          [segment.id]: option.id === segment.answer_id,
                        }));
                      }}
                      style={[styles.opt, mediaAnswer === option.id && styles.optOn]}
                    >
                      <Text style={styles.optText}>{option.target}</Text>
                      {option.roman ? <Text style={styles.meta}>/{option.roman}/</Text> : null}
                    </AnimatedPressable>
                  ))}
                </View>
                {mediaAnswer ? (
                  <Text style={[styles.feedback, { color: correct ? "#22c55e" : "#ef4444" }]}>
                    {correct
                      ? "✓ Correct — you caught it!"
                      : `The word was ${segment.options.find((option) => option.id === segment.answer_id)?.target}.`}
                  </Text>
                ) : null}
                {mediaAnswer && mediaSegmentIndex < ex.segments.length - 1 ? (
                  <PrimaryButton label="Next 10 seconds →" onPress={() => {
                    stopMediaClip();
                    setMediaSegmentIndex((index) => index + 1);
                    setMediaAnswer("");
                  }} variant="netflix" />
                ) : null}
                {mediaAnswer && mediaSegmentIndex === ex.segments.length - 1 && !done ? (
                  <PrimaryButton label="Finish challenge" onPress={() => void finishExercise(
                    Object.values(mediaResults).filter(Boolean).length,
                    ex.segments!.length,
                  )} variant="netflix" />
                ) : null}
              </GlassPanel>
            );
          })() : null}
          {ex?.skill === "music-video" && ex.sections && ex.sections.length > 0 ? (() => {
            const section = ex.sections[Math.min(mvIndex, ex.sections.length - 1)];
            const scored = Boolean(mvScore && mvScore.section_id === section.id);
            return (
              <GlassPanel style={styles.card}>
                <Text style={styles.sectionTitle}>🎬 {ex.title}</Text>
                {ex.title_target ? <Text style={styles.songTarget}>{ex.title_target}</Text> : null}
                <Text style={styles.tip}>{ex.instructions}</Text>
                <Text style={styles.meta}>
                  Section {mvIndex + 1} of {ex.sections.length} ·
                  {" "}{section.start_sec}–{section.end_sec}s
                </Text>
                <View style={styles.verse}>
                  <Text style={styles.songTarget}>{section.target}</Text>
                  {section.roman ? <Text style={styles.meta}>/{section.roman}/</Text> : null}
                </View>
                <PrimaryButton
                  label={mediaPlaying ? "▶ Playing section…" : "▶ Play this section"}
                  onPress={() => playMediaClip(section.tts_text || section.target, section.duration_sec)}
                  disabled={mediaPlaying}
                  variant="brand"
                />
                {mediaPlaying ? (
                  <PrimaryButton label="⏸ Pause & translate" onPress={stopMediaClip} variant="ghost" />
                ) : null}
                <Text style={styles.prompt}>{section.prompt}</Text>
                <TextInput
                  style={[styles.input, { minHeight: 72 }]}
                  value={mvDraft}
                  onChangeText={setMvDraft}
                  multiline
                  placeholder="Type the meaning in English (gist is enough)…"
                  placeholderTextColor={theme.colors.muted}
                  editable={!scored || !mvScore?.passed}
                />
                <PrimaryButton
                  label={mvScoring ? "Scoring…" : "Check gist (RAG)"}
                  onPress={() => void checkMusicVideoGist()}
                  disabled={mvScoring || !mvDraft.trim() || (scored && Boolean(mvScore?.passed))}
                  variant="netflix"
                />
                {scored && mvScore ? (
                  <>
                    <Text style={[styles.feedback, { color: mvScore.passed ? "#22c55e" : "#ef4444" }]}>
                      {mvScore.feedback} ({mvScore.score}/100)
                    </Text>
                    <Text style={styles.translation}>Reference: {mvScore.reference_en}</Text>
                    {mvScore.explain_en ? <Text style={styles.tip}>💡 {mvScore.explain_en}</Text> : null}
                  </>
                ) : null}
                {scored && mvIndex < ex.sections.length - 1 ? (
                  <PrimaryButton label="Next section →" onPress={() => {
                    stopMediaClip();
                    setMvIndex((i) => i + 1);
                    setMvDraft("");
                    setMvScore(null);
                  }} variant="brand" />
                ) : null}
                {scored && mvIndex === ex.sections.length - 1 && !done ? (
                  <PrimaryButton
                    label={`Finish music video (${Object.values(mvResults).filter(Boolean).length}/${ex.sections.length})`}
                    onPress={() => void finishExercise(
                      Object.values(mvResults).filter(Boolean).length,
                      ex.sections!.length,
                    )}
                    variant="netflix"
                  />
                ) : null}
              </GlassPanel>
            );
          })() : null}
          {ex?.dialogues ? (
            <GlassPanel style={styles.card}>
              <Text style={styles.sectionTitle}>🗨️ Real conversations ({ex.dialogues.length})</Text>
              {ex.dialogues.map((dialogue) => (
                <View key={dialogue.id} style={styles.dialogue}>
                  <Text style={styles.prompt}>{dialogue.situation_en}</Text>
                  {dialogue.turns.map((turn, index) => (
                    <AnimatedPressable
                      key={`${turn.speaker}-${index}`}
                      onPress={() => {
                        stopSpeech();
                        speakNatural(turn.target, { locale: course.code });
                      }}
                      style={styles.turn}
                    >
                      <Text style={styles.optText}>🔊 {turn.speaker}: {turn.target}</Text>
                      {turn.roman ? <Text style={styles.meta}>/{turn.roman}/</Text> : null}
                      <Text style={styles.meta}>{turn.en}</Text>
                    </AnimatedPressable>
                  ))}
                </View>
              ))}
            </GlassPanel>
          ) : null}
          {ex?.entries ? (
            <GlassPanel style={styles.card}>
              <Text style={styles.sectionTitle}>😎 Slang & idioms ({ex.entries.length})</Text>
              {ex.entries.map((entry, index) => (
                <AnimatedPressable
                  key={`${entry.phrase}-${index}`}
                  onPress={() => {
                    stopSpeech();
                    speakNatural(entry.phrase, { locale: course.code });
                  }}
                  style={styles.turn}
                >
                  <Text style={styles.optText}>🔊 {entry.phrase}</Text>
                  <Text style={styles.meta}>{entry.meaning}</Text>
                </AnimatedPressable>
              ))}
            </GlassPanel>
          ) : null}
          {ex?.songs?.[0] ? (() => {
            const song = ex.songs[0];
            const verse = song.verses[Math.min(verseIndex, song.verses.length - 1)];
            return (
              <GlassPanel style={styles.card}>
                <Text style={styles.sectionTitle}>🎵 {song.title_en}</Text>
                {song.title_target ? <Text style={styles.songTarget}>{song.title_target}</Text> : null}
                <Text style={styles.meta}>Verse {verseIndex + 1} of {song.verses.length} · {song.license}</Text>
                <View style={styles.verse}>
                  <Text style={styles.songTarget}>{verse.target}</Text>
                  {verse.roman ? <Text style={styles.meta}>/{verse.roman}/</Text> : null}
                  <Text style={styles.translation}>English: {verse.en}</Text>
                  <Text style={styles.tip}>💡 {verse.explain_en}</Text>
                </View>
                <View style={styles.row}>
                  <PrimaryButton label="▶ Play verse" onPress={() => {
                    stopSpeech();
                    speakNatural(verse.tts_text || verse.target, { locale: course.code });
                  }} variant="brand" />
                  <PrimaryButton label="■ Stop" onPress={stopSpeech} variant="ghost" />
                </View>
                <View style={styles.row}>
                  <PrimaryButton label="← Previous" onPress={() => setVerseIndex((v) => Math.max(0, v - 1))} variant="ghost" />
                  <PrimaryButton label="Next verse →" onPress={() => setVerseIndex((v) => Math.min(song.verses.length - 1, v + 1))} variant="ghost" />
                </View>
                <PrimaryButton label="♫ Play full song" onPress={() => {
                  stopSpeech();
                  speakNatural(song.verses.map((v) => v.tts_text || v.target).join(" "), { locale: course.code });
                }} variant="netflix" />
                {song.source_url ? (
                  <PrimaryButton label="Traditional cultural listening ↗" onPress={() => void Linking.openURL(song.source_url!)} variant="ghost" />
                ) : null}
              </GlassPanel>
            );
          })() : null}
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
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8, alignItems: "center" },
  fallbackLabel: { color: theme.colors.muted, fontSize: 12, marginTop: 4 },
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
  sectionTitle: { color: theme.colors.text, fontSize: 18, fontWeight: "800" },
  dialogue: { gap: 6, padding: 10, borderRadius: 10, borderWidth: 1, borderColor: theme.colors.border },
  turn: { gap: 3, padding: 9, borderRadius: 8, backgroundColor: "rgba(255,255,255,0.04)" },
  verse: { gap: 8, padding: 14, borderRadius: 12, backgroundColor: "rgba(124,58,237,0.16)" },
  songTarget: { color: theme.colors.text, fontSize: 20, fontWeight: "800" },
  translation: { color: theme.colors.accent, fontSize: 14, fontWeight: "700" },
  studyGrid: { flexDirection: "row", flexWrap: "wrap", gap: 7 },
  studyWord: {
    width: "47%", padding: 9, borderRadius: 8, borderWidth: 1,
    borderColor: theme.colors.border, backgroundColor: "rgba(255,255,255,0.04)",
  },
  feedback: { fontSize: 14, fontWeight: "800" },
  storyText: { color: theme.colors.text, fontSize: 21, lineHeight: 38 },
  storyWord: {
    color: theme.colors.accent, backgroundColor: "rgba(124,58,237,0.18)",
    textDecorationLine: "underline",
  },
  wordCoach: {
    gap: 8, padding: 12, borderWidth: 2, borderColor: theme.colors.accent,
    borderRadius: 12, backgroundColor: "rgba(124,58,237,0.10)",
  },
});
