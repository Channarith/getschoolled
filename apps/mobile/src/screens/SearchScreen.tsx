import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { searchLearnable, type LearnableItem } from "../api";
import { useT } from "../i18n";
import { theme } from "../theme";

// Static settings items searchable client-side — admin/flags excluded.
const SETTINGS_ITEMS = [
  { title: "Account settings", section: "account", keywords: "profile email name" },
  { title: "Language", section: "language", keywords: "locale language translate" },
  { title: "Voice & Audio", section: "voice", keywords: "voice tts audio narration speed" },
  { title: "Notifications", section: "notifications", keywords: "email push notification" },
  { title: "Subscription", section: "subscription", keywords: "plan billing tier upgrade" },
];

type ResultItem =
  | { kind: "course"; item: LearnableItem }
  | { kind: "setting"; title: string; section: string };

function useDebounce<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}

export default function SearchScreen({
  onBack,
  onOpenCourse,
  onOpenSettings,
}: {
  onBack: () => void;
  onOpenCourse: (id: string) => void;
  onOpenSettings: (section?: string) => void;
}) {
  const { t } = useT();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ResultItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<TextInput>(null);

  const debouncedQuery = useDebounce(query, 300);

  useEffect(() => {
    // Focus the input when the screen mounts
    const timeout = setTimeout(() => inputRef.current?.focus(), 100);
    return () => clearTimeout(timeout);
  }, []);

  useEffect(() => {
    const q = debouncedQuery.trim();
    if (!q) {
      setResults([]);
      setError("");
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError("");

    (async () => {
      try {
        const lower = q.toLowerCase();

        // Client-side settings filter
        const settingMatches: ResultItem[] = SETTINGS_ITEMS.filter(
          (s) =>
            s.title.toLowerCase().includes(lower) ||
            s.keywords.toLowerCase().includes(lower),
        ).map((s) => ({ kind: "setting" as const, title: s.title, section: s.section }));

        // API search for courses/learnables
        const res = await searchLearnable({ q, limit: "8" });
        const courseMatches: ResultItem[] = res.items
          .slice(0, 8)
          .map((item) => ({ kind: "course" as const, item }));

        if (!cancelled) {
          setResults([...courseMatches, ...settingMatches]);
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [debouncedQuery]);

  const renderItem = ({ item }: { item: ResultItem }) => {
    if (item.kind === "course") {
      const c = item.item;
      return (
        <TouchableOpacity
          style={styles.result}
          accessibilityRole="button"
          onPress={() => onOpenCourse(c.id)}
        >
          <View style={styles.resultIcon}>
            <Text style={styles.resultIconText}>&#x1F4DA;</Text>
          </View>
          <View style={styles.resultBody}>
            <Text style={styles.resultTitle} numberOfLines={1}>
              {c.title}
            </Text>
            <Text style={styles.resultMeta} numberOfLines={1}>
              {[c.category, c.level, c.duration_min ? `${c.duration_min} min` : null]
                .filter(Boolean)
                .join(" · ")}
            </Text>
          </View>
          <Text style={styles.resultBadge}>Course</Text>
        </TouchableOpacity>
      );
    }

    // setting
    return (
      <TouchableOpacity
        style={styles.result}
        accessibilityRole="button"
        onPress={() => onOpenSettings(item.section)}
      >
        <View style={styles.resultIcon}>
          <Text style={styles.resultIconText}>&#x2699;&#xFE0F;</Text>
        </View>
        <View style={styles.resultBody}>
          <Text style={styles.resultTitle}>{item.title}</Text>
        </View>
        <Text style={styles.resultBadge}>Settings</Text>
      </TouchableOpacity>
    );
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Pressable
          onPress={onBack}
          style={styles.backBtn}
          accessibilityRole="button"
          accessibilityLabel="Back"
        >
          <Text style={styles.backText}>&#x2190;</Text>
        </Pressable>
        <TextInput
          ref={inputRef}
          style={styles.input}
          placeholder="Search courses, games, settings…"
          placeholderTextColor={theme.colors.muted}
          value={query}
          onChangeText={setQuery}
          returnKeyType="search"
          autoCorrect={false}
          autoCapitalize="none"
          clearButtonMode="while-editing"
          accessibilityLabel="Search"
        />
        {query.length > 0 && (
          <Pressable onPress={() => setQuery("")} style={styles.clearBtn}>
            <Text style={styles.clearText}>✕</Text>
          </Pressable>
        )}
      </View>

      {/* Body */}
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={theme.colors.accent} size="large" />
        </View>
      ) : error ? (
        <View style={styles.center}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : query.trim().length === 0 ? (
        <View style={styles.center}>
          <Text style={styles.hint}>Type to search courses, games, and settings</Text>
        </View>
      ) : results.length === 0 ? (
        <View style={styles.center}>
          <Text style={styles.hint}>No results for &ldquo;{query}&rdquo;</Text>
        </View>
      ) : (
        <FlatList
          data={results}
          keyExtractor={(item, idx) =>
            item.kind === "course" ? `course-${item.item.id}` : `setting-${idx}`
          }
          renderItem={renderItem}
          contentContainerStyle={styles.list}
          keyboardShouldPersistTaps="handled"
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.bg,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: theme.spacing.screenX,
    paddingTop: 56,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
    gap: 8,
  },
  backBtn: {
    padding: 6,
    marginRight: 2,
  },
  backText: {
    color: theme.colors.accent,
    fontSize: 20,
  },
  input: {
    flex: 1,
    backgroundColor: theme.colors.panel2,
    borderRadius: theme.radius.pill,
    paddingHorizontal: 16,
    paddingVertical: 9,
    color: theme.colors.text,
    fontSize: 15,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  clearBtn: {
    padding: 6,
  },
  clearText: {
    color: theme.colors.muted,
    fontSize: 14,
  },
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  hint: {
    color: theme.colors.muted,
    fontSize: 14,
    textAlign: "center",
  },
  errorText: {
    color: "#ff8a8a",
    fontSize: 14,
    textAlign: "center",
  },
  list: {
    paddingVertical: 8,
  },
  result: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: theme.spacing.screenX,
    paddingVertical: 12,
    gap: 12,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
  },
  resultIcon: {
    width: 32,
    alignItems: "center",
  },
  resultIconText: {
    fontSize: 18,
  },
  resultBody: {
    flex: 1,
  },
  resultTitle: {
    color: theme.colors.text,
    fontSize: 14,
    fontWeight: "600",
  },
  resultMeta: {
    color: theme.colors.muted,
    fontSize: 12,
    marginTop: 2,
  },
  resultBadge: {
    color: theme.colors.accent,
    fontSize: 11,
    fontWeight: "700",
    backgroundColor: "rgba(110,168,254,0.12)",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: theme.radius.pill,
    overflow: "hidden",
  },
});
