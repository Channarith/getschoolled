import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View,
} from "react-native";

import {
  getRewards, getRewardsCatalog, redeemReward,
  type RewardPrize, type RewardsSummary,
} from "../api";
import AnimatedPressable from "../components/AnimatedPressable";
import DropdownListSelector from "../components/DropdownListSelector";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { useAndroidBackTo } from "../hooks/useAndroidBack";
import { useT } from "../i18n";
import { theme } from "../theme";

function formatRewardReason(reason: string): string {
  const [kind, rawDetail = ""] = reason.split(":", 2);
  const detail = rawDetail.replace(/[_-]+/g, " ").trim();
  if (kind === "live_gift") return `Gift sent: ${detail || "item"}`;
  if (kind === "live_gift_received") return `Gift received: ${detail || "item"}`;
  if (kind === "language") {
    const lang = (rawDetail || "").trim().toUpperCase();
    return `Language: ${lang || "practice"}`;
  }
  return reason.replace(/[_-]+/g, " ");
}

function formatRewardRef(ref: string): string {
  const value = (ref || "").trim();
  if (!value) return "";
  if (value.length <= 18) return ` (${value})`;
  return ` (${value.slice(0, 10)}...${value.slice(-5)})`;
}

export default function RewardsScreen({ onBack }: { onBack: () => void }) {
  const { t } = useT();
  useAndroidBackTo(onBack);
  const [summary, setSummary] = useState<RewardsSummary | null>(null);
  const [prizes, setPrizes] = useState<RewardPrize[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");
  const [selectedPrizeId, setSelectedPrizeId] = useState("");
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [selectedHistoryKey, setSelectedHistoryKey] = useState("");

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

  useEffect(() => {
    if (!prizes.length) {
      setSelectedPrizeId("");
      return;
    }
    if (!selectedPrizeId || !prizes.some((p) => p.id === selectedPrizeId)) {
      setSelectedPrizeId(prizes[0].id);
    }
  }, [prizes, selectedPrizeId]);

  const selectedPrize = prizes.find((p) => p.id === selectedPrizeId) ?? null;
  const historyRows = summary?.ledger.slice(0, 12).map((e, i) => ({
    key: `${e.ts}-${i}`,
    label: `${e.delta > 0 ? "+" : ""}${e.delta} · ${formatRewardReason(e.reason)}${formatRewardRef(e.ref)}`,
  })) ?? [];
  const selectedHistory = historyRows.find((h) => h.key === selectedHistoryKey) ?? historyRows[0] ?? null;

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
      {prizes.length ? (
        <>
          <DropdownListSelector
            title={t("rewards.catalog")}
            selectedLabel={selectedPrize ? `${selectedPrize.name} · ${selectedPrize.cost_points} pts` : "—"}
            selectedKey={selectedPrizeId}
            options={prizes.map((p) => ({ key: p.id, label: `${p.name} · ${p.cost_points} pts` }))}
            open={catalogOpen}
            onToggle={() => setCatalogOpen((v) => !v)}
            onSelect={(id) => {
              setSelectedPrizeId(id);
              setCatalogOpen(false);
            }}
            maxHeight={240}
          />
          {selectedPrize ? (
            <AnimatedPressable onPress={() => void redeem(selectedPrize.id)} disabled={busyId === selectedPrize.id}>
              <GlassPanel style={styles.prize}>
                <Text style={styles.prizeName}>{selectedPrize.name}</Text>
                <Text style={styles.prizeCost}>{selectedPrize.cost_points} pts</Text>
              </GlassPanel>
            </AnimatedPressable>
          ) : null}
        </>
      ) : null}
      {historyRows.length ? (
        <DropdownListSelector
          title={t("rewards.history")}
          selectedLabel={selectedHistory?.label ?? t("rewards.history")}
          selectedKey={selectedHistory?.key ?? ""}
          options={historyRows}
          open={historyOpen}
          onToggle={() => setHistoryOpen((v) => !v)}
          onSelect={(key) => {
            setSelectedHistoryKey(key);
            setHistoryOpen(false);
          }}
          maxHeight={220}
        />
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
  prize: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 8 },
  prizeName: { color: theme.colors.text, fontSize: 15, fontWeight: "700", flex: 1 },
  prizeCost: { color: theme.colors.netflix, fontWeight: "800" },
  ledger: { color: theme.colors.muted, fontSize: 13 },
  err: { color: theme.colors.netflix, fontSize: 13 },
});
