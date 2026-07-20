import { ScrollView, StyleSheet, Text, View } from "react-native";

import AnimatedPressable from "./AnimatedPressable";
import GlassPanel from "./GlassPanel";
import { theme } from "../theme";

export type DropdownOption = {
  key: string;
  label: string;
};

type Props = {
  title: string;
  selectedLabel: string;
  selectedKey: string;
  options: DropdownOption[];
  open: boolean;
  onToggle: () => void;
  onSelect: (key: string) => void;
  maxHeight?: number;
};

export default function DropdownListSelector({
  title,
  selectedLabel,
  selectedKey,
  options,
  open,
  onToggle,
  onSelect,
  maxHeight = 260,
}: Props) {
  return (
    <GlassPanel style={styles.panel} padded={false}>
      <AnimatedPressable
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        onPress={onToggle}
        style={styles.header}
      >
        <View style={styles.headerBody}>
          <Text style={styles.title}>{title}</Text>
          <Text numberOfLines={1} style={styles.selected}>{selectedLabel}</Text>
        </View>
        <Text style={styles.chevron}>{open ? "▲" : "▼"}</Text>
      </AnimatedPressable>
      {open ? (
        <ScrollView nestedScrollEnabled style={[styles.options, { maxHeight }]}>
          {options.map((opt) => {
            const selected = opt.key === selectedKey;
            return (
              <AnimatedPressable
                key={opt.key}
                accessibilityRole="button"
                accessibilityState={{ selected }}
                onPress={() => onSelect(opt.key)}
                style={[styles.option, selected && styles.optionSelected]}
              >
                <Text style={[styles.optionLabel, selected && styles.optionLabelSelected]}>
                  {opt.label}
                </Text>
                {selected ? <Text style={styles.tick}>✓</Text> : null}
              </AnimatedPressable>
            );
          })}
        </ScrollView>
      ) : null}
    </GlassPanel>
  );
}

const styles = StyleSheet.create({
  panel: { overflow: "hidden" },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  headerBody: { flex: 1, marginRight: 8 },
  title: {
    color: theme.colors.muted,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.4,
  },
  selected: {
    color: theme.colors.text,
    fontSize: 15,
    fontWeight: "700",
    marginTop: 2,
  },
  chevron: { color: theme.colors.muted, fontSize: 12, fontWeight: "800" },
  options: {
    borderTopWidth: 1,
    borderTopColor: theme.colors.border,
    backgroundColor: "rgba(0,0,0,0.18)",
  },
  option: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 12,
    paddingVertical: 11,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(255,255,255,0.06)",
  },
  optionSelected: { backgroundColor: "rgba(229, 9, 20, 0.16)" },
  optionLabel: { color: theme.colors.text, fontSize: 14, fontWeight: "600", flex: 1, marginRight: 8 },
  optionLabelSelected: { color: "#fff", fontWeight: "800" },
  tick: { color: theme.colors.netflix, fontWeight: "900" },
});
