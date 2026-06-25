import { ActivityIndicator, StyleSheet, Text } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import AnimatedPressable from "./AnimatedPressable";
import { theme } from "../theme";

type Props = {
  label: string;
  onPress?: () => void;
  disabled?: boolean;
  loading?: boolean;
  variant?: "netflix" | "brand" | "ghost";
};

export default function PrimaryButton({
  label, onPress, disabled, loading, variant = "netflix",
}: Props) {
  const busy = disabled || loading;
  if (variant === "ghost") {
    return (
      <AnimatedPressable
        disabled={busy}
        onPress={onPress}
        style={[styles.ghost, busy && styles.disabled]}
      >
        <Text style={styles.ghostText}>{loading ? "…" : label}</Text>
      </AnimatedPressable>
    );
  }

  const colors =
    variant === "netflix"
      ? [theme.colors.netflix, theme.colors.netflixDark]
      : [theme.colors.brand, "#0284c7"];

  return (
    <AnimatedPressable disabled={busy} onPress={onPress} style={busy && styles.disabled}>
      <LinearGradient colors={colors} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.btn}>
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.label}>{label}</Text>
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
  label: { color: "#fff", fontWeight: "800", fontSize: 16, letterSpacing: 0.3 },
  ghost: {
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.35)",
    paddingVertical: 12,
    alignItems: "center",
  },
  ghostText: { color: theme.colors.text, fontWeight: "700" },
  disabled: { opacity: 0.55 },
});
