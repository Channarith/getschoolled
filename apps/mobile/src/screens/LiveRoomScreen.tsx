import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator, Alert, Animated, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput,
  useWindowDimensions, View,
} from "react-native";

import {
  deleteLiveRoom, liveRoomAdvance,
  getLiveRoom, getLiveGiftCatalog, joinLiveRoom, leaveLiveRoom, liveRoomAskStream, liveRoomBan, liveRoomCallNext,
  liveRoomChat, liveRoomDismissReport, liveRoomEnd, liveRoomFinishTurn, liveRoomFollowHost, liveRoomLeaveQueue,
  liveRoomMediaToken,
  liveRoomPlayGame, liveRoomRaiseHand, liveRoomReaction, liveRoomReport,
  liveRoomSendGift, liveRoomStartGame, liveRoomStartPresentation,
  liveRoomTick, liveRoomUnban,
  startGroupClass,
  type LiveGiftCatalogItem, type LiveGroupGameType, type LiveKitMedia, type LiveRoomState,
} from "../api";
import { useAuth } from "../auth/AuthContext";
import { useAndroidBackTo } from "../hooks/useAndroidBack";
import { useT } from "../i18n";
import { speakNatural, stopSpeech } from "../tts";
import { buildNarrationSpeakOptions } from "../narrationTts";
import { startVoiceListening, stopVoiceListening } from "../voiceAssistant";
import GlassPanel from "../components/GlassPanel";
import { LiveKitVideoView } from "../components/liveKitRuntime";
import { useLiveKitRoom } from "../components/useLiveKitRoom";
import PrimaryButton from "../components/PrimaryButton";
import { getLiveRoomLocation } from "../liveRoomLocation";
import { useLiveRoomSocket } from "../liveRoomWs";
import { theme } from "../theme";

const STORAGE: Record<string, { participantId: string; identity: string }> = {};
const MOD_STORAGE: Record<string, string> = {};
const REACTIONS = ["❤️", "👏", "🔥", "😂", "🎉", "👍"] as const;
const GAME_LIBRARY: {
  type: LiveGroupGameType; label: string; prompt: string; answer: string;
}[] = [
  { type: "quiz_race", label: "⚡ First answer race", prompt: "What does AI stand for?", answer: "artificial intelligence" },
  { type: "tic_tac_toe", label: "⭕ Learning tic-tac-toe", prompt: "What does ML stand for?", answer: "machine learning" },
  { type: "hangman", label: "🔤 Learning hangman", prompt: "An AI model learns from this", answer: "data" },
  { type: "multiple_choice", label: "🔢 Multiple choice dash", prompt: "Which is AI? A) Neural network B) Hammer C) Bicycle", answer: "A" },
  { type: "true_false", label: "✅ True or false", prompt: "AI systems learn patterns from data.", answer: "true" },
  { type: "word_scramble", label: "🔀 Word scramble", prompt: "Unscramble this AI term", answer: "algorithm" },
  { type: "fill_blank", label: "✍️ Fill the blank", prompt: "AI models learn from ____.", answer: "data" },
  { type: "emoji_decode", label: "🧩 Emoji decode", prompt: "Decode: 🧠 + 💻", answer: "artificial intelligence" },
  { type: "lightning_round", label: "🌩️ Lightning round", prompt: "Name the field that lets computers understand language.", answer: "natural language processing" },
  { type: "team_buzzer", label: "🔔 Team buzzer", prompt: "Buzz in: What is a chatbot powered by?", answer: "artificial intelligence" },
  { type: "hot_seat", label: "🔥 Hot seat", prompt: "Explain the abbreviation LLM.", answer: "large language model" },
  { type: "jeopardy", label: "💎 Jeopardy challenge", prompt: "This AI system generates new text, images, or audio.", answer: "generative AI" },
];

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
type SheetKind = null | "chat" | "ask" | "react" | "gifts" | "games" | "more";

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

function initials(name: string): string {
  return (name || "?")
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

// One seat / profile card in the classroom strip: the AI host, a learner (with
// mic/hand/mute state), the current viewer, or an empty "Open seat" slot. Live
// webcam goes in the TOP window of the card (never a floating PiP over the
// slide) — parity with the web participant grid.
function SeatTile({
  name, host, me, floor, hand, muted, open, track, cameraOn, onToggleCamera, onPress,
}: {
  name?: string;
  host?: boolean;
  me?: boolean;
  floor?: boolean;
  hand?: boolean;
  muted?: boolean;
  open?: boolean;
  track?: object | null;
  cameraOn?: boolean;
  onToggleCamera?: () => void;
  /** Tap to expand this tile to full-screen. */
  onPress?: () => void;
}) {
  if (open) {
    return (
      <View style={[styles.seat, styles.seatOpen]}>
        <View style={styles.seatVideoWindow}>
          <Text style={styles.seatOpenText}>Open{"\n"}seat</Text>
        </View>
        <View style={styles.seatFooter}>
          <Text style={styles.seatNameMuted} numberOfLines={1}>—</Text>
        </View>
      </View>
    );
  }
  const hasVideo = Boolean(track);
  const label = host ? "Host" : me ? "You" : name;
  const seatStyle = [
    styles.seat,
    host && styles.seatHost,
    floor && styles.seatFloor,
    me && !floor && styles.seatMe,
  ];
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${label ?? "Seat"} — tap to expand`}
      style={({ pressed }) => [...seatStyle, pressed && styles.seatPressed]}
    >
      {/* Transparent background when video is live so the SurfaceView shows through on Android. */}
      <View style={[styles.seatVideoWindow, hasVideo && styles.seatVideoWindowLive]}>
        {hasVideo ? (
          <LiveKitVideoView track={track ?? null} mirror={Boolean(me)} />
        ) : (
          <Text style={styles.seatAvatar}>{host ? "🎓" : initials(name || "")}</Text>
        )}
        <View style={styles.seatBadges}>
          {floor ? <Text style={styles.seatBadge}>🎤</Text> : null}
          {hand ? <Text style={styles.seatBadge}>✋</Text> : null}
          {muted ? <Text style={styles.seatBadge}>🔇</Text> : null}
          {/* Camera toggle is a nested Pressable so it fires independently of the
              outer expand-to-fullscreen press — inner Pressable wins on Android/iOS. */}
          {me && onToggleCamera ? (
            <Pressable onPress={onToggleCamera} hitSlop={8} accessibilityRole="button"
              accessibilityLabel={cameraOn && hasVideo ? "Turn camera off" : "Turn camera on"}>
              <Text style={styles.seatBadge}>{cameraOn && hasVideo ? "📹" : "📷"}</Text>
            </Pressable>
          ) : null}
        </View>
      </View>
      <View style={styles.seatFooter}>
        <Text style={styles.seatName} numberOfLines={1}>{label}</Text>
      </View>
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
  const { width, height } = useWindowDimensions();
  // The presenter is effectively the phone's fullscreen lecture view. Scale up
  // aggressively on small phones while retaining comfortable line lengths on
  // tablets and landscape screens.
  const shortSide = Math.min(width, height);
  const presenterTitleSize = Math.max(30, Math.min(46, shortSide * 0.09));
  const presenterBodySize = Math.max(20, Math.min(30, shortSide * 0.058));
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
  const [gameResponse, setGameResponse] = useState("");
  const [voiceListening, setVoiceListening] = useState(false);
  const [busy, setBusy] = useState(false);
  const [wasBlocked, setWasBlocked] = useState(false);
  const [giftBalance, setGiftBalance] = useState(0);
  const [giftCatalog, setGiftCatalog] = useState<LiveGiftCatalogItem[]>([]);
  const [giftRecipientId, setGiftRecipientId] = useState("");
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

  // De-dupe room updates from the 3s tick + WebSocket: skip setState when the
  // snapshot is unchanged so we don't re-render the whole screen every 3s on an
  // idle tick (a source of slow-timer jank).
  const lastRoomSigRef = useRef("");
  const applyRoom = useCallback((next: LiveRoomState) => {
    const sig = JSON.stringify(next);
    if (sig === lastRoomSigRef.current) return;
    lastRoomSigRef.current = sig;
    setRoom(next);
  }, []);

  const socket = useLiveRoomSocket(roomId, Boolean(participantId), applyRoom);
  const giftAnimation = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!socket.giftOverlay) return;
    giftAnimation.setValue(0);
    Animated.sequence([
      Animated.spring(giftAnimation, {
        toValue: 1,
        useNativeDriver: true,
        friction: 4,
        tension: 70,
      }),
      Animated.delay(2400),
      Animated.timing(giftAnimation, {
        toValue: 2,
        duration: 900,
        useNativeDriver: true,
      }),
    ]).start();
  }, [giftAnimation, socket.giftOverlay]);

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

  // Heartbeat the room clock so a mobile-only group class still auto-starts,
  // auto-advances slides, and auto-ends when its allotted time is up (parity with
  // web). Idempotent server-side; harmless for open-ended rooms. The tick returns
  // the full room, so it doubles as the poll — no separate refresh interval is
  // needed (that was redundant work); applyRoom de-dupes so idle ticks don't
  // re-render.
  useEffect(() => {
    if (!participantId) return;
    const t = setInterval(() => {
      void liveRoomTick(roomId, participantId).then((r) => applyRoom(r.room)).catch(() => undefined);
    }, 3000);  // 3s so slides auto-advance close to the 5s dwell (and presence stays fresh)
    return () => clearInterval(t);
  }, [participantId, roomId, applyRoom]);

  // Audio: the AI host (Theodore) has no camera, so its "voice" is TTS. Speak the
  // current slide (title + narration) whenever it changes, and speak Theodore's
  // Q&A answers / announcements as they arrive — in the learner's language. This
  // is why "no audio comes out" otherwise: nobody publishes host audio to LiveKit.
  const spokenSlideRef = useRef<number>(-1);
  const spokenWelcomeRef = useRef<string>("");
  const spokenChatRef = useRef<string>("");
  const didInitChatRef = useRef(false);
  // Always-fresh room for the narration onDone callback (floor/queue guards).
  const roomRef = useRef<LiveRoomState | null>(null);
  roomRef.current = room;

  useEffect(() => {
    if (!room) return;
    const welcome = room.welcome_message?.trim();
    if (!participantId || muted || room.presenting || !welcome) return;
    if (spokenWelcomeRef.current === room.room_id) return;
    spokenWelcomeRef.current = room.room_id;
    void buildNarrationSpeakOptions(locale).then((base) => {
      speakNatural(welcome, base);
    });
  }, [participantId, muted, room, locale]);

  useEffect(() => {
    if (!participantId || muted || !room?.presenting) return;
    const s = room?.slide;
    if (!s || spokenSlideRef.current === s.index) return;
    spokenSlideRef.current = s.index;
    // Narrate the full slide body (substantive lecture), not just the one-line
    // script — the server paces auto-advance to this so it isn't cut off.
    const text = `${s.title}. ${s.body || s.narration || ""}`.trim();
    const spokenFor = s.index;
    if (text) {
      void buildNarrationSpeakOptions(locale).then((base) => {
        speakNatural(text, {
          ...base,
          // Advance the moment the AI finishes this slide (moderator/admin drives
          // it; others follow the room state). Guarded so we never skip a learner
          // who holds/awaits the floor. Server timed dwell remains the fallback.
          onDone: () => {
            const r = roomRef.current;
            if (
              canModerate &&
              r?.presenting &&
              r.status !== "ended" &&
              spokenSlideRef.current === spokenFor &&
              !r.floor_participant_id &&
              !(r.speaking_queue?.some((e) => e.status === "waiting"))
            ) {
              void liveRoomAdvance(roomId, modKey).then((next) => setRoom(next)).catch(() => undefined);
            }
          },
        });
      });
    }
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
    const msg = latest;
    if (!muted) {
      void buildNarrationSpeakOptions(locale).then((base) => {
        speakNatural(msg.text, base);
      });
    }
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

  // Single shared LiveKit connection for the whole room: one connection maps each
  // participant's video track to their seat (self-view under "You", every remote
  // learner under their own name), so a group class shows MULTIPLE live feeds.
  const { trackFor, setCameraEnabled } = useLiveKitRoom(
    media,
    room?.participants ?? [],
    hasFloor,
    Boolean(participantId) && !classEnded,
  );
  const [cameraOn, setCameraOn] = useState(true);
  type FocusedTile =
    | { kind: "host"; name: string }
    | { kind: "participant"; id: string; identity?: string; name: string; me: boolean };
  const [focusedTile, setFocusedTile] = useState<FocusedTile | null>(null);
  const toggleCamera = useCallback(async () => {
    const next = !cameraOn;
    const ok = await setCameraEnabled(next);
    if (ok) setCameraOn(next);
  }, [cameraOn, setCameraEnabled]);

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

  const startFullscreenVoiceQuestion = async () => {
    if (!hasFloor) {
      await toggleHand();
      return;
    }
    stopSpeech();
    setError("");
    const started = await startVoiceListening({
      locale,
      continuous: true,
      onResult: (transcript) => {
        setQuestion((previous) => `${previous} ${transcript}`.trim());
      },
      onError: (code) => {
        setVoiceListening(false);
        setError(
          code === "permission_denied"
            ? "Microphone permission is required to ask by voice."
            : "Voice input is unavailable. Check the microphone and try again.",
        );
      },
      onEnd: () => setVoiceListening(false),
    });
    setVoiceListening(started);
  };

  const submitFullscreenVoiceQuestion = async () => {
    if (!participantId || !question.trim()) return;
    stopVoiceListening();
    setVoiceListening(false);
    setBusy(true);
    try {
      const res = await liveRoomAskStream(roomId, participantId, question.trim(), locale);
      if (res.room) setRoom(res.room);
      setQuestion("");
      if (res.queued) {
        setError(`You're #${res.queue_position ?? myPos} in the Q&A queue.`);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (!hasFloor && voiceListening) {
      stopVoiceListening();
      setVoiceListening(false);
    }
  }, [hasFloor, voiceListening]);

  useEffect(() => () => stopVoiceListening(), []);

  const leaveAndBack = () => {
    stopSpeech();
    stopVoiceListening();
    if (participantId) {
      void leaveLiveRoom(roomId, participantId).catch(() => undefined);
    }
    onBack();
  };
  useAndroidBackTo(leaveAndBack);

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
        <PrimaryButton label="← Back" onPress={leaveAndBack} variant="ghost" />
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
      {socket.giftOverlay ? (
        <Animated.View
          pointerEvents="none"
          style={[
            styles.giftSpectacular,
            {
              opacity: giftAnimation.interpolate({
                inputRange: [0, 0.15, 1, 2],
                outputRange: [0, 1, 1, 0],
              }),
              transform: [
                {
                  scale: giftAnimation.interpolate({
                    inputRange: [0, 1, 2],
                    outputRange: [0.15, 1.1, 1.45],
                  }),
                },
                {
                  translateY: giftAnimation.interpolate({
                    inputRange: [0, 1, 2],
                    outputRange: [80, 0, -180],
                  }),
                },
                {
                  rotate: giftAnimation.interpolate({
                    inputRange: [0, 0.6, 1, 2],
                    outputRange: ["-12deg", "8deg", "0deg", "4deg"],
                  }),
                },
              ],
            },
          ]}
        >
          <Text style={styles.giftSpectacularEmoji}>{socket.giftOverlay.emoji}</Text>
          <Text style={styles.giftSpectacularLabel}>{socket.giftOverlay.label}</Text>
        </Animated.View>
      ) : null}
      {socket.hostAnswer && (socket.hostAnswer.text || !socket.hostAnswer.done) ? (
        <View style={styles.hostAnswer}>
          <Text style={styles.hostAnswerTitle}>
            🎓 Theodore{socket.hostAnswer.asker ? ` → ${socket.hostAnswer.asker}` : ""}
            {!socket.hostAnswer.done ? " is answering…" : ""}
          </Text>
          <Text style={styles.hostAnswerText} numberOfLines={4}>
            {socket.hostAnswer.text || "…"}
          </Text>
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

      {/* Seats: the AI host + everyone in the room + open slots, so you can see
          who's here and where there's room to drop in (like the web grid). */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.seatsRow}
        contentContainerStyle={styles.seatsContent}
      >
        {room?.host ? (
          <SeatTile
            name={room.host.name}
            host
            onPress={() => setFocusedTile({ kind: "host", name: room.host!.name })}
          />
        ) : null}
        {(room?.participants ?? [])
          .filter((p) => p.role !== "host")
          .map((p) => {
            const mine = p.id === participantId;
            return (
              <SeatTile
                key={p.id}
                name={p.name}
                me={mine}
                floor={p.id === room?.floor_participant_id}
                hand={p.hand_raised && p.id !== room?.floor_participant_id}
                muted={p.muted || p.muted_by_host}
                track={mine && !cameraOn ? null : trackFor(p.id, p.identity)}
                cameraOn={mine ? cameraOn : undefined}
                onToggleCamera={mine ? () => void toggleCamera() : undefined}
                onPress={() => setFocusedTile({
                  kind: "participant",
                  id: p.id,
                  identity: p.identity,
                  name: p.name,
                  me: mine,
                })}
              />
            );
          })}
        {Array.from({ length: Math.max(0, room?.seats_left ?? 0) }).map((_, i) => (
          <SeatTile key={`open-${i}`} open />
        ))}
      </ScrollView>

      {/* Presenter hero fills the screen; everything else opens from the bar. */}
      <GlassPanel style={styles.hero}>
        <Text style={styles.presenterHost} numberOfLines={1}>
          🎓 {room?.host?.name ?? "Theodore (AI Host)"}
          {room?.presenting ? ` · Slide ${(room?.slide.index ?? 0) + 1}` : " · Welcome"}
        </Text>
        <ScrollView style={styles.heroScroll} contentContainerStyle={styles.heroContent}>
          <Text
            style={[
              styles.presenterTitle,
              { fontSize: presenterTitleSize, lineHeight: presenterTitleSize * 1.18 },
            ]}
          >
            {room?.presenting ? room?.slide.title : "Welcome to Transparent AI"}
          </Text>
          <Text
            style={[
              styles.presenterBody,
              { fontSize: presenterBodySize, lineHeight: presenterBodySize * 1.45 },
            ]}
          >
            {room?.presenting
              ? (room?.slide.narration || room?.slide.body)
              : room?.welcome_message}
          </Text>
        </ScrollView>
        {participantId ? (
          <View style={styles.floatingVoice}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Send an animated gift"
              style={({ pressed }) => [
                styles.floatingGiftBtn,
                pressed && styles.hostBtnPressed,
              ]}
              onPress={() => setSheet("gifts")}
            >
              <Text style={styles.floatingVoiceIcon}>🎁</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Play a group learning game"
              style={({ pressed }) => [
                styles.floatingGameBtn,
                pressed && styles.hostBtnPressed,
              ]}
              onPress={() => setSheet("games")}
            >
              <Text style={styles.floatingVoiceIcon}>🎮</Text>
            </Pressable>
            {hasFloor ? (
              <>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={voiceListening ? "Stop listening" : "Ask Theodore by voice"}
                  style={({ pressed }) => [
                    styles.floatingVoiceBtn,
                    voiceListening && styles.floatingVoiceBtnListening,
                    pressed && styles.hostBtnPressed,
                  ]}
                  onPress={() => {
                    if (voiceListening) {
                      stopVoiceListening();
                      setVoiceListening(false);
                    } else {
                      void startFullscreenVoiceQuestion();
                    }
                  }}
                >
                  <Text style={styles.floatingVoiceIcon}>{voiceListening ? "🎙️" : "🎤"}</Text>
                  <Text style={styles.floatingVoiceLabel}>
                    {voiceListening ? "Listening…" : "Speak"}
                  </Text>
                </Pressable>
                {question.trim() ? (
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel="Send spoken question to Theodore"
                    style={({ pressed }) => [
                      styles.floatingAskBtn,
                      pressed && styles.hostBtnPressed,
                    ]}
                    disabled={busy}
                    onPress={() => void submitFullscreenVoiceQuestion()}
                  >
                    <Text style={styles.floatingVoiceLabel}>✓ Ask</Text>
                  </Pressable>
                ) : null}
              </>
            ) : (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={inQueue ? "Lower your hand" : "Raise your hand to ask by voice"}
                style={({ pressed }) => [
                  styles.floatingVoiceBtn,
                  inQueue && styles.floatingVoiceBtnQueued,
                  pressed && styles.hostBtnPressed,
                ]}
                disabled={busy}
                onPress={() => void toggleHand()}
              >
                <Text style={styles.floatingVoiceIcon}>✋</Text>
                <Text style={styles.floatingVoiceLabel}>
                  {inQueue ? `Queued #${myPos}` : "Ask"}
                </Text>
              </Pressable>
            )}
          </View>
        ) : null}
        {muted ? <Text style={styles.mutedHint}>Audio muted — tap 🔊 up top to hear the teacher</Text> : null}
        {hasFloor ? (
          <Text style={styles.floorChip}>🎤 You&apos;re live — open &ldquo;More&rdquo; to finish your turn</Text>
        ) : inQueue ? (
          <Text style={styles.floorChip}>✋ You&apos;re #{myPos} in line</Text>
        ) : null}
        {media ? (
          <Text style={styles.camHint}>
            {cameraOn ? "📹 Your camera is on — tap 📹 on your card to turn it off" : "📷 Camera off — tap 📷 on your card to turn it on"}
          </Text>
        ) : null}
      </GlassPanel>

      {/* Host / admin bar — same controls as web (Start, Close, Delete), not buried in More. */}
      {canModerate ? (
        <View style={styles.hostBar}>
          {!room?.presenting ? (
            <Pressable
              style={({ pressed }) => [styles.hostBtn, styles.hostBtnPrimary, pressed && styles.hostBtnPressed]}
              onPress={() => {
                void (async () => {
                  try {
                    setRoom(await liveRoomStartPresentation(roomId, modKey));
                  } catch (e) {
                    setError((e as Error).message);
                  }
                })();
              }}
            >
              <Text style={styles.hostBtnText}>🎬 Start class</Text>
            </Pressable>
          ) : (
            <Pressable
              style={({ pressed }) => [styles.hostBtn, pressed && styles.hostBtnPressed]}
              onPress={() => {
                void (async () => {
                  try {
                    setRoom(await liveRoomAdvance(roomId, modKey));
                  } catch (e) {
                    setError((e as Error).message);
                  }
                })();
              }}
            >
              <Text style={styles.hostBtnText}>▶ Next slide</Text>
            </Pressable>
          )}
          <Pressable
            style={({ pressed }) => [styles.hostBtn, styles.hostBtnWarn, pressed && styles.hostBtnPressed]}
            onPress={() => {
              Alert.alert(
                "Close session",
                "End this class for everyone?",
                [
                  { text: "Cancel", style: "cancel" },
                  {
                    text: "Close",
                    style: "destructive",
                    onPress: () => {
                      void (async () => {
                        try {
                          setRoom(await liveRoomEnd(roomId, modKey));
                        } catch (e) {
                          setError((e as Error).message);
                        }
                      })();
                    },
                  },
                ],
              );
            }}
          >
            <Text style={styles.hostBtnText}>⛔ Close</Text>
          </Pressable>
          {account?.is_admin ? (
            <Pressable
              style={({ pressed }) => [styles.hostBtn, styles.hostBtnDanger, pressed && styles.hostBtnPressed]}
              onPress={() => {
                Alert.alert(
                  "Delete session",
                  "Delete this session permanently? This cannot be undone.",
                  [
                    { text: "Cancel", style: "cancel" },
                    {
                      text: "Delete",
                      style: "destructive",
                      onPress: () => {
                        void (async () => {
                          try {
                            await deleteLiveRoom(roomId);
                            leaveAndBack();
                          } catch (e) {
                            setError((e as Error).message);
                          }
                        })();
                      },
                    },
                  ],
                );
              }}
            >
              <Text style={styles.hostBtnText}>🗑 Delete</Text>
            </Pressable>
          ) : null}
        </View>
      ) : null}

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
        <IconTab icon="🎮" onPress={() => setSheet("games")} />
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
                // Stream Theodore's answer: it renders live in the room (host_delta
                // over the WebSocket) and is narrated when finalized.
                const res = await liveRoomAskStream(roomId, participantId, question.trim(), locale);
                if (res.room) setRoom(res.room);
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

      {/* ---- Group learning games ---- */}
      <BottomSheet visible={sheet === "games"} title="Group learning game" onClose={() => setSheet(null)}>
        {!room?.group_game ? (
          canModerate ? (
            <View style={styles.sheetSection}>
              <Text style={styles.meta}>Start a synchronized game for everybody.</Text>
              {GAME_LIBRARY.map((game) => (
                <PrimaryButton
                  key={game.type}
                  label={game.label}
                  onPress={() => void liveRoomStartGame(
                    roomId, modKey, game.type, game.prompt, game.answer, 25,
                  ).then((r) => setRoom(r.room))}
                />
              ))}
            </View>
          ) : <Text style={styles.meta}>Waiting for Theodore or the class admin to start a game.</Text>
        ) : (
          <View style={styles.sheetSection}>
            <Text style={styles.gameKind}>
              {room.group_game.type.replaceAll("_", " ")} · {room.group_game.points} points
            </Text>
            <Text style={styles.gamePrompt}>{room.group_game.prompt}</Text>
            {room.group_game.masked ? <Text style={styles.gameMasked}>{room.group_game.masked}</Text> : null}
            {room.group_game.scrambled ? <Text style={styles.gameMasked}>{room.group_game.scrambled}</Text> : null}
            {room.group_game.type === "tic_tac_toe" ? (
              <View style={styles.gameBoard}>
                {(room.group_game.board ?? Array(9).fill("")).map((mark, i) => (
                  <Pressable
                    key={i}
                    style={styles.gameCell}
                    disabled={Boolean(mark) || room.group_game?.status !== "active" || busy}
                    onPress={() => {
                      if (!participantId) return;
                      void liveRoomPlayGame(roomId, participantId, {
                        answer: gameResponse.trim(), cell: i,
                      }).then((r) => { setRoom(r.room); setGameResponse(""); });
                    }}
                  >
                    <Text style={styles.gameCellText}>{mark || "·"}</Text>
                  </Pressable>
                ))}
              </View>
            ) : null}
            {room.group_game.status === "active" ? (
              <View style={styles.controls}>
                <TextInput
                  value={gameResponse}
                  onChangeText={setGameResponse}
                  placeholder={room.group_game.type === "hangman" ? "One letter" : "Your answer"}
                  placeholderTextColor={theme.colors.muted}
                  maxLength={room.group_game.type === "hangman" ? 1 : 200}
                  style={styles.input}
                />
                {room.group_game.type !== "tic_tac_toe" ? (
                  <PrimaryButton
                    label="Play"
                    onPress={() => {
                      if (!participantId || !gameResponse.trim()) return;
                      const action = room.group_game?.type === "hangman"
                        ? { letter: gameResponse.trim().slice(0, 1) }
                        : { answer: gameResponse.trim() };
                      void liveRoomPlayGame(roomId, participantId, action)
                        .then((r) => { setRoom(r.room); setGameResponse(""); });
                    }}
                  />
                ) : null}
              </View>
            ) : (
              <Text style={styles.gameWinner}>
                {room.group_game.status === "won" ? `🏆 ${room.group_game.winner_name} wins!` : "Game complete"}
              </Text>
            )}
          </View>
        )}
      </BottomSheet>

      {/* ---- Gifts ---- */}
      <BottomSheet visible={sheet === "gifts"} title={`Gifts · ${giftBalance} pts`} onClose={() => setSheet(null)}>
        <Text style={styles.cardTitle}>Send to</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.giftRecipients}>
          {room?.host ? (
            <Pressable
              style={[
                styles.giftRecipient,
                (!giftRecipientId || giftRecipientId === room.host.id) && styles.giftRecipientActive,
              ]}
              onPress={() => setGiftRecipientId(room.host.id)}
            >
              <Text style={styles.giftRecipientText}>🎓 {room.host.name}</Text>
            </Pressable>
          ) : null}
          {(room?.participants ?? [])
            .filter((p) => p.role !== "host" && p.id !== participantId)
            .map((p) => (
              <Pressable
                key={p.id}
                style={[
                  styles.giftRecipient,
                  giftRecipientId === p.id && styles.giftRecipientActive,
                ]}
                onPress={() => setGiftRecipientId(p.id)}
              >
                <Text style={styles.giftRecipientText}>👤 {p.name}</Text>
              </Pressable>
            ))}
        </ScrollView>
        <View style={styles.giftGrid}>
          {giftCatalog.map((g) => (
            <Pressable
              key={g.id}
              style={[styles.giftItem, (busy || giftBalance < g.cost_points) && { opacity: 0.4 }]}
              disabled={busy || giftBalance < g.cost_points}
              onPress={async () => {
                setBusy(true);
                try {
                  const res = await liveRoomSendGift(
                    roomId,
                    participantId,
                    g.id,
                    giftRecipientId || room?.host?.id || "",
                  );
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

          {canModerate ? (
            <View style={styles.sheetSection}>
              <Text style={styles.cardTitle}>Host controls</Text>
              <View style={styles.controls}>
                {!room?.presenting ? (
                  <PrimaryButton
                    label="🎬 Start class"
                    variant="netflix"
                    onPress={async () => {
                      try { setRoom(await liveRoomStartPresentation(roomId, modKey)); }
                      catch (e) { setError((e as Error).message); }
                    }}
                  />
                ) : null}
                <PrimaryButton label="Call next" onPress={async () => setRoom(await liveRoomCallNext(roomId, modKey))} />
                {room?.floor_participant_id ? (
                  <PrimaryButton
                    label="End turn"
                    variant="ghost"
                    onPress={async () => setRoom(await liveRoomFinishTurn(roomId, room.floor_participant_id!, modKey))}
                  />
                ) : null}
                <PrimaryButton
                  label="⛔ Close session"
                  variant="ghost"
                  onPress={async () => {
                    try { setRoom(await liveRoomEnd(roomId, modKey)); setSheet(null); }
                    catch (e) { setError((e as Error).message); }
                  }}
                />
                {account?.is_admin ? (
                  <PrimaryButton
                    label="🗑 Delete session"
                    variant="ghost"
                    onPress={() => {
                      Alert.alert(
                        "Delete session",
                        "Delete this session permanently? This cannot be undone.",
                        [
                          { text: "Cancel", style: "cancel" },
                          {
                            text: "Delete",
                            style: "destructive",
                            onPress: () => {
                              void (async () => {
                                try {
                                  await deleteLiveRoom(roomId);
                                  leaveAndBack();
                                } catch (e) {
                                  setError((e as Error).message);
                                }
                              })();
                            },
                          },
                        ],
                      );
                    }}
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

      {/* ---- Full-screen tile overlay ----
          Tapping any seat tile expands it to fill the screen. The overlay sits
          at zIndex 150 so it covers the normal class UI but stays below the
          live-event overlays (gift spectacular, reactions, toast) at zIndex 300,
          which continue to float on top even in fullscreen mode. */}
      {focusedTile && (() => {
        const isHost = focusedTile.kind === "host";
        const fsParticipant = focusedTile.kind === "participant" ? focusedTile : null;
        const fsTrack = fsParticipant
          ? (fsParticipant.me && !cameraOn ? null : trackFor(fsParticipant.id, fsParticipant.identity))
          : null;
        const fsName = isHost ? (focusedTile.name || "Theodore") : (fsParticipant?.name ?? "");
        const fsMe = Boolean(fsParticipant?.me);
        const fsFloor = !isHost && room?.floor_participant_id === fsParticipant?.id;
        const fsMuted = !isHost && Boolean(
          room?.participants.find((p) => p.id === fsParticipant?.id)?.muted,
        );
        return (
          <Pressable
            style={styles.fsOverlay}
            onPress={() => setFocusedTile(null)}
            accessibilityRole="button"
            accessibilityLabel="Close fullscreen"
          >
            {/* Video feed or slide/avatar fallback */}
            <View style={styles.fsVideo} pointerEvents="none">
              {fsTrack ? (
                <LiveKitVideoView track={fsTrack} mirror={fsMe} zOrder={1} />
              ) : isHost && room?.presenting && room?.slide ? (
                <View style={styles.fsSlide}>
                  <Text style={styles.fsSlideLabel}>
                    🎓 {fsName} · Slide {(room.slide.index ?? 0) + 1}
                  </Text>
                  <Text style={styles.fsSlideTitle}>{room.slide.title}</Text>
                  <Text style={styles.fsSlideBody}>
                    {room.slide.narration || room.slide.body}
                  </Text>
                </View>
              ) : (
                <View style={styles.fsAvatarWrap}>
                  <Text style={styles.fsAvatar}>{isHost ? "🎓" : initials(fsName)}</Text>
                </View>
              )}
            </View>

            {/* Host answer bubble — repeated here so it stays visible in fullscreen */}
            {socket.hostAnswer && (socket.hostAnswer.text || !socket.hostAnswer.done) ? (
              <View style={styles.fsHostAnswer} pointerEvents="none">
                <Text style={styles.hostAnswerTitle}>
                  🎓 Theodore{socket.hostAnswer.asker ? ` → ${socket.hostAnswer.asker}` : ""}
                  {!socket.hostAnswer.done ? " is answering…" : ""}
                </Text>
                <Text style={styles.hostAnswerText} numberOfLines={4}>
                  {socket.hostAnswer.text || "…"}
                </Text>
              </View>
            ) : null}

            {/* Name + status bar at bottom */}
            <View style={styles.fsInfo} pointerEvents="none">
              <Text style={styles.fsInfoName}>{isHost ? "Host · " : ""}{fsName}</Text>
              <View style={styles.fsInfoBadges}>
                {fsFloor ? <Text style={styles.fsBadge}>🎤 Speaking</Text> : null}
                {fsMuted ? <Text style={styles.fsBadge}>🔇</Text> : null}
              </View>
            </View>

            {/* Camera toggle for local user */}
            {fsMe ? (
              <Pressable
                style={styles.fsCamBtn}
                onPress={(e) => { e.stopPropagation?.(); void toggleCamera(); }}
                accessibilityRole="button"
                accessibilityLabel={cameraOn && Boolean(fsTrack) ? "Turn camera off" : "Turn camera on"}
              >
                <Text style={styles.fsCamBtnText}>
                  {cameraOn && Boolean(fsTrack) ? "📹" : "📷"}
                </Text>
              </Pressable>
            ) : null}

            {/* Close button */}
            <View style={styles.fsClose} pointerEvents="none">
              <Text style={styles.fsCloseText}>✕</Text>
            </View>
          </Pressable>
        );
      })()}
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
  seatsRow: { flexGrow: 0, marginTop: 8, marginBottom: 4, maxHeight: 118 },
  seatsContent: { gap: 8, paddingVertical: 2, paddingRight: 8, alignItems: "flex-start" },
  // Profile card: webcam fills the TOP window; name strip sits below — never a
  // floating PiP over the training slide.
  seat: {
    width: 88, height: 110, borderRadius: 12, overflow: "hidden",
    backgroundColor: "rgba(30,27,75,0.9)",
    borderWidth: 1, borderColor: "rgba(255,255,255,0.12)",
  },
  seatHost: { backgroundColor: "rgba(124,58,237,0.35)", borderColor: "#a78bfa" },
  seatFloor: { borderColor: theme.colors.accent, borderWidth: 2 },
  seatMe: { borderColor: theme.colors.success },
  seatPressed: { opacity: 0.75 },
  seatOpen: {
    backgroundColor: "transparent",
    borderStyle: "dashed", borderColor: "rgba(255,255,255,0.3)",
  },
  seatVideoWindow: {
    flex: 1, width: "100%",
    alignItems: "center", justifyContent: "center",
    backgroundColor: "rgba(15,12,40,0.85)",
    overflow: "hidden",
  },
  // When a live video track is present, the parent must be transparent so the
  // Android SurfaceView (zOrder=0, rendered below the RN layer) shows through.
  seatVideoWindowLive: { backgroundColor: "transparent" },
  seatFooter: {
    height: 22, paddingHorizontal: 4,
    alignItems: "center", justifyContent: "center",
    backgroundColor: "rgba(0,0,0,0.45)",
  },
  seatOpenText: { color: theme.colors.muted, fontSize: 11, textAlign: "center", fontWeight: "600" },
  seatAvatar: { color: theme.colors.text, fontSize: 26, fontWeight: "800" },
  seatName: { color: theme.colors.text, fontSize: 11, fontWeight: "700", maxWidth: 80, textAlign: "center" },
  seatNameMuted: { color: theme.colors.muted, fontSize: 11, fontWeight: "600" },
  seatBadges: { flexDirection: "row", gap: 2, position: "absolute", top: 2, right: 4 },
  seatBadge: { fontSize: 11 },
  hero: { flex: 1, gap: 8, position: "relative" },
  presenterHost: { color: "#c4b5fd", fontSize: 13, fontWeight: "600" },
  heroScroll: { flex: 1 },
  heroContent: { gap: 10, paddingBottom: 8 },
  presenterTitle: { color: theme.colors.text, fontSize: 26, fontWeight: "800", lineHeight: 32 },
  presenterBody: { color: theme.colors.text, fontSize: 17, lineHeight: 25, opacity: 0.94 },
  floatingVoice: {
    position: "absolute",
    right: 12,
    bottom: 12,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    zIndex: 20,
  },
  floatingVoiceBtn: {
    minWidth: 72,
    minHeight: 58,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(124,58,237,0.94)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.35)",
  },
  floatingVoiceBtnQueued: { backgroundColor: "rgba(180,83,9,0.96)" },
  floatingVoiceBtnListening: { backgroundColor: "rgba(220,38,38,0.96)" },
  floatingGiftBtn: {
    width: 52,
    height: 52,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(190,24,93,0.96)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.35)",
  },
  floatingGameBtn: {
    width: 52, height: 52, borderRadius: 18, alignItems: "center", justifyContent: "center",
    backgroundColor: "rgba(109,40,217,0.96)", borderWidth: 1,
    borderColor: "rgba(255,255,255,0.35)",
  },
  floatingAskBtn: {
    minHeight: 58,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(5,150,105,0.96)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.35)",
  },
  floatingVoiceIcon: { fontSize: 22 },
  floatingVoiceLabel: { color: "#fff", fontSize: 12, fontWeight: "800" },
  mutedHint: { color: theme.colors.muted, fontSize: 12, fontStyle: "italic" },
  floorChip: {
    color: "#e9d5ff", fontSize: 13, fontWeight: "600",
    backgroundColor: "rgba(124,58,237,0.35)",
    paddingVertical: 6, paddingHorizontal: 10, borderRadius: 999, overflow: "hidden",
    alignSelf: "flex-start",
  },
  camHint: { color: theme.colors.muted, fontSize: 12, fontStyle: "italic" },

  // Bottom action bar of icon "tabs".
  hostBar: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    paddingTop: 8,
    paddingBottom: 2,
  },
  hostBtn: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 10,
    backgroundColor: "rgba(255,255,255,0.1)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.18)",
  },
  hostBtnPrimary: {
    backgroundColor: "rgba(219,39,119,0.85)",
    borderColor: "rgba(251,113,133,0.6)",
  },
  hostBtnWarn: {
    backgroundColor: "rgba(180,83,9,0.85)",
    borderColor: "rgba(251,191,36,0.45)",
  },
  hostBtnDanger: {
    backgroundColor: "rgba(185,28,28,0.9)",
    borderColor: "rgba(248,113,113,0.5)",
  },
  hostBtnPressed: { opacity: 0.7 },
  hostBtnText: { color: "#fff", fontSize: 13, fontWeight: "700" },
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
  giftRecipients: { gap: 8, paddingBottom: 10 },
  giftRecipient: {
    paddingHorizontal: 12,
    paddingVertical: 9,
    borderRadius: 999,
    backgroundColor: "rgba(255,255,255,0.08)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.15)",
  },
  giftRecipientActive: {
    backgroundColor: "rgba(190,24,93,0.65)",
    borderColor: "#f9a8d4",
  },
  giftRecipientText: { color: theme.colors.text, fontSize: 13, fontWeight: "700" },
  giftItem: {
    width: "30%", padding: 8, borderRadius: 10,
    backgroundColor: "rgba(0,0,0,0.25)", alignItems: "center",
  },
  giftEmoji: { fontSize: 24 },
  gameKind: { color: "#c4b5fd", fontSize: 12, fontWeight: "800", textTransform: "uppercase" },
  gamePrompt: { color: theme.colors.text, fontSize: 22, lineHeight: 28, fontWeight: "900", textAlign: "center" },
  gameMasked: { color: "#fff", fontSize: 32, letterSpacing: 5, textAlign: "center", fontWeight: "800" },
  gameBoard: { width: 270, alignSelf: "center", flexDirection: "row", flexWrap: "wrap", gap: 6 },
  gameCell: {
    width: 86, height: 86, borderRadius: 12, alignItems: "center", justifyContent: "center",
    backgroundColor: "rgba(124,58,237,.22)", borderWidth: 1, borderColor: "#8b5cf6",
  },
  gameCellText: { color: "#fff", fontSize: 34, fontWeight: "900" },
  gameWinner: { color: "#fbbf24", fontSize: 24, fontWeight: "900", textAlign: "center" },

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
    position: "absolute", top: 8, alignSelf: "center", zIndex: 300,
    backgroundColor: "rgba(15,7,32,0.92)", paddingHorizontal: 14, paddingVertical: 8, borderRadius: 999,
  },
  giftSpectacular: {
    position: "absolute",
    top: "32%",
    alignSelf: "center",
    zIndex: 300,
    maxWidth: "88%",
    alignItems: "center",
    justifyContent: "center",
  },
  giftSpectacularEmoji: { fontSize: 132 },
  giftSpectacularLabel: {
    color: "#fff",
    fontSize: 18,
    lineHeight: 24,
    fontWeight: "900",
    textAlign: "center",
    textShadowColor: "#000",
    textShadowOffset: { width: 0, height: 2 },
    textShadowRadius: 8,
  },
  toastText: { color: "#fff", fontSize: 13 },
  hostAnswer: {
    marginHorizontal: 12, marginTop: 6, padding: 10, borderRadius: 12,
    backgroundColor: "rgba(99,102,241,0.16)",
    borderWidth: 1, borderColor: "rgba(99,102,241,0.35)",
  },
  hostAnswerTitle: { color: theme.colors.muted, fontSize: 12, fontWeight: "700", marginBottom: 2 },
  hostAnswerText: { color: theme.colors.text, fontSize: 13 },
  overlay: { ...StyleSheet.absoluteFillObject, zIndex: 300 },
  floatingReaction: { position: "absolute", bottom: 120, fontSize: 28 },

  // Full-screen tile (tap any seat to expand).
  fsOverlay: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 150,
    backgroundColor: "#000",
    justifyContent: "flex-end",
  },
  fsVideo: { ...StyleSheet.absoluteFillObject },
  fsSlide: {
    flex: 1, padding: 28, justifyContent: "center", gap: 16,
    backgroundColor: "linear-gradient(#0d0b1a, #1a0d2e)" as never,
  },
  fsSlideLabel: { color: "#c4b5fd", fontSize: 13, fontWeight: "600" },
  fsSlideTitle: { color: "#fff", fontSize: 28, fontWeight: "800", lineHeight: 36 },
  fsSlideBody: { color: "#e2e8f0", fontSize: 17, lineHeight: 26, opacity: 0.92 },
  fsAvatarWrap: {
    ...StyleSheet.absoluteFillObject, alignItems: "center", justifyContent: "center",
    backgroundColor: "rgba(20,10,50,0.95)",
  },
  fsAvatar: { fontSize: 96 },
  fsInfo: {
    paddingHorizontal: 18, paddingVertical: 14,
    backgroundColor: "rgba(0,0,0,0.72)",
    flexDirection: "row", alignItems: "center", gap: 10,
  },
  fsInfoName: { color: "#fff", fontSize: 18, fontWeight: "700", flex: 1 },
  fsInfoBadges: { flexDirection: "row", gap: 8 },
  fsBadge: { color: "#e9d5ff", fontSize: 14, fontWeight: "600" },
  fsClose: {
    position: "absolute", top: 16, right: 16,
    backgroundColor: "rgba(0,0,0,0.55)", borderRadius: 999,
    width: 36, height: 36, alignItems: "center", justifyContent: "center",
  },
  fsCloseText: { color: "#fff", fontSize: 18, fontWeight: "700" },
  fsCamBtn: {
    position: "absolute", top: 16, left: 16,
    backgroundColor: "rgba(0,0,0,0.55)", borderRadius: 999,
    width: 44, height: 44, alignItems: "center", justifyContent: "center",
  },
  fsCamBtnText: { fontSize: 22 },
  fsHostAnswer: {
    marginHorizontal: 16, marginBottom: 8, padding: 10, borderRadius: 12,
    backgroundColor: "rgba(99,102,241,0.25)",
    borderWidth: 1, borderColor: "rgba(99,102,241,0.5)",
  },
});
