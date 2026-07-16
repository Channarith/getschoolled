import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";

import {
  getLiveRoom, getLiveGiftCatalog, joinLiveRoom, leaveLiveRoom, liveRoomAsk, liveRoomBan, liveRoomCallNext,
  liveRoomChat, liveRoomDismissReport, liveRoomFinishTurn, liveRoomFollowHost, liveRoomLeaveQueue,
  liveRoomMediaToken,
  liveRoomRaiseHand, liveRoomReaction, liveRoomReport, liveRoomSendGift, liveRoomStartPresentation,
  liveRoomTick, liveRoomUnban,
  startGroupClass,
  type LiveGiftCatalogItem, type LiveKitMedia, type LiveRoomState,
} from "../api";
import { useAuth } from "../auth/AuthContext";
import { useT } from "../i18n";
import { speakNatural, stopSpeech } from "../tts";
import GlassPanel from "../components/GlassPanel";
import LiveKitParticipantTile from "../components/LiveKitParticipantTile";
import PrimaryButton from "../components/PrimaryButton";
import { getLiveRoomLocation } from "../liveRoomLocation";
import { useLiveRoomSocket } from "../liveRoomWs";
import { theme } from "../theme";

const STORAGE: Record<string, { participantId: string; identity: string }> = {};
const MOD_STORAGE: Record<string, string> = {};
const REACTIONS = ["❤️", "👏", "🔥", "😂", "🎉", "👍"] as const;

const CLASS_END_COUNTDOWN = 5;

// Courteous farewell shown when a group lesson's allotted time expires, keyed by
// language so the learner is thanked in the language they speak (English fallback).
const FAREWELL_BY_CODE: Record<string, string> = {
  en: "Thank you for attending today's class. We hope you enjoyed learning with us, and we look forward to welcoming you back soon.",
  es: "Gracias por asistir a la clase de hoy. Esperamos que haya disfrutado aprender con nosotros y deseamos verle de nuevo pronto.",
  fr: "Merci d'avoir assisté au cours d'aujourd'hui. Nous espérons que vous avez apprécié d'apprendre avec nous et avons hâte de vous revoir bientôt.",
  de: "Vielen Dank für Ihre Teilnahme am heutigen Kurs. Wir hoffen, dass Ihnen das Lernen mit uns gefallen hat, und freuen uns, Sie bald wiederzusehen.",
  pt: "Obrigado por participar da aula de hoje. Esperamos que tenha gostado de aprender conosco e esperamos vê-lo novamente em breve.",
  zh: "感谢您参加今天的课程。希望您在学习中收获满满，期待下次再会！",
  ja: "本日の授業にご参加いただき、誠にありがとうございました。またお会いできる日を楽しみにしております。",
  ko: "오늘 수업에 참여해 주셔서 감사합니다. 즐거운 배움의 시간이 되셨길 바라며, 다음에 또 뵙겠습니다.",
  ar: "شكرًا لحضوركم درس اليوم. نتمنى أن تكونوا قد استمتعتم بالتعلّم معنا، ونتطلّع إلى رؤيتكم مجددًا قريبًا.",
  hi: "आज की कक्षा में शामिल होने के लिए धन्यवाद। हमें आशा है कि आपको हमारे साथ सीखना अच्छा लगा।",
  km: "សូមអរគុណសម្រាប់ការចូលរួមថ្នាក់រៀនថ្ងៃនេះ។ សង្ឃឹមថាអ្នកបានរីករាយនឹងការសិក្សាជាមួយយើង។",
  tr: "Bugünkü derse katıldığınız için teşekkür ederiz. Bizimle öğrenmekten keyif aldığınızı umuyoruz.",
  ru: "Спасибо за участие в сегодняшнем занятии. Надеемся, вам понравилось учиться с нами.",
};

function farewellFor(locale: string): string {
  const code = (locale || "").toLowerCase().split("-")[0];
  return FAREWELL_BY_CODE[code] || FAREWELL_BY_CODE.en;
}

// Which pop-up sheet (if any) is open. Everything except the presenter lives in a
// sheet so the small phone screen stays focused on the teacher/slide.
type SheetKind = null | "chat" | "ask" | "react" | "gifts" | "more";

// A single tab in the bottom action bar: a large tappable icon + tiny caption,
// with an optional unread/position badge and an active (highlighted) state.
function IconTab({
  icon, label, onPress, active, badge, disabled,
}: {
  icon: string;
  // Omit the label for obvious icons (chat, gift, react, more) — the glyph alone
  // is enough and keeps the phone bar clean. Provide it only when the icon is
  // ambiguous or stateful (e.g. Ask, or the raise-hand toggle).
  label?: string;
  onPress: () => void;
  active?: boolean;
  badge?: number;
  disabled?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityLabel={label || icon}
      style={({ pressed }) => [styles.iconTab, pressed && styles.iconTabPressed, disabled && { opacity: 0.4 }]}
      hitSlop={{ top: 8, bottom: 8, left: 4, right: 4 }}
    >
      <View>
        <Text style={[styles.iconGlyph, active && styles.iconGlyphActive]}>{icon}</Text>
        {badge ? (
          <View style={styles.badge}>
            <Text style={styles.badgeText}>{badge > 99 ? "99+" : badge}</Text>
          </View>
        ) : null}
      </View>
      {label ? (
        <Text style={[styles.iconLabel, active && styles.iconLabelActive]} numberOfLines={1}>{label}</Text>
      ) : null}
    </Pressable>
  );
}

// A bottom sheet that slides up over the presenter. Tapping the dimmed backdrop
// or the ✕ closes it. Content is scrollable and capped so it never covers the
// whole screen.
function BottomSheet({
  visible, title, onClose, children,
}: {
  visible: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.sheetRoot}>
        <Pressable style={styles.sheetBackdrop} onPress={onClose} />
        <View style={styles.sheet}>
          <View style={styles.sheetHandle} />
          <View style={styles.sheetHead}>
            <Text style={styles.sheetTitle} numberOfLines={1}>{title}</Text>
            <Pressable onPress={onClose} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
              <Text style={styles.sheetClose}>✕</Text>
            </Pressable>
          </View>
          {children}
        </View>
      </View>
    </Modal>
  );
}

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
  const [followingHost, setFollowingHost] = useState(false);
  const [endLeft, setEndLeft] = useState(CLASS_END_COUNTDOWN);
  const [muted, setMuted] = useState(false);
  const [sheet, setSheet] = useState<SheetKind>(null);
  const [chatSeen, setChatSeen] = useState(0);
  const chatSeenInit = useRef(false);
  const [joinedModKey, setJoinedModKey] = useState("");
  const modKey = moderatorKey || joinedModKey || MOD_STORAGE[roomId] || "";
  const classEnded = room?.status === "ended";
  // Can this viewer start/drive the class? The room's first-seat admin (holds the
  // moderator key) or the platform admin (admin@salareen.com, authorized by token).
  const canModerate = Boolean(modKey) || Boolean(account?.is_admin);

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

  // Heartbeat the room clock so a mobile-only group class still auto-starts,
  // auto-advances slides, and auto-ends when its allotted time is up (parity with
  // web). Idempotent server-side; harmless for open-ended rooms.
  useEffect(() => {
    if (!participantId) return;
    const t = setInterval(() => {
      void liveRoomTick(roomId, participantId).then((r) => setRoom(r.room)).catch(() => undefined);
    }, 3000);  // 3s so slides auto-advance close to the 5s dwell (and presence stays fresh)
    return () => clearInterval(t);
  }, [participantId, roomId]);

  // Kick off the AI presentation once the moderator/admin is in the room and it
  // isn't already presenting. Without this the class never enters "presenting",
  // so the server never auto-advances and it's stuck on slide 1. (Server-side
  // auto-start only fires for a FULL room or 5 min past the scheduled time — a
  // lone learner would otherwise wait forever.) Idempotent + authorized server-side.
  const autoStartedRef = useRef(false);
  useEffect(() => {
    if (autoStartedRef.current) return;
    if (!participantId || !room || classEnded) return;
    if (room.presenting) { autoStartedRef.current = true; return; }
    if (!canModerate) return;
    autoStartedRef.current = true;
    void liveRoomStartPresentation(roomId, modKey)
      .then((r) => setRoom(r))
      .catch(() => { autoStartedRef.current = false; });   // allow a retry on transient failure
  }, [participantId, room, classEnded, canModerate, modKey, roomId]);

  // Audio: the AI host (Theodore) has no camera, so its "voice" is TTS. Speak the
  // current slide (title + narration) whenever it changes, and speak Theodore's
  // Q&A answers / announcements as they arrive — in the learner's language. This
  // is why "no audio comes out" otherwise: nobody publishes host audio to LiveKit.
  const spokenSlideRef = useRef<number>(-1);
  const spokenChatRef = useRef<string>("");
  const didInitChatRef = useRef(false);

  useEffect(() => {
    if (!participantId || muted) return;
    const s = room?.slide;
    if (!s || spokenSlideRef.current === s.index) return;
    spokenSlideRef.current = s.index;
    // Narrate the full slide body (substantive lecture), not just the one-line
    // script — the server paces auto-advance to this so it isn't cut off.
    const text = `${s.title}. ${s.body || s.narration || ""}`.trim();
    if (text) speakNatural(text, { locale });
  }, [room?.slide?.index, participantId, muted, locale]);

  useEffect(() => {
    if (!participantId) return;
    const chat = room?.chat ?? [];
    // Newest message spoken BY Theodore that isn't the slide-narration echo
    // ("📖 …", already spoken via the slide effect) or a system "Room" note.
    let latest: { id: string; from_name: string; text: string } | undefined;
    for (let i = chat.length - 1; i >= 0; i--) {
      const m = chat[i];
      if (m.from_name.includes("Theodore") && !m.text.startsWith("📖")) { latest = m; break; }
    }
    if (!latest) return;
    // Don't replay history on join: seed the marker to the newest on first sight.
    if (!didInitChatRef.current) {
      didInitChatRef.current = true;
      spokenChatRef.current = latest.id;
      return;
    }
    if (spokenChatRef.current === latest.id) return;
    spokenChatRef.current = latest.id;
    if (!muted) speakNatural(latest.text, { locale });
  }, [room?.chat, participantId, muted, locale]);

  useEffect(() => () => stopSpeech(), []);  // stop narration when leaving the screen

  const toggleMute = () => {
    setMuted((m) => {
      const next = !m;
      if (next) stopSpeech();
      return next;
    });
  };

  // Unread-chat badge: seed to the current length once (don't flag history as
  // unread), keep it synced while the chat sheet is open, and count new messages
  // that arrive while it's closed.
  const chatLen = room?.chat?.length ?? 0;
  useEffect(() => {
    if (!chatSeenInit.current && chatLen > 0) {
      chatSeenInit.current = true;
      setChatSeen(chatLen);
    }
  }, [chatLen]);
  useEffect(() => {
    if (sheet === "chat") setChatSeen(chatLen);
  }, [sheet, chatLen]);
  const unread = Math.max(0, chatLen - chatSeen);

  const openChat = () => { setChatSeen(chatLen); setSheet("chat"); };

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
      // The first-seat admin receives the moderator key so their client can
      // start the class (and thus drive slide auto-advance).
      if (joined.moderator_key) {
        setJoinedModKey(joined.moderator_key);
        MOD_STORAGE[roomId] = joined.moderator_key;
      }
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

  // Raise your hand (join the Q&A queue) or lower it (leave). The AI/host calls
  // on raised hands in turn; only the floor holder is actually heard.
  const toggleHand = async () => {
    if (!participantId || hasFloor) return;
    try {
      if (inQueue) {
        setRoom(await liveRoomLeaveQueue(roomId, participantId));
      } else {
        setRoom(await liveRoomRaiseHand(roomId, participantId, question.trim()));
      }
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const leaveAndBack = () => {
    stopSpeech();
    if (participantId) {
      void leaveLiveRoom(roomId, participantId).catch(() => undefined);
    }
    onBack();
  };

  // When the class ends (its allotted time expired), count down and then excuse
  // the learner back to the previous screen — mirrors the web farewell.
  useEffect(() => {
    if (!classEnded || !participantId) return;
    setEndLeft(CLASS_END_COUNTDOWN);
    const iv = setInterval(() => {
      setEndLeft((n) => {
        if (n <= 1) { clearInterval(iv); leaveAndBack(); return 0; }
        return n - 1;
      });
    }, 1000);
    return () => clearInterval(iv);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classEnded, participantId]);

  if (classEnded && participantId) {
    return (
      <View style={[styles.wrap, styles.endWrap]}>
        <Text style={styles.endEmoji}>🎓</Text>
        <Text style={styles.endTitle}>Class complete</Text>
        <Text style={styles.endMsg}>{farewellFor(locale)}</Text>
        <Text style={styles.meta}>Returning in {endLeft}s…</Text>
        <PrimaryButton label="Leave now" onPress={leaveAndBack} />
      </View>
    );
  }

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
        <Pressable onPress={leaveAndBack} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
          <Text style={styles.leaveText}>← Leave</Text>
        </Pressable>
        <Text style={styles.title} numberOfLines={1}>{room?.title ?? "Live class"}</Text>
        <Pressable onPress={toggleMute} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
          <Text style={styles.muteBtn}>{muted ? "🔇" : "🔊"}</Text>
        </Pressable>
      </View>
      <Text style={styles.meta} numberOfLines={1}>
        👁 {socket.viewerCount || room?.viewer_count || room?.participants.length || 0}
        {" · ❤️ "}{socket.followerCount}
        {socket.connected ? " · live" : " · polling"}
      </Text>
      {error ? <Text style={styles.error}>{error}</Text> : null}

      {/* Presenter hero fills the screen; everything else opens from the bar. */}
      <GlassPanel style={styles.hero}>
        <Text style={styles.presenterHost} numberOfLines={1}>
          🎓 {room?.host?.name ?? "Theodore (AI Host)"} · Slide {(room?.slide.index ?? 0) + 1}
        </Text>
        <ScrollView style={styles.heroScroll} contentContainerStyle={styles.heroContent}>
          <Text style={styles.presenterTitle}>{room?.slide.title}</Text>
          <Text style={styles.presenterBody}>{room?.slide.narration || room?.slide.body}</Text>
        </ScrollView>
        {muted ? <Text style={styles.mutedHint}>Audio muted — tap 🔊 up top to hear the teacher</Text> : null}
        {hasFloor ? (
          <Text style={styles.floorChip}>🎤 You&apos;re live — open &ldquo;More&rdquo; to finish your turn</Text>
        ) : inQueue ? (
          <Text style={styles.floorChip}>✋ You&apos;re #{myPos} in line</Text>
        ) : null}
        {hasFloor && media ? (
          <View style={styles.pip}>
            <LiveKitParticipantTile
              media={media}
              canPublish={hasFloor}
              participantName={me?.name ?? "You"}
              fallbackEmoji="🎤"
            />
          </View>
        ) : null}
      </GlassPanel>

      {/* Bottom action bar — icons reveal chat / ask / react / gifts / more. */}
      <View style={styles.actionBar}>
        {/* Obvious icons go label-less; Ask and the raise-hand toggle keep a
            short caption because the glyph alone is ambiguous / stateful. */}
        <IconTab icon="💬" badge={unread || undefined} onPress={openChat} />
        <IconTab icon="❓" label="Ask" onPress={() => setSheet("ask")} />
        <IconTab
          icon="✋"
          label={hasFloor ? "Live" : inQueue ? "Lower" : "Hand"}
          active={inQueue || hasFloor}
          badge={myPos || undefined}
          disabled={hasFloor}
          onPress={() => void toggleHand()}
        />
        <IconTab icon="😀" onPress={() => setSheet("react")} />
        <IconTab icon="🎁" onPress={() => setSheet("gifts")} />
        <IconTab icon="⋯" onPress={() => setSheet("more")} />
      </View>

      {/* ---- Chat ---- */}
      <BottomSheet visible={sheet === "chat"} title="Chat" onClose={() => setSheet(null)}>
        <ScrollView style={styles.sheetScroll}>
          {chatLen === 0 ? <Text style={styles.meta}>No messages yet — say hello 👋</Text> : null}
          {(room?.chat ?? []).map((m) => (
            <Text key={m.id} style={styles.chatLine}>
              <Text style={styles.chatName}>{m.from_name}: </Text>{m.text}
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
            loading={busy}
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
          />
        </View>
      </BottomSheet>

      {/* ---- Ask Theodore ---- */}
      <BottomSheet visible={sheet === "ask"} title="Ask Theodore" onClose={() => setSheet(null)}>
        <Text style={styles.meta}>
          Your question goes to the AI teacher. If someone&apos;s speaking, you&apos;ll join the Q&amp;A queue.
        </Text>
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
            loading={busy}
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
                  setSheet(null);
                }
                setQuestion("");
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          />
        </View>
      </BottomSheet>

      {/* ---- Reactions ---- */}
      <BottomSheet visible={sheet === "react"} title="Send a reaction" onClose={() => setSheet(null)}>
        <View style={styles.reactPicker}>
          {REACTIONS.map((emoji) => (
            <Pressable
              key={emoji}
              style={styles.reactPick}
              onPress={async () => {
                socket.pushReaction(emoji);
                setSheet(null);
                try {
                  setRoom(await liveRoomReaction(roomId, participantId, emoji));
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              <Text style={styles.reactPickEmoji}>{emoji}</Text>
            </Pressable>
          ))}
        </View>
      </BottomSheet>

      {/* ---- Gifts ---- */}
      <BottomSheet visible={sheet === "gifts"} title={`Gifts · ${giftBalance} pts`} onClose={() => setSheet(null)}>
        <View style={styles.giftGrid}>
          {giftCatalog.map((g) => (
            <Pressable
              key={g.id}
              style={[styles.giftItem, (busy || giftBalance < g.cost_points) && { opacity: 0.4 }]}
              disabled={busy || giftBalance < g.cost_points}
              onPress={async () => {
                setBusy(true);
                try {
                  const res = await liveRoomSendGift(roomId, participantId, g.id);
                  setRoom(res.room);
                  setGiftBalance(res.sender_balance);
                  setSheet(null);
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
      </BottomSheet>

      {/* ---- More: follow, people, Q&A, host controls, moderation ---- */}
      <BottomSheet visible={sheet === "more"} title="Room" onClose={() => setSheet(null)}>
        <ScrollView style={styles.sheetScroll}>
          <PrimaryButton
            label={followingHost ? "✓ Following host" : "Follow host"}
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
          {hasFloor ? (
            <PrimaryButton
              label="Done speaking"
              onPress={async () => {
                if (!participantId) return;
                setRoom(await liveRoomFinishTurn(roomId, participantId, modKey));
                setSheet(null);
              }}
            />
          ) : null}

          {(room?.speaking_queue?.length ?? 0) > 0 ? (
            <View style={styles.sheetSection}>
              <Text style={styles.cardTitle}>Q&amp;A queue</Text>
              {room?.floor_holder ? <Text style={styles.meta}>🎤 Now: {room.floor_holder.name}</Text> : null}
              {(room?.speaking_queue ?? []).filter((e) => e.status === "waiting").map((e) => (
                <Text key={e.id} style={styles.meta}>#{e.position} {e.name}{e.question ? ` — ${e.question}` : ""}</Text>
              ))}
            </View>
          ) : null}

          <View style={styles.sheetSection}>
            <Text style={styles.cardTitle}>In the room ({(room?.participants ?? []).length})</Text>
            {(room?.participants ?? []).map((p) => (
              <View key={p.id} style={styles.personRow}>
                <Text style={styles.personName} numberOfLines={1}>
                  {p.id === room?.floor_participant_id ? "🎤 " : p.role === "host" ? "🎓 " : "👤 "}
                  {p.name}{p.id === participantId ? " (you)" : ""}
                  {p.hand_raised && p.id !== room?.floor_participant_id ? " ✋" : ""}
                </Text>
                {p.role !== "host" && p.id !== participantId ? (
                  <View style={styles.personActions}>
                    {modKey ? (
                      <Pressable onPress={async () => setRoom(await liveRoomBan(roomId, p.id, modKey))}>
                        <Text style={styles.linkDanger}>Block</Text>
                      </Pressable>
                    ) : null}
                    <Pressable
                      onPress={async () => {
                        if (!participantId) return;
                        try {
                          await liveRoomReport(roomId, participantId, p.id, "Reported from mobile", "other");
                          setError("");
                        } catch (e) {
                          setError((e as Error).message);
                        }
                      }}
                    >
                      <Text style={styles.linkMuted}>Report</Text>
                    </Pressable>
                  </View>
                ) : null}
              </View>
            ))}
          </View>

          {modKey ? (
            <View style={styles.sheetSection}>
              <Text style={styles.cardTitle}>Host controls</Text>
              <View style={styles.controls}>
                <PrimaryButton label="Call next" onPress={async () => setRoom(await liveRoomCallNext(roomId, modKey))} />
                {room?.floor_participant_id ? (
                  <PrimaryButton
                    label="End turn"
                    variant="ghost"
                    onPress={async () => setRoom(await liveRoomFinishTurn(roomId, room.floor_participant_id!, modKey))}
                  />
                ) : null}
              </View>
            </View>
          ) : null}

          {modKey && (room?.reports?.length ?? 0) > 0 ? (
            <View style={styles.sheetSection}>
              <Text style={styles.cardTitle}>User reports</Text>
              {(room?.reports ?? []).map((rep) => (
                <View key={rep.id} style={styles.personRow}>
                  <Text style={styles.meta} numberOfLines={2}>{rep.reported_name} ({rep.category}) — {rep.reason}</Text>
                  <View style={styles.personActions}>
                    <Pressable onPress={async () => setRoom(await liveRoomBan(roomId, rep.reported_participant_id, modKey))}>
                      <Text style={styles.linkDanger}>Block</Text>
                    </Pressable>
                    <Pressable onPress={async () => setRoom(await liveRoomDismissReport(roomId, rep.id, modKey))}>
                      <Text style={styles.linkMuted}>Dismiss</Text>
                    </Pressable>
                  </View>
                </View>
              ))}
            </View>
          ) : null}

          {modKey && (room?.banned?.length ?? 0) > 0 ? (
            <View style={styles.sheetSection}>
              <Text style={styles.cardTitle}>Blocked</Text>
              {(room?.banned ?? []).map((b) => (
                <View key={b.identity} style={styles.personRow}>
                  <Text style={styles.meta}>{b.name}</Text>
                  <Pressable onPress={async () => setRoom(await liveRoomUnban(roomId, b.identity, modKey))}>
                    <Text style={styles.linkMuted}>Unblock</Text>
                  </Pressable>
                </View>
              ))}
            </View>
          ) : null}
        </ScrollView>
      </BottomSheet>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, padding: 16, gap: 8 },
  endWrap: { alignItems: "center", justifyContent: "center", gap: 14 },
  endEmoji: { fontSize: 52 },
  endTitle: { color: theme.colors.text, fontSize: 24, fontWeight: "800" },
  endMsg: { color: theme.colors.text, fontSize: 16, textAlign: "center", lineHeight: 24 },
  header: { flexDirection: "row", alignItems: "center", gap: 10 },
  leaveText: { color: theme.colors.accent, fontSize: 15, fontWeight: "700" },
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
  cardTitle: { color: theme.colors.text, fontSize: 15, fontWeight: "700", marginBottom: 4 },
  muteBtn: { fontSize: 24 },
  error: { color: "#f87171" },

  // Presenter hero — takes all the vertical space between the meta row and the
  // action bar so the teacher/slide is the clear focus on a phone.
  hero: { flex: 1, gap: 8, position: "relative" },
  presenterHost: { color: "#c4b5fd", fontSize: 13, fontWeight: "600" },
  heroScroll: { flex: 1 },
  heroContent: { gap: 10, paddingBottom: 8 },
  presenterTitle: { color: theme.colors.text, fontSize: 26, fontWeight: "800", lineHeight: 32 },
  presenterBody: { color: theme.colors.text, fontSize: 17, lineHeight: 25, opacity: 0.94 },
  mutedHint: { color: theme.colors.muted, fontSize: 12, fontStyle: "italic" },
  floorChip: {
    color: "#e9d5ff", fontSize: 13, fontWeight: "600",
    backgroundColor: "rgba(124,58,237,0.35)",
    paddingVertical: 6, paddingHorizontal: 10, borderRadius: 999, overflow: "hidden",
    alignSelf: "flex-start",
  },
  pip: {
    position: "absolute", right: 10, bottom: 10, width: 96, height: 128,
    borderRadius: 12, overflow: "hidden", borderWidth: 1, borderColor: "rgba(255,255,255,0.25)",
  },

  // Bottom action bar of icon "tabs".
  actionBar: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    paddingTop: 10,
    paddingBottom: 6,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: theme.colors.border,
  },
  iconTab: { flex: 1, alignItems: "center", gap: 3, paddingVertical: 2 },
  iconTabPressed: { opacity: 0.5 },
  iconGlyph: { fontSize: 24, textAlign: "center" },
  iconGlyphActive: { transform: [{ scale: 1.1 }] },
  iconLabel: { color: theme.colors.muted, fontSize: 11 },
  iconLabelActive: { color: theme.colors.accent, fontWeight: "700" },
  badge: {
    position: "absolute", top: -4, right: -10, minWidth: 16, height: 16, paddingHorizontal: 4,
    borderRadius: 8, backgroundColor: "#ef4444", alignItems: "center", justifyContent: "center",
  },
  badgeText: { color: "#fff", fontSize: 10, fontWeight: "700" },

  // Bottom sheets.
  sheetRoot: { flex: 1, justifyContent: "flex-end" },
  sheetBackdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(0,0,0,0.5)" },
  sheet: {
    backgroundColor: "#160b2e",
    borderTopLeftRadius: 20, borderTopRightRadius: 20,
    paddingHorizontal: 16, paddingTop: 8, paddingBottom: 28,
    maxHeight: "72%", gap: 10,
  },
  sheetHandle: { alignSelf: "center", width: 42, height: 5, borderRadius: 999, backgroundColor: "rgba(255,255,255,0.25)", marginBottom: 6 },
  sheetHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  sheetTitle: { color: theme.colors.text, fontSize: 17, fontWeight: "800", flex: 1 },
  sheetClose: { color: theme.colors.muted, fontSize: 18, fontWeight: "700" },
  sheetScroll: { maxHeight: 360 },
  sheetSection: { marginTop: 12, gap: 4 },

  reactPicker: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-around", gap: 8, paddingVertical: 6 },
  reactPick: {
    width: 60, height: 60, borderRadius: 14, alignItems: "center", justifyContent: "center",
    backgroundColor: "rgba(255,255,255,0.08)",
  },
  reactPickEmoji: { fontSize: 30 },

  giftGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  giftItem: {
    width: "30%", padding: 8, borderRadius: 10,
    backgroundColor: "rgba(0,0,0,0.25)", alignItems: "center",
  },
  giftEmoji: { fontSize: 24 },

  chatLine: { color: theme.colors.text, fontSize: 14, marginBottom: 8, lineHeight: 20 },
  chatName: { color: "#c4b5fd", fontWeight: "600" },
  controls: { flexDirection: "row", gap: 8, alignItems: "center" },

  personRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8, paddingVertical: 6 },
  personName: { color: theme.colors.text, fontSize: 14, flex: 1 },
  personActions: { flexDirection: "row", gap: 14, alignItems: "center" },
  linkDanger: { color: "#f87171", fontSize: 13, fontWeight: "700" },
  linkMuted: { color: theme.colors.muted, fontSize: 13, fontWeight: "600" },

  // Overlays (kept).
  toast: {
    position: "absolute", top: 8, alignSelf: "center", zIndex: 20,
    backgroundColor: "rgba(15,7,32,0.92)", paddingHorizontal: 14, paddingVertical: 8, borderRadius: 999,
  },
  giftBanner: {
    position: "absolute", top: 48, alignSelf: "center", zIndex: 20,
    backgroundColor: "rgba(219,39,119,0.85)", paddingHorizontal: 14, paddingVertical: 8, borderRadius: 12,
  },
  toastText: { color: "#fff", fontSize: 13 },
  overlay: { ...StyleSheet.absoluteFillObject, zIndex: 15 },
  floatingReaction: { position: "absolute", bottom: 120, fontSize: 28 },
});
