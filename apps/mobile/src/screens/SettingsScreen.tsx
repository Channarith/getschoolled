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

export default function SettingsScreen() {
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

  // Apply patches synchronously so the UI flips immediately, then persist +
  // reschedule notifications in the background. Without this, AsyncStorage's
  // async write let chip taps appear "additive" because the visual didn't
  // catch up to the state until storage I/O completed.
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
      Alert.alert("Notifications disabled",
        "Enable notifications for AI Classroom in your phone's Settings.");
    }
  };

  const sendTest = async () => {
    const ok = await ensurePermissions();
    if (!ok) {
      Alert.alert("Permission needed", "Allow notifications first.");
      return;
    }
    await fireImmediate(
      "AI Classroom test alert",
      "If you see this, notifications are working. 🎉",
    );
    await refreshScheduled();
  };

  return (
    <ScrollView style={styles.bg} contentContainerStyle={{ paddingTop: 56, paddingBottom: 32 }}>
      <View style={styles.header}>
        <Text style={styles.title}>Settings</Text>
        <Text style={styles.sub}>Notifications, alerts, account.</Text>
      </View>

      <Section title="Notifications">
        <Row label="Allow notifications"
             desc="Daily reminders, new-class alerts, completion banners.">
          <Switch
            value={s.notificationsEnabled}
            onValueChange={(v) => update({ notificationsEnabled: v })}
            thumbColor={s.notificationsEnabled ? "#0ea5e9" : "#666"} />
        </Row>
        <Row label="Daily class reminder"
             desc={`A nudge at ${pad(s.dailyReminderHour)}:00 every day.`}>
          <Switch
            value={s.dailyReminder && s.notificationsEnabled}
            onValueChange={(v) => update({ dailyReminder: v })}
            disabled={!s.notificationsEnabled}
            thumbColor={s.dailyReminder ? "#0ea5e9" : "#666"} />
        </Row>
        <View style={[styles.row, { flexDirection: "column", alignItems: "stretch", gap: 8 }]}>
          <Text style={styles.label}>Reminder time</Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            {[7, 9, 12, 15, 18, 20, 21].map((h) => {
              const selected = s.dailyReminderHour === h;
              // On web, react-native-web's Pressable keeps a :focus outline +
              // hover bg after click, which makes a previously-tapped chip
              // look selected even when state has moved on. Force the
              // selected style off explicitly when the chip is not the
              // current value, and disable the web hover/focus ring.
              // Use TouchableOpacity instead of Pressable to avoid the
              // sticky :focus / :active background browsers leave on a
              // recently-clicked Pressable on react-native-web (which made
              // multiple chips look "selected" simultaneously even though
              // state had moved on). TouchableOpacity only animates opacity
              // on press and clears on release.
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
        <Row label="New-class alerts"
             desc="Get alerted when fresh audio classes match your interests.">
          <Switch
            value={s.newContentAlerts && s.notificationsEnabled}
            onValueChange={(v) => update({ newContentAlerts: v })}
            disabled={!s.notificationsEnabled}
            thumbColor={s.newContentAlerts ? "#0ea5e9" : "#666"} />
        </Row>
        <Row label="Completion banners"
             desc="Celebrate when you finish a class — and queue the next one.">
          <Switch
            value={s.completionAlerts && s.notificationsEnabled}
            onValueChange={(v) => update({ completionAlerts: v })}
            disabled={!s.notificationsEnabled}
            thumbColor={s.completionAlerts ? "#0ea5e9" : "#666"} />
        </Row>
      </Section>

      <Section title="Diagnostics">
        <Row label={`Scheduled on this device: ${scheduled}`}
             desc="Local notifications waiting in the OS scheduler.">
          <Pressable onPress={() => void refreshScheduled()} style={styles.btn}>
            <Text style={styles.btnText}>Refresh</Text>
          </Pressable>
        </Row>
        <Row label="Send a test alert"
             desc="Fires immediately so you can verify the channel works.">
          <Pressable onPress={() => void sendTest()} style={styles.btn}>
            <Text style={styles.btnText}>Send</Text>
          </Pressable>
        </Row>
        <Row label={`Permission: ${permission}`}
             desc="Tap if iOS / Android dropped the prompt.">
          <Pressable onPress={() => void askPermission()} style={styles.btn}>
            <Text style={styles.btnText}>Request</Text>
          </Pressable>
        </Row>
      </Section>

      <Section title="About">
        <Text style={styles.about}>
          AI Classroom mobile · v0.1{"\n"}
          Backend: see app.json → expo.extra.curriculumUrl. Make sure the
          curriculum service is running and reachable from your device.
        </Text>
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
});
