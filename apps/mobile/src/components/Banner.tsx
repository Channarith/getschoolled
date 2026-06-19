import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

// Top in-app alert banner. Slides in / out, auto-dismisses unless `sticky`.
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

export default function Banner({ banner, onDismiss }: Props) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (!banner) { setVisible(false); return; }
    setVisible(true);
    const ttl = banner.ttlMs ?? 4500;
    if (ttl <= 0) return;
    const t = setTimeout(() => { setVisible(false); onDismiss(); }, ttl);
    return () => clearTimeout(t);
  }, [banner, onDismiss]);

  if (!banner || !visible) return null;
  const kind = banner.kind || "info";
  const accent = ACCENTS[kind];
  return (
    <View style={[styles.wrap, { borderColor: accent }]} accessibilityLiveRegion="polite">
      <View style={[styles.dot, { backgroundColor: accent }]} />
      <View style={{ flex: 1 }}>
        <Text style={styles.title}>{banner.title}</Text>
        {banner.body ? <Text style={styles.body}>{banner.body}</Text> : null}
      </View>
      {banner.cta ? (
        <Pressable
          onPress={() => { banner.onPress?.(); setVisible(false); onDismiss(); }}
          style={[styles.cta, { backgroundColor: accent }]}
        >
          <Text style={styles.ctaText}>{banner.cta}</Text>
        </Pressable>
      ) : null}
      <Pressable onPress={() => { setVisible(false); onDismiss(); }} hitSlop={8}>
        <Text style={styles.x}>×</Text>
      </Pressable>
    </View>
  );
}

const ACCENTS: Record<BannerKind, string> = {
  info: "#0ea5e9", success: "#16a34a", warn: "#f59e0b", live: "#ef4444",
};

const styles = StyleSheet.create({
  wrap: {
    position: "absolute", top: 44, left: 12, right: 12, zIndex: 50,
    flexDirection: "row", alignItems: "center", gap: 10,
    backgroundColor: "#151c34", borderWidth: 1, borderColor: "#0ea5e9",
    borderRadius: 14, paddingVertical: 10, paddingHorizontal: 12,
    shadowColor: "#000", shadowOpacity: 0.4, shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 }, elevation: 6,
  },
  dot: { width: 10, height: 10, borderRadius: 5 },
  title: { color: "#e8ecf6", fontWeight: "700", fontSize: 14 },
  body: { color: "#c5cce0", fontSize: 12, marginTop: 2 },
  cta: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999 },
  ctaText: { color: "#fff", fontWeight: "700", fontSize: 12 },
  x: { color: "#9aa6c2", fontSize: 22, paddingHorizontal: 4 },
});
