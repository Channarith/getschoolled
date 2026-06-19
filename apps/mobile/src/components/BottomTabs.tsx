import { Pressable, StyleSheet, Text, View } from "react-native";

import type { TabId } from "../types";

type Tab = { id: TabId; label: string; emoji: string };

const TABS: Tab[] = [
  { id: "home",          label: "Home",     emoji: "🏠" },
  { id: "drive",         label: "Drive",    emoji: "🎧" },
  { id: "mylist",        label: "My List",  emoji: "★" },
  { id: "notifications", label: "Alerts",   emoji: "🔔" },
  { id: "settings",      label: "Settings", emoji: "⚙" },
];

export default function BottomTabs({
  active, onChange, unreadCount = 0,
}: {
  active: TabId; onChange: (id: TabId) => void; unreadCount?: number;
}) {
  return (
    <View style={styles.bar} accessibilityRole="tablist">
      {TABS.map((t) => {
        const isActive = t.id === active;
        return (
          <Pressable
            key={t.id} onPress={() => onChange(t.id)}
            accessibilityRole="tab"
            accessibilityState={{ selected: isActive }}
            style={styles.tab}
          >
            <View>
              <Text style={[styles.icon, isActive && styles.iconActive]}>{t.emoji}</Text>
              {t.id === "notifications" && unreadCount > 0 ? (
                <View style={styles.badge}>
                  <Text style={styles.badgeText}>
                    {unreadCount > 99 ? "99+" : unreadCount}
                  </Text>
                </View>
              ) : null}
            </View>
            <Text style={[styles.label, isActive && styles.labelActive]}>{t.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: "row", backgroundColor: "#0b1020",
    borderTopWidth: 1, borderTopColor: "#1d2746",
    paddingBottom: 18, paddingTop: 6,
  },
  tab: { flex: 1, alignItems: "center", paddingVertical: 4 },
  icon: { fontSize: 22, opacity: 0.55, color: "#e8ecf6" },
  iconActive: { opacity: 1 },
  label: { fontSize: 11, marginTop: 2, color: "#9aa6c2" },
  labelActive: { color: "#0ea5e9", fontWeight: "700" },
  badge: {
    position: "absolute", top: -4, right: -10,
    backgroundColor: "#ef4444", minWidth: 18, height: 18,
    borderRadius: 9, paddingHorizontal: 5,
    alignItems: "center", justifyContent: "center",
  },
  badgeText: { color: "#fff", fontSize: 10, fontWeight: "800" },
});
