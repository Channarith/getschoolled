import { StyleSheet, Text, View } from "react-native";

import { useT } from "../i18n";
import { theme } from "../theme";
import VoicePicker from "./VoicePicker";

/** Bottom of the main page, like the site's profile menu: the one voice control. The voice sets the app language, so there is no language list. */
export default function HomeFooter() {
  const { t } = useT();
  return (
    <View testID="home-footer" style={styles.wrap}>
      <Text style={styles.title}>{t("voice.footerTitle")}</Text>
      <VoicePicker />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 10, paddingHorizontal: theme.spacing.screenX, paddingTop: 24 },
  title: { color: theme.colors.muted, fontSize: 12, fontWeight: "800", letterSpacing: 0.6, textTransform: "uppercase" },
});
