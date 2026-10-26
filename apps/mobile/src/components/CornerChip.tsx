import { StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";

import { theme } from "../theme";

/** One small glass control. Corner actions share this instead of a row of buttons. */
export default function CornerChip({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
}) {
  return <View style={[styles.chip, style]}>{children}</View>;
}

const styles = StyleSheet.create({
  chip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
    minHeight: 32,
    borderRadius: theme.radius.pill,
    backgroundColor: "rgba(10, 14, 24, 0.62)",
    borderWidth: 1,
    borderColor: "rgba(232, 200, 114, 0.75)",
  },
});
