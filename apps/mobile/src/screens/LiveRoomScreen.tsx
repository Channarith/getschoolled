import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";

import {
  getLiveRoom, getLiveGiftCatalog, joinLiveRoom, leaveLiveRoom, liveRoomAsk, liveRoomBan, liveRoomCallNext,
  liveRoomChat, liveRoomDismissReport, liveRoomFinishTurn, liveRoomFollowHost, liveRoomLeaveQueue,
  liveRoomMediaToken,
  liveRoomRaiseHand, liveRoomReaction, liveRoomReport, liveRoomSendGift, liveRoomUnban,
  startGroupClass,
  type LiveGiftCatalogItem, type LiveKitMedia, type LiveRoomState,
} from "../api";
import { useAuth } from "../auth/AuthContext";
import { useT } from "../i18n";
import GlassPanel from "../components/GlassPanel";
import LiveKitParticipantTile from "../components/LiveKitParticipantTile";
import PrimaryButton from "../components/PrimaryButton";
import { getLiveRoomLocation } from "../liveRoomLocation";
import { useLiveRoomSocket } from "../liveRoomWs";
import { theme } from "../theme";

const STORAGE: Record<string, { participantId: string; identity: string }> = {};
const MOD_STORAGE: Record<string, string> = {};
const REACTIONS = ["❤️", "👏", "🔥", "😂", "🎉", "👍"] as const;

export default function LiveRoomScreen({
  roomId,
  onBack,
  moderatorKey = "",
}: {
  roomId: string;
  onBack: () => void;
  moderatorKey?: string;
}) {
  const { account } = useAuth();
  const { locale } = useT();
  const [name, setName] = useState("");
  const [participantId, setParticipantId] = useState("");
  const [identity, setIdentity] = useState("");
  const [media, setMedia] = useState<LiveKitMedia | null>(null);
  const [room, setRoom] = useState<LiveRoomState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [chat, setChat] = useState("");
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [wasBlocked, setWasBlocked] = useState(false);
  const [giftBalance, setGiftBalance] = useState(0);
  const [giftCatalog, setGiftCatalog] = useState<LiveGiftCatalogItem[]>([]);
  const [showGifts, setShowGifts] = useState(false);
  const [followingHost, setFollowingHost] = useState(false);
  const modKey = moderatorKey || MOD_STORAGE[roomId] || "";

  const socket = useLiveRoomSocket(roomId, Boolean(participantId), setRoom);

  const refresh = async () => {
    try {
      setRoom(await getLiveRoom(roomId, modKey));
      setError("");
    } catch (e) {
      const msg = (e as Error).message;
      // Room not open yet (never started, or the server was restarted). Show a
      // human message instead of a raw "404 Not Found"; joining will (re)open it.
      setError(msg.includes("404") || msg.toLowerCase().includes("unknown live room")
        ? "This class hasn't started yet — tap Enter room to open it."
        : msg);
    }
  };

  useEffect(() => {
    if (moderatorKey) MOD_STORAGE[roomId] = moderatorKey;
  }, [moderatorKey, roomId]);

  useEffect(() => {
    void refresh().finally(() => setLoading(false));
    void getLiveGiftCatalog()
      .then((c) => setGiftCatalog(c.gifts))
      .catch(() => setGiftCatalog([]));
  }, [roomId]);

  useEffect(() => {
    if (!participantId || socket.connected) return;
    const t = setInterval(() => void refresh(), 3000);
    return () => clearInterval(t);
  }, [participantId, roomId, socket.connected]);

  async function handleJoin(nameOverride?: string, accountId?: string) {
    const joinName = (nameOverride ?? name).trim();
    if (!joinName) {
      setError("Enter your name");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const ident =
        STORAGE[roomId]?.identity
        || (accountId ? `mobile-acct-${accountId}` : `mobile-${joinName.toLowerCase()}`);
      let joined: Awaited<ReturnType<typeof joinLiveRoom>>;
      try {
        joined = await joinLiveRoom(roomId, joinName, ident, locale);
      } catch (joinErr) {
        // Room not open yet: for a group-class room (`class-<id>`) open it first
        // (idempotent server-side), then retry the join once so entering works.
        const msg = (joinErr as Error).message;
        const is404 = msg.includes("404") || msg.toLowerCase().includes("unknown live room");
        if (is404 && roomId.startsWith("class-")) {
          const geo = await getLiveRoomLocation();
          await startGroupClass(roomId.slice("class-".length), geo);
          joined = await joinLiveRoom(roomId, joinName, ident, locale);
        } else {
          throw joinErr;
        }
      }
      setParticipantId(joined.participant.id);
      setIdentity(joined.participant.identity);
      setMedia(joined.media ?? null);
      setGiftBalance(joined.gift_balance ?? 500);
      setFollowingHost(Boolean(joined.following_host));
      socket.setFollowerCount(joined.host_follower_count ?? 0);
      STORAGE[roomId] = { participantId: joined.participant.id, identity: joined.participant.identity };
      setRoom(joined.room);
    } catch (e) {
      const msg = (e as Error).message;
      if (msg.toLowerCase().includes("block") || msg.toLowerCase().includes("removed")) {
        setWasBlocked(true);
      }
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  // Signed-in users don't type a name — derive it from their profile and join
  // automatically. Guests still get the name prompt as a fallback.
  const autoJoinedRef = useRef(false);
  useEffect(() => {
    if (autoJoinedRef.current || participantId) return;
    const profileName = (account?.display_name || "").trim();
    if (!profileName) return;
    autoJoinedRef.current = true;
    setName(profileName);
    void handleJoin(profileName, account?.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [account, participantId]);

  useEffect(() => {
    if (!identity || !room) return;
    // Only show "blocked" for an ACTUAL ban (identity on the room's banned list).
    // Previously any room snapshot that momentarily lacked our participant id
    // (a stale poll/WS frame, prune, or replica lag) tripped a false "blocked".
    const banned = (room.banned ?? []).some((b) => b.identity === identity);
    if (banned) setWasBlocked(true);
  }, [room, identity]);

  const me = room?.participants.find((p) => p.id === participantId);
  const hasFloor = room?.floor_participant_id === participantId;

  // Hard mutex: learners join without publish rights; when the host/AI grants
  // the floor (me.can_publish flips) re-fetch a fresh token that permits
  // publishing (and a no-publish one when the floor is released).
  const publishRef = useRef<boolean | null>(null);
  useEffect(() => {
    if (!participantId) { publishRef.current = null; return; }
    const cp = Boolean(me?.can_publish);
    if (publishRef.current === cp) return;
    publishRef.current = cp;
    let alive = true;
    void liveRoomMediaToken(roomId, participantId)
      .then((r) => { if (alive) setMedia(r.media); })
      .catch(() => undefined);
    return () => { alive = false; };
  }, [me?.can_publish, participantId, roomId]);
  const inQueue = Boolean(room?.speaking_queue?.some(
    (e) => e.participant_id === participantId && (e.status === "waiting" || e.status === "speaking")
  ));
  const myPos = room?.speaking_queue?.find(
    (e) => e.participant_id === participantId && e.status === "waiting"
  )?.position ?? 0;

  const leaveAndBack = () => {
    if (participantId) {
      void leaveLiveRoom(roomId, participantId).catch(() => undefined);
    }
    onBack();
  };

  if (wasBlocked) {
    return (
      <View style={styles.wrap}>
        <Text style={styles.title}>Removed from class</Text>
        <Text style={styles.meta}>You were blocked from this live room.</Text>
        <PrimaryButton label="Back" onPress={leaveAndBack} />
      </View>
    );
  }

  if (!participantId) {
    return (
      <View style={styles.wrap}>
        <PrimaryButton label="← Back" onPress={onBack} variant="ghost" />
        <Text style={styles.title}>Salareen Live Room</Text>
        <Text style={styles.meta}>Theodore hosts · grid up to {room?.room_size ?? 6} seats</Text>
        {loading ? <ActivityIndicator color={theme.colors.accent} /> : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <GlassPanel style={styles.joinCard}>
          <TextInput
            value={name}
            onChangeText={setName}
            placeholder="Your name"
            placeholderTextColor={theme.colors.muted}
            style={styles.input}
          />
          <PrimaryButton label={busy ? "Joining…" : "Enter room"} onPress={() => void handleJoin()} loading={busy} />
        </GlassPanel>
      </View>
    );
  }

  return (
    <View style={styles.wrap}>
      {socket.presenceToast ? (
        <View style={styles.toast}>
          <Text style={styles.toastText}>
            {socket.presenceToast.kind === "join" ? "👋" : "👋"}{" "}
            {socket.presenceToast.name} {socket.presenceToast.kind === "join" ? "joined" : "left"}
          </Text>
        </View>
      ) : null}
      {socket.giftBanner ? (
        <View style={styles.giftBanner}>
          <Text style={styles.toastText}>{socket.giftBanner}</Text>
        </View>
      ) : null}
      <View style={styles.overlay} pointerEvents="none">
        {socket.floatingReactions.map((r) => (
          <Text key={r.id} style={[styles.floatingReaction, { left: `${r.left}%` }]}>
            {r.emoji}
          </Text>
        ))}
      </View>

      <View style={styles.header}>
        <PrimaryButton label="← Leave" onPress={leaveAndBack} variant="ghost" />
        <Text style={styles.title} numberOfLines={1}>{room?.title ?? "Live class"}</Text>
      </View>
      <Text style={styles.meta}>
        👁 {socket.viewerCount || room?.viewer_count || room?.participants.length || 0}
        {" · "}
        ❤️ {socket.followerCount} followers
        {socket.connected ? " · live" : " · polling"}
      </Text>
      <PrimaryButton
        label={followingHost ? "Following host" : "Follow host"}
        variant="ghost"
        onPress={async () => {
          try {
            const r = await liveRoomFollowHost(roomId, identity, followingHost);
            setFollowingHost(r.following);
            socket.setFollowerCount(r.follower_count);
          } catch (e) {
            setError((e as Error).message);
          }
        }}
      />
      {error ? <Text style={styles.error}>{error}</Text> : null}

      <GlassPanel style={styles.slide}>
        <Text style={styles.meta}>Slide {(room?.slide.index ?? 0) + 1}</Text>
        <Text style={styles.cardTitle}>{room?.slide.title}</Text>
        <Text style={styles.meta}>{room?.slide.narration || room?.slide.body}</Text>
      </GlassPanel>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.gridScroll}>
        {(room?.participants ?? []).map((p) => {
          const isMe = p.id === participantId;
          const emoji = p.role === "host" ? "🎓" : p.id === room?.floor_participant_id ? "🎤" : "👤";
          if (isMe && hasFloor && media) {
            return (
              <LiveKitParticipantTile
                key={p.id}
                media={media}
                canPublish={hasFloor}
                participantName={p.name}
                fallbackEmoji={emoji}
                large={p.role === "host"}
              />
            );
          }
          return (
            <View key={p.id} style={[
              styles.tile,
              p.role === "host" && styles.hostTile,
              p.id === room?.floor_participant_id && styles.speakingTile,
            ]}>
              <Text style={styles.tileEmoji}>{emoji}</Text>
              <Text style={styles.tileName} numberOfLines={1}>{p.name}</Text>
              {p.hand_raised && p.id !== room?.floor_participant_id ? <Text>✋</Text> : null}
              {modKey && p.role !== "host" && p.id !== participantId ? (
                <PrimaryButton
                  label="Block"
                  variant="ghost"
                  onPress={async () => setRoom(await liveRoomBan(roomId, p.id, modKey))}
                />
              ) : null}
              {p.role !== "host" && p.id !== participantId ? (
                <PrimaryButton
                  label="Report"
                  variant="ghost"
                  onPress={async () => {
                    if (!participantId) return;
                    setBusy(true);
                    try {
                      await liveRoomReport(roomId, participantId, p.id, "Reported from mobile", "other");
                      setError("");
                    } catch (e) {
                      setError((e as Error).message);
                    } finally {
                      setBusy(false);
                    }
                  }}
                />
              ) : null}
            </View>
          );
        })}
      </ScrollView>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.reactionRow}>
        {REACTIONS.map((emoji) => (
          <Pressable
            key={emoji}
            style={styles.reactionBtn}
            onPress={async () => {
              socket.pushReaction(emoji);
              try {
                setRoom(await liveRoomReaction(roomId, participantId, emoji));
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            <Text style={styles.reactionEmoji}>{emoji}</Text>
          </Pressable>
        ))}
        <PrimaryButton
          label={`🎁 Gifts (${giftBalance})`}
          variant="ghost"
          onPress={() => setShowGifts((v) => !v)}
        />
      </ScrollView>

      {showGifts ? (
        <View style={styles.giftGrid}>
          {giftCatalog.map((g) => (
            <Pressable
              key={g.id}
              style={styles.giftItem}
              disabled={busy || giftBalance < g.cost_points}
              onPress={async () => {
                setBusy(true);
                try {
                  const res = await liveRoomSendGift(roomId, participantId, g.id);
                  setRoom(res.room);
                  setGiftBalance(res.sender_balance);
                  setShowGifts(false);
                } catch (e) {
                  setError((e as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              <Text style={styles.giftEmoji}>{g.emoji}</Text>
              <Text style={styles.meta}>{g.name}</Text>
              <Text style={styles.meta}>{g.cost_points} pts</Text>
            </Pressable>
          ))}
        </View>
      ) : null}

      {(room?.speaking_queue?.length ?? 0) > 0 ? (
        <GlassPanel style={styles.slide}>
          <Text style={styles.cardTitle}>Q&A queue</Text>
          {room?.floor_holder ? (
            <Text style={styles.meta}>🎤 Now: {room.floor_holder.name}</Text>
          ) : null}
          {(room?.speaking_queue ?? []).filter((e) => e.status === "waiting").map((e) => (
            <Text key={e.id} style={styles.meta}>
              #{e.position} {e.name}{e.question ? ` — ${e.question}` : ""}
            </Text>
          ))}
          {myPos > 0 && !hasFloor ? (
            <Text style={styles.meta}>You are #{myPos} in line.</Text>
          ) : null}
        </GlassPanel>
      ) : null}

      {modKey && (room?.reports?.length ?? 0) > 0 ? (
        <GlassPanel style={styles.slide}>
          <Text style={styles.cardTitle}>User reports</Text>
          {(room?.reports ?? []).map((rep) => (
            <View key={rep.id} style={styles.controls}>
              <Text style={styles.meta}>
                {rep.reported_name} ({rep.category}) — {rep.reason}
                {"\n"}from {rep.reporter_name}
              </Text>
              <PrimaryButton
                label="Block"
                variant="ghost"
                onPress={async () => setRoom(await liveRoomBan(roomId, rep.reported_participant_id, modKey))}
              />
              <PrimaryButton
                label="Dismiss"
                variant="ghost"
                onPress={async () => setRoom(await liveRoomDismissReport(roomId, rep.id, modKey))}
              />
            </View>
          ))}
        </GlassPanel>
      ) : null}

      {modKey && (room?.banned?.length ?? 0) > 0 ? (
        <GlassPanel style={styles.slide}>
          <Text style={styles.cardTitle}>Blocked</Text>
          {(room?.banned ?? []).map((b) => (
            <View key={b.identity} style={styles.controls}>
              <Text style={styles.meta}>{b.name}</Text>
              <PrimaryButton
                label="Unblock"
                variant="ghost"
                onPress={async () => setRoom(await liveRoomUnban(roomId, b.identity, modKey))}
              />
            </View>
          ))}
        </GlassPanel>
      ) : null}

      <ScrollView style={styles.chatBox}>
        {(room?.chat ?? []).map((m) => (
          <Text key={m.id} style={styles.chatLine}>
            <Text style={styles.chatName}>{m.from_name}: </Text>
            {m.text}
          </Text>
        ))}
      </ScrollView>

      <View style={styles.controls}>
        <TextInput
          value={chat}
          onChangeText={setChat}
          placeholder="Chat…"
          placeholderTextColor={theme.colors.muted}
          style={[styles.input, { flex: 1 }]}
        />
        <PrimaryButton
          label="Send"
          onPress={async () => {
            if (!chat.trim() || !participantId) return;
            setBusy(true);
            try {
              setRoom(await liveRoomChat(roomId, participantId, chat.trim()));
              setChat("");
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
          loading={busy}
        />
      </View>
      <View style={styles.controls}>
        <TextInput
          value={question}
          onChangeText={setQuestion}
          placeholder="Ask Theodore…"
          placeholderTextColor={theme.colors.muted}
          style={[styles.input, { flex: 1 }]}
        />
        <PrimaryButton
          label="Ask"
          onPress={async () => {
            if (!question.trim() || !participantId) return;
            setBusy(true);
            try {
              const res = await liveRoomAsk(roomId, participantId, question.trim(), locale);
              setRoom(res.room);
              if (res.queued) {
                setError(`You're #${res.queue_position ?? myPos} in the Q&A queue.`);
              } else {
                setError("");
              }
              setQuestion("");
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
          loading={busy}
        />
      </View>
      <PrimaryButton
        label={
          hasFloor ? "You're speaking"
            : inQueue ? `Leave queue (#${myPos})`
            : "Join Q&A queue"
        }
        variant="ghost"
        onPress={async () => {
          if (!participantId) return;
          if (inQueue && !hasFloor) {
            setRoom(await liveRoomLeaveQueue(roomId, participantId));
          } else {
            setRoom(await liveRoomRaiseHand(roomId, participantId, question.trim()));
          }
        }}
      />
      {hasFloor ? (
        <PrimaryButton
          label="Done speaking"
          onPress={async () => {
            if (!participantId) return;
            setRoom(await liveRoomFinishTurn(roomId, participantId, modKey));
          }}
        />
      ) : null}
      {modKey ? (
        <View style={styles.controls}>
          <PrimaryButton
            label="Call next"
            onPress={async () => setRoom(await liveRoomCallNext(roomId, modKey))}
          />
          {room?.floor_participant_id ? (
            <PrimaryButton
              label="End turn"
              variant="ghost"
              onPress={async () => setRoom(
                await liveRoomFinishTurn(roomId, room.floor_participant_id!, modKey)
              )}
            />
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, padding: 16, gap: 10 },
  header: { flexDirection: "row", alignItems: "center", gap: 8 },
  title: { color: theme.colors.text, fontSize: 18, fontWeight: "700", flex: 1 },
  meta: { color: theme.colors.muted, fontSize: 13 },
  joinCard: { gap: 10, marginTop: 12 },
  input: {
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: 10,
    padding: 10,
    color: theme.colors.text,
    backgroundColor: "rgba(0,0,0,0.2)",
  },
  slide: { gap: 6 },
  cardTitle: { color: theme.colors.text, fontSize: 16, fontWeight: "600" },
  gridScroll: { maxHeight: 190 },
  tile: {
    width: 88,
    height: 88,
    marginRight: 8,
    borderRadius: 12,
    backgroundColor: "rgba(99,102,241,0.35)",
    alignItems: "center",
    justifyContent: "center",
    padding: 6,
  },
  hostTile: { backgroundColor: "rgba(124,58,237,0.5)", width: 100 },
  speakingTile: { borderWidth: 2, borderColor: "#34d399" },
  tileEmoji: { fontSize: 22 },
  tileName: { color: theme.colors.text, fontSize: 11, marginTop: 4 },
  reactionRow: { maxHeight: 44 },
  reactionBtn: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    marginRight: 6,
    borderRadius: 8,
    backgroundColor: "rgba(255,255,255,0.08)",
  },
  reactionEmoji: { fontSize: 20 },
  giftGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  giftItem: {
    width: "30%",
    padding: 8,
    borderRadius: 10,
    backgroundColor: "rgba(0,0,0,0.25)",
    alignItems: "center",
  },
  giftEmoji: { fontSize: 24 },
  chatBox: { flex: 1, maxHeight: 160, backgroundColor: "rgba(0,0,0,0.25)", borderRadius: 10, padding: 8 },
  chatLine: { color: theme.colors.text, fontSize: 13, marginBottom: 6 },
  chatName: { color: "#c4b5fd", fontWeight: "600" },
  controls: { flexDirection: "row", gap: 8, alignItems: "center" },
  error: { color: "#f87171" },
  toast: {
    position: "absolute",
    top: 8,
    alignSelf: "center",
    zIndex: 20,
    backgroundColor: "rgba(15,7,32,0.92)",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
  },
  giftBanner: {
    position: "absolute",
    top: 48,
    alignSelf: "center",
    zIndex: 20,
    backgroundColor: "rgba(219,39,119,0.85)",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 12,
  },
  toastText: { color: "#fff", fontSize: 13 },
  overlay: { ...StyleSheet.absoluteFillObject, zIndex: 15 },
  floatingReaction: {
    position: "absolute",
    bottom: 120,
    fontSize: 28,
  },
});
