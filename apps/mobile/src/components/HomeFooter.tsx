import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { LANGUAGES, languageInfo, useT, type LocaleCode } from "../i18n";
import { theme } from "../theme";
import DropdownListSelector from "./DropdownListSelector";
import VoicePicker from "./VoicePicker";

/** Bottom of the main page, like the site's footer: the app language, then the voices and genders we support. */
export default function HomeFooter() {
  const { t, locale, setLocale } = useT();
  const [open, setOpen] = useState(false);
  const current = languageInfo(locale);
  return (
    <View testID="home-footer" style={styles.wrap}>
      <Text style={styles.title}>{t("voice.footerTitle")}</Text>
      <DropdownListSelector
        title={t("settings.language")}
        selectedLabel={`${current.flag} ${current.native}`}
        selectedKey={locale}
        options={LANGUAGES.map((lang) => ({ key: lang.code, label: `${lang.flag} ${lang.native}` }))}
        open={open}
        onToggle={() => setOpen((v) => !v)}
        onSelect={(code) => { setLocale(code as LocaleCode); setOpen(false); }}
      />
      <VoicePicker />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 10, paddingHorizontal: theme.spacing.screenX, paddingTop: 24 },
  title: { color: theme.colors.muted, fontSize: 12, fontWeight: "800", letterSpacing: 0.6, textTransform: "uppercase" },
});
