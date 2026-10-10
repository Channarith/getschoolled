import { ActivityIndicator, StyleSheet, Text, useWindowDimensions } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import AnimatedPressable from "./AnimatedPressable";
import { theme } from "../theme";

type Props = {
  label: string;
  onPress?: () => void;
  disabled?: boolean;
  loading?: boolean;
  variant?: "netflix" | "brand" | "ghost";
  /** Forwarded to the underlying Pressable for E2E (Maestro) targeting. */
  testID?: string;
};

export default function PrimaryButton({
  label, onPress, disabled, loading, variant = "netflix", testID,
}: Props) {
  const busy = disabled || loading;
  const { width } = useWindowDimensions();
  const textMax = { maxWidth: Math.max(140, width - 64) };
  if (variant === "ghost") {
    return (
      <AnimatedPressable
        testID={testID}
        disabled={busy}
        onPress={onPress}
        style={[styles.ghost, busy && styles.disabled]}
      >
        <Text style={[styles.ghostText, textMax]}>{loading ? "…" : label}</Text>
      </AnimatedPressable>
    );
  }

  const colors =
    variant === "netflix"
      ? [theme.colors.netflix, theme.colors.netflixDark]
      : [theme.colors.brand, "#0284c7"];

  return (
    <AnimatedPressable testID={testID} disabled={busy} onPress={onPress} style={busy && styles.disabled}>
      <LinearGradient colors={colors} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.btn}>
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={[styles.label, textMax]}>{label}</Text>
        )}
      </LinearGradient>
    </AnimatedPressable>
  );
}

const styles = StyleSheet.create({
  btn: {
    borderRadius: theme.radius.md,
    paddingVertical: 14,
    paddingHorizontal: 20,
    alignItems: "center",
    ...theme.shadow.card,
  },
  label: { color: "#fff", fontWeight: "800", fontSize: 16, lineHeight: 20, textAlign: "center" },
  ghost: {
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.35)",
    paddingVertical: 12,
    paddingHorizontal: 12,
    alignItems: "center",
  },
  ghostText: { color: theme.colors.text, fontWeight: "700", lineHeight: 18, textAlign: "center" },
  disabled: { opacity: 0.55 },
});
