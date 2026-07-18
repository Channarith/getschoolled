import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View,
} from "react-native";

import {
  getRewards, getRewardsCatalog, redeemReward,
  type RewardPrize, type RewardsSummary,
} from "../api";
import AnimatedPressable from "../components/AnimatedPressable";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { useAndroidBackTo } from "../hooks/useAndroidBack";
import { useT } from "../i18n";
import { theme } from "../theme";

export default function RewardsScreen({ onBack }: { onBack: () => void }) {
  const { t } = useT();
  useAndroidBackTo(onBack);
  const [summary, setSummary] = useState<RewardsSummary | null>(null);
  const [prizes, setPrizes] = useState<RewardPrize[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [r, c] = await Promise.all([getRewards(), getRewardsCatalog()]);
      setSummary(r);
      setPrizes(c.prizes);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function redeem(id: string) {
    setBusyId(id);
    setError("");
    try {
      const r = await redeemReward(id);
      setSummary((s) => s ? { ...s, balance: r.balance } : s);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusyId("");
    }
  }

  return (
    <ScrollView
      style={styles.bg}
      contentContainerStyle={styles.scroll}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load(); }}
          tintColor={theme.colors.netflix} />
      }
    >
      <PrimaryButton label={t("rewards.back")} onPress={onBack} variant="ghost" />
      <Text style={styles.title}>{t("rewards.title")}</Text>
      {loading ? <ActivityIndicator color={theme.colors.netflix} /> : null}
      {error ? <Text style={styles.err}>{error}</Text> : null}
      {summary ? (
        <GlassPanel>
          <Text style={styles.balance}>{t("rewards.balance", { n: summary.balance })}</Text>
        </GlassPanel>
      ) : null}
      <Text style={styles.section}>{t("rewards.catalog")}</Text>
      {prizes.map((p) => (
        <AnimatedPressable key={p.id} onPress={() => void redeem(p.id)} disabled={busyId === p.id}>
          <GlassPanel style={styles.prize}>
            <Text style={styles.prizeName}>{p.name}</Text>
            <Text style={styles.prizeCost}>{p.cost_points} pts</Text>
          </GlassPanel>
        </AnimatedPressable>
      ))}
      {summary?.ledger.length ? (
        <>
          <Text style={styles.section}>{t("rewards.history")}</Text>
          {summary.ledger.slice(0, 12).map((e, i) => (
            <Text key={`${e.ts}-${i}`} style={styles.ledger}>
              {e.delta > 0 ? "+" : ""}{e.delta} · {e.reason}
            </Text>
          ))}
        </>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  bg: { flex: 1 },
  scroll: { paddingHorizontal: theme.spacing.screenX, paddingTop: 56, paddingBottom: 32, gap: 10 },
  title: { color: theme.colors.text, fontSize: 26, fontWeight: "800" },
  balance: { color: theme.colors.accent, fontSize: 22, fontWeight: "800" },
  section: { color: theme.colors.muted, fontSize: 12, fontWeight: "800", letterSpacing: 0.8, marginTop: 8 },
  prize: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  prizeName: { color: theme.colors.text, fontSize: 15, fontWeight: "700", flex: 1 },
  prizeCost: { color: theme.colors.netflix, fontWeight: "800" },
  ledger: { color: theme.colors.muted, fontSize: 13 },
  err: { color: theme.colors.netflix, fontSize: 13 },
});
