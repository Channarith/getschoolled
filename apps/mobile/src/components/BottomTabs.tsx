import { Pressable, StyleSheet, Text, View } from "react-native";

import { useT } from "../i18n";
import type { StringKey } from "../i18n/strings";
import type { TabId } from "../types";

type TabSpec = { id: TabId; labelKey: StringKey; emoji: string };

const TABS: TabSpec[] = [
  { id: "home",          labelKey: "tab.home",     emoji: "🏠" },
  { id: "drive",         labelKey: "tab.drive",    emoji: "🎧" },
  { id: "mylist",        labelKey: "tab.mylist",   emoji: "★" },
  { id: "notifications", labelKey: "tab.alerts",   emoji: "🔔" },
  { id: "settings",      labelKey: "tab.settings", emoji: "⚙" },
];

export default function BottomTabs({
  active, onChange, unreadCount = 0,
}: {
  active: TabId; onChange: (id: TabId) => void; unreadCount?: number;
}) {
  const { t } = useT();
  return (
    <View style={styles.bar} accessibilityRole="tablist">
      {TABS.map((tab) => {
        const isActive = tab.id === active;
        return (
          <Pressable
            key={tab.id} onPress={() => onChange(tab.id)}
            accessibilityRole="tab"
            accessibilityState={{ selected: isActive }}
            style={styles.tab}
          >
            <View>
              <Text style={[styles.icon, isActive && styles.iconActive]}>{tab.emoji}</Text>
              {tab.id === "notifications" && unreadCount > 0 ? (
                <View style={styles.badge}>
                  <Text style={styles.badgeText}>
                    {unreadCount > 99 ? "99+" : unreadCount}
                  </Text>
                </View>
              ) : null}
            </View>
            <Text style={[styles.label, isActive && styles.labelActive]}>{t(tab.labelKey)}</Text>
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
