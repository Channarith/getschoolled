import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator, ScrollView, StyleSheet, Text, View,
} from "react-native";

import {
  getGamesCatalog, getLeaderboard, newGame, submitGame,
  type AgeGroupInfo, type GamesCatalog, type GameRound, type GameSubmit,
  type GameTypeInfo, type Leader,
} from "../api";
import { useAuth } from "../auth/AuthContext";
import AnimatedPressable from "../components/AnimatedPressable";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { useAndroidBack } from "../hooks/useAndroidBack";
import { useT } from "../i18n";
import PotionLab, { type PotionAgeKey } from "./PotionLab";
import { theme } from "../theme";

type Props = {
  subject: string;
  onBack: () => void;
};

const SUBJECT_EMOJI: Record<string, string> = {
  biology: "🧬", chemistry: "⚗️", physics: "🪐", math: "➗", science: "🔬",
  history: "🏛️", art: "🎨", technology: "💻", programming: "👾",
  life_growth: "🌱", etiquette: "🤝", wordplay: "🔤", geometry: "📐",
  creation: "🛠️", farming: "🌾",
};

function subjectLabel(subject: string): string {
  return subject.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function GameScreen({ subject, onBack }: Props) {
  const { t, locale } = useT();
  const { account } = useAuth();
  const [cat, setCat] = useState<GamesCatalog | null>(null);
  const [gameType, setGameType] = useState("quiz");
  const [ageGroup, setAgeGroup] = useState("teen");
  const [round, setRound] = useState<GameRound | null>(null);
  const [answers, setAnswers] = useState<Record<string, number | string>>({});
  const [selTerm, setSelTerm] = useState("");
  const [result, setResult] = useState<GameSubmit | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [timeLeft, setTimeLeft] = useState(0);
  const [potionActive, setPotionActive] = useState(false);
  const [leaders, setLeaders] = useState<Leader[]>([]);
  const startedAt = useRef(0);

  useAndroidBack(() => {
    if (potionActive) {
      setPotionActive(false);
      return true;
    }
    onBack();
    return true;
  });

  useEffect(() => {
    getGamesCatalog(locale).then(setCat).catch(() => {});
  }, [locale]);

  useEffect(() => {
    void getLeaderboard(subject, ageGroup)
      .then((r) => setLeaders(r.leaders.slice(0, 10)))
      .catch(() => setLeaders([]));
  }, [subject, ageGroup]);

  const gameTypes: GameTypeInfo[] = useMemo(() => {
    const base = cat?.game_types ?? [];
    if (base.length) return base;
    return [
      { id: "quiz", name: "Quiz", desc: "" },
      { id: "speed", name: "Speed", desc: "" },
      { id: "match", name: "Match", desc: "" },
    ];
  }, [cat]);

  const ageGroups: AgeGroupInfo[] = useMemo(() => {
    const base = cat?.age_groups ?? [];
    if (base.length) return base;
    return [
      { id: "kids", name: "Kids", range: "5-8" },
      { id: "tween", name: "Tweens", range: "9-12" },
      { id: "teen", name: "Teens", range: "13-17" },
      { id: "adult", name: "Adults", range: "18+" },
    ];
  }, [cat]);

  const finish = useCallback(async () => {
    if (!round) return;
    const elapsed = (Date.now() - startedAt.current) / 1000;
    setLoading(true);
    setError("");
    try {
      const r = await submitGame(round.game_id, answers, elapsed);
      setResult(r);
      setRound(null);
    } catch (e) {
      const msg = (e as Error).message;
      if (msg.includes("404") || msg.includes("expired")) {
        setError(t("game.sessionExpired"));
        setRound(null);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, [round, answers, t]);

  useEffect(() => {
    const timed = round && (round.game_type === "speed" || round.game_type === "marathon");
    if (!timed || round!.time_limit_s <= 0) return;
    if (timeLeft <= 0) { void finish(); return; }
    const timer = setTimeout(() => setTimeLeft((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [round, timeLeft, finish]);

  async function play() {
    // Potion Lab is a real-time arcade game (its own view); launch it with the
    // chosen age group so difficulty scales (kids = slow/simple, adults = fast/complex).
    if (subject === "chemistry" && gameType === "potion") {
      setError(""); setResult(null);
      setPotionActive(true);
      return;
    }
    setError(""); setResult(null); setAnswers({}); setSelTerm("");
    setLoading(true);
    try {
      const n = gameType === "marathon" ? 20 : gameType === "match" ? 8 : 12;
      const r = await newGame(subject, gameType, ageGroup, n);
      startedAt.current = Date.now();
      setTimeLeft(r.time_limit_s || 0);
      setRound(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function pickOption(itemId: string, idx: number) {
    setAnswers((a) => ({ ...a, [itemId]: idx }));
  }
  function pickMatch(optionId: string) {
    if (!selTerm) return;
    setAnswers((a) => ({ ...a, [selTerm]: optionId }));
    setSelTerm("");
  }

  const emoji = SUBJECT_EMOJI[subject] ?? "📘";
  const timed = round && (round.game_type === "speed" || round.game_type === "marathon");

  if (potionActive) {
    return <PotionLab age={ageGroup as PotionAgeKey} onBack={() => setPotionActive(false)} />;
  }

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <PrimaryButton label={t("game.back")} onPress={onBack} variant="ghost" />
        <Text style={styles.title}>{emoji} {subjectLabel(subject)}</Text>
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <ScrollView contentContainerStyle={styles.body} showsVerticalScrollIndicator={false}>
        {leaders.length > 0 ? (
          <GlassPanel style={styles.card}>
            <Text style={styles.cardTitle}>{t("game.leaderboard")}</Text>
            <Text style={styles.meta}>{t("game.leaderboardSub")}</Text>
            {leaders.map((l) => (
              <Text key={`${l.rank}-${l.name}`} style={styles.leaderRow}>
                #{l.rank} {l.name} · {l.game_points} pts
              </Text>
            ))}
          </GlassPanel>
        ) : null}
        {/* Picker */}
        {!round && !result && (
          <GlassPanel style={styles.card}>
            <Text style={styles.cardTitle}>{t("game.chooseMode")}</Text>
            <View style={styles.chipRow}>
              {gameTypes.map((g) => (
                <AnimatedPressable
                  key={g.id}
                  onPress={() => setGameType(g.id)}
                  style={[styles.chip, gameType === g.id && styles.chipOn]}
                >
                  <Text style={[styles.chipText, gameType === g.id && styles.chipTextOn]}>
                    {g.name}
                  </Text>
                </AnimatedPressable>
              ))}
              {subject === "chemistry" && (
                <AnimatedPressable
                  onPress={() => setGameType("potion")}
                  style={[styles.chip, styles.chipPotion, gameType === "potion" && styles.chipPotionOn]}
                >
                  <Text style={[styles.chipText, gameType === "potion" && styles.chipTextOn]}>
                    {t("game.potionLab")}
                  </Text>
                </AnimatedPressable>
              )}
            </View>
            {subject === "chemistry" && gameType === "potion" && (
              <Text style={styles.label}>{t("game.potionTip")}</Text>
            )}
            <Text style={styles.label}>{t("game.ageGroup")}</Text>
            <View style={styles.chipRow}>
              {ageGroups.map((a) => (
                <AnimatedPressable
                  key={a.id}
                  onPress={() => setAgeGroup(a.id)}
                  style={[styles.chip, ageGroup === a.id && styles.chipOn]}
                >
                  <Text style={[styles.chipText, ageGroup === a.id && styles.chipTextOn]}>
                    {a.name}
                  </Text>
                </AnimatedPressable>
              ))}
            </View>
            <PrimaryButton
              label={t("game.play")}
              onPress={() => void play()}
              loading={loading}
              disabled={loading}
              variant="netflix"
            />
          </GlassPanel>
        )}

        {/* Quiz / speed / marathon / extended (MCQ) */}
        {round && round.items && (
          <>
            <View style={styles.roundHeader}>
              <Text style={styles.roundTitle}>{round.game_type}</Text>
              {timed && round.time_limit_s > 0 ? (
                <Text style={[styles.timer, timeLeft <= 10 && styles.timerLow]}>
                  ⏱ {timeLeft}s
                </Text>
              ) : null}
            </View>
            {round.items.map((it, qi) => {
              const letters = it.meta?.letters as string | undefined;
              return (
                <GlassPanel key={it.id} style={styles.card}>
                  {letters ? (
                    <Text style={styles.letters}>{String(letters).split("").join(" ")}</Text>
                  ) : null}
                  <Text style={styles.prompt}>{qi + 1}. {it.prompt}</Text>
                  <View style={styles.optionsCol}>
                    {it.options.map((opt, idx) => {
                      const on = answers[it.id] === idx;
                      return (
                        <AnimatedPressable
                          key={idx}
                          onPress={() => pickOption(it.id, idx)}
                          style={[styles.option, on && styles.optionOn]}
                        >
                          <Text style={[styles.optionText, on && styles.optionTextOn]}>{opt}</Text>
                        </AnimatedPressable>
                      );
                    })}
                  </View>
                </GlassPanel>
              );
            })}
            <PrimaryButton
              label={t("game.submit")}
              onPress={() => void finish()}
              loading={loading}
              disabled={loading}
              variant="netflix"
            />
          </>
        )}

        {/* Match */}
        {round && round.terms && round.options && (
          <GlassPanel style={styles.card}>
            <Text style={styles.cardTitle}>{t("game.matchHint")}</Text>
            <View style={styles.matchGrid}>
              <View style={styles.matchCol}>
                {round.terms.map((term) => {
                  const done = Boolean(answers[term.id]);
                  return (
                    <AnimatedPressable
                      key={term.id}
                      onPress={() => setSelTerm(term.id)}
                      style={[
                        styles.matchCell,
                        selTerm === term.id && styles.matchCellSel,
                        done && styles.matchCellDone,
                      ]}
                    >
                      <Text style={styles.matchText}>{term.term} {done ? "✓" : ""}</Text>
                    </AnimatedPressable>
                  );
                })}
              </View>
              <View style={styles.matchCol}>
                {round.options.map((o) => {
                  const taken = Object.values(answers).includes(o.id);
                  return (
                    <AnimatedPressable
                      key={o.id}
                      onPress={() => pickMatch(o.id)}
                      disabled={!selTerm}
                      style={[styles.matchCell, taken && styles.matchCellTaken]}
                    >
                      <Text style={styles.matchText}>{o.text}</Text>
                    </AnimatedPressable>
                  );
                })}
              </View>
            </View>
            <PrimaryButton
              label={t("game.submit")}
              onPress={() => void finish()}
              loading={loading}
              disabled={loading}
              variant="netflix"
            />
          </GlassPanel>
        )}

        {/* Result */}
        {result && (
          <GlassPanel style={[styles.card, styles.resultCard]}>
            <Text style={styles.scoreTitle}>
              {result.result.correct}/{result.result.total} · +{result.points_earned} pts 🎉
            </Text>
            <Text style={styles.meta}>
              {t("game.accuracy")} {Math.round(result.result.accuracy * 100)}%
              {result.result.speed_bonus > 0 ? ` · +${result.result.speed_bonus} speed` : ""}
              {result.result.accuracy_bonus > 0 ? ` · +${result.result.accuracy_bonus} perfect` : ""}
            </Text>
            <Text style={styles.meta}>
              {t("game.balance")}: {result.balance} pts
              {result.rank ? ` · ${t("game.rank")} #${result.rank}` : ""}
            </Text>
            <View style={styles.resultList}>
              {result.result.results.map((r) => (
                <Text
                  key={r.id}
                  style={[styles.resultLine, { color: r.correct ? "#4ade80" : "#f87171" }]}
                >
                  {r.correct ? "✓" : "✗"} {r.explain}
                </Text>
              ))}
            </View>
            <PrimaryButton
              label={t("game.playAgain")}
              onPress={() => void play()}
              variant="netflix"
            />
          </GlassPanel>
        )}

        {!account ? <Text style={styles.meta}>{t("game.signInSave")}</Text> : null}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, paddingHorizontal: 16, paddingTop: 56, gap: 8 },
  header: { flexDirection: "row", alignItems: "center", gap: 8 },
  title: { color: theme.colors.text, fontSize: 20, fontWeight: "700", flex: 1 },
  body: { gap: 12, paddingBottom: 32 },
  card: { gap: 10 },
  cardTitle: { color: theme.colors.text, fontSize: 16, fontWeight: "700" },
  label: { color: theme.colors.muted, fontSize: 13, marginTop: 4 },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    backgroundColor: "rgba(255,255,255,0.14)",
    borderRadius: 999, borderWidth: 1, borderColor: "rgba(255,255,255,0.3)",
    paddingHorizontal: 14, paddingVertical: 8,
  },
  chipOn: { backgroundColor: theme.colors.netflix, borderColor: theme.colors.netflix },
  chipPotion: { borderColor: "#a78bfa" },
  chipPotionOn: { backgroundColor: "#7c3aed", borderColor: "#7c3aed" },
  chipText: { color: "#f8fafc", fontWeight: "700", fontSize: 13 },
  chipTextOn: { color: "#fff", fontWeight: "800" },
  roundHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  roundTitle: { color: theme.colors.text, fontSize: 15, fontWeight: "700", textTransform: "capitalize" },
  timer: { color: "#4ade80", fontWeight: "800", fontSize: 15 },
  timerLow: { color: "#f87171" },
  letters: { fontFamily: "monospace", fontSize: 22, letterSpacing: 4, color: theme.colors.accent },
  prompt: { color: theme.colors.text, fontSize: 15, fontWeight: "600", lineHeight: 21 },
  optionsCol: { gap: 8 },
  option: {
    borderWidth: 1, borderColor: theme.colors.border, borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: 12, backgroundColor: "rgba(0,0,0,0.2)",
  },
  optionOn: { borderColor: theme.colors.accent, backgroundColor: "rgba(110,168,254,0.2)" },
  optionText: { color: theme.colors.text, fontSize: 14 },
  optionTextOn: { color: "#fff", fontWeight: "700" },
  matchGrid: { flexDirection: "row", gap: 10 },
  matchCol: { flex: 1, gap: 8 },
  matchCell: {
    borderWidth: 1, borderColor: theme.colors.border, borderRadius: 10,
    paddingHorizontal: 10, paddingVertical: 10, backgroundColor: "rgba(0,0,0,0.2)",
  },
  matchCellSel: { borderColor: theme.colors.accent, backgroundColor: "rgba(110,168,254,0.2)" },
  matchCellDone: { borderColor: "#4ade80" },
  matchCellTaken: { opacity: 0.45 },
  matchText: { color: theme.colors.text, fontSize: 13 },
  resultCard: { borderColor: theme.colors.netflix, borderWidth: 1 },
  scoreTitle: { color: theme.colors.text, fontSize: 18, fontWeight: "800" },
  resultList: { gap: 4, marginTop: 4 },
  resultLine: { fontSize: 13, lineHeight: 18 },
  meta: { color: theme.colors.muted, fontSize: 13, lineHeight: 18 },
  leaderRow: { color: theme.colors.text, fontSize: 13, lineHeight: 20 },
  error: { color: "#f87171", fontSize: 13 },
});
