import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";

import AnimatedPressable from "./AnimatedPressable";
import { useT } from "../i18n";
import type { StringKey } from "../i18n/strings";
import { theme } from "../theme";
import type { TabId } from "../types";

type TabSpec = {
  id: TabId;
  labelKey: StringKey;
  icon: keyof typeof Ionicons.glyphMap;
  iconActive: keyof typeof Ionicons.glyphMap;
};

const TABS: TabSpec[] = [
  { id: "home", labelKey: "tab.home", icon: "home-outline", iconActive: "home" },
  { id: "drive", labelKey: "tab.drive", icon: "headset-outline", iconActive: "headset" },
  { id: "mylist", labelKey: "tab.mylist", icon: "bookmark-outline", iconActive: "bookmark" },
  { id: "careers", labelKey: "tab.careers", icon: "briefcase-outline", iconActive: "briefcase" },
  { id: "notifications", labelKey: "tab.alerts", icon: "notifications-outline", iconActive: "notifications" },
  { id: "settings", labelKey: "tab.settings", icon: "settings-outline", iconActive: "settings" },
];

export default function BottomTabs({
  active, onChange, unreadCount = 0,
}: {
  active: TabId; onChange: (id: TabId) => void; unreadCount?: number;
}) {
  const { t } = useT();
  return (
    <View style={styles.wrap}>
      <LinearGradient
        colors={["rgba(11,16,32,0)", "rgba(11,16,32,0.92)", "rgba(11,16,32,0.98)"]}
        style={StyleSheet.absoluteFill}
        pointerEvents="none"
      />
      <View style={styles.bar} accessibilityRole="tablist">
        {TABS.map((tab) => {
          const isActive = tab.id === active;
          const color = isActive ? "#fff" : theme.colors.muted;
          return (
            <AnimatedPressable
              key={tab.id}
              onPress={() => onChange(tab.id)}
              accessibilityRole="tab"
              accessibilityState={{ selected: isActive }}
              style={styles.tab}
            >
              <View style={styles.iconWrap}>
                <Ionicons
                  name={isActive ? tab.iconActive : tab.icon}
                  size={24}
                  color={color}
                />
                {tab.id === "notifications" && unreadCount > 0 ? (
                  <View style={styles.badge}>
                    <Text style={styles.badgeText}>
                      {unreadCount > 99 ? "99+" : unreadCount}
                    </Text>
                  </View>
                ) : null}
              </View>
              <Text style={[styles.label, isActive && styles.labelActive]}>
                {t(tab.labelKey)}
              </Text>
              {isActive ? <View style={styles.activeDot} /> : null}
            </AnimatedPressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: theme.colors.border,
    paddingBottom: 20,
    paddingTop: 8,
  },
  bar: { flexDirection: "row" },
  tab: { flex: 1, alignItems: "center", paddingVertical: 4 },
  iconWrap: { height: 28, justifyContent: "center" },
  label: {
    fontSize: 9,
    marginTop: 4,
    color: theme.colors.muted,
    fontWeight: "600",
  },
  labelActive: { color: "#fff", fontWeight: "800" },
  activeDot: {
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: theme.colors.netflix,
    marginTop: 4,
  },
  badge: {
    position: "absolute",
    top: -4,
    right: -12,
    backgroundColor: theme.colors.netflix,
    minWidth: 16,
    height: 16,
    borderRadius: 8,
    paddingHorizontal: 4,
    alignItems: "center",
    justifyContent: "center",
  },
  badgeText: { color: "#fff", fontSize: 9, fontWeight: "800" },
});
