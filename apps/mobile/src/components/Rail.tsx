import { FlatList, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";

import AnimatedPressable from "./AnimatedPressable";
import { categoryGradient, theme } from "../theme";

type Props<T> = {
  title: string;
  subtitle?: string;
  data: T[];
  emptyMessage?: string;
  renderItem: (item: T) => React.ReactNode;
  keyExtractor: (item: T) => string;
};

export default function Rail<T>({
  title, subtitle, data, emptyMessage, renderItem, keyExtractor,
}: Props<T>) {
  return (
    <View style={styles.rail}>
      <View style={styles.header}>
        <Text style={styles.title}>{title}</Text>
        {subtitle ? <Text style={styles.sub}>{subtitle}</Text> : null}
      </View>
      {data.length === 0 ? (
        <Text style={styles.empty}>{emptyMessage || "Nothing here yet."}</Text>
      ) : (
        <FlatList
          horizontal
          showsHorizontalScrollIndicator={false}
          data={data}
          keyExtractor={keyExtractor}
          style={styles.list}
          contentContainerStyle={{ paddingHorizontal: theme.spacing.screenX }}
          renderItem={({ item }) => (
            <View style={{ marginRight: theme.spacing.railGap }}>{renderItem(item)}</View>
          )}
        />
      )}
    </View>
  );
}

export function CourseCard({
  emoji = "🎧", title, meta, onPress, savedBadge, progressPct, category,
}: {
  emoji?: string;
  title: string;
  meta?: string;
  onPress?: () => void;
  savedBadge?: boolean;
  progressPct?: number;
  category?: string;
}) {
  const [c1, c2] = categoryGradient(category || title);
  return (
    <AnimatedPressable onPress={onPress} style={styles.card}>
      <LinearGradient colors={[c1, c2]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.poster}>
        <Text style={styles.posterEmoji}>{emoji}</Text>
        <Text numberOfLines={2} style={styles.posterTitle}>{title}</Text>
        {savedBadge ? (
          <View style={styles.savedBadge}>
            <Ionicons name="bookmark" size={14} color={theme.colors.gold} />
          </View>
        ) : null}
        {typeof progressPct === "number" ? (
          <View style={styles.progressTrack}>
            <View style={[styles.progressBar, { width: `${Math.max(4, Math.min(100, progressPct))}%` }]} />
          </View>
        ) : null}
      </LinearGradient>
      <View style={styles.cardBody}>
        <Text numberOfLines={2} style={styles.cardTitle}>{title}</Text>
        {meta ? <Text style={styles.cardMeta}>{meta}</Text> : null}
      </View>
    </AnimatedPressable>
  );
}

export function CategoryTile({ category, count, countLabel, onPress }: {
  category: string;
  count: number;
  countLabel?: string;
  onPress?: () => void;
}) {
  const [c1, c2] = categoryGradient(category);
  return (
    <AnimatedPressable onPress={onPress} style={styles.tile}>
      <LinearGradient colors={[c1, c2]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.tileGrad}>
        <Text style={styles.tileTitle}>{category}</Text>
        <Text style={styles.tileCount}>{countLabel || `${count} classes`}</Text>
        <Ionicons name="chevron-forward" size={16} color="rgba(255,255,255,0.7)" style={styles.tileChevron} />
      </LinearGradient>
    </AnimatedPressable>
  );
}

const styles = StyleSheet.create({
  rail: { marginBottom: theme.spacing.section, width: "100%", overflow: "hidden" },
  list: { width: "100%" },
  header: { paddingHorizontal: theme.spacing.screenX, marginBottom: 10 },
  title: { ...theme.typography.railTitle, color: theme.colors.text },
  sub: { ...theme.typography.caption, color: theme.colors.muted, marginTop: 2 },
  empty: {
    color: theme.colors.muted,
    paddingHorizontal: theme.spacing.screenX,
    fontStyle: "italic",
  },
  card: {
    width: 168,
    borderRadius: theme.radius.md,
    overflow: "hidden",
    backgroundColor: theme.colors.panelSolid,
    ...theme.shadow.card,
  },
  poster: {
    height: 112,
    padding: 10,
    justifyContent: "flex-end",
    position: "relative",
  },
  posterEmoji: { fontSize: 28, position: "absolute", top: 10, right: 10, opacity: 0.85 },
  posterTitle: {
    color: "#fff",
    fontWeight: "800",
    fontSize: 13,
    lineHeight: 16,
    textShadowColor: "rgba(0,0,0,0.5)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 4,
  },
  savedBadge: {
    position: "absolute",
    top: 8,
    left: 8,
    backgroundColor: "rgba(0,0,0,0.35)",
    borderRadius: 6,
    padding: 4,
  },
  progressTrack: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    height: 3,
    backgroundColor: "rgba(0,0,0,0.35)",
  },
  progressBar: { height: 3, backgroundColor: theme.colors.netflix },
  cardBody: { padding: 10 },
  cardTitle: { color: theme.colors.text, fontSize: 13, fontWeight: "700", lineHeight: 17 },
  cardMeta: { color: theme.colors.muted, fontSize: 11, marginTop: 4 },
  tile: {
    width: 148,
    height: 96,
    borderRadius: theme.radius.md,
    overflow: "hidden",
    ...theme.shadow.card,
  },
  tileGrad: {
    flex: 1,
    padding: 12,
    justifyContent: "space-between",
  },
  tileTitle: { color: "#fff", fontWeight: "800", fontSize: 15 },
  tileCount: { color: "rgba(255,255,255,0.85)", fontSize: 11, fontWeight: "600" },
  tileChevron: { position: "absolute", right: 10, bottom: 10 },
});
