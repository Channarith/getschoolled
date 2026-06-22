import { useEffect, useState } from "react";
import {
  Alert, Pressable, ScrollView, StyleSheet, Switch, Text,
  TouchableOpacity, View,
} from "react-native";

import {
  ensurePermissions, fireImmediate, listScheduled,
  rescheduleDailyReminder,
} from "../notifications";
import {
  DEFAULT_SETTINGS, getSettings, setSettings, type Settings,
} from "../storage";
import { LANGUAGES, languageInfo, useT } from "../i18n";

export default function SettingsScreen() {
  const { t, locale, setLocale } = useT();
  const [s, setS] = useState<Settings>(DEFAULT_SETTINGS);
  const [permission, setPermission] = useState<"unknown" | "granted" | "denied">("unknown");
  const [scheduled, setScheduled] = useState<number>(0);

  const refreshScheduled = async () => {
    try { setScheduled((await listScheduled()).length); } catch {}
  };

  useEffect(() => {
    void getSettings().then(setS);
    void refreshScheduled();
  }, []);

  const update = (patch: Partial<Settings>): void => {
    setS((cur) => {
      const next = { ...cur, ...patch };
      void setSettings(patch).then(async () => {
        if ("dailyReminder" in patch || "dailyReminderHour" in patch
            || "notificationsEnabled" in patch) {
          await rescheduleDailyReminder(next);
          await refreshScheduled();
        }
      });
      return next;
    });
  };

  const askPermission = async () => {
    const ok = await ensurePermissions();
    setPermission(ok ? "granted" : "denied");
    if (ok) {
      await rescheduleDailyReminder();
      await refreshScheduled();
    } else {
      Alert.alert(t("settings.permDeniedTitle"), t("settings.permDeniedBody"));
    }
  };

  const sendTest = async () => {
    const ok = await ensurePermissions();
    if (!ok) {
      Alert.alert(t("settings.permRequiredTitle"), t("settings.permRequiredBody"));
      return;
    }
    await fireImmediate(t("settings.testTitle"), t("settings.testBody"));
    await refreshScheduled();
  };

  const current = languageInfo(locale);
  return (
    <ScrollView style={styles.bg} contentContainerStyle={{ paddingTop: 56, paddingBottom: 32 }}>
      <View style={styles.header}>
        <Text style={styles.title}>{t("settings.title")}</Text>
        <Text style={styles.sub}>{t("settings.sub")}</Text>
      </View>

      <Section title={t("settings.sectionLang")}>
        <Row label={t("settings.language")} desc={t("settings.languageDesc")}>
          <Text style={styles.currentLang}>{current.flag}  {current.native}</Text>
        </Row>
        <View style={{ paddingHorizontal: 10, paddingBottom: 10 }}>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            {LANGUAGES.map((lang) => {
              const selected = lang.code === locale;
              return (
                <TouchableOpacity key={lang.code} activeOpacity={0.7}
                  accessibilityRole="button"
                  accessibilityState={{ selected }}
                  onPress={() => setLocale(lang.code)}
                  style={[styles.langChip, selected ? styles.langChipOn : styles.langChipOff]}
                >
                  <Text style={[styles.langText, selected && styles.langTextOn]}>
                    {lang.flag} {lang.native}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>
      </Section>

      <Section title={t("settings.sectionNotif")}>
        <Row label={t("settings.allow")} desc={t("settings.allowDesc")}>
          <Switch
            value={s.notificationsEnabled}
            onValueChange={(v) => update({ notificationsEnabled: v })}
            thumbColor={s.notificationsEnabled ? "#0ea5e9" : "#666"} />
        </Row>
        <Row label={t("settings.daily")}
             desc={t("settings.dailyDesc", { hour: pad(s.dailyReminderHour) })}>
          <Switch
            value={s.dailyReminder && s.notificationsEnabled}
            onValueChange={(v) => update({ dailyReminder: v })}
            disabled={!s.notificationsEnabled}
            thumbColor={s.dailyReminder ? "#0ea5e9" : "#666"} />
        </Row>
        <View style={[styles.row, { flexDirection: "column", alignItems: "stretch", gap: 8 }]}>
          <Text style={styles.label}>{t("settings.time")}</Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            {[7, 9, 12, 15, 18, 20, 21].map((h) => {
              const selected = s.dailyReminderHour === h;
              return (
                <TouchableOpacity key={h} activeOpacity={0.7}
                  accessibilityRole="button"
                  accessibilityState={{ selected }}
                  onPress={() => update({ dailyReminderHour: h })}
                  style={[
                    styles.hourChip,
                    selected ? styles.hourChipOn : styles.hourChipOff,
                  ]}
                >
                  <Text style={[styles.hourText, selected && styles.hourTextOn]}>
                    {pad(h)}:00
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>
        <Row label={t("settings.newAlerts")} desc={t("settings.newAlertsDesc")}>
          <Switch
            value={s.newContentAlerts && s.notificationsEnabled}
            onValueChange={(v) => update({ newContentAlerts: v })}
            disabled={!s.notificationsEnabled}
            thumbColor={s.newContentAlerts ? "#0ea5e9" : "#666"} />
        </Row>
        <Row label={t("settings.completion")} desc={t("settings.completionDesc")}>
          <Switch
            value={s.completionAlerts && s.notificationsEnabled}
            onValueChange={(v) => update({ completionAlerts: v })}
            disabled={!s.notificationsEnabled}
            thumbColor={s.completionAlerts ? "#0ea5e9" : "#666"} />
        </Row>
      </Section>

      <Section title={t("settings.sectionDiag")}>
        <Row label={t("settings.scheduled", { n: scheduled })} desc={t("settings.scheduledDesc")}>
          <Pressable onPress={() => void refreshScheduled()} style={styles.btn}>
            <Text style={styles.btnText}>{t("settings.refresh")}</Text>
          </Pressable>
        </Row>
        <Row label={t("settings.testAlert")} desc={t("settings.testAlertDesc")}>
          <Pressable onPress={() => void sendTest()} style={styles.btn}>
            <Text style={styles.btnText}>{t("settings.send")}</Text>
          </Pressable>
        </Row>
        <Row label={t("settings.permission", { status: permission })}
             desc={t("settings.permissionDesc")}>
          <Pressable onPress={() => void askPermission()} style={styles.btn}>
            <Text style={styles.btnText}>{t("settings.request")}</Text>
          </Pressable>
        </Row>
      </Section>

      <Section title={t("settings.sectionAbout")}>
        <Text style={styles.about}>{t("settings.aboutBody")}</Text>
      </Section>
    </ScrollView>
  );
}

function pad(n: number) { return String(n).padStart(2, "0"); }

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {children}
    </View>
  );
}

function Row({ label, desc, children }: {
  label: string; desc?: string; children?: React.ReactNode;
}) {
  return (
    <View style={styles.row}>
      <View style={{ flex: 1, marginRight: 12 }}>
        <Text style={styles.label}>{label}</Text>
        {desc ? <Text style={styles.desc}>{desc}</Text> : null}
      </View>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  bg: { backgroundColor: "#0b1020", flex: 1 },
  header: { paddingHorizontal: 16, paddingBottom: 16 },
  title: { color: "#e8ecf6", fontSize: 24, fontWeight: "800" },
  sub: { color: "#9aa6c2", marginTop: 4 },
  section: { marginHorizontal: 12, marginBottom: 14, backgroundColor: "#151c34", borderRadius: 14, padding: 8 },
  sectionTitle: { color: "#9aa6c2", fontSize: 12, fontWeight: "800", letterSpacing: 1, textTransform: "uppercase", margin: 8 },
  row: { flexDirection: "row", alignItems: "center", padding: 10 },
  label: { color: "#e8ecf6", fontWeight: "700" },
  desc: { color: "#9aa6c2", marginTop: 4, fontSize: 12, lineHeight: 16 },
  btn: { backgroundColor: "#1d2746", paddingHorizontal: 14, paddingVertical: 8, borderRadius: 999 },
  btnText: { color: "#0ea5e9", fontWeight: "700" },
  hourChip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999 },
  hourChipOff: { backgroundColor: "#1d2746" },
  hourChipOn: { backgroundColor: "#0ea5e9" },
  hourText: { color: "#9aa6c2", fontWeight: "700" },
  hourTextOn: { color: "#001022" },
  about: { color: "#9aa6c2", padding: 10, lineHeight: 18, fontSize: 13 },
  currentLang: { color: "#e8ecf6", fontWeight: "700" },
  langChip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999 },
  langChipOff: { backgroundColor: "#1d2746" },
  langChipOn: { backgroundColor: "#0ea5e9" },
  langText: { color: "#9aa6c2", fontWeight: "600" },
  langTextOn: { color: "#001022", fontWeight: "800" },
});
