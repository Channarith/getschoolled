import { useEffect, useState } from "react";
import {
  ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { getHomeRails, type HomeRail } from "../api";
import Rail, { CourseCard } from "../components/Rail";
import PrimaryButton from "../components/PrimaryButton";
import { useAndroidBackTo } from "../hooks/useAndroidBack";
import { useT } from "../i18n";

interface KidsScreenProps {
  onOpenCourse: (id: string) => void;
  onBack: () => void;
}

export default function KidsScreen({ onOpenCourse, onBack }: KidsScreenProps) {
  const { locale } = useT();
  useAndroidBackTo(onBack);
  const [rails, setRails] = useState<HomeRail[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const load = async (alive?: { current: boolean }) => {
    setError("");
    try {
      const result = await getHomeRails(true, locale);
      if (!alive || alive.current) setRails(result);
    } catch (e) {
      if (!alive || alive.current) setError(String(e));
    } finally {
      if (!alive || alive.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  };

  useEffect(() => {
    const alive = { current: true };
    setLoading(true);
    void load(alive);
    return () => { alive.current = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locale]);

  const allEmpty = !loading && rails.every((r) => r.courses.length === 0);

  return (
    <View style={styles.wrap}>
      <LinearGradient
        colors={["#7c3aed", "#db2777"]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.header}
      >
        <PrimaryButton label="← Back" onPress={onBack} variant="ghost" />
        <Text style={styles.title}>🎓 Kids Academy</Text>
        <Text style={styles.subtitle}>Learning adventures for young explorers!</Text>
      </LinearGradient>

      {loading && !refreshing ? (
        <ActivityIndicator color="#db2777" style={{ marginTop: 32 }} />
      ) : null}
      {error ? <Text style={styles.error}>{error}</Text> : null}

      <ScrollView
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => { setRefreshing(true); void load(); }}
            tintColor="#db2777"
          />
        }
      >
        {allEmpty ? (
          <Text style={styles.empty}>
            🌟 No kids courses available yet. Check back soon!
          </Text>
        ) : null}
        {rails.map((rail) =>
          rail.courses.length === 0 ? null : (
            <Rail
              key={rail.key}
              title={rail.title}
              subtitle={rail.reason}
              data={rail.courses}
              keyExtractor={(c) => c.course_id}
              renderItem={(c) => (
                <CourseCard
                  title={c.title}
                  category={c.category}
                  format={c.format}
                  onPress={() => onOpenCourse(c.course_id)}
                />
              )}
            />
          )
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, paddingTop: 56 },
  header: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 22,
    gap: 8,
  },
  title: { color: "#fff", fontSize: 24, fontWeight: "900", marginTop: 4 },
  subtitle: { color: "rgba(255,255,255,0.85)", fontSize: 13, lineHeight: 18 },
  empty: {
    color: "#9ca3af", textAlign: "center",
    marginTop: 40, fontSize: 15, lineHeight: 22,
  },
  error: { color: "#f87171", fontSize: 13, margin: 16 },
});
