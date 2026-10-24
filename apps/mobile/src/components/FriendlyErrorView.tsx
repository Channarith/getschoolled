import React, { useEffect, useRef, useState } from "react";
import { AccessibilityInfo, Animated, Easing, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SvgXml } from "react-native-svg";

import { useT } from "../i18n";
import { theme } from "../theme";
import {
  FRIENDLY_ART,
  FRIENDLY_COPY,
  FRIENDLY_KIND_MOOD,
  classifyStatus,
  type FriendlyKind,
} from "../friendlyError.generated";

type Props = {
  status?: number | null;
  kind?: FriendlyKind;
  /** Main action. Return true when things work again. */
  onRetry?: () => Promise<boolean | void> | boolean | void;
  onBack?: () => void;
  /** Network-style failures retry by themselves after this many seconds (0 = never). */
  autoRetrySeconds?: number;
  /** Technical text for support, tucked behind a small toggle. */
  details?: string;
};

export function friendlyKindFor(status?: number | null, description?: string): FriendlyKind {
  if (status) return classifyStatus(status) || "oops";
  if (/offline|internet|network|connect|timed out|timeout|host|dns/i.test(description || "")) return "network";
  return "oops";
}

export default function FriendlyErrorView({ status = null, kind: kindProp, onRetry, onBack, autoRetrySeconds = 0, details }: Props) {
  const { locale } = useT();
  const base = String(locale || "en").toLowerCase().split("-")[0];
  const copy = FRIENDLY_COPY[base] || FRIENDLY_COPY.en;
  const fallback = FRIENDLY_COPY.en;
  const kind: FriendlyKind = kindProp || classifyStatus(status) || "oops";
  const text = copy[kind] || fallback[kind];
  const common = { ...fallback.common, ...(copy.common || {}) };
  const [note, setNote] = useState("");
  const [left, setLeft] = useState(onRetry && autoRetrySeconds > 0 && (kind === "network" || kind === "offline") ? autoRetrySeconds : 0);
  const [showDetails, setShowDetails] = useState(false);
  const busy = useRef(false);
  const float = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    let loop: Animated.CompositeAnimation | null = null;
    let cancelled = false;
    Promise.resolve(AccessibilityInfo.isReduceMotionEnabled?.()).then((reduce) => {
      if (reduce || cancelled) return;
      loop = Animated.loop(Animated.sequence([
        Animated.timing(float, { toValue: 1, duration: 1800, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        Animated.timing(float, { toValue: 0, duration: 1800, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      ]));
      loop.start();
    }).catch(() => undefined);
    return () => { cancelled = true; loop?.stop(); };
  }, [float]);

  const tryNow = async () => {
    if (busy.current) return;
    busy.current = true;
    setNote(common.checking);
    let ok = true;
    try {
      const result = onRetry ? await onRetry() : true;
      ok = result !== false;
    } catch { ok = false; }
    busy.current = false;
    if (!ok) {
      setNote(common.stillDown);
      if (autoRetrySeconds > 0) setLeft(autoRetrySeconds);
    }
  };

  useEffect(() => {
    if (left <= 0) return undefined;
    const id = setTimeout(() => {
      if (left <= 1) { setLeft(0); void tryNow(); } else setLeft(left - 1);
    }, 1000);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [left]);

  const countdown = left > 0 ? common.retryIn.replace("{n}", String(left)) : note;
  const code = status ? common.status.replace("{code}", String(status)) : "";
  return (
    <ScrollView
      contentContainerStyle={styles.wrap}
      testID="friendly-error"
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
    >
      <Animated.View style={{ transform: [{ translateY: float.interpolate({ inputRange: [0, 1], outputRange: [0, -6] }) }] }}>
        <SvgXml xml={FRIENDLY_ART[FRIENDLY_KIND_MOOD[kind]]} width={220} height={238} accessibilityLabel="Sala, the Salareen mascot" />
      </Animated.View>
      <Text style={styles.title}>{text.title}</Text>
      <Text style={styles.body}>{text.body}</Text>
      <Text style={styles.hint}>{text.hint}</Text>
      {countdown ? <Text style={styles.note}>{countdown}</Text> : null}
      <View style={styles.actions}>
        {onRetry ? (
          <Pressable accessibilityRole="button" style={[styles.btn, styles.primary]} onPress={() => void tryNow()} testID="friendly-retry">
            <Text style={styles.primaryText}>{common.tryAgain}</Text>
          </Pressable>
        ) : null}
        {onBack ? (
          <Pressable accessibilityRole="button" style={styles.btn} onPress={onBack} testID="friendly-back">
            <Text style={styles.btnText}>{common.back}</Text>
          </Pressable>
        ) : null}
      </View>
      {code ? <Text style={styles.code}>{code}</Text> : null}
      {details ? (
        <Pressable onPress={() => setShowDetails((v) => !v)} accessibilityRole="button">
          <Text style={styles.detailsToggle}>{showDetails ? "▾" : "▸"} {status ? code : "Support details"}</Text>
          {showDetails ? <Text style={styles.details}>{details}</Text> : null}
        </Pressable>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  wrap: { flexGrow: 1, alignItems: "center", justifyContent: "center", padding: 24, gap: 12, backgroundColor: "#0b1020" },
  title: { color: "#f6e08a", fontSize: 22, fontWeight: "700", textAlign: "center" },
  body: { color: "#dbe4ff", fontSize: 16, lineHeight: 23, textAlign: "center" },
  hint: { color: "#5eead4", fontSize: 14, textAlign: "center" },
  note: { color: "#9fb0e6", fontSize: 14, textAlign: "center" },
  actions: { flexDirection: "row", flexWrap: "wrap", gap: 10, justifyContent: "center", marginTop: 6 },
  btn: { minHeight: 48, minWidth: 48, paddingHorizontal: 20, borderRadius: theme.radius.pill, borderWidth: 2, borderColor: "#d4af37", alignItems: "center", justifyContent: "center" },
  btnText: { color: "#f6e08a", fontSize: 16, fontWeight: "700" },
  primary: { backgroundColor: "#f6e08a", borderColor: "#f6e08a" },
  primaryText: { color: "#0b1020", fontSize: 16, fontWeight: "800" },
  code: { color: "#8d9bd0", fontSize: 12 },
  detailsToggle: { color: "#8d9bd0", fontSize: 12, marginTop: 4 },
  details: { color: "rgba(255,255,255,0.7)", fontSize: 11, fontFamily: "monospace", marginTop: 6, maxWidth: 320 },
});
