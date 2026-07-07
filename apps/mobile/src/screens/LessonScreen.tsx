import * as Speech from "expo-speech";
import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";

import {
  advanceLessonSession, askLessonSession, startLessonSession,
  type LessonAnswer, type LessonSessionView, type LessonSlide,
} from "../api";
import AnimatedPressable from "../components/AnimatedPressable";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { useT } from "../i18n";
import { getSettings } from "../storage";
import { theme } from "../theme";
import { speakNatural } from "../tts";

type Props = {
  lessonId: string;
  title: string;
  preview?: string;
  onBack: () => void;
};

export default function LessonScreen({ lessonId, title, preview, onBack }: Props) {
  const { t, locale } = useT();
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
  const slideRef = useRef<LessonSlide | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      setError("");
      try {
        const settings = await getSettings();
        const v = await startLessonSession(lessonId, settings.studentId);
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
  }, [lessonId]);

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
    speakNatural(text, {
      locale,
      onDone: () => setNarrating(false),
      onStopped: () => setNarrating(false),
      onError: () => setNarrating(false),
    });
  }

  async function next() {
    if (!view) return;
    stopNarration();
    setAdvancing(true);
    setError("");
    try {
      const s = await advanceLessonSession(view.session.session_id);
      const prevIdx = slideRef.current?.index ?? -1;
      if (s.index <= prevIdx) {
        setAtEnd(true);
      }
      setSlide(s);
      slideRef.current = s;
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAdvancing(false);
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
        <Text style={styles.title} numberOfLines={1}>{view?.lesson.title || title}</Text>
      </View>

      {loading ? (
        <ActivityIndicator color={theme.colors.accent} style={{ marginTop: 24 }} />
      ) : error && !slide ? (
        // Graceful in-app fallback when no live session is available for this item.
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
                {!atEnd ? (
                  <PrimaryButton
                    label={t("lesson.next")}
                    onPress={() => void next()}
                    loading={advancing}
                    disabled={advancing}
                    variant="netflix"
                  />
                ) : (
                  <Text style={styles.meta}>{t("lesson.complete")}</Text>
                )}
              </View>
            </GlassPanel>
          ) : null}

          {/* Ask the tutor */}
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
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, paddingHorizontal: 16, paddingTop: 56, gap: 8 },
  header: { flexDirection: "row", alignItems: "center", gap: 8 },
  title: { color: theme.colors.text, fontSize: 18, fontWeight: "700", flex: 1 },
  body: { gap: 12, paddingBottom: 32 },
  progress: { color: theme.colors.muted, fontSize: 12, fontWeight: "700" },
  card: { gap: 10 },
  cardTitle: { color: theme.colors.text, fontSize: 16, fontWeight: "700" },
  slideTitle: { color: theme.colors.text, fontSize: 19, fontWeight: "800", lineHeight: 25 },
  slideBody: { color: theme.colors.text, fontSize: 15, lineHeight: 23 },
  slideActions: { flexDirection: "row", flexWrap: "wrap", gap: 8, alignItems: "center", marginTop: 4 },
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
