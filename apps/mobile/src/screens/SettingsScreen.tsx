import { useCallback, useEffect, useState } from "react";
import {
  Alert, ScrollView, StyleSheet, Switch, Text, View,
} from "react-native";

import {
  CURRICULUM_URL, IDENTITY_URL, checkServiceReachable, getTtsInstructors, getTtsVoices,
  listStudents, type Instructor, type StudentProfile, type VoiceGroup,
} from "../api";
import { useAuth } from "../auth/AuthContext";
import AnimatedPressable from "../components/AnimatedPressable";
import DropdownListSelector from "../components/DropdownListSelector";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { DEPLOY_MODE } from "../config";
import { useIntroSplash } from "../introSplash";
import {
  ensurePermissions, fireImmediate, listScheduled,
  rescheduleDailyReminder,
} from "../notifications";
import {
  markNotDriving, requestDrivingPermissions, type DrivingStatus,
} from "../drivingDetection";
import {
  DEFAULT_SETTINGS, getSettings, setSettings,
  type Settings, type TrainingLocale,
} from "../storage";
import { TRAINING_LOCALE_LABELS, TRAINING_LOCALES } from "../trainingLocale";
import { applyVoicePrefsToTts, voicePrefsFromSettings } from "../narrationTts";
import { LANGUAGES, languageInfo, useT, type LocaleCode } from "../i18n";
import { theme } from "../theme";
import { APP_VERSION } from "../version";

type Props = {
  onAuthChange?: () => void;
  onOpenLearningProfile?: () => void;
  drivingStatus?: DrivingStatus;
  onDrivingSettingsChange?: () => void;
  guestMode?: boolean;
  onOpenAccount?: () => void;
  onOpenRewards?: () => void;
  onOpenLanguages?: () => void;
  onOpenBilling?: () => void;
  onOpenBugReport?: () => void;
  onSignIn?: () => void;
};

export default function SettingsScreen({
  onAuthChange, onOpenLearningProfile, drivingStatus, onDrivingSettingsChange,
  guestMode = false, onOpenAccount, onOpenRewards, onOpenLanguages, onOpenBilling,
  onOpenBugReport, onSignIn,
}: Props) {
  const { t, locale, setLocale } = useT();
  const { playFullIntro } = useIntroSplash();
  const { account, signOut, refreshAccount } = useAuth();
  const [s, setS] = useState<Settings>(DEFAULT_SETTINGS);
  const [permission, setPermission] = useState<"unknown" | "granted" | "denied">("unknown");
  const [scheduled, setScheduled] = useState<number>(0);
  const [student, setStudent] = useState<StudentProfile | null>(null);
  const [identityUp, setIdentityUp] = useState<boolean | null>(null);
  const [voiceGroups, setVoiceGroups] = useState<VoiceGroup[]>([]);
  const [instructors, setInstructors] = useState<Instructor[]>([]);
  const [localeOpen, setLocaleOpen] = useState(false);
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [instructorOpen, setInstructorOpen] = useState(false);
  const [trainingLocaleOpen, setTrainingLocaleOpen] = useState(false);
  const [hourOpen, setHourOpen] = useState(false);

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

  const refreshStudent = useCallback(async () => {
    try {
      const students = (await listStudents()).students;
      setStudent(students[0] ?? null);
    } catch {
      setStudent(null);
    }
  }, []);

  const refreshScheduled = async () => {
    try { setScheduled((await listScheduled()).length); } catch {}
  };

  useEffect(() => {
    void getSettings().then((settings) => {
      setS(settings);
      applyVoicePrefsToTts(voicePrefsFromSettings(settings));
    });
    void refreshScheduled();
    void refreshStudent();
    void refreshAccount();
    void probeIdentity();
    void getTtsVoices().then((r) => setVoiceGroups(r.groups)).catch(() => setVoiceGroups([]));
    void getTtsInstructors().then((r) => setInstructors(r.instructors)).catch(() => setInstructors([]));
  }, [refreshStudent, refreshAccount, probeIdentity]);

  const update = (patch: Partial<Settings>): void => {
    setS((cur) => {
      const next = { ...cur, ...patch };
      void setSettings(patch).then(async () => {
        if ("voiceId" in patch || "instructorId" in patch || "voiceGender" in patch) {
          applyVoicePrefsToTts({
            voiceId: next.voiceId,
            instructorId: next.instructorId,
            voiceGender: next.voiceGender,
          });
        }
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

  async function onSignOut() {
    await signOut();
    onAuthChange?.();
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
  const voiceOptions = [
    { key: "", label: t("settings.voiceDefault") },
    ...voiceGroups.flatMap((g) => g.voices).map((v) => ({
      key: v.id,
      label: `${v.accent}${v.gender ? ` · ${v.gender === "male" ? "M" : "F"}` : ""}`,
    })),
  ];
  const selectedVoice = voiceOptions.find((v) => v.key === s.voiceId) ?? voiceOptions[0];
  const instructorOptions = [
    { key: "", label: t("settings.instructorAuto") },
    ...instructors.map((p) => ({ key: p.id, label: `${p.emoji} ${p.label}` })),
  ];
  const selectedInstructor = instructorOptions.find((p) => p.key === s.instructorId) ?? instructorOptions[0];
  const trainingLocaleOptions = TRAINING_LOCALES.map((loc) => ({
    key: loc,
    label: TRAINING_LOCALE_LABELS[loc],
  }));
  const selectedTrainingLocale = trainingLocaleOptions.find((loc) => loc.key === s.trainingLocale)
    ?? trainingLocaleOptions[0];
  const reminderHours = [7, 8, 9, 12, 15, 18, 20, 21];
  const selectedReminderHour = `${pad(s.dailyReminderHour)}:00`;

  return (
    <ScrollView style={styles.bg} contentContainerStyle={{ paddingTop: 56, paddingBottom: 32 }}>
      <View style={styles.header}>
        <Text style={styles.title}>{t("settings.title")}</Text>
        <Text style={styles.sub}>{t("settings.sub")}</Text>
      </View>

      <Section title={t("settings.sectionAccount")}>
        {guestMode ? (
          <>
            <Text style={styles.about}>{t("settings.previewBadge")}</Text>
            <View style={{ gap: 10, marginTop: 8 }}>
              <PrimaryButton label={t("preview.signIn")} onPress={onSignIn} variant="netflix" />
            </View>
          </>
        ) : (
          <>
            <Text style={styles.about}>
              {t("settings.accountSignedIn", { email: account?.email || "" })}
            </Text>
            <Text style={styles.about}>
              {student?.onboarding_completed_at
                ? t("settings.learningProfileDone", { category: categoryLabel || "saved" })
                : t("settings.learningProfilePending")}
            </Text>
            <View style={{ gap: 10, marginTop: 8 }}>
              <PrimaryButton label={t("settings.openAccount")} onPress={onOpenAccount} variant="netflix" />
              <PrimaryButton label={t("settings.openRewards")} onPress={onOpenRewards} variant="brand" />
              <PrimaryButton label={t("settings.openLanguages")} onPress={onOpenLanguages} variant="brand" />
              <PrimaryButton label={t("settings.openBilling")} onPress={onOpenBilling} variant="ghost" />
              <PrimaryButton label={t("settings.openSurvey")} onPress={onOpenLearningProfile} variant="brand" />
              <PrimaryButton label={t("settings.signOut")} onPress={() => void onSignOut()} variant="ghost" />
            </View>
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
        <Text style={styles.desc}>{t("settings.languageDesc")}</Text>
        <View style={{ marginTop: 10 }}>
          <DropdownListSelector
            title={t("settings.language")}
            selectedLabel={`${current.flag} ${current.native}`}
            selectedKey={locale}
            options={LANGUAGES.map((lang) => ({ key: lang.code, label: `${lang.flag} ${lang.native}` }))}
            open={localeOpen}
            onToggle={() => setLocaleOpen((v) => !v)}
            onSelect={(code) => {
              setLocale(code as LocaleCode);
              setLocaleOpen(false);
            }}
          />
        </View>
      </Section>

      <Section title={t("settings.sectionVoice")}>
        <Text style={styles.desc}>{t("settings.voiceDesc")}</Text>
        <View style={{ marginTop: 10 }}>
          <DropdownListSelector
            title={t("settings.sectionVoice")}
            selectedLabel={selectedVoice.label}
            selectedKey={selectedVoice.key}
            options={voiceOptions}
            open={voiceOpen}
            onToggle={() => setVoiceOpen((v) => !v)}
            onSelect={(key) => {
              update({ voiceId: key });
              setVoiceOpen(false);
            }}
          />
        </View>
      </Section>

      <Section title={t("settings.sectionInstructor")}>
        <Text style={styles.desc}>{t("settings.instructorDesc")}</Text>
        <View style={{ marginTop: 10 }}>
          <DropdownListSelector
            title={t("settings.sectionInstructor")}
            selectedLabel={selectedInstructor.label}
            selectedKey={selectedInstructor.key}
            options={instructorOptions}
            open={instructorOpen}
            onToggle={() => setInstructorOpen((v) => !v)}
            onSelect={(key) => {
              update({ instructorId: key });
              setInstructorOpen(false);
            }}
          />
        </View>
      </Section>

      <Section title={t("settings.sectionTrainingLang")}>
        <Text style={styles.desc}>{t("settings.trainingLangDesc")}</Text>
        <View style={{ marginTop: 10 }}>
          <DropdownListSelector
            title={t("settings.sectionTrainingLang")}
            selectedLabel={selectedTrainingLocale?.label ?? ""}
            selectedKey={selectedTrainingLocale?.key ?? ""}
            options={trainingLocaleOptions}
            open={trainingLocaleOpen}
            onToggle={() => setTrainingLocaleOpen((v) => !v)}
            onSelect={(key) => {
              update({ trainingLocale: key as TrainingLocale });
              setTrainingLocaleOpen(false);
            }}
          />
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
          <DropdownListSelector
            title={t("settings.time")}
            selectedLabel={selectedReminderHour}
            selectedKey={String(s.dailyReminderHour)}
            options={reminderHours.map((h) => ({ key: String(h), label: `${pad(h)}:00` }))}
            open={hourOpen}
            onToggle={() => setHourOpen((v) => !v)}
            onSelect={(key) => {
              update({ dailyReminderHour: Number(key) });
              setHourOpen(false);
            }}
            maxHeight={180}
          />
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
        {onOpenBugReport ? (
          <View style={{ marginTop: 10 }}>
            <PrimaryButton
              label={t("settings.openBugReport")}
              onPress={onOpenBugReport}
              variant="brand"
            />
          </View>
        ) : null}
      </Section>

      <Section title={t("settings.sectionIntro")}>
        <Row label={t("settings.introSplash")} desc={t("settings.introSplashDesc")}>
          <Switch
            value={s.introSplashEnabled}
            onValueChange={(v) => update({ introSplashEnabled: v })}
            thumbColor={s.introSplashEnabled ? theme.colors.netflix : "#666"} />
        </Row>
        <Row label={t("settings.playFullIntro")} desc={t("settings.playFullIntroDesc")}>
          <AnimatedPressable onPress={playFullIntro} style={styles.btn}>
            <Text style={styles.btnText}>{t("settings.playFullIntro")}</Text>
          </AnimatedPressable>
        </Row>
      </Section>

      <Section title={t("settings.sectionAbout")}>
        <Text style={styles.about}>{t("settings.aboutBody", { version: APP_VERSION })}</Text>
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
  about: { color: theme.colors.muted, lineHeight: 18, fontSize: 13 },
  currentLang: { color: theme.colors.text, fontWeight: "700" },
});
