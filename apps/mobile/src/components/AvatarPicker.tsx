import { useMemo, useState } from "react";
import {
  Pressable, ScrollView, StyleSheet, Text, View,
} from "react-native";

import AvatarImage from "./AvatarImage";
import {
  AVATAR_STYLES,
  avatarsByStyle,
  getAvatar,
  resolveAvatarId,
  type AvatarStyle,
} from "../avatars";
import { theme } from "../theme";

type Props = {
  value?: string | null;
  onChange: (avatarId: string) => void;
  disabled?: boolean;
  heading?: string;
};

export default function AvatarPicker({
  value,
  onChange,
  disabled,
  heading = "Choose your avatar",
}: Props) {
  const selected = resolveAvatarId(value);
  const selectedEntry = getAvatar(selected);
  const [style, setStyle] = useState<AvatarStyle>(selectedEntry.style);
  const items = useMemo(() => avatarsByStyle(style), [style]);

  return (
    <View style={styles.wrap} accessibilityRole="summary">
      <View style={styles.previewRow}>
        <AvatarImage avatarId={selected} size={72} />
        <View style={{ flex: 1 }}>
          <Text style={styles.heading}>{heading}</Text>
          <Text style={styles.sub}>
            {selectedEntry.label} · {selectedEntry.style === "realistic" ? "Realistic" : "Cute"}
          </Text>
        </View>
      </View>

      <View style={styles.tabs} accessibilityRole="tablist">
        {AVATAR_STYLES.map((s) => {
          const active = style === s.id;
          return (
            <Pressable
              key={s.id}
              accessibilityRole="tab"
              accessibilityState={{ selected: active }}
              disabled={disabled}
              onPress={() => setStyle(s.id)}
              style={[styles.tab, active && styles.tabActive]}
            >
              <Text style={[styles.tabText, active && styles.tabTextActive]}>{s.label}</Text>
            </Pressable>
          );
        })}
      </View>

      <ScrollView horizontal={false} contentContainerStyle={styles.grid}>
        {items.map((entry) => {
          const isSelected = entry.id === selected;
          return (
            <Pressable
              key={entry.id}
              accessibilityRole="button"
              accessibilityLabel={entry.alt}
              accessibilityState={{ selected: isSelected }}
              disabled={disabled}
              onPress={() => onChange(entry.id)}
              style={[styles.cell, isSelected && styles.cellSelected]}
            >
              <AvatarImage avatarId={entry.id} size={56} accessibilityLabel="" />
              <Text style={styles.label}>{entry.label}</Text>
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 12 },
  previewRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  heading: { color: theme.colors.text, fontSize: 17, fontWeight: "800" },
  sub: { color: theme.colors.muted, fontSize: 13, marginTop: 2 },
  tabs: { flexDirection: "row", gap: 8, flexWrap: "wrap" },
  tab: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  tabActive: {
    borderColor: theme.colors.gold || "#f59e0b",
    backgroundColor: "rgba(245,158,11,0.14)",
  },
  tabText: { color: theme.colors.text, fontSize: 13, fontWeight: "600" },
  tabTextActive: { fontWeight: "800" },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  cell: {
    width: "30%",
    minWidth: 96,
    flexGrow: 1,
    alignItems: "center",
    gap: 6,
    padding: 10,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: theme.colors.border,
    backgroundColor: "rgba(0,0,0,0.18)",
  },
  cellSelected: {
    borderColor: theme.colors.gold || "#f59e0b",
    borderWidth: 2,
    backgroundColor: "rgba(245,158,11,0.12)",
  },
  label: { color: theme.colors.text, fontSize: 12, fontWeight: "700" },
});
