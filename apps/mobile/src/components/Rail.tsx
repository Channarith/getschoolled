import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";

// Horizontal scrolling row of cards (Netflix rail). Generic over the row type
// so it can render audio courses, continue-listening rows, recommendations,
// or category tiles.

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
    <View style={{ marginBottom: 18 }}>
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
          contentContainerStyle={{ paddingHorizontal: 12 }}
          renderItem={({ item }) => <View style={{ marginRight: 10 }}>{renderItem(item)}</View>}
        />
      )}
    </View>
  );
}

export function CourseCard({
  emoji = "🎧", title, meta, onPress, savedBadge, progressPct,
}: {
  emoji?: string; title: string; meta?: string;
  onPress?: () => void; savedBadge?: boolean;
  progressPct?: number;
}) {
  return (
    <Pressable onPress={onPress} style={styles.card}>
      <View style={styles.thumb}>
        <Text style={styles.emoji}>{emoji}</Text>
        {savedBadge ? <Text style={styles.saved}>★</Text> : null}
      </View>
      <Text numberOfLines={2} style={styles.cardTitle}>{title}</Text>
      {meta ? <Text style={styles.cardMeta}>{meta}</Text> : null}
      {typeof progressPct === "number" ? (
        <View style={styles.progressTrack}>
          <View style={[styles.progressBar, { width: `${Math.max(2, Math.min(100, progressPct))}%` }]} />
        </View>
      ) : null}
    </Pressable>
  );
}

export function CategoryTile({ category, count, onPress }: {
  category: string; count: number; onPress?: () => void;
}) {
  const colors = HUES[Math.abs(hash(category)) % HUES.length];
  return (
    <Pressable onPress={onPress} style={[styles.tile, { backgroundColor: colors.bg }]}>
      <Text style={[styles.tileTitle, { color: colors.fg }]}>{category}</Text>
      <Text style={[styles.tileCount, { color: colors.fg }]}>{count} classes</Text>
    </Pressable>
  );
}

function hash(s: string) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  return h;
}
const HUES = [
  { bg: "#0ea5e9", fg: "#001022" }, { bg: "#22c55e", fg: "#04210f" },
  { bg: "#f59e0b", fg: "#311c01" }, { bg: "#a855f7", fg: "#1a0530" },
  { bg: "#ef4444", fg: "#310606" }, { bg: "#06b6d4", fg: "#012c34" },
  { bg: "#84cc16", fg: "#0e1f02" }, { bg: "#ec4899", fg: "#3b0723" },
];

const styles = StyleSheet.create({
  header: { paddingHorizontal: 16, marginBottom: 8 },
  title: { color: "#e8ecf6", fontSize: 18, fontWeight: "800" },
  sub: { color: "#9aa6c2", fontSize: 12, marginTop: 2 },
  empty: { color: "#9aa6c2", paddingHorizontal: 16, fontStyle: "italic" },
  card: { width: 168, backgroundColor: "#151c34", borderRadius: 12, padding: 10 },
  thumb: { backgroundColor: "#0b1020", height: 92, borderRadius: 8,
           alignItems: "center", justifyContent: "center", marginBottom: 8,
           position: "relative" },
  emoji: { fontSize: 36 },
  saved: { position: "absolute", top: 4, right: 8, color: "#fbbf24", fontSize: 16, fontWeight: "800" },
  cardTitle: { color: "#e8ecf6", fontSize: 13, fontWeight: "700", lineHeight: 17 },
  cardMeta: { color: "#9aa6c2", fontSize: 11, marginTop: 4 },
  progressTrack: { height: 3, backgroundColor: "#23304f", borderRadius: 2, marginTop: 6, overflow: "hidden" },
  progressBar: { height: 3, backgroundColor: "#0ea5e9" },
  tile: { width: 140, height: 90, borderRadius: 12, padding: 12, justifyContent: "space-between" },
  tileTitle: { fontWeight: "800", fontSize: 16 },
  tileCount: { fontSize: 12, fontWeight: "600", opacity: 0.8 },
});
