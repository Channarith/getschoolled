import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator, Modal, RefreshControl, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";

import {
  createLiveRoom, listLiveRooms,
  type LiveRoomBrowse, type LiveRoomListing,
} from "../api";
import { useAuth } from "../auth/AuthContext";
import AnimatedPressable from "../components/AnimatedPressable";
import GlassPanel from "../components/GlassPanel";
import PrimaryButton from "../components/PrimaryButton";
import { useT } from "../i18n";
import { getLiveRoomLocation } from "../liveRoomLocation";
import { theme } from "../theme";

function fmtPlace(r: LiveRoomListing): string {
  const parts = [r.city, r.state, r.country].filter((p) => p && p !== "—");
  return parts.join(", ") || "—";
}

export default function LiveRoomsScreen({
  onOpenRoom,
  onBack,
}: {
  onOpenRoom: (roomId: string, moderatorKey?: string) => void;
  onBack: () => void;
}) {
  const { t } = useT();
  const { account } = useAuth();
  const [browse, setBrowse] = useState<LiveRoomBrowse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [geoLabel, setGeoLabel] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const geo = await getLiveRoomLocation();
      const label = [geo.city, geo.state, geo.country].filter(Boolean).join(", ");
      setGeoLabel(label);
      const data = await listLiveRooms({
        lat: geo.latitude,
        lng: geo.longitude,
        radius_km: geo.latitude ? 500 : 0,
        grouped: true,
      });
      setBrowse(data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function handleCreate() {
    const title = newTitle.trim() || t("live.defaultTitle");
    const creator = account?.display_name || "Host";
    setBusy(true);
    setError("");
    try {
      const geo = await getLiveRoomLocation();
      const res = await createLiveRoom(title, creator, geo);
      setShowCreate(false);
      setNewTitle("");
      onOpenRoom(res.room.room_id, res.listing.moderator_key || "");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function renderRoomCard(r: LiveRoomListing) {
    return (
      <AnimatedPressable
        key={r.room_id}
        onPress={() => onOpenRoom(r.room_id)}
        style={styles.roomCard}
      >
        <View style={styles.roomRow}>
          <Text style={styles.roomTitle} numberOfLines={1}>{r.title}</Text>
          {r.status === "live" ? (
            <Text style={styles.liveDot}>● LIVE</Text>
          ) : null}
        </View>
        <Text style={styles.roomMeta}>
          {r.creator_name || r.host_name} · 👥 {r.viewer_count || r.learner_count}
          {r.seats_left > 0 ? ` · ${r.seats_left} seats` : " · full"}
        </Text>
        <Text style={styles.roomPlace}>
          📍 {fmtPlace(r)}
          {r.distance_km != null ? ` · ${r.distance_km} km` : ""}
        </Text>
      </AnimatedPressable>
    );
  }

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <PrimaryButton label={t("live.back")} onPress={onBack} variant="ghost" />
        <Text style={styles.title}>{t("live.title")}</Text>
      </View>
      <Text style={styles.lead}>{t("live.intro")}</Text>
      {geoLabel ? <Text style={styles.geo}>📍 {geoLabel}</Text> : null}

      <View style={styles.actions}>
        <PrimaryButton label={t("live.goLive")} onPress={() => setShowCreate(true)} variant="netflix" />
        <PrimaryButton label={t("live.refresh")} onPress={() => { setRefreshing(true); void load(); }} variant="ghost" />
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}
      {loading && !refreshing ? (
        <ActivityIndicator color={theme.colors.accent} style={{ marginTop: 24 }} />
      ) : null}

      <ScrollView
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void load(); }} />
        }
      >
        {!loading && (browse?.total ?? 0) === 0 ? (
          <Text style={styles.meta}>{t("live.empty")}</Text>
        ) : null}

        {/* Nearby flat list (sorted by distance when geo available) */}
        {(browse?.rooms?.length ?? 0) > 0 ? (
          <GlassPanel style={styles.section}>
            <Text style={styles.sectionTitle}>{t("live.nearby")}</Text>
            {browse!.rooms.map(renderRoomCard)}
          </GlassPanel>
        ) : null}

        {/* Grouped by country → state → city (Bigo-style) */}
        {browse?.groups?.map((g) => (
          <GlassPanel key={g.country} style={styles.section}>
            <Text style={styles.sectionTitle}>
              🌍 {g.country} <Text style={styles.count}>({g.count})</Text>
            </Text>
            {g.states.map((st) => (
              <View key={`${g.country}-${st.state}`} style={styles.stateBlock}>
                <Text style={styles.stateTitle}>{st.state}</Text>
                {st.cities.map((ci) => (
                  <View key={`${g.country}-${st.state}-${ci.city}`} style={styles.cityBlock}>
                    <Text style={styles.cityTitle}>{ci.city} ({ci.count})</Text>
                    {ci.rooms.map(renderRoomCard)}
                  </View>
                ))}
              </View>
            ))}
          </GlassPanel>
        ))}
      </ScrollView>

      <Modal visible={showCreate} transparent animationType="slide" onRequestClose={() => setShowCreate(false)}>
        <View style={styles.modalScrim}>
          <GlassPanel style={styles.modalCard}>
            <Text style={styles.sectionTitle}>{t("live.createTitle")}</Text>
            <TextInput
              style={styles.input}
              placeholder={t("live.titlePlaceholder")}
              placeholderTextColor={theme.colors.muted}
              value={newTitle}
              onChangeText={setNewTitle}
            />
            <View style={styles.modalActions}>
              <PrimaryButton label={t("live.cancel")} onPress={() => setShowCreate(false)} variant="ghost" />
              <PrimaryButton
                label={busy ? t("live.creating") : t("live.create")}
                onPress={() => void handleCreate()}
                loading={busy}
                variant="netflix"
              />
            </View>
          </GlassPanel>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, paddingHorizontal: 16, paddingTop: 56, gap: 8 },
  header: { flexDirection: "row", alignItems: "center", gap: 8 },
  title: { color: theme.colors.text, fontSize: 20, fontWeight: "800", flex: 1 },
  lead: { color: theme.colors.muted, fontSize: 14, lineHeight: 20 },
  geo: { color: theme.colors.accent, fontSize: 13 },
  actions: { flexDirection: "row", gap: 8, flexWrap: "wrap" },
  list: { gap: 12, paddingBottom: 32 },
  section: { gap: 10 },
  sectionTitle: { color: theme.colors.text, fontSize: 16, fontWeight: "800" },
  count: { color: theme.colors.muted, fontWeight: "600", fontSize: 14 },
  stateBlock: { gap: 8, marginTop: 4 },
  stateTitle: { color: theme.colors.accent, fontSize: 14, fontWeight: "700" },
  cityBlock: { gap: 6, marginLeft: 8 },
  cityTitle: { color: theme.colors.muted, fontSize: 13, fontWeight: "600" },
  roomCard: {
    borderWidth: 1, borderColor: theme.colors.border, borderRadius: 12,
    padding: 12, backgroundColor: "rgba(0,0,0,0.2)", gap: 4,
  },
  roomRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  roomTitle: { color: theme.colors.text, fontSize: 15, fontWeight: "700", flex: 1 },
  liveDot: { color: "#f87171", fontSize: 11, fontWeight: "800" },
  roomMeta: { color: theme.colors.muted, fontSize: 12 },
  roomPlace: { color: theme.colors.muted, fontSize: 12 },
  meta: { color: theme.colors.muted, fontSize: 14, textAlign: "center", marginTop: 24 },
  error: { color: "#f87171", fontSize: 13 },
  modalScrim: {
    flex: 1, backgroundColor: theme.colors.scrimHeavy,
    justifyContent: "flex-end", padding: 16,
  },
  modalCard: { gap: 12, marginBottom: 24 },
  input: {
    borderWidth: 1, borderColor: theme.colors.border, borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: 12, color: theme.colors.text,
    backgroundColor: "rgba(0,0,0,0.25)",
  },
  modalActions: { flexDirection: "row", gap: 8, justifyContent: "flex-end" },
});
