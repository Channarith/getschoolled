import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator, Alert, Linking, Modal, RefreshControl, ScrollView,
  StyleSheet, Text, TextInput, TouchableOpacity, View,
} from "react-native";

import {
  checkoutGroupClass,
  confirmGroupClassPayment,
  listGroupClasses,
  listLessons,
  registerGroupClass,
  reviewGroupClass,
  scheduleGroupClass,
  startGroupClass,
  type GroupClassRow, type GroupClassStart, type LessonRow,
} from "../api";
import { useAuth } from "../auth/AuthContext";
import AnimatedPressable from "../components/AnimatedPressable";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import StartTimeField, { defaultStartDate } from "../components/StartTimeField";
import { useAndroidBackTo } from "../hooks/useAndroidBack";
import { useT } from "../i18n";
import { getLiveRoomLocation } from "../liveRoomLocation";
import { getAttendeeCode, setAttendeeCode } from "../liveRoomAccess";
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
  onOpenLiveRooms,
  onBack,
}: {
  onOpenRoom: (roomId: string, moderatorKey?: string) => void;
  onOpenLiveRooms: () => void;
  onBack: () => void;
}) {
  const { t } = useT();
  useAndroidBackTo(onBack);
  const { account } = useAuth();
  const [rows, setRows] = useState<GroupClassRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [filterAudience, setFilterAudience] = useState<string>("all");
  const [filterRating, setFilterRating] = useState(false);
  const [filterFree, setFilterFree] = useState(false);
  const [sortBy, setSortBy] = useState<"soon" | "rating" | "seats">("soon");
  const [schedAudience, setSchedAudience] = useState("general");
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
      if (gc.payment_required || gc.attendee_code_required) {
        let attendeeCode = getAttendeeCode(gc.id);
        if (!attendeeCode) {
          const checkout = await checkoutGroupClass(
            gc.id,
            account?.display_name || "Learner",
            account?.email || "",
          );
          const paid = await confirmGroupClassPayment(gc.id, checkout.checkout.session_id);
          attendeeCode = paid.attendee_code || "";
          setAttendeeCode(gc.id, attendeeCode);
        }
      }
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
          const attendeeCode = getAttendeeCode(gc.id);
          if (attendeeCode) setAttendeeCode(roomId, attendeeCode);
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

  async function handleReview(gc: GroupClassRow, rating = 5) {
    if (rating < 1 || rating > 5) {
      Alert.alert("Review", "Rating must be between 1 and 5.");
      return;
    }
    setBusyId(gc.id);
    setError("");
    try {
      await reviewGroupClass(gc.id, Math.round(rating), "");
      await load();
      Alert.alert("Review", "Thanks! Your review was saved.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusyId("");
    }
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
        audience: schedAudience,
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

  const filtered = useMemo(() => {
    let list = rows;
    const ql = q.trim().toLowerCase();
    if (ql) list = list.filter(gc =>
      gc.title.toLowerCase().includes(ql) ||
      (gc.instructor_name || "").toLowerCase().includes(ql) ||
      (gc.language || "").toLowerCase().includes(ql)
    );
    if (filterAudience !== "all") list = list.filter(gc => (gc.audience || "general") === filterAudience);
    if (filterRating) list = list.filter(gc => (gc.instructor_stats?.review_avg ?? gc.review_avg ?? 0) >= 4);
    if (filterFree) list = list.filter(gc => !gc.payment_required);
    if (sortBy === "rating") list = [...list].sort((a, b) =>
      (b.instructor_stats?.review_avg ?? b.review_avg ?? 0) - (a.instructor_stats?.review_avg ?? a.review_avg ?? 0)
    );
    else if (sortBy === "seats") list = [...list].sort((a, b) => b.seats_left - a.seats_left);
    else list = [...list].sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());
    return list;
  }, [rows, q, filterAudience, filterRating, filterFree, sortBy]);

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <PrimaryButton label={t("group.back")} onPress={onBack} variant="ghost" />
        <Text style={styles.title}>{t("group.title")}</Text>
      </View>
      <Text style={styles.lead}>{t("group.intro")}</Text>
      <View style={styles.topActions}>
        <PrimaryButton label="🎓 Host a Class" onPress={() => setShowSchedule(true)} variant="brand" />
        <PrimaryButton label={t("live.browseCta")} onPress={onOpenLiveRooms} variant="ghost" />
      </View>
      {loading && !refreshing ? (
        <ActivityIndicator color={theme.colors.accent} style={{ marginTop: 24 }} />
      ) : null}
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {/* Search */}
      <View style={styles.searchWrap}>
        <TextInput
          style={styles.searchInput}
          placeholder="Search classes, instructors…"
          placeholderTextColor={theme.colors.muted}
          value={q}
          onChangeText={setQ}
          returnKeyType="search"
          clearButtonMode="while-editing"
        />
      </View>
      {/* Filter chips */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 8 }} contentContainerStyle={{ paddingHorizontal: theme.spacing.screenX }}>
        {["all","general","kids","professional","corporate"].map(aud => (
          <TouchableOpacity key={aud} onPress={() => setFilterAudience(aud)}
            style={[{ borderRadius: 20, borderWidth: 1, borderColor: filterAudience === aud ? theme.colors.accent : theme.colors.border, paddingHorizontal: 14, paddingVertical: 6, marginRight: 8, backgroundColor: filterAudience === aud ? "rgba(110,168,254,0.15)" : "rgba(255,255,255,0.04)" }]}>
            <Text style={{ color: filterAudience === aud ? "#fff" : theme.colors.muted, fontSize: 13, fontWeight: "600" }}>
              {aud === "all" ? "All" : aud === "kids" ? "👶 Kids" : aud.charAt(0).toUpperCase() + aud.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
        <TouchableOpacity onPress={() => setFilterRating(v => !v)}
          style={[{ borderRadius: 20, borderWidth: 1, borderColor: filterRating ? theme.colors.accent : theme.colors.border, paddingHorizontal: 14, paddingVertical: 6, marginRight: 8, backgroundColor: filterRating ? "rgba(110,168,254,0.15)" : "rgba(255,255,255,0.04)" }]}>
          <Text style={{ color: filterRating ? "#fff" : theme.colors.muted, fontSize: 13, fontWeight: "600" }}>⭐ 4+</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => setFilterFree(v => !v)}
          style={[{ borderRadius: 20, borderWidth: 1, borderColor: filterFree ? theme.colors.accent : theme.colors.border, paddingHorizontal: 14, paddingVertical: 6, marginRight: 8, backgroundColor: filterFree ? "rgba(110,168,254,0.15)" : "rgba(255,255,255,0.04)" }]}>
          <Text style={{ color: filterFree ? "#fff" : theme.colors.muted, fontSize: 13, fontWeight: "600" }}>Free</Text>
        </TouchableOpacity>
      </ScrollView>
      {/* Sort row */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 8 }} contentContainerStyle={{ paddingHorizontal: theme.spacing.screenX }}>
        {([["soon","Starting Soon"],["rating","Top Rated"],["seats","Most Seats"]] as const).map(([val, label]) => (
          <TouchableOpacity key={val} onPress={() => setSortBy(val)}
            style={[{ borderRadius: 20, borderWidth: 1, borderColor: sortBy === val ? theme.colors.accent : theme.colors.border, paddingHorizontal: 14, paddingVertical: 6, marginRight: 8, backgroundColor: sortBy === val ? "rgba(110,168,254,0.15)" : "rgba(255,255,255,0.04)" }]}>
            <Text style={{ color: sortBy === val ? "#fff" : theme.colors.muted, fontSize: 13, fontWeight: "600" }}>{label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
      <ScrollView
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load(); }} />
        }
      >
        {rows.length === 0 && !loading ? (
          <Text style={styles.meta}>{t("group.empty")}</Text>
        ) : null}
        {filtered.map((gc) => {
          const busy = busyId === gc.id;
          const platform = PLATFORM_LABEL[gc.platform] ?? gc.platform;
          const isAdmin = Boolean(account?.is_admin);
          // The class host can open their own class (non-admin instructors included).
          const myAccountId = account?.id;
          const isHost = myAccountId && (
            myAccountId === gc.instructor_account_id ||
            myAccountId === gc.created_by_account_id
          );
          const canOpen = isAdmin || Boolean(isHost);
          // A full class is grayed out (not joinable) for everyone except the host/admin.
          const full = gc.seats_left <= 0;
          const joinBlocked = full && !canOpen;
          return (
            <GlassPanel key={gc.id} style={styles.card}>
              <View style={styles.badgeRow}>
                <Text style={styles.badge}>{platform}</Text>
                {gc.status === "live" ? <Text style={styles.liveBadge}>● {t("group.live")}</Text> : null}
              </View>
              <Text style={styles.cardTitle}>{gc.title}</Text>
              {gc.language && gc.language !== "en" ? <Text style={styles.meta}>{gc.language.toUpperCase()} · {gc.audience ? gc.audience.charAt(0).toUpperCase() + gc.audience.slice(1) : "General"}</Text> : null}
              <Text style={styles.meta}>{fmtTime(gc.start_time)}</Text>
              <Text style={styles.meta}>
                {t("group.seatsLeft")}: {gc.seats_left}/{gc.capacity}
                {gc.room_size ? ` · ${gc.room_size}-seat room` : ""}
              </Text>
              <Text style={styles.meta}>
                Rating {(gc.instructor_stats?.review_avg ?? gc.review_avg ?? 0).toFixed(2)} / 5 ·
                {(gc.instructor_stats?.review_count ?? gc.review_count ?? 0)} reviews ·
                {(gc.instructor_stats?.courses_taught ?? 0)} taught
              </Text>
              {gc.payment_required || gc.attendee_code_required ? (
                <Text style={styles.meta}>
                  Paid class{gc.price_per_user_usd ? ` · $${gc.price_per_user_usd.toFixed(2)}` : ""} ·
                  Commission {((gc.commission_rate ?? 0.15) * 100).toFixed(0)}%
                </Text>
              ) : null}
              {gc.audit_required && gc.audit_status !== "approved" ? (
                <Text style={styles.error}>Pending Salareen audit approval.</Text>
              ) : null}
              {gc.platform === "teams" && gc.external_camera_ingest_supported ? (
                <Text style={styles.meta}>
                  Teams room-device camera ingest ready
                  {gc.device_profile ? ` (${gc.device_profile})` : ""}
                  {gc.camera_source_count ? ` · ${gc.camera_source_count} source(s)` : ""}
                </Text>
              ) : null}
              <View style={styles.actions}>
                {/* One button: first join opens + hosts the class; later joins
                    drop into the running room. A full class is grayed out except
                    for the admin (monitor). */}
                <PrimaryButton
                  label={joinBlocked ? t("group.full") : t("group.join")}
                  onPress={() => void handleJoin(gc)}
                  loading={busy}
                  disabled={busy || joinBlocked}
                  variant="brand"
                />
                <PrimaryButton
                  label={t("group.register")}
                  onPress={() => promptRegister(gc)}
                  disabled={busy}
                  variant="ghost"
                />
                {canOpen ? (
                  <PrimaryButton
                    label={isHost && !isAdmin ? "🎓 Open My Class" : t("group.openClass")}
                    onPress={() => void handleStart(gc)}
                    loading={busy}
                    disabled={busy}
                    variant="netflix"
                  />
                ) : null}
                <PrimaryButton
                  label="Rate"
                  onPress={() => void handleReview(gc, 5)}
                  loading={busy}
                  disabled={busy}
                  variant="ghost"
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
              <Text style={styles.formLabel}>Audience</Text>
              <View style={styles.segRow}>
                {["general","kids","professional","corporate"].map(aud => (
                  <TouchableOpacity key={aud} onPress={() => setSchedAudience(aud)}
                    style={[styles.seg, schedAudience === aud && styles.segOn]}>
                    <Text style={[styles.segText, schedAudience === aud && styles.segTextOn]}>
                      {aud === "kids" ? "👶 Kids" : aud.charAt(0).toUpperCase() + aud.slice(1)}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
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
  topActions: { gap: 8 },
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
  searchWrap: {
    marginHorizontal: theme.spacing.screenX,
    marginBottom: 10,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: theme.colors.border,
    backgroundColor: "rgba(255,255,255,0.06)",
    paddingHorizontal: 12,
  },
  searchInput: { color: theme.colors.text, fontSize: 14, paddingVertical: 10 },
  formLabel: { color: theme.colors.muted, fontSize: 12, fontWeight: "700", marginTop: 12, marginBottom: 6 },
  segRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  seg: { borderRadius: 16, borderWidth: 1, borderColor: theme.colors.border, paddingHorizontal: 12, paddingVertical: 5 },
  segOn: { borderColor: theme.colors.accent, backgroundColor: "rgba(110,168,254,0.15)" },
  segText: { color: theme.colors.muted, fontSize: 13 },
  segTextOn: { color: "#fff", fontWeight: "700" },
});
