import { useEffect, useRef, useState } from "react";
import { Animated, StyleSheet, Text, View } from "react-native";

import AnimatedPressable from "./AnimatedPressable";
import GlassPanel from "./GlassPanel";
import { theme } from "../theme";

export type BannerKind = "info" | "success" | "warn" | "live";

export type BannerPayload = {
  kind?: BannerKind;
  title: string;
  body?: string;
  cta?: string;
  onPress?: () => void;
  ttlMs?: number;
};

type Props = { banner: BannerPayload | null; onDismiss: () => void };

const ACCENTS: Record<BannerKind, string> = {
  info: theme.colors.brand,
  success: theme.colors.success,
  warn: theme.colors.gold,
  live: theme.colors.netflix,
};

export default function Banner({ banner, onDismiss }: Props) {
  const [visible, setVisible] = useState(false);
  const slide = useRef(new Animated.Value(-80)).current;
  const opacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!banner) {
      Animated.parallel([
        Animated.timing(slide, { toValue: -80, duration: 180, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0, duration: 180, useNativeDriver: true }),
      ]).start(() => setVisible(false));
      return;
    }
    setVisible(true);
    Animated.parallel([
      Animated.spring(slide, { toValue: 0, useNativeDriver: true, speed: 18, bounciness: 6 }),
      Animated.timing(opacity, { toValue: 1, duration: theme.motion.fadeDuration, useNativeDriver: true }),
    ]).start();
    const ttl = banner.ttlMs ?? 4500;
    if (ttl <= 0) return;
    const t = setTimeout(() => {
      Animated.parallel([
        Animated.timing(slide, { toValue: -80, duration: 200, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0, duration: 200, useNativeDriver: true }),
      ]).start(() => { setVisible(false); onDismiss(); });
    }, ttl);
    return () => clearTimeout(t);
  }, [banner, onDismiss, slide, opacity]);

  if (!banner || !visible) return null;
  const kind = banner.kind || "info";
  const accent = ACCENTS[kind];

  const dismiss = () => {
    Animated.parallel([
      Animated.timing(slide, { toValue: -80, duration: 200, useNativeDriver: true }),
      Animated.timing(opacity, { toValue: 0, duration: 200, useNativeDriver: true }),
    ]).start(() => { setVisible(false); onDismiss(); });
  };

  return (
    <Animated.View
      style={[styles.wrap, { transform: [{ translateY: slide }], opacity }]}
      accessibilityLiveRegion="polite"
    >
      <GlassPanel style={[styles.panel, { borderLeftColor: accent }]} padded={false}>
        <View style={styles.inner}>
          <View style={[styles.dot, { backgroundColor: accent }]} />
          <View style={{ flex: 1 }}>
            <Text style={styles.title}>{banner.title}</Text>
            {banner.body ? <Text style={styles.body}>{banner.body}</Text> : null}
          </View>
          {banner.cta ? (
            <AnimatedPressable
              onPress={() => { banner.onPress?.(); dismiss(); }}
              style={[styles.cta, { backgroundColor: accent }]}
            >
              <Text style={styles.ctaText}>{banner.cta}</Text>
            </AnimatedPressable>
          ) : null}
          <AnimatedPressable onPress={dismiss} hitSlop={8}>
            <Text style={styles.x}>×</Text>
          </AnimatedPressable>
        </View>
      </GlassPanel>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    position: "absolute", top: 44, left: 12, right: 12, zIndex: 50,
  },
  panel: {
    borderLeftWidth: 4,
    ...theme.shadow.hero,
  },
  inner: {
    flexDirection: "row", alignItems: "center", gap: 10,
    paddingVertical: 10, paddingHorizontal: 12,
  },
  dot: { width: 10, height: 10, borderRadius: 5 },
  title: { color: theme.colors.text, fontWeight: "700", fontSize: 14 },
  body: { color: theme.colors.muted, fontSize: 12, marginTop: 2 },
  cta: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: theme.radius.pill },
  ctaText: { color: "#fff", fontWeight: "700", fontSize: 12 },
  x: { color: theme.colors.muted, fontSize: 22, paddingHorizontal: 4 },
});
