import { useCallback, useEffect, useState } from "react";
import {
  Alert, ScrollView, StyleSheet, Switch, Text, TextInput, View,
} from "react-native";

import { CURRICULUM_URL, IDENTITY_URL, checkServiceReachable, getMe, listStudents, login, signup,
  type Account, type StudentProfile,
} from "../api";
import AnimatedPressable from "../components/AnimatedPressable";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { DEPLOY_MODE, QA_TEST_ACCOUNTS } from "../config";
import {
  ensurePermissions, fireImmediate, listScheduled,
  rescheduleDailyReminder,
} from "../notifications";
import {
  markNotDriving, requestDrivingPermissions, type DrivingStatus,
} from "../drivingDetection";
import {
  DEFAULT_SETTINGS, clearAuthToken, getSettings, setAuthToken, setSettings,
  type Settings,
} from "../storage";
import {
  NARRATION_VOICE_LABELS, NARRATION_VOICE_STYLES, type NarrationVoicePref,
} from "../voiceProfiles";
import { LANGUAGES, languageInfo, useT } from "../i18n";
import { theme } from "../theme";

type Props = {
  onAuthChange?: () => void;
  onOpenLearningProfile?: () => void;
  drivingStatus?: DrivingStatus;
  onDrivingSettingsChange?: () => void;
};

export default function SettingsScreen({
  onAuthChange, onOpenLearningProfile, drivingStatus, onDrivingSettingsChange,
}: Props) {
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
  const [identityUp, setIdentityUp] = useState<boolean | null>(null);

  const probeIdentity = useCallback(async () => {
    const up = await checkServiceReachable(IDENTITY_URL);
    setIdentityUp(up);
    return up;
  }, []);

  const backendDownMessage = useCallback((url: string) => {
    const host = url.replace("http://", "");
    return DEPLOY_MODE === "local"
      ? t("auth.backendDownLocal", { url: host })
      : t("auth.backendDownCloud", { url: host });
  }, [t]);

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
    void probeIdentity();
  }, [refreshAccount, probeIdentity]);

  const update = (patch: Partial<Settings>): void => {
    setS((cur) => {
      const next = { ...cur, ...patch };
      void setSettings(patch).then(async () => {
        if ("dailyReminder" in patch || "dailyReminderHour" in patch
            || "notificationsEnabled" in patch) {
          await rescheduleDailyReminder(next);
          await refreshScheduled();
        }
        if ("driveDetectionEnabled" in patch || "driveUseLocation" in patch
            || "driveUseMotionSensors" in patch || "driveAutoLaunch" in patch
            || "driveDrivingAlerts" in patch) {
          onDrivingSettingsChange?.();
        }
      });
      return next;
    });
  };

  async function toggleDriveDetection(enabled: boolean) {
    if (!enabled) {
      update({ driveDetectionEnabled: false });
      return;
    }
    const perms = await requestDrivingPermissions({
      location: s.driveUseLocation,
      motion: s.driveUseMotionSensors,
    });
    if (!perms.location && !perms.motion) {
      Alert.alert(t("settings.drivePermsDeniedTitle"), t("settings.drivePermsDeniedBody"));
      return;
    }
    setS((cur) => {
      const next = {
        ...cur,
        driveDetectionEnabled: true,
        driveUseLocation: perms.location && cur.driveUseLocation,
        driveUseMotionSensors: perms.motion && cur.driveUseMotionSensors,
      };
      void setSettings({
        driveDetectionEnabled: true,
        driveUseLocation: next.driveUseLocation,
        driveUseMotionSensors: next.driveUseMotionSensors,
      }).then(() => onDrivingSettingsChange?.());
      return next;
    });
  }

  async function requestDrivePermissions() {
    const perms = await requestDrivingPermissions({
      location: true,
      motion: true,
    });
    if (!perms.location && !perms.motion) {
      Alert.alert(t("settings.drivePermsDeniedTitle"), t("settings.drivePermsDeniedBody"));
      return;
    }
    update({
      driveUseLocation: perms.location,
      driveUseMotionSensors: perms.motion,
    });
  }

  const drivePhase = drivingStatus?.phase ?? "unknown";
  const driveStatusText = drivePhase === "driving"
    ? t("settings.driveStatusDriving")
    : drivePhase === "idle"
      ? t("settings.driveStatusIdle")
      : t("settings.driveStatusUnknown");
  const locPerm = drivingStatus?.locationGranted ? "granted" : "off";
  const motionPerm = drivingStatus?.motionGranted ? "granted" : "off";

  async function onAuthSubmit() {
    setAuthBusy(true);
    setAuthError("");
    try {
      const up = await probeIdentity();
      if (!up) {
        setAuthError(backendDownMessage(IDENTITY_URL));
        return;
      }
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
            <View style={{ gap: 10, marginTop: 8 }}>
              <PrimaryButton label={t("settings.openSurvey")} onPress={onOpenLearningProfile} variant="brand" />
              <PrimaryButton label={t("settings.signOut")} onPress={() => void onSignOut()} variant="ghost" />
            </View>
          </>
        ) : (
          <>
            <Text style={styles.about}>{t("settings.accountGuest")}</Text>
            <View style={{ gap: 10, marginTop: 8 }}>
              {mode === "signup" ? (
                <TextInput
                  style={styles.input}
                  placeholder={t("auth.displayName")}
                  placeholderTextColor={theme.colors.muted}
                  value={displayName}
                  onChangeText={setDisplayName}
                />
              ) : null}
              <TextInput
                style={styles.input}
                placeholder={t("auth.email")}
                placeholderTextColor={theme.colors.muted}
                autoCapitalize="none"
                keyboardType="email-address"
                value={email}
                onChangeText={setEmail}
              />
              <TextInput
                style={styles.input}
                placeholder={t("auth.password")}
                placeholderTextColor={theme.colors.muted}
                secureTextEntry
                value={password}
                onChangeText={setPassword}
              />
              {authError ? <Text style={styles.error}>{authError}</Text> : null}
              <PrimaryButton
                label={mode === "login" ? t("auth.signIn") : t("auth.signUp")}
                onPress={() => void onAuthSubmit()}
                loading={authBusy}
                disabled={authBusy}
              />
              <AnimatedPressable onPress={() => setMode(mode === "login" ? "signup" : "login")}>
                <Text style={styles.link}>
                  {mode === "login" ? t("auth.createAccount") : t("auth.haveAccount")}
                </Text>
              </AnimatedPressable>
            </View>
            {__DEV__ ? (
              <View style={{ marginTop: 12 }}>
                <Text style={styles.desc}>{t("auth.qaHint")}</Text>
                <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
                  {QA_TEST_ACCOUNTS.map((qa) => (
                    <AnimatedPressable key={qa.email} onPress={() => void fillQa(qa.email, qa.password)}
                      style={styles.qaChip}>
                      <Text style={styles.qaText}>{t("auth.useQa", { label: qa.label })}</Text>
                    </AnimatedPressable>
                  ))}
                </View>
              </View>
            ) : null}
          </>
        )}
        <Text style={[
          styles.desc,
          { marginTop: 10 },
          identityUp === false && styles.backendDown,
          identityUp === true && styles.backendUp,
        ]}>
          {identityUp === false
            ? backendDownMessage(IDENTITY_URL)
            : identityUp === true
              ? `${t("auth.backendUp")} · ${t("settings.backendUrls", {
                curriculum: CURRICULUM_URL.replace("http://", ""),
                identity: IDENTITY_URL.replace("http://", ""),
              })}`
              : t("settings.backendUrls", {
                curriculum: CURRICULUM_URL.replace("http://", ""),
                identity: IDENTITY_URL.replace("http://", ""),
              })}
        </Text>
      </Section>

      <Section title={t("settings.sectionLang")}>
        <Row label={t("settings.language")} desc={t("settings.languageDesc")}>
          <Text style={styles.currentLang}>{current.flag}  {current.native}</Text>
        </Row>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            {LANGUAGES.map((lang) => {
              const selected = lang.code === locale;
              return (
                <AnimatedPressable
                  key={lang.code}
                  accessibilityRole="button"
                  accessibilityState={{ selected }}
                  onPress={() => setLocale(lang.code)}
                  style={[styles.langChip, selected ? styles.langChipOn : styles.langChipOff]}
                >
                  <Text style={[styles.langText, selected && styles.langTextOn]}>
                    {lang.flag} {lang.native}
                  </Text>
                </AnimatedPressable>
              );
            })}
          </View>
      </Section>

      <Section title={t("settings.sectionNarration")}>
        <Text style={styles.desc}>{t("settings.narrationDesc")}</Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
          {(["auto", ...NARRATION_VOICE_STYLES] as NarrationVoicePref[]).map((style) => {
            const selected = s.narrationVoicePref === style;
            const label = style === "auto"
              ? t("settings.narrationAuto")
              : NARRATION_VOICE_LABELS[style];
            return (
              <AnimatedPressable
                key={style}
                accessibilityRole="button"
                accessibilityState={{ selected }}
                onPress={() => update({ narrationVoicePref: style })}
                style={[styles.langChip, selected ? styles.langChipOn : styles.langChipOff]}
              >
                <Text style={[styles.langText, selected && styles.langTextOn]}>{label}</Text>
              </AnimatedPressable>
            );
          })}
        </View>
      </Section>

      <Section title={t("settings.sectionDrive")}>
        <Row label={t("settings.driveStatus", { status: driveStatusText })}
             desc={drivingStatus?.speedMph != null
               ? `${Math.round(drivingStatus.speedMph)} mph`
               : undefined}>
          {drivePhase === "driving" ? (
            <AnimatedPressable onPress={() => markNotDriving()} style={styles.btn}>
              <Text style={styles.btnText}>{t("settings.driveNotDriving")}</Text>
            </AnimatedPressable>
          ) : null}
        </Row>
        <Row label={t("settings.driveDetect")} desc={t("settings.driveDetectDesc")}>
          <Switch
            value={s.driveDetectionEnabled}
            onValueChange={(v) => void toggleDriveDetection(v)}
            thumbColor={s.driveDetectionEnabled ? theme.colors.netflix : "#666"} />
        </Row>
        <Row label={t("settings.driveLocation")} desc={t("settings.driveLocationDesc")}>
          <Switch
            value={s.driveUseLocation && s.driveDetectionEnabled}
            onValueChange={(v) => update({ driveUseLocation: v })}
            disabled={!s.driveDetectionEnabled}
            thumbColor={s.driveUseLocation ? theme.colors.netflix : "#666"} />
        </Row>
        <Row label={t("settings.driveMotion")} desc={t("settings.driveMotionDesc")}>
          <Switch
            value={s.driveUseMotionSensors && s.driveDetectionEnabled}
            onValueChange={(v) => update({ driveUseMotionSensors: v })}
            disabled={!s.driveDetectionEnabled}
            thumbColor={s.driveUseMotionSensors ? theme.colors.netflix : "#666"} />
        </Row>
        <Row label={t("settings.driveAutoLaunch")} desc={t("settings.driveAutoLaunchDesc")}>
          <Switch
            value={s.driveAutoLaunch && s.driveDetectionEnabled}
            onValueChange={(v) => update({ driveAutoLaunch: v })}
            disabled={!s.driveDetectionEnabled}
            thumbColor={s.driveAutoLaunch ? theme.colors.netflix : "#666"} />
        </Row>
        <Row label={t("settings.driveAlerts")} desc={t("settings.driveAlertsDesc")}>
          <Switch
            value={s.driveDrivingAlerts && s.driveDetectionEnabled && s.notificationsEnabled}
            onValueChange={(v) => update({ driveDrivingAlerts: v })}
            disabled={!s.driveDetectionEnabled || !s.notificationsEnabled}
            thumbColor={s.driveDrivingAlerts ? theme.colors.netflix : "#666"} />
        </Row>
        <Row label={t("settings.drivePerms")}
             desc={t("settings.drivePermsDesc", { location: locPerm, motion: motionPerm })}>
          <AnimatedPressable onPress={() => void requestDrivePermissions()} style={styles.btn}>
            <Text style={styles.btnText}>{t("settings.request")}</Text>
          </AnimatedPressable>
        </Row>
      </Section>

      <Section title={t("settings.sectionNotif")}>
        <Row label={t("settings.allow")} desc={t("settings.allowDesc")}>
          <Switch
            value={s.notificationsEnabled}
            onValueChange={(v) => update({ notificationsEnabled: v })}
            thumbColor={s.notificationsEnabled ? theme.colors.netflix : "#666"} />
        </Row>
        <Row label={t("settings.daily")}
             desc={t("settings.dailyDesc", { hour: pad(s.dailyReminderHour) })}>
          <Switch
            value={s.dailyReminder && s.notificationsEnabled}
            onValueChange={(v) => update({ dailyReminder: v })}
            disabled={!s.notificationsEnabled}
            thumbColor={s.dailyReminder ? theme.colors.netflix : "#666"} />
        </Row>
        <View style={[styles.row, { flexDirection: "column", alignItems: "stretch", gap: 8 }]}>
          <Text style={styles.label}>{t("settings.time")}</Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            {[7, 9, 12, 15, 18, 20, 21].map((h) => {
              const selected = s.dailyReminderHour === h;
              return (
                <AnimatedPressable
                  key={h}
                  accessibilityRole="button"
                  accessibilityState={{ selected }}
                  onPress={() => update({ dailyReminderHour: h })}
                  style={[styles.hourChip, selected ? styles.hourChipOn : styles.hourChipOff]}
                >
                  <Text style={[styles.hourText, selected && styles.hourTextOn]}>
                    {pad(h)}:00
                  </Text>
                </AnimatedPressable>
              );
            })}
          </View>
        </View>
        <Row label={t("settings.newAlerts")} desc={t("settings.newAlertsDesc")}>
          <Switch
            value={s.newContentAlerts && s.notificationsEnabled}
            onValueChange={(v) => update({ newContentAlerts: v })}
            disabled={!s.notificationsEnabled}
            thumbColor={s.newContentAlerts ? theme.colors.netflix : "#666"} />
        </Row>
        <Row label={t("settings.completion")} desc={t("settings.completionDesc")}>
          <Switch
            value={s.completionAlerts && s.notificationsEnabled}
            onValueChange={(v) => update({ completionAlerts: v })}
            disabled={!s.notificationsEnabled}
            thumbColor={s.completionAlerts ? theme.colors.netflix : "#666"} />
        </Row>
      </Section>

      <Section title={t("settings.sectionDiag")}>
        <Row label={t("settings.scheduled", { n: scheduled })} desc={t("settings.scheduledDesc")}>
          <AnimatedPressable onPress={() => void refreshScheduled()} style={styles.btn}>
            <Text style={styles.btnText}>{t("settings.refresh")}</Text>
          </AnimatedPressable>
        </Row>
        <Row label={t("settings.testAlert")} desc={t("settings.testAlertDesc")}>
          <AnimatedPressable onPress={() => void sendTest()} style={styles.btn}>
            <Text style={styles.btnText}>{t("settings.send")}</Text>
          </AnimatedPressable>
        </Row>
        <Row label={t("settings.permission", { status: permission })}
             desc={t("settings.permissionDesc")}>
          <AnimatedPressable onPress={() => void askPermission()} style={styles.btn}>
            <Text style={styles.btnText}>{t("settings.request")}</Text>
          </AnimatedPressable>
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
    <GlassPanel style={styles.section} padded={false}>
      <Text style={styles.sectionTitle}>{title}</Text>
      <View style={{ padding: 10 }}>{children}</View>
    </GlassPanel>
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
  bg: { flex: 1, backgroundColor: "transparent" },
  header: { paddingHorizontal: theme.spacing.screenX, paddingBottom: 16 },
  title: { ...theme.typography.title, color: theme.colors.text },
  sub: { color: theme.colors.muted, marginTop: 4 },
  section: { marginHorizontal: 12, marginBottom: 14 },
  sectionTitle: {
    ...theme.typography.kicker,
    color: theme.colors.muted,
    margin: 12,
    marginBottom: 0,
  },
  row: { flexDirection: "row", alignItems: "center", paddingVertical: 10 },
  label: { color: theme.colors.text, fontWeight: "700" },
  desc: { color: theme.colors.muted, marginTop: 4, fontSize: 12, lineHeight: 16 },
  btn: {
    backgroundColor: "rgba(29, 39, 70, 0.85)",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: theme.radius.pill,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  btnText: { color: theme.colors.text, fontWeight: "700" },
  link: { color: theme.colors.accent, textAlign: "center", paddingVertical: 8 },
  input: {
    backgroundColor: "rgba(29, 39, 70, 0.75)",
    color: theme.colors.text,
    borderRadius: theme.radius.md,
    paddingHorizontal: 12,
    paddingVertical: 12,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  error: { color: "#ff8a8a", fontSize: 13 },
  backendDown: { color: "#ff8a8a" },
  backendUp: { color: theme.colors.success },
  qaChip: {
    backgroundColor: "rgba(29, 39, 70, 0.75)",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: theme.radius.pill,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  qaText: { color: theme.colors.muted, fontSize: 12, fontWeight: "600" },
  hourChip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: theme.radius.pill },
  hourChipOff: { backgroundColor: "rgba(29, 39, 70, 0.75)", borderWidth: 1, borderColor: theme.colors.border },
  hourChipOn: { backgroundColor: theme.colors.netflix },
  hourText: { color: theme.colors.muted, fontWeight: "700" },
  hourTextOn: { color: "#fff" },
  about: { color: theme.colors.muted, lineHeight: 18, fontSize: 13 },
  currentLang: { color: theme.colors.text, fontWeight: "700" },
  langChip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: theme.radius.pill },
  langChipOff: { backgroundColor: "rgba(29, 39, 70, 0.75)", borderWidth: 1, borderColor: theme.colors.border },
  langChipOn: { backgroundColor: theme.colors.netflix },
  langText: { color: theme.colors.muted, fontWeight: "600" },
  langTextOn: { color: "#fff", fontWeight: "800" },
});
