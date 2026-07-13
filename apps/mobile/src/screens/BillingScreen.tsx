import { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";

import {
  getConsumerPlans, getSubscription, subscribeToPlan,
  type ConsumerPlan, type Subscription,
} from "../api";
import { useAuth } from "../auth/AuthContext";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { useT } from "../i18n";
import { theme } from "../theme";

export default function BillingScreen({ onBack }: { onBack: () => void }) {
  const { t } = useT();
  const { refreshAccount } = useAuth();
  const [plans, setPlans] = useState<Record<string, ConsumerPlan>>({});
  const [sub, setSub] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    void (async () => {
      try {
        const [p, s] = await Promise.all([getConsumerPlans(), getSubscription()]);
        setPlans(p);
        setSub(s);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function pick(tier: string) {
    setBusy(tier);
    setError("");
    try {
      const r = await subscribeToPlan(tier);
      setSub(r.subscription);
      await refreshAccount();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  return (
    <ScrollView style={styles.bg} contentContainerStyle={styles.scroll}>
      <PrimaryButton label={t("billing.back")} onPress={onBack} variant="ghost" />
      <Text style={styles.title}>{t("billing.title")}</Text>
      {loading ? <ActivityIndicator color={theme.colors.netflix} /> : null}
      {error ? <Text style={styles.err}>{error}</Text> : null}
      {sub ? (
        <GlassPanel>
          <Text style={styles.current}>{t("billing.current", { tier: sub.tier, status: sub.status })}</Text>
        </GlassPanel>
      ) : null}
      {Object.values(plans).map((p) => (
        <GlassPanel key={p.tier} style={styles.plan}>
          <Text style={styles.planName}>{p.display_name}</Text>
          <Text style={styles.planPrice}>${p.price_usd}/{p.billing_interval}</Text>
          <Text style={styles.planBlurb}>{p.blurb}</Text>
          <PrimaryButton
            label={t("billing.choose")}
            onPress={() => void pick(p.tier)}
            loading={busy === p.tier}
            variant="netflix"
          />
        </GlassPanel>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  bg: { flex: 1 },
  scroll: { paddingHorizontal: theme.spacing.screenX, paddingTop: 56, paddingBottom: 32, gap: 10 },
  title: { color: theme.colors.text, fontSize: 26, fontWeight: "800" },
  current: { color: theme.colors.accent, fontSize: 15, fontWeight: "700" },
  plan: { gap: 8 },
  planName: { color: theme.colors.text, fontSize: 18, fontWeight: "800" },
  planPrice: { color: theme.colors.netflix, fontWeight: "700" },
  planBlurb: { color: theme.colors.muted, fontSize: 13, lineHeight: 18 },
  err: { color: theme.colors.netflix, fontSize: 13 },
});
