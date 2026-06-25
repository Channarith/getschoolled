import { StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";

import { theme } from "../theme";

type Props = {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  padded?: boolean;
};

export default function GlassPanel({ children, style, padded = true }: Props) {
  return (
    <View style={[styles.panel, padded && styles.padded, style]}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  panel: {
    backgroundColor: theme.colors.glass,
    borderRadius: theme.radius.lg,
    borderWidth: 1,
    borderColor: theme.colors.border,
    overflow: "hidden",
    ...theme.shadow.card,
  },
  padded: { padding: 12 },
});
