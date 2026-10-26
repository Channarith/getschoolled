import { StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { theme } from "../theme";

type Props = {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  padded?: boolean;
};

/** Frosted glass with a gold rim, a thin gold trace, and a light reflection. */
export default function GlassPanel({ children, style, padded = true }: Props) {
  return (
    <View style={[styles.panel, padded && styles.padded, style]}>
      <LinearGradient
        colors={[theme.colors.glassHighlight, "rgba(255,255,255,0.05)", "transparent"]}
        start={{ x: 0, y: 0 }}
        end={{ x: 0.85, y: 1 }}
        style={styles.sheen}
        pointerEvents="none"
      />
      <View style={styles.trace} pointerEvents="none" />
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  panel: {
    backgroundColor: theme.colors.glass,
    borderRadius: theme.radius.lg,
    borderWidth: 1,
    borderColor: "rgba(232, 200, 114, 0.55)",
    overflow: "hidden",
    ...theme.shadow.card,
  },
  padded: { padding: 12 },
  sheen: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 36,
  },
  trace: {
    position: "absolute",
    top: 10,
    bottom: 10,
    left: 0,
    width: 2,
    backgroundColor: theme.colors.goldTrace,
    borderRadius: 2,
  },
});
