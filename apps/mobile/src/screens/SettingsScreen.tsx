import { useCallback, useEffect, useState } from "react";
import {
  Alert, Pressable, ScrollView, StyleSheet, Switch, Text, TextInput,
  TouchableOpacity, View,
} from "react-native";

import {
  CURRICULUM_URL, IDENTITY_URL, getMe, listStudents, login, signup,
  type Account, type StudentProfile,
} from "../api";
import { QA_TEST_ACCOUNTS } from "../config";
import {
  ensurePermissions, fireImmediate, listScheduled,
  rescheduleDailyReminder,
} from "../notifications";
import {
  DEFAULT_SETTINGS, clearAuthToken, getSettings, setAuthToken, setSettings,
  type Settings,
} from "../storage";
import { LANGUAGES, languageInfo, useT } from "../i18n";

type Props = {
  onAuthChange?: () => void;
  onOpenLearningProfile?: () => void;
};

export default function SettingsScreen({ onAuthChange, onOpenLearningProfile }: Props) {
  const { t, locale, setLocale } = useT();
  const [s, setS] = useState<Settings>(DEFAULT_SETTINGS);
  const [permission, setPermission] = useState<"unknown" | "granted" | "denied">("unknown");
  const [scheduled, setScheduled] = useState<number>(0);
  const [account, setAccount] = useState<Account | null>(null);
  const [student, setStudent] = useState<StudentProfile | null>(null);
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState("");

  const refreshAccount = useCallback(async () => {
    try {
      const me = await getMe();
      setAccount(me);
      const students = (await listStudents()).students;
      setStudent(students[0] ?? null);
    } catch {
      setAccount(null);
      setStudent(null);
    }
  }, []);

  const refreshScheduled = async () => {
    try { setScheduled((await listScheduled()).length); } catch {}
  };

  useEffect(() => {
    void getSettings().then(setS);
    void refreshScheduled();
    void refreshAccount();
  }, [refreshAccount]);

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

  async function onAuthSubmit() {
    setAuthBusy(true);
    setAuthError("");
    try {
      const res = mode === "login"
        ? await login(email.trim(), password)
        : await signup(email.trim(), password, displayName.trim() || email.split("@")[0]);
      await setAuthToken(res.token);
      setAccount(res.account);
      await refreshAccount();
      onAuthChange?.();
    } catch (e) {
      setAuthError(String(e));
    } finally {
      setAuthBusy(false);
    }
  }

  async function onSignOut() {
    await clearAuthToken();
    setAccount(null);
    setStudent(null);
    onAuthChange?.();
  }

  async function fillQa(qaEmail: string, qaPassword: string) {
    setEmail(qaEmail);
    setPassword(qaPassword);
    setMode("login");
  }

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
  const categoryLabel = student?.learner_category?.replace(/_/g, " ") || "";

  return (
    <ScrollView style={styles.bg} contentContainerStyle={{ paddingTop: 56, paddingBottom: 32 }}>
      <View style={styles.header}>
        <Text style={styles.title}>{t("settings.title")}</Text>
        <Text style={styles.sub}>{t("settings.sub")}</Text>
      </View>

      <Section title={t("settings.sectionAccount")}>
        {account ? (
          <>
            <Text style={styles.about}>{t("settings.accountSignedIn", { email: account.email })}</Text>
            <Text style={styles.about}>
              {student?.onboarding_completed_at
                ? t("settings.learningProfileDone", { category: categoryLabel || "saved" })
                : t("settings.learningProfilePending")}
            </Text>
            <View style={{ padding: 10, gap: 8 }}>
              <Pressable onPress={onOpenLearningProfile} style={styles.btnWide}>
                <Text style={styles.btnText}>{t("settings.openSurvey")}</Text>
              </Pressable>
              <Pressable onPress={() => void onSignOut()} style={styles.btnWide}>
                <Text style={styles.btnTextMuted}>{t("settings.signOut")}</Text>
              </Pressable>
            </View>
          </>
        ) : (
          <>
            <Text style={styles.about}>{t("settings.accountGuest")}</Text>
            <View style={{ paddingHorizontal: 10, gap: 8 }}>
              {mode === "signup" ? (
                <TextInput
                  style={styles.input}
                  placeholder={t("auth.displayName")}
                  placeholderTextColor="#6b7280"
                  value={displayName}
                  onChangeText={setDisplayName}
                />
              ) : null}
              <TextInput
                style={styles.input}
                placeholder={t("auth.email")}
                placeholderTextColor="#6b7280"
                autoCapitalize="none"
                keyboardType="email-address"
                value={email}
                onChangeText={setEmail}
              />
              <TextInput
                style={styles.input}
                placeholder={t("auth.password")}
                placeholderTextColor="#6b7280"
                secureTextEntry
                value={password}
                onChangeText={setPassword}
              />
              {authError ? <Text style={styles.error}>{authError}</Text> : null}
              <Pressable disabled={authBusy} onPress={() => void onAuthSubmit()} style={styles.btnWidePrimary}>
                <Text style={styles.btnTextPrimary}>
                  {authBusy ? "…" : mode === "login" ? t("auth.signIn") : t("auth.signUp")}
                </Text>
              </Pressable>
              <Pressable onPress={() => setMode(mode === "login" ? "signup" : "login")}>
                <Text style={styles.link}>
                  {mode === "login" ? t("auth.createAccount") : t("auth.haveAccount")}
                </Text>
              </Pressable>
            </View>
            {__DEV__ ? (
              <View style={{ padding: 10 }}>
                <Text style={styles.desc}>{t("auth.qaHint")}</Text>
                <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
                  {QA_TEST_ACCOUNTS.map((qa) => (
                    <Pressable key={qa.email} onPress={() => void fillQa(qa.email, qa.password)}
                      style={styles.qaChip}>
                      <Text style={styles.qaText}>{t("auth.useQa", { label: qa.label })}</Text>
                    </Pressable>
                  ))}
                </View>
              </View>
            ) : null}
          </>
        )}
        <Text style={[styles.desc, { padding: 10 }]}>
          {t("settings.backendUrls", {
            curriculum: CURRICULUM_URL.replace("http://", ""),
            identity: IDENTITY_URL.replace("http://", ""),
          })}
        </Text>
      </Section>

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
  btnWide: { backgroundColor: "#1d2746", paddingVertical: 12, borderRadius: 10, alignItems: "center" },
  btnWidePrimary: { backgroundColor: "#0ea5e9", paddingVertical: 12, borderRadius: 10, alignItems: "center" },
  btnText: { color: "#0ea5e9", fontWeight: "700" },
  btnTextMuted: { color: "#9aa6c2", fontWeight: "700" },
  btnTextPrimary: { color: "#001022", fontWeight: "800" },
  link: { color: "#0ea5e9", textAlign: "center", paddingVertical: 8 },
  input: {
    backgroundColor: "#1d2746", color: "#e8ecf6", borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: 10,
  },
  error: { color: "#ff6b6b", fontSize: 13 },
  qaChip: { backgroundColor: "#1d2746", paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999 },
  qaText: { color: "#9aa6c2", fontSize: 12, fontWeight: "600" },
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
