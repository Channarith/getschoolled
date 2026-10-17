import { useEffect, useState } from "react";
import {
  Linking, Modal, ScrollView, StyleSheet, Text, View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  completeMobileAccountOnboarding,
  getConsumerPlans,
  getMe,
  getMobileFreePlanOffer,
  selectMobileOnboardingPlan,
  startMobileBillingCheckout,
  type ConsumerPlan,
} from "../api";
import { SETUP_COLORS as C } from "../learnerCheck";
import AnimatedPressable from "./AnimatedPressable";
import KenBurnsImage from "./KenBurnsImage";

const ART = require("../../assets/setup-assistant/plan.webp");
const TIER_ORDER = ["free", "basic", "pro", "premium"] as const;

function formatPrice(plan: ConsumerPlan): string {
  if (plan.price_usd <= 0) return "$0";
  return `$${Math.round(plan.price_usd)}`;
}

type Props = {
  visible: boolean;
  displayName: string;
  ageBand: string;
  onComplete: () => void;
};

export default function MobileOnboardingPlanStep({
  visible,
  displayName,
  ageBand,
  onComplete,
}: Props) {
  const [plans, setPlans] = useState<Record<string, ConsumerPlan>>({});
  const [freeOffer, setFreeOffer] = useState(true);
  const [tier, setTier] = useState("free");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [awaitingCheckout, setAwaitingCheckout] = useState(false);

  useEffect(() => {
    if (!visible) return;
    void getMobileFreePlanOffer()
      .then((offer) => {
        setFreeOffer(offer.available);
        if (!offer.available) {
          setTier((current) => (current === "free" ? "basic" : current));
        }
      })
      .catch(() => undefined);
    void getConsumerPlans()
      .then(setPlans)
      .catch(() => undefined);
  }, [visible]);

  const choices = TIER_ORDER
    .map((id) => plans[id])
    .filter((plan): plan is ConsumerPlan => Boolean(plan))
    .filter((plan) => freeOffer || plan.tier !== "free");

  async function finishFree() {
    await selectMobileOnboardingPlan("free");
    await completeMobileAccountOnboarding(displayName.trim(), ageBand);
    onComplete();
  }

  async function finishPaid(selected: string) {
    await selectMobileOnboardingPlan(selected);
    await completeMobileAccountOnboarding(displayName.trim(), ageBand);
    onComplete();
  }

  async function confirmPlan() {
    setBusy(true);
    setError("");
    try {
      if (tier === "free") {
        await finishFree();
        return;
      }
      const me = await getMe();
      const session = await startMobileBillingCheckout(me.id, tier);
      if (session.url && /^https?:\/\//i.test(session.url)) {
        setAwaitingCheckout(true);
        await Linking.openURL(session.url);
        return;
      }
      await finishPaid(tier);
    } catch (reason) {
      setError(String(reason).replace(/^Error:\s*/, ""));
    } finally {
      setBusy(false);
    }
  }

  async function confirmCheckoutDone() {
    setBusy(true);
    setError("");
    try {
      await finishPaid(tier);
    } catch (reason) {
      const message = String(reason).replace(/^Error:\s*/, "");
      setError(
        message.includes("402") || /checkout|payment|billing/i.test(message)
          ? `${message} Finish payment in the browser, then tap “I've paid”.`
          : message,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal visible={visible} animationType="fade" presentationStyle="fullScreen">
      <SafeAreaView style={styles.root} edges={["top", "left", "right", "bottom"]}>
        <View style={styles.header}>
          <Text style={styles.brand}>Salareen</Text>
          <Text style={styles.kicker}>Your plan</Text>
        </View>
        <View style={styles.split}>
          <View style={styles.artPane}>
            <KenBurnsImage source={ART} style={StyleSheet.absoluteFill} />
          </View>
          <ScrollView style={styles.pane} contentContainerStyle={styles.paneBody}>
            <Text style={styles.title}>Pick a plan to start.</Text>
            <Text style={styles.body}>
              {freeOffer
                ? "Free is a 14-day English trial for the first 100 people. Paid plans add group classes and AI agents."
                : "The free plan is unavailable right now. Choose Standard, Pro, or VIP to continue."}
            </Text>
            <View style={styles.plans}>
              {choices.map((plan) => {
                const on = tier === plan.tier;
                const disabled = plan.tier === "free" && !freeOffer;
                return (
                  <AnimatedPressable
                    key={plan.tier}
                    disabled={disabled}
                    style={[styles.plan, on && styles.planOn, disabled && styles.planDisabled]}
                    onPress={() => setTier(plan.tier)}
                    accessibilityRole="radio"
                    accessibilityState={{ checked: on, disabled }}
                    accessibilityLabel={`${plan.display_name} ${formatPrice(plan)}`}
                  >
                    <Text style={styles.planName}>{plan.display_name}</Text>
                    <Text style={styles.planPrice}>{formatPrice(plan)}</Text>
                    <Text style={styles.planBlurb}>{plan.blurb}</Text>
                  </AnimatedPressable>
                );
              })}
            </View>
            {awaitingCheckout ? (
              <Text style={styles.note}>
                Complete checkout in your browser. When payment is confirmed, return here and tap below.
              </Text>
            ) : null}
            {error ? <Text style={styles.error} accessibilityLiveRegion="polite">{error}</Text> : null}
            <View style={styles.foot}>
              {awaitingCheckout ? (
                <AnimatedPressable
                  disabled={busy}
                  style={[styles.button, busy && styles.disabled]}
                  onPress={() => void confirmCheckoutDone()}
                >
                  <Text style={styles.buttonText}>{busy ? "Checking…" : "I've paid — continue"}</Text>
                </AnimatedPressable>
              ) : (
                <AnimatedPressable
                  disabled={busy || !tier}
                  style={[styles.button, (busy || !tier) && styles.disabled]}
                  onPress={() => void confirmPlan()}
                >
                  <Text style={styles.buttonText}>
                    {busy ? "Working…" : tier === "free" ? "Start learning" : "Continue to payment"}
                  </Text>
                </AnimatedPressable>
              )}
            </View>
          </ScrollView>
        </View>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.panel },
  header: {
    flexDirection: "row", alignItems: "center", gap: 12,
    paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: C.border, backgroundColor: C.bg,
  },
  brand: { color: C.text, fontSize: 17, fontWeight: "800" },
  kicker: { color: C.teal, fontSize: 12, fontWeight: "800", letterSpacing: 0.6, marginLeft: "auto" },
  split: { flex: 1, flexDirection: "row", minHeight: 0 },
  artPane: { flex: 1, minWidth: 0, backgroundColor: C.panel2, overflow: "hidden" },
  pane: { flex: 1, minWidth: 0, backgroundColor: C.panel, borderLeftWidth: 1, borderLeftColor: C.border },
  paneBody: { padding: 20, gap: 10, flexGrow: 1 },
  title: { color: C.text, fontSize: 28, fontWeight: "900" },
  body: { color: C.muted, fontSize: 15, lineHeight: 22 },
  plans: { gap: 10, marginTop: 8 },
  plan: {
    borderRadius: 14, borderWidth: 1, borderColor: C.border, padding: 14, gap: 4, backgroundColor: C.panel2,
  },
  planOn: { borderColor: C.accent, backgroundColor: C.panel },
  planDisabled: { opacity: 0.4 },
  planName: { color: C.text, fontSize: 18, fontWeight: "800" },
  planPrice: { color: C.accent, fontSize: 16, fontWeight: "800" },
  planBlurb: { color: C.muted, fontSize: 13, lineHeight: 18 },
  note: { color: C.warmText, fontSize: 14, lineHeight: 20 },
  foot: { marginTop: 12 },
  button: { minHeight: 48, borderRadius: 12, backgroundColor: C.accent, justifyContent: "center", alignItems: "center" },
  buttonText: { color: "#ffffff", fontSize: 16, fontWeight: "800" },
  disabled: { opacity: 0.45 },
  error: { color: C.danger, marginTop: 8 },
});
