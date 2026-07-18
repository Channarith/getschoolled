import { useEffect, useState } from "react";
import {
  ActivityIndicator, Alert, Linking, Modal, RefreshControl, ScrollView,
  StyleSheet, Text, TextInput, View,
} from "react-native";

import {
  listGroupClasses, listLessons, registerGroupClass, scheduleGroupClass, startGroupClass,
  type GroupClassRow, type GroupClassStart, type LessonRow,
} from "../api";
import { useAuth } from "../auth/AuthContext";
import AnimatedPressable from "../components/AnimatedPressable";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import StartTimeField, { defaultStartDate } from "../components/StartTimeField";
import { useT } from "../i18n";
import { getLiveRoomLocation } from "../liveRoomLocation";
import { theme } from "../theme";

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      weekday: "short", month: "short", day: "numeric",
      hour: "numeric", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

const PLATFORM_LABEL: Record<string, string> = {
  salareen: "Salareen",
  zoom: "Zoom",
  teams: "Teams",
  meet: "Meet",
};

export default function GroupClassesScreen({
  onOpenRoom,
  onBack,
}: {
  onOpenRoom: (roomId: string, moderatorKey?: string) => void;
  onBack: () => void;
}) {
  const { t } = useT();
  const { account } = useAuth();
  const [rows, setRows] = useState<GroupClassRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");
  const [started, setStarted] = useState<GroupClassStart | null>(null);
  const [registerTarget, setRegisterTarget] = useState<GroupClassRow | null>(null);
  const [registerName, setRegisterName] = useState("");
  const [registerEmail, setRegisterEmail] = useState("");
  const [showSchedule, setShowSchedule] = useState(false);
  const [lessons, setLessons] = useState<LessonRow[]>([]);
  const [schedTitle, setSchedTitle] = useState("");
  const [schedLessonId, setSchedLessonId] = useState("");
  const [schedPlatform, setSchedPlatform] = useState("salareen");
  const [schedMeetingUrl, setSchedMeetingUrl] = useState("");
  const [schedStart, setSchedStart] = useState(() => defaultStartDate());
  const [schedDuration, setSchedDuration] = useState("45");
  const [schedCapacity, setSchedCapacity] = useState("12");
  const [schedRoomSize, setSchedRoomSize] = useState("6");

  const load = async () => {
    setError("");
    try {
      setRows(await listGroupClasses(true));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void load();
    void listLessons()
      .then((ls) => {
        setLessons(ls);
        if (ls.length) setSchedLessonId(ls[0].lesson_id);
      })
      .catch(() => {});
  }, []);

  function roomIdFor(gc: GroupClassRow): string {
    return gc.live_room_id || `class-${gc.id}`;
  }

  function openSalareenRoom(gc: GroupClassRow, modKey = "") {
    onOpenRoom(roomIdFor(gc), modKey);
  }

  async function handleJoin(gc: GroupClassRow) {
    setError("");
    if (gc.needs_bridge && gc.meeting_url) {
      const ok = await Linking.canOpenURL(gc.meeting_url);
      if (!ok) {
        setError(t("group.cannotOpenMeeting"));
        return;
      }
      await Linking.openURL(gc.meeting_url);
      return;
    }
    if (gc.platform === "salareen" || gc.live_room_id) {
      // A Salareen room only exists on the server once the class has been
      // "started" (open_room). Joining a not-yet-live class hits a room id that
      // doesn't exist -> 404. Open it first (idempotent) so entering succeeds,
      // then join as a learner (no moderator key — tapping Join isn't hosting).
      if (!gc.live_room_id && gc.status !== "live") {
        setBusyId(gc.id);
        try {
          const geo = await getLiveRoomLocation();
          const res = await startGroupClass(gc.id, geo);
          const roomId = res.bridge.live_room_id || res.bridge.livekit_room || roomIdFor(gc);
          void load();
          // First person in opens + hosts the class (gets the moderator key).
          onOpenRoom(roomId, res.bridge.moderator_key || "");
        } catch (e) {
          setError((e as Error).message);
        } finally {
          setBusyId("");
        }
        return;
      }
      openSalareenRoom(gc);
      return;
    }
    setError(t("group.joinUnavailable"));
  }

  async function handleStart(gc: GroupClassRow) {
    setBusyId(gc.id);
    setError("");
    try {
      const geo = await getLiveRoomLocation();
      const res = await startGroupClass(gc.id, geo);
      setStarted(res);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusyId("");
    }
  }

  function openStartedRoom() {
    if (!started) return;
    const gc = started.class;
    const roomId = started.bridge.live_room_id
      || started.bridge.livekit?.room
      || started.bridge.livekit_room
      || `class-${gc.id}`;
    const modKey = started.bridge.moderator_key || "";
    setStarted(null);
    onOpenRoom(roomId, modKey);
  }

  async function openStartedMeeting() {
    if (!started?.class.meeting_url) return;
    await Linking.openURL(started.class.meeting_url);
  }

  async function submitSchedule() {
    if (!schedLessonId) return;
    setBusyId("schedule");
    setError("");
    try {
      const lesson = lessons.find((l) => l.lesson_id === schedLessonId);
      const roomSize = Number(schedRoomSize) || 6;
      await scheduleGroupClass({
        title: schedTitle.trim() || lesson?.title || "Group class",
        lesson_id: schedLessonId,
        platform: schedPlatform,
        meeting_url: schedMeetingUrl.trim(),
        start_time: schedStart.toISOString(),
        duration_min: Number(schedDuration) || 45,
        capacity: schedPlatform === "salareen" ? roomSize - 1 : Number(schedCapacity) || 12,
        room_size: schedPlatform === "salareen" ? roomSize : undefined,
        language: lesson?.language ?? "en",
      });
      setShowSchedule(false);
      setSchedTitle("");
      setSchedMeetingUrl("");
      setSchedStart(defaultStartDate());
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusyId("");
    }
  }

  function promptRegister(gc: GroupClassRow) {
    setRegisterTarget(gc);
    setRegisterName(account?.display_name || "");
    setRegisterEmail(account?.email || "");
  }

  async function submitRegister() {
    if (!registerTarget) return;
    const name = registerName.trim();
    if (!name) {
      Alert.alert(t("group.registerTitle"), t("group.registerNameRequired"));
      return;
    }
    setBusyId(registerTarget.id);
    setError("");
    try {
      await registerGroupClass(registerTarget.id, name, registerEmail.trim());
      setRegisterTarget(null);
      await load();
      Alert.alert(t("group.registerTitle"), t("group.registerSuccess"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusyId("");
    }
  }

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <PrimaryButton label={t("group.back")} onPress={onBack} variant="ghost" />
        <Text style={styles.title}>{t("group.title")}</Text>
      </View>
      <Text style={styles.lead}>{t("group.intro")}</Text>
      <PrimaryButton label={t("group.scheduleCta")} onPress={() => setShowSchedule(true)} variant="brand" />
      {loading && !refreshing ? (
        <ActivityIndicator color={theme.colors.accent} style={{ marginTop: 24 }} />
      ) : null}
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <ScrollView
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load(); }} />
        }
      >
        {rows.length === 0 && !loading ? (
          <Text style={styles.meta}>{t("group.empty")}</Text>
        ) : null}
        {rows.map((gc) => {
          const busy = busyId === gc.id;
          const platform = PLATFORM_LABEL[gc.platform] ?? gc.platform;
          const isAdmin = Boolean(account?.is_admin);
          // A full class is grayed out (not joinable) for everyone except the
          // administrator, who can still drop in to monitor the session.
          const full = gc.seats_left <= 0;
          const joinBlocked = full && !isAdmin;
          return (
            <GlassPanel key={gc.id} style={styles.card}>
              <View style={styles.badgeRow}>
                <Text style={styles.badge}>{platform}</Text>
                {gc.status === "live" ? <Text style={styles.liveBadge}>● {t("group.live")}</Text> : null}
              </View>
              <Text style={styles.cardTitle}>{gc.title}</Text>
              <Text style={styles.meta}>{fmtTime(gc.start_time)}</Text>
              <Text style={styles.meta}>
                {t("group.seatsLeft")}: {gc.seats_left}/{gc.capacity}
                {gc.room_size ? ` · ${gc.room_size}-seat room` : ""}
              </Text>
              <View style={styles.actions}>
                {/* One button: first join opens + hosts the class; later joins
                    drop into the running room. No separate register/start step.
                    A full class is grayed out except for the admin (monitor). */}
                <PrimaryButton
                  label={joinBlocked ? t("group.full") : t("group.join")}
                  onPress={() => void handleJoin(gc)}
                  loading={busy}
                  disabled={busy || joinBlocked}
                  variant="brand"
                />
              </View>
            </GlassPanel>
          );
        })}
      </ScrollView>

      <Modal
        visible={registerTarget !== null}
        transparent
        animationType="slide"
        onRequestClose={() => setRegisterTarget(null)}
      >
        <View style={styles.modalScrim}>
          <GlassPanel style={styles.modalCard}>
            <Text style={styles.cardTitle}>{t("group.registerTitle")}</Text>
            <Text style={styles.meta}>{registerTarget?.title}</Text>
            <TextInput
              style={styles.input}
              placeholder={t("group.registerName")}
              placeholderTextColor={theme.colors.muted}
              value={registerName}
              onChangeText={setRegisterName}
            />
            <TextInput
              style={styles.input}
              placeholder={t("group.registerEmail")}
              placeholderTextColor={theme.colors.muted}
              autoCapitalize="none"
              keyboardType="email-address"
              value={registerEmail}
              onChangeText={setRegisterEmail}
            />
            <View style={styles.actions}>
              <PrimaryButton label={t("group.cancel")} onPress={() => setRegisterTarget(null)} variant="ghost" />
              <PrimaryButton label={t("group.register")} onPress={() => void submitRegister()} variant="netflix" />
            </View>
          </GlassPanel>
        </View>
      </Modal>

      <Modal
        visible={started !== null}
        transparent
        animationType="fade"
        onRequestClose={() => setStarted(null)}
      >
        <View style={styles.modalScrim}>
          <GlassPanel style={styles.modalCard}>
            <Text style={styles.cardTitle}>{t("group.startedTitle")}</Text>
            {started?.bridge.note ? (
              <Text style={styles.meta}>{started.bridge.note}</Text>
            ) : null}
            {started?.class.title ? (
              <Text style={styles.meta}>{started.class.title}</Text>
            ) : null}
            <View style={styles.actionsCol}>
              {started?.bridge.needs_bridge && started.class.meeting_url ? (
                <PrimaryButton
                  label={t("group.openMeeting")}
                  onPress={() => void openStartedMeeting()}
                  variant="brand"
                />
              ) : null}
              <PrimaryButton
                label={t("group.openClass")}
                onPress={openStartedRoom}
                variant="netflix"
              />
              <PrimaryButton
                label={t("group.close")}
                onPress={() => setStarted(null)}
                variant="ghost"
              />
            </View>
          </GlassPanel>
        </View>
      </Modal>

      <Modal visible={showSchedule} transparent animationType="slide" onRequestClose={() => setShowSchedule(false)}>
        <View style={styles.modalScrim}>
          <ScrollView contentContainerStyle={{ padding: 16 }}>
            <GlassPanel style={styles.modalCard}>
              <Text style={styles.cardTitle}>{t("group.scheduleCta")}</Text>
              <TextInput style={styles.input} placeholder={t("group.scheduleTitle")}
                placeholderTextColor={theme.colors.muted} value={schedTitle} onChangeText={setSchedTitle} />
              {lessons.map((l) => (
                <AnimatedPressable
                  key={l.lesson_id}
                  onPress={() => setSchedLessonId(l.lesson_id)}
                  style={[styles.lessonPick, schedLessonId === l.lesson_id && styles.lessonPickOn]}
                >
                  <Text style={styles.meta}>{l.title}</Text>
                </AnimatedPressable>
              ))}
              <TextInput style={styles.input} placeholder="Platform (salareen/zoom/teams/meet)"
                placeholderTextColor={theme.colors.muted} value={schedPlatform} onChangeText={setSchedPlatform} />
              <TextInput style={styles.input} placeholder={t("group.scheduleMeeting")}
                placeholderTextColor={theme.colors.muted} value={schedMeetingUrl} onChangeText={setSchedMeetingUrl} />
              <StartTimeField
                value={schedStart}
                onChange={setSchedStart}
                label={t("group.scheduleWhen")}
              />
              <TextInput style={styles.input} placeholder={t("group.scheduleDuration")}
                placeholderTextColor={theme.colors.muted} value={schedDuration} onChangeText={setSchedDuration}
                keyboardType="number-pad" />
              <TextInput style={styles.input} placeholder={t("group.scheduleCapacity")}
                placeholderTextColor={theme.colors.muted} value={schedCapacity} onChangeText={setSchedCapacity}
                keyboardType="number-pad" />
              <TextInput style={styles.input} placeholder={t("group.scheduleRoomSize")}
                placeholderTextColor={theme.colors.muted} value={schedRoomSize} onChangeText={setSchedRoomSize}
                keyboardType="number-pad" />
              <View style={styles.actions}>
                <PrimaryButton label={t("group.cancel")} onPress={() => setShowSchedule(false)} variant="ghost" />
                <PrimaryButton label={t("group.scheduleSubmit")} onPress={() => void submitSchedule()}
                  loading={busyId === "schedule"} variant="netflix" />
              </View>
            </GlassPanel>
          </ScrollView>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, paddingHorizontal: 16, paddingTop: 56, gap: 8 },
  header: { flexDirection: "row", alignItems: "center", gap: 8 },
  title: { color: theme.colors.text, fontSize: 20, fontWeight: "700", flex: 1 },
  lead: { color: theme.colors.muted, fontSize: 13, lineHeight: 18, marginBottom: 4 },
  list: { gap: 12, paddingBottom: 32 },
  card: { gap: 8 },
  badgeRow: { flexDirection: "row", gap: 8, alignItems: "center" },
  badge: {
    fontSize: 11, fontWeight: "700", color: theme.colors.accent,
    backgroundColor: "rgba(110,168,254,0.15)",
    paddingHorizontal: 8, paddingVertical: 2, borderRadius: 999,
  },
  liveBadge: { fontSize: 11, fontWeight: "700", color: "#f87171" },
  cardTitle: { color: theme.colors.text, fontSize: 16, fontWeight: "600", lineHeight: 22 },
  meta: { color: theme.colors.muted, fontSize: 13, lineHeight: 18 },
  actions: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 4 },
  actionsCol: { gap: 10, marginTop: 12 },
  error: { color: "#f87171", fontSize: 13 },
  modalScrim: {
    flex: 1, justifyContent: "flex-end",
    backgroundColor: theme.colors.scrimHeavy,
  },
  modalCard: { borderBottomLeftRadius: 0, borderBottomRightRadius: 0, gap: 10 },
  input: {
    borderWidth: 1, borderColor: theme.colors.border, borderRadius: 10,
    padding: 12, color: theme.colors.text, backgroundColor: "rgba(0,0,0,0.2)",
  },
  lessonPick: {
    borderWidth: 1, borderColor: theme.colors.border, borderRadius: 8, padding: 10, marginBottom: 6,
  },
  lessonPickOn: { borderColor: theme.colors.accent, backgroundColor: "rgba(110,168,254,0.1)" },
});
