"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  getLiveRoom,
  getLiveGiftCatalog,
  getMe,
  getToken,
  joinLiveRoom,
  leaveLiveRoom,
  liveRoomBan,
  liveRoomUnban,
  liveRoomReport,
  liveRoomDismissReport,
  liveRoomAdvance,
  liveRoomStartPresentation,
  liveRoomEnd,
  deleteLiveRoom,
  liveRoomTick,
  liveRoomAsk,
  liveRoomChat,
  liveRoomMute,
  liveRoomRaiseHand,
  liveRoomCallNext,
  liveRoomCallOn,
  liveRoomMediaToken,
  liveRoomFinishTurn,
  liveRoomLeaveQueue,
  liveRoomRecordStart,
  liveRoomRecordStop,
  liveRoomReaction,
  liveRoomSendGift,
  liveRoomFollowHost,
  type LiveGiftCatalogItem,
  type LiveParticipant,
  type LiveRoomJoin,
  type LiveRoomState,
} from "../../lib/api";
import { friendlyError } from "../../lib/errors";
import { LiveKitAudio, LiveKitVideoTile, useLiveKitRoom } from "../../components/LiveKitRoomGrid";
import LocalRecorder from "../../components/LocalRecorder";
import { useLiveRoomSocket } from "../../lib/liveRoomSocket";
import { useT } from "../../lib/i18n";
import { speakNaturally, cancelSpeech } from "../../lib/tts";

const REACTIONS = ["❤️", "👏", "🔥", "😂", "🎉", "👍"] as const;

// Minimal Web Speech API shape (Chrome/Edge expose webkitSpeechRecognition).
// Used to capture a learner's spoken question while they hold the floor so it
// can be sent to Theodore on "Done speaking".
type SpeechRec = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  onresult: (e: {
    resultIndex: number;
    results: { length: number; [i: number]: { isFinal: boolean; [j: number]: { transcript: string } } };
  }) => void;
  onerror: (e: { error?: string }) => void;
  onend: () => void;
  start: () => void;
  stop: () => void;
};

const ROOM_STORAGE_KEY = "salareen-live-participant";
const MODERATOR_STORAGE_KEY = "salareen-live-moderator";

// Seconds the "class complete" farewell shows before learners are excused.
const CLASS_END_COUNTDOWN = 5;

// A professional, courteous thank-you for attendance, shown when a group lesson
// reaches the end of its allotted time. Rotated through several languages so the
// farewell greets our international learners in their own tongue.
const CLASS_COMPLETE_MESSAGES: { code: string; lang: string; text: string; rtl?: boolean }[] = [
  { code: "en", lang: "English", text: "Thank you for attending today's class. We hope you enjoyed learning with us, and we look forward to welcoming you back soon." },
  { code: "es", lang: "Español", text: "Gracias por asistir a la clase de hoy. Esperamos que haya disfrutado aprender con nosotros y deseamos verle de nuevo pronto." },
  { code: "fr", lang: "Français", text: "Merci d'avoir assisté au cours d'aujourd'hui. Nous espérons que vous avez apprécié d'apprendre avec nous et avons hâte de vous revoir bientôt." },
  { code: "de", lang: "Deutsch", text: "Vielen Dank für Ihre Teilnahme am heutigen Kurs. Wir hoffen, dass Ihnen das Lernen mit uns gefallen hat, und freuen uns, Sie bald wiederzusehen." },
  { code: "pt", lang: "Português", text: "Obrigado por participar da aula de hoje. Esperamos que tenha gostado de aprender conosco e esperamos vê-lo novamente em breve." },
  { code: "zh", lang: "中文", text: "感谢您参加今天的课程。希望您在学习中收获满满，期待下次再会！" },
  { code: "ja", lang: "日本語", text: "本日の授業にご参加いただき、誠にありがとうございました。またお会いできる日を楽しみにしております。" },
  { code: "ko", lang: "한국어", text: "오늘 수업에 참여해 주셔서 감사합니다. 즐거운 배움의 시간이 되셨길 바라며, 다음에 또 뵙겠습니다." },
  { code: "ar", lang: "العربية", text: "شكرًا لحضوركم درس اليوم. نتمنى أن تكونوا قد استمتعتم بالتعلّم معنا، ونتطلّع إلى رؤيتكم مجددًا قريبًا.", rtl: true },
  { code: "hi", lang: "हिन्दी", text: "आज की कक्षा में शामिल होने के लिए धन्यवाद। हमें आशा है कि आपको हमारे साथ सीखना अच्छा लगा, और हम आपसे शीघ्र ही पुनः मिलने की आशा करते हैं।" },
  { code: "km", lang: "ភាសាខ្មែរ", text: "សូមអរគុណសម្រាប់ការចូលរួមថ្នាក់រៀនថ្ងៃនេះ។ សង្ឃឹមថាអ្នកបានរីករាយនឹងការសិក្សាជាមួយយើង ហើយសង្ឃឹមជួបអ្នកម្តងទៀតឆាប់ៗនេះ។" },
  { code: "tr", lang: "Türkçe", text: "Bugünkü derse katıldığınız için teşekkür ederiz. Bizimle öğrenmekten keyif aldığınızı umuyor ve sizi yakında tekrar görmeyi dört gözle bekliyoruz." },
  { code: "ru", lang: "Русский", text: "Спасибо за участие в сегодняшнем занятии. Надеемся, вам понравилось учиться с нами, и будем рады видеть вас снова." },
];

// Show the learner's own language first, then the rest — a courteous farewell
// that greets everyone but leads with the language they speak.
function orderedFarewell(primaryLang?: string): typeof CLASS_COMPLETE_MESSAGES {
  const code = (primaryLang || "").toLowerCase().split("-")[0];
  const idx = CLASS_COMPLETE_MESSAGES.findIndex((m) => m.code === code);
  if (idx <= 0) return CLASS_COMPLETE_MESSAGES;
  return [
    CLASS_COMPLETE_MESSAGES[idx],
    ...CLASS_COMPLETE_MESSAGES.slice(0, idx),
    ...CLASS_COMPLETE_MESSAGES.slice(idx + 1),
  ];
}

/** Full-screen farewell shown when a group lesson's allotted time expires: a
 * courteous multilingual thank-you plus a short countdown, after which the
 * learner is excused (navigated out of the room). */
function ClassCompleteOverlay({ onDone, primaryLang }: { onDone: () => void; primaryLang?: string }) {
  const [remaining, setRemaining] = useState(CLASS_END_COUNTDOWN);
  const [msgIdx, setMsgIdx] = useState(0);
  const messages = useMemo(() => orderedFarewell(primaryLang), [primaryLang]);

  useEffect(() => {
    const tick = window.setInterval(() => {
      setRemaining((n) => {
        if (n <= 1) {
          window.clearInterval(tick);
          onDone();
          return 0;
        }
        return n - 1;
      });
    }, 1000);
    return () => window.clearInterval(tick);
  }, [onDone]);

  useEffect(() => {
    const rot = window.setInterval(
      () => setMsgIdx((i) => (i + 1) % messages.length),
      1100,
    );
    return () => window.clearInterval(rot);
  }, [messages.length]);

  const msg = messages[msgIdx] ?? messages[0];

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 200,
        background:
          "linear-gradient(160deg, var(--accent) 0%, var(--accent-2) 100%)",
        color: "#fff",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        padding: "24px",
        gap: 18,
      }}
    >
      <div style={{ fontSize: 56 }}>🎓</div>
      <h1 style={{ margin: 0, fontSize: 34, fontWeight: 800 }}>Class complete</h1>
      <div
        key={msgIdx}
        dir={msg.rtl ? "rtl" : "ltr"}
        style={{
          maxWidth: 640,
          fontSize: 20,
          lineHeight: 1.6,
          minHeight: 96,
          display: "flex",
          flexDirection: "column",
          gap: 6,
          animation: "class-end-fade 1.1s ease-in-out",
        }}
      >
        <span style={{ fontSize: 13, textTransform: "uppercase", letterSpacing: 1, opacity: 0.85 }}>
          {msg.lang}
        </span>
        <span>{msg.text}</span>
      </div>
      <div style={{ fontSize: 15, opacity: 0.9 }}>
        Returning to Group Classes in {remaining}s…
      </div>
      <button
        type="button"
        onClick={onDone}
        style={{
          marginTop: 4,
          background: "rgba(255,255,255,0.16)",
          color: "#fff",
          border: "1px solid rgba(255,255,255,0.5)",
          borderRadius: 999,
          padding: "8px 22px",
          cursor: "pointer",
          fontSize: 14,
        }}
      >
        Leave now
      </button>
      <style jsx global>{`
        @keyframes class-end-fade {
          0% { opacity: 0; transform: translateY(6px); }
          20% { opacity: 1; transform: translateY(0); }
          100% { opacity: 1; }
        }
      `}</style>
    </div>
  );
}

function gridLayout(roomSize: number): { cols: number; rows: number } {
  if (roomSize <= 2) return { cols: 2, rows: 1 }; // solo 1:1 — AI host + you side by side
  if (roomSize <= 4) return { cols: 2, rows: 2 };
  if (roomSize <= 6) return { cols: 3, rows: 2 };
  return { cols: 3, rows: 3 };
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function ParticipantTile({
  p,
  large,
  localStream,
  liveKitTrack,
  hasFloor,
  slide,
  onContainerRef,
}: {
  p: LiveParticipant;
  large?: boolean;
  localStream?: MediaStream | null;
  liveKitTrack?: MediaStreamTrack | null;
  hasFloor?: boolean;
  slide?: { index: number; title: string; body: string; narration: string } | null;
  // Lets the parent grab this tile's element (e.g. to fullscreen the host).
  onContainerRef?: (el: HTMLDivElement | null) => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const isHost = p.role === "host";

  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    if (liveKitTrack) {
      el.srcObject = new MediaStream([liveKitTrack]);
      return;
    }
    if (localStream) el.srcObject = localStream;
  }, [localStream, liveKitTrack]);

  const hasVideo = Boolean(liveKitTrack || localStream);

  const toggleFullscreen = () => {
    const el = containerRef.current;
    if (!el) return;
    if (document.fullscreenElement) void document.exitFullscreen().catch(() => undefined);
    else void el.requestFullscreen?.().catch(() => undefined);
  };

  return (
    <div
      ref={(el) => { containerRef.current = el; onContainerRef?.(el); }}
      onDoubleClick={toggleFullscreen}
      style={{
        position: "relative",
        borderRadius: large ? 16 : 12,
        overflow: "hidden",
        background: isHost
          ? "linear-gradient(145deg, var(--accent) 0%, var(--accent-2) 100%)"
          : "color-mix(in srgb, var(--accent) 8%, var(--panel))",
        border: hasFloor
          ? "2px solid var(--accent-2)"
          : p.hand_raised
            ? "2px solid #d99a1c"
            : "1px solid var(--border)",
        minHeight: large ? 220 : 110,
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-end",
      }}
    >
      {hasVideo ? (
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            objectFit: "cover",
            opacity: 0.85,
          }}
        />
      ) : isHost && slide ? (
        // The AI instructor has no camera — its "video feed" IS the current slide.
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            gap: 10,
            padding: large ? "28px 32px" : "14px 16px",
            color: "#fff",
            textAlign: "left",
          }}
        >
          <div style={{ fontSize: 12, opacity: 0.85, textTransform: "uppercase", letterSpacing: 0.5 }}>
            🎓 Theodore · Slide {slide.index + 1}
          </div>
          <div style={{ fontSize: large ? 26 : 18, fontWeight: 800, lineHeight: 1.2 }}>
            {slide.title}
          </div>
          <div style={{ fontSize: large ? 15 : 13, lineHeight: 1.5, opacity: 0.95, overflow: "hidden" }}>
            {slide.narration || slide.body}
          </div>
        </div>
      ) : (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: large ? 48 : 28,
            fontWeight: 700,
            color: isHost ? "rgba(255,255,255,0.95)" : "var(--muted)",
          }}
        >
          {isHost ? "🎓" : initials(p.name)}
        </div>
      )}
      <div
        style={{
          position: "relative",
          padding: "8px 10px",
          background: "linear-gradient(transparent, rgba(0,0,0,0.75))",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 6,
          fontSize: 12,
        }}
      >
        <span style={{ fontWeight: 600 }}>
          {isHost ? "Host · " : ""}
          {p.name}
        </span>
        <span style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {hasFloor && <span title="Speaking now">🎤</span>}
          {p.hand_raised && !hasFloor && <span title="In Q&A queue">✋</span>}
          {(p.muted || p.muted_by_host) && <span title="Muted">🔇</span>}
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); toggleFullscreen(); }}
            title="Maximize / fullscreen (double-click the tile)"
            aria-label="Maximize"
            style={{
              background: "rgba(0,0,0,0.35)", color: "#fff", border: "none",
              borderRadius: 6, cursor: "pointer", fontSize: 12, lineHeight: 1,
              padding: "2px 5px",
            }}
          >
            ⛶
          </button>
        </span>
      </div>
    </div>
  );
}

export default function LiveRoomPage({ params }: { params: { roomId: string } }) {
  const roomId = decodeURIComponent(params.roomId);
  const { locale } = useT();
  const [displayName, setDisplayName] = useState("");
  const [joinInfo, setJoinInfo] = useState<LiveRoomJoin | null>(null);
  const [room, setRoom] = useState<LiveRoomState | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [chatDraft, setChatDraft] = useState("");
  const [askDraft, setAskDraft] = useState("");
  const [localStream, setLocalStream] = useState<MediaStream | null>(null);
  const [moderatorKey, setModeratorKey] = useState("");
  const [isPlatformAdmin, setIsPlatformAdmin] = useState(false);
  // Can this viewer moderate the room? The room's first-joiner admin (has the
  // moderator key) OR the platform admin (admin@salareen.com), who moderates any
  // room via their Bearer token — the moderator endpoints accept either.
  const canModerate = Boolean(moderatorKey) || isPlatformAdmin;
  const [wasRemoved, setWasRemoved] = useState(false);
  const [giftBalance, setGiftBalance] = useState(0);
  const [giftCatalog, setGiftCatalog] = useState<LiveGiftCatalogItem[]>([]);
  const [showGifts, setShowGifts] = useState(false);
  const [showChat, setShowChat] = useState(true);
  const [focusInstructor, setFocusInstructor] = useState(false);
  const [followingHost, setFollowingHost] = useState(false);
  const [followerCount, setFollowerCount] = useState(0);
  // Fullscreen the host presenter (the slide fills the screen). Tracks the
  // native fullscreen state so the toggle label/icon stays in sync (Esc exits).
  const hostTileRef = useRef<HTMLDivElement | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  // AI teacher audio: Theodore narrates each slide out loud (neural TTS with an
  // on-device fallback) while presenting. On by default; a toggle lets you mute.
  const [aiAudioOn, setAiAudioOn] = useState(true);
  const spokenSlideRef = useRef<number | null>(null);
  // Always-fresh room snapshot for callbacks (e.g. narration onend) so they read
  // current floor/queue state without re-subscribing the effect on every tick.
  const roomRef = useRef<LiveRoomState | null>(null);
  roomRef.current = room;
  // Floor mic: while this learner holds the floor we listen to their voice and
  // build a transcript, then send it to Theodore as a question when they tap
  // "Done speaking". `listening` drives the UI; `micNote` surfaces a clear
  // reason when the mic can't run (insecure origin, blocked, unsupported).
  const [listening, setListening] = useState(false);
  const [spokenText, setSpokenText] = useState("");
  const [micNote, setMicNote] = useState("");
  const recognitionRef = useRef<SpeechRec | null>(null);
  const spokenFinalRef = useRef("");
  const leftVoluntarily = useRef(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const viewerSetterRef = useRef<(n: number) => void>(() => {});

  useEffect(() => {
    if (typeof document === "undefined") return;
    const onFs = () => setIsFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", onFs);
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, []);

  const toggleHostFullscreen = () => {
    if (typeof document === "undefined") return;
    if (document.fullscreenElement) {
      void document.exitFullscreen().catch(() => undefined);
      return;
    }
    const el = hostTileRef.current;
    if (el?.requestFullscreen) void el.requestFullscreen().catch(() => undefined);
  };

  // De-dupe room updates from the 3s tick + WebSocket: if nothing actually
  // changed since the last snapshot, skip setState so we don't re-render the
  // whole (large) live-room tree every 3 seconds for no reason. This is the main
  // cause of "setInterval handler took Nms" — a full re-render on an idle tick.
  const lastRoomSigRef = useRef("");
  const applyRoom = useCallback((next: LiveRoomState) => {
    const sig = JSON.stringify(next);
    if (sig === lastRoomSigRef.current) return;
    lastRoomSigRef.current = sig;
    setRoom(next);
    if (typeof next.viewer_count === "number") {
      viewerSetterRef.current(next.viewer_count);
    }
  }, []);

  const socket = useLiveRoomSocket(roomId, Boolean(joinInfo), applyRoom);
  viewerSetterRef.current = socket.setViewerCount;

  const me = useMemo(() => {
    const id = joinInfo?.participant.id;
    if (!id || !room) return joinInfo?.participant ?? null;
    return room.participants.find((p) => p.id === id) ?? joinInfo.participant;
  }, [joinInfo, room]);
  const hasFloor = me?.id === room?.floor_participant_id;
  // Language for narration + voice capture: the learner's profile/device
  // language, falling back to the app locale.
  const narrationLocale = me?.language || locale;

  // Hard mutex: learners join with a no-publish token. When the host/AI grants
  // the floor (me.can_publish flips), re-fetch a fresh token that permits
  // publishing and reconnect; when the floor is released, re-fetch a no-publish
  // token so LiveKit itself refuses to publish. liveMedia overrides the join
  // token once refreshed.
  const [liveMedia, setLiveMedia] = useState<LiveRoomJoin["media"] | null>(null);
  const publishRef = useRef<boolean | null>(null);
  useEffect(() => {
    if (!joinInfo) {
      publishRef.current = null;
      setLiveMedia(null);
      return;
    }
    const cp = Boolean(me?.can_publish);
    if (publishRef.current === cp) return;
    publishRef.current = cp;
    let alive = true;
    void liveRoomMediaToken(roomId, joinInfo.participant.id)
      .then((r) => { if (alive) setLiveMedia(r.media); })
      .catch(() => undefined);
    return () => { alive = false; };
  }, [me?.can_publish, joinInfo, roomId]);

  const { tiles: liveKitTiles, audioTracks, connectFailed: liveKitFailed } =
    useLiveKitRoom(
      liveMedia ?? joinInfo?.media,
      room?.participants ?? joinInfo?.room.participants ?? [],
      Boolean(hasFloor && me?.can_publish),
    );

  const trackFor = useCallback(
    (participantId: string) =>
      liveKitTiles.find((t) => t.participantId === participantId)?.track ?? null,
    [liveKitTiles],
  );

  const layout = useMemo(() => gridLayout(room?.room_size ?? 6), [room?.room_size]);
  const myQueuePos = useMemo(() => {
    if (!me || !room?.speaking_queue) return 0;
    const entry = room.speaking_queue.find(
      (e) => e.participant_id === me.id && e.status === "waiting"
    );
    return entry?.position ?? 0;
  }, [me, room?.speaking_queue]);
  const inQueue = Boolean(room?.speaking_queue?.some(
    (e) => e.participant_id === me?.id && (e.status === "waiting" || e.status === "speaking")
  ));

  const refresh = useCallback(async () => {
    try {
      const mod =
        moderatorKey ||
        sessionStorage.getItem(`${MODERATOR_STORAGE_KEY}:${roomId}`) ||
        "";
      setRoom(await getLiveRoom(roomId, mod));
    } catch (e) {
      setError(friendlyError(e, "Offline"));
    }
  }, [roomId, moderatorKey]);

  useEffect(() => {
    const stored = sessionStorage.getItem(`${ROOM_STORAGE_KEY}:${roomId}`);
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as { name: string; participantId: string; identity: string };
        setDisplayName(parsed.name);
      } catch {
        /* ignore */
      }
    }
    const mod = sessionStorage.getItem(`${MODERATOR_STORAGE_KEY}:${roomId}`);
    if (mod) setModeratorKey(mod);
    void refresh();
  }, [roomId, refresh]);

  useEffect(() => {
    if (!joinInfo || !room || leftVoluntarily.current) return;
    const stillHere = room.participants.some((p) => p.id === joinInfo.participant.id);
    if (!stillHere) {
      setWasRemoved(true);
      sessionStorage.removeItem(`${ROOM_STORAGE_KEY}:${roomId}`);
      localStream?.getTracks().forEach((t) => t.stop());
    }
  }, [room, joinInfo, roomId, localStream]);

  // Note: we intentionally do NOT run a separate room-refresh poll here. The
  // heartbeat tick below already returns the full room every 3s (and the socket
  // pushes live updates), so a second interval calling getLiveRoom was redundant
  // work — double the fetches + re-renders — which contributed to slow-timer
  // ('setInterval handler took Nms') warnings. The one-time refresh on mount
  // still primes the join screen.

  useEffect(() => {
    void getLiveGiftCatalog()
      .then((c) => setGiftCatalog(c.gifts))
      .catch(() => setGiftCatalog([]));
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [room?.chat.length]);

  async function enableCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      setLocalStream(stream);
    } catch {
      /* camera optional */
    }
  }

  async function handleJoin(nameOverride?: string, accountId?: string) {
    const name = (nameOverride ?? displayName).trim();
    if (!name) {
      setError("Enter your name to join.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const stored = sessionStorage.getItem(`${ROOM_STORAGE_KEY}:${roomId}`);
      let identity = "";
      if (stored) {
        try {
          identity = (JSON.parse(stored) as { identity?: string }).identity ?? "";
        } catch {
          identity = "";
        }
      }
      // Prefer a stable identity tied to the signed-in account so re-joins are the
      // same participant; fall back to a name slug for guests.
      const fallbackIdentity = accountId
        ? `web-acct-${accountId}`
        : `web-${name.toLowerCase().replace(/\s+/g, "-")}`;
      const info = await joinLiveRoom(roomId, name, identity || fallbackIdentity, locale);
      setJoinInfo(info);
      setRoom(info.room);
      // The admin (first joiner) receives the moderator key so their client can
      // start the class and advance slides.
      if (info.is_admin && info.moderator_key) setModeratorKey(info.moderator_key);
      setGiftBalance(info.gift_balance ?? 500);
      setFollowingHost(Boolean(info.following_host));
      setFollowerCount(info.host_follower_count ?? 0);
      sessionStorage.setItem(
        `${ROOM_STORAGE_KEY}:${roomId}`,
        JSON.stringify({
          name,
          participantId: info.participant.id,
          identity: info.participant.identity,
        })
      );
      await enableCamera();
    } catch (e) {
      const msg = friendlyError(e, "Could not join room");
      if (msg.toLowerCase().includes("block") || msg.toLowerCase().includes("removed") || msg.includes("403")) {
        setWasRemoved(true);
      }
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  // Signed-in users don't type a name — it's derived from their profile and they
  // join automatically. Guests (no session) still get the name prompt as a
  // fallback.
  const autoJoinedRef = useRef(false);
  useEffect(() => {
    if (autoJoinedRef.current || joinInfo || !getToken()) return;
    autoJoinedRef.current = true;
    void getMe()
      .then((acct) => {
        // Platform admin (admin@salareen.com) can moderate/close/delete ANY room.
        if (acct.is_admin) setIsPlatformAdmin(true);
        const name = (acct.display_name || "").trim();
        if (name) {
          setDisplayName(name);
          void handleJoin(name, acct.id);
        } else {
          autoJoinedRef.current = false; // no profile name -> show the prompt
        }
      })
      .catch(() => {
        autoJoinedRef.current = false; // not signed in / error -> show the prompt
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roomId, joinInfo]);

  // The class hit the end of its allotted time. After the farewell countdown,
  // excuse the learner: leave the room (best-effort) and return to the class list.
  const excuseFromClass = useCallback(() => {
    leftVoluntarily.current = true;
    const pid = joinInfo?.participant.id;
    localStream?.getTracks().forEach((t) => t.stop());
    sessionStorage.removeItem(`${ROOM_STORAGE_KEY}:${roomId}`);
    const go = () => { window.location.href = "/group-classes"; };
    if (pid) {
      void leaveLiveRoom(roomId, pid).then(go).catch(go);
    } else {
      go();
    }
  }, [joinInfo, roomId, localStream]);

  async function handleLeave() {
    if (!me) return;
    leftVoluntarily.current = true;
    setBusy(true);
    try {
      await leaveLiveRoom(roomId, me.id);
      sessionStorage.removeItem(`${ROOM_STORAGE_KEY}:${roomId}`);
      localStream?.getTracks().forEach((t) => t.stop());
      window.location.href = "/group-classes";
    } catch (e) {
      setError(friendlyError(e, "Could not leave"));
    } finally {
      setBusy(false);
    }
  }

  async function sendChat() {
    if (!me || !chatDraft.trim()) return;
    setBusy(true);
    try {
      setRoom(await liveRoomChat(roomId, me.id, chatDraft.trim()));
      setChatDraft("");
    } catch (e) {
      setError(friendlyError(e, "Chat failed"));
    } finally {
      setBusy(false);
    }
  }

  async function askQuestion() {
    if (!me || !askDraft.trim()) return;
    setBusy(true);
    try {
      const res = await liveRoomAsk(roomId, me.id, askDraft.trim(), locale);
      setRoom(res.room);
      if (res.queued) {
        setError(`You're #${res.queue_position ?? myQueuePos} in the Q&A queue. Theodore will call on you in turn.`);
      } else {
        setError("");
      }
      setAskDraft("");
    } catch (e) {
      setError(friendlyError(e, "Question failed"));
    } finally {
      setBusy(false);
    }
  }

  async function toggleHand() {
    if (!me) return;
    setBusy(true);
    try {
      if (inQueue && !hasFloor) {
        setRoom(await liveRoomLeaveQueue(roomId, me.id));
      } else {
        setRoom(await liveRoomRaiseHand(roomId, me.id, askDraft.trim()));
      }
    } catch (e) {
      setError(friendlyError(e, "Could not update queue"));
    } finally {
      setBusy(false);
    }
  }

  async function callNext() {
    if (!canModerate) return;
    setBusy(true);
    try {
      setRoom(await liveRoomCallNext(roomId, moderatorKey));
      setError("");
    } catch (e) {
      setError(friendlyError(e, "Could not call next"));
    } finally {
      setBusy(false);
    }
  }

  async function callOn(participantId: string) {
    if (!canModerate) return;
    setBusy(true);
    try {
      setRoom(await liveRoomCallOn(roomId, participantId, moderatorKey));
      setError("");
    } catch (e) {
      setError(friendlyError(e, "Could not give the floor"));
    } finally {
      setBusy(false);
    }
  }

  async function finishTurn() {
    setBusy(true);
    try {
      const pid = room?.floor_participant_id || me?.id || "";
      setRoom(await liveRoomFinishTurn(roomId, pid, moderatorKey));
    } catch (e) {
      setError(friendlyError(e, "Could not end turn"));
    } finally {
      setBusy(false);
    }
  }

  // Stop the floor microphone (idempotent).
  const stopListening = useCallback(() => {
    const rec = recognitionRef.current;
    recognitionRef.current = null;
    setListening(false);
    if (rec) {
      try { rec.stop(); } catch { /* already stopped */ }
    }
  }, []);

  // Start listening to the learner who holds the floor. Best-effort: mirrors the
  // /class "Speak now" guards (secure context, permission, browser support) and
  // falls back to typing when the mic can't run.
  const startListening = useCallback(async () => {
    if (recognitionRef.current) return; // already listening
    setMicNote("");
    if (typeof window !== "undefined" && !window.isSecureContext) {
      setMicNote(
        "Your microphone needs a secure connection — open Salareen over https:// to speak, " +
        "or type your question below and tap Ask."
      );
      return;
    }
    const w = window as unknown as {
      SpeechRecognition?: new () => SpeechRec;
      webkitSpeechRecognition?: new () => SpeechRec;
    };
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!Ctor) {
      setMicNote("Voice input isn't supported in this browser — type your question below and tap Ask.");
      return;
    }
    try {
      if (navigator.mediaDevices?.getUserMedia) {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach((t) => t.stop()); // only needed the grant
      }
    } catch {
      setMicNote(
        "Microphone access is blocked — allow the mic (address-bar icon), then tap 🎤 Speak. " +
        "You can also type your question below."
      );
      return;
    }
    let rec: SpeechRec;
    try {
      rec = new Ctor();
    } catch {
      setMicNote("Couldn't start the microphone — type your question below and tap Ask.");
      return;
    }
    rec.lang = narrationLocale || "en-US";
    rec.interimResults = true;
    rec.continuous = true;
    rec.maxAlternatives = 1;
    spokenFinalRef.current = "";
    setSpokenText("");
    rec.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        const txt = r[0]?.transcript ?? "";
        if (r.isFinal) spokenFinalRef.current = `${spokenFinalRef.current} ${txt}`.trim();
        else interim += txt;
      }
      setSpokenText(`${spokenFinalRef.current} ${interim}`.trim());
    };
    rec.onerror = (ev) => {
      const code = ev?.error || "";
      if (code === "not-allowed" || code === "service-not-allowed") {
        setMicNote("Microphone is blocked — allow it (address-bar icon) and use https://. You can type instead.");
        stopListening();
      } else if (code === "audio-capture") {
        setMicNote("No microphone found — check your device, or type your question below.");
        stopListening();
      }
      // "no-speech"/"aborted" are transient; keep the session going.
    };
    rec.onend = () => {
      setListening(false);
      recognitionRef.current = null;
    };
    recognitionRef.current = rec;
    setListening(true);
    try {
      rec.start();
    } catch {
      setListening(false);
      recognitionRef.current = null;
      setMicNote("Couldn't start the microphone — type your question below and tap Ask.");
    }
  }, [narrationLocale, stopListening]);

  // Learner is done speaking: send whatever we heard (or typed) to Theodore as a
  // question — the server answers a floor-holder immediately and releases the
  // floor. With nothing captured, just hand the floor back.
  async function doneSpeaking() {
    if (!me) return;
    const question = (spokenFinalRef.current || spokenText || askDraft).trim();
    stopListening();
    setBusy(true);
    try {
      if (question) {
        const res = await liveRoomAsk(roomId, me.id, question, narrationLocale);
        setRoom(res.room);
        setAskDraft("");
        setSpokenText("");
        spokenFinalRef.current = "";
        setError("");
      } else {
        const pid = room?.floor_participant_id || me.id;
        setRoom(await liveRoomFinishTurn(roomId, pid, moderatorKey));
      }
    } catch (e) {
      setError(friendlyError(e, "Couldn't send your question to Theodore"));
    } finally {
      setBusy(false);
    }
  }

  async function toggleMute() {
    if (!me) return;
    setBusy(true);
    try {
      // Toggle against the effective muted state (self-mute OR host mute) so the
      // button's label ("Mute"/"Unmute") always matches what it does.
      const currentlyMuted = Boolean(me.muted || me.muted_by_host);
      setRoom(await liveRoomMute(roomId, me.id, !currentlyMuted, false, "", me.id));
    } catch (e) {
      setError(friendlyError(e, "Could not toggle mute"));
    } finally {
      setBusy(false);
    }
  }

  async function hostAdvance() {
    setBusy(true);
    try {
      setRoom(await liveRoomAdvance(roomId, moderatorKey));
    } catch (e) {
      setError(friendlyError(e, "Advance failed"));
    } finally {
      setBusy(false);
    }
  }

  async function startPresentation() {
    setBusy(true);
    try {
      setRoom(await liveRoomStartPresentation(roomId, moderatorKey));
    } catch (e) {
      setError(friendlyError(e, "Could not start the class"));
    } finally {
      setBusy(false);
    }
  }

  // Heartbeat: drives AI auto-start (full / 5-min rule) and auto-advance. Any
  // joined client ticks every 8s; the server makes it idempotent.
  useEffect(() => {
    if (!joinInfo) return;
    const t = window.setInterval(() => {
      void liveRoomTick(roomId, joinInfo.participant.id).then((r) => applyRoom(r)).catch(() => undefined);
    }, 3000);  // 3s so slides auto-advance close to the 5s dwell (and presence stays fresh)
    return () => window.clearInterval(t);
  }, [joinInfo, roomId, applyRoom]);

  // AI teacher voice: Theodore narrates each new slide out loud while presenting
  // (neural TTS via the speech service, on-device fallback). Keyed on the slide
  // index so each slide is spoken once — on Start class and on every auto/manual
  // advance. Muting, the class ending, or leaving stops and resets it.
  const classLive = Boolean(room?.presenting) && room?.status !== "ended";
  const slideIdx = room?.slide?.index;
  const slideTitle = room?.slide?.title;
  const slideNarration = room?.slide?.narration;
  const slideBody = room?.slide?.body;
  useEffect(() => {
    if (!aiAudioOn || !classLive || slideIdx == null) {
      cancelSpeech();
      if (!classLive) spokenSlideRef.current = null;
      return;
    }
    if (spokenSlideRef.current === slideIdx) return;
    spokenSlideRef.current = slideIdx;
    // Narrate the full slide body (a substantive mini-lecture), not just the
    // terse one-line script — so the class actually teaches and runs for its
    // natural length. The server paces auto-advance to this narration.
    const text = `${slideTitle ? slideTitle + ". " : ""}${(slideBody || slideNarration || "").trim()}`.trim();
    if (text) {
      cancelSpeech();  // stop the previous slide's narration before the new one
      const spokenFor = slideIdx;
      speakNaturally(text, {
        locale: narrationLocale,
        // Advance the instant the AI finishes narrating this slide (not after a
        // timed estimate). The moderator's client drives it; everyone else
        // follows via the room state. Guarded so we don't skip past a learner
        // who has (or is waiting for) the floor, and only while still on this
        // slide. The server's timed dwell remains a fallback if audio is muted.
        onend: () => {
          const r = roomRef.current;
          if (
            canModerate &&
            Boolean(r?.presenting) &&
            r?.status !== "ended" &&
            spokenSlideRef.current === spokenFor &&
            !r?.floor_participant_id &&
            !(r?.speaking_queue?.some((e) => e.status === "waiting"))
          ) {
            void liveRoomAdvance(roomId, moderatorKey).then((next) => setRoom(next)).catch(() => undefined);
          }
        },
      });
    }
  }, [aiAudioOn, classLive, slideIdx, slideTitle, slideNarration, slideBody, narrationLocale,
      canModerate, moderatorKey, roomId]);

  // Always stop narration when leaving the room.
  useEffect(() => () => cancelSpeech(), []);

  // When this learner is granted the floor, open the mic to capture their spoken
  // question; when they lose it (or leave), stop listening and clear the draft.
  useEffect(() => {
    if (hasFloor) {
      void startListening();
    } else {
      stopListening();
      setSpokenText("");
      spokenFinalRef.current = "";
      setMicNote("");
    }
    return () => stopListening();
  }, [hasFloor, startListening, stopListening]);

  async function toggleRecording() {
    setBusy(true);
    try {
      if (room?.recording.status === "recording") {
        setRoom(await liveRoomRecordStop(roomId));
      } else {
        setRoom(await liveRoomRecordStart(roomId));
      }
    } catch (e) {
      setError(friendlyError(e, "Recording failed"));
    } finally {
      setBusy(false);
    }
  }

  async function banLearner(participantId: string, name: string) {
    if (!canModerate) return;
    const reason = window.prompt(`Block ${name}? Optional reason:`) ?? "";
    if (reason === null) return;
    setBusy(true);
    try {
      setRoom(await liveRoomBan(roomId, participantId, reason, moderatorKey));
    } catch (e) {
      setError(friendlyError(e, "Ban failed"));
    } finally {
      setBusy(false);
    }
  }

  async function unbanLearner(identity: string) {
    if (!canModerate) return;
    setBusy(true);
    try {
      setRoom(await liveRoomUnban(roomId, identity, moderatorKey));
    } catch (e) {
      setError(friendlyError(e, "Unban failed"));
    } finally {
      setBusy(false);
    }
  }

  async function reportLearner(participantId: string, name: string) {
    if (!me?.id) return;
    const reason =
      window.prompt(`Report ${name} — what happened? (required)`)?.trim() ?? "";
    if (!reason) return;
    const category =
      window.prompt(
        "Category: spam, harassment, inappropriate, disruptive, or other",
        "other"
      )?.trim().toLowerCase() || "other";
    setBusy(true);
    try {
      await liveRoomReport(roomId, me.id, participantId, reason, category);
      window.alert("Report submitted. A moderator will review it.");
    } catch (e) {
      setError(friendlyError(e, "Report failed"));
    } finally {
      setBusy(false);
    }
  }

  // Admin/moderator: close this session for everyone (status -> ended).
  async function closeSession() {
    if (!canModerate) return;
    if (typeof window !== "undefined" && !window.confirm("Close this session for everyone?")) return;
    setBusy(true);
    try {
      setRoom(await liveRoomEnd(roomId, moderatorKey));
    } catch (e) {
      setError(friendlyError(e, "Could not close session"));
    } finally {
      setBusy(false);
    }
  }

  // Platform admin: delete this session permanently (cleanup), then leave.
  async function deleteSession() {
    if (!isPlatformAdmin) return;
    if (typeof window !== "undefined" && !window.confirm("Delete this session permanently?")) return;
    setBusy(true);
    try {
      await deleteLiveRoom(roomId);
      window.location.href = "/group-classes";
    } catch (e) {
      setError(friendlyError(e, "Could not delete session"));
      setBusy(false);
    }
  }

  async function dismissReport(reportId: string) {
    if (!canModerate) return;
    setBusy(true);
    try {
      setRoom(await liveRoomDismissReport(roomId, reportId, moderatorKey));
    } catch (e) {
      setError(friendlyError(e, "Dismiss failed"));
    } finally {
      setBusy(false);
    }
  }

  if (wasRemoved) {
    return (
      <main className="container" style={{ maxWidth: 480 }}>
        <h1>Removed from class</h1>
        <p className="muted">
          You were blocked from this live room and cannot rejoin until a moderator lifts the ban.
        </p>
        <button onClick={() => { window.location.href = "/group-classes"; }}>Back to Group Classes</button>
      </main>
    );
  }

  if (!joinInfo) {
    return (
      <main className="container" style={{ maxWidth: 480 }}>
        <h1>Salareen Live Room</h1>
        <p className="muted">
          {(room?.room_size ?? 6) <= 2
            ? "Your private 1:1 session with Theodore, your AI teacher."
            : `Join Theodore's multi-user class — up to ${room?.room_size ?? 6} seats in the grid.`}
        </p>
        {room && (
          <div className="card" style={{ marginBottom: 12 }}>
            <strong>{room.title}</strong>
            <div className="muted">
              {room.learner_count}/{room.learner_capacity} learners · {room.seats_left} seats left
            </div>
          </div>
        )}
        {error && <div className="card" style={{ borderColor: "#ff6b6b", marginBottom: 12 }}>{error}</div>}
        <div className="card">
          <label>
            <div className="muted">Your display name</div>
            <input
              style={{ width: "100%", marginTop: 6 }}
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Ada"
              onKeyDown={(e) => e.key === "Enter" && void handleJoin()}
            />
          </label>
          <button
            onClick={() => void handleJoin()}
            disabled={busy}
            style={{ marginTop: 12, background: "var(--accent)", color: "#fff", width: "100%" }}
          >
            {busy ? "Joining…" : "Enter live room"}
          </button>
        </div>
      </main>
    );
  }

  const learners = (room?.participants ?? []).filter((p) => p.role !== "host");
  const host = room?.host;
  const emptySlots = Math.max(0, (room?.learner_capacity ?? 0) - learners.length);

  return (
    <main
      style={{
        minHeight: "100vh",
        // Match the site's light "warm campus" theme (globals.css tokens) so the
        // classroom looks like the rest of the app, not a separate dark product.
        background:
          "linear-gradient(180deg, var(--bg) 0%, color-mix(in srgb, var(--bg) 88%, var(--accent)) 100%)",
        color: "var(--text)",
        padding: "12px 16px 24px",
      }}
    >
      {room?.status === "ended" && (
        <ClassCompleteOverlay onDone={excuseFromClass} primaryLang={me?.language || locale} />
      )}
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 12,
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <div>
          <div style={{ fontSize: 12, color: "var(--accent)" }}>Salareen Live · {roomId}</div>
          <h2 style={{ margin: "4px 0 0", fontSize: 20 }}>{room?.title ?? "Live class"}</h2>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13, flexWrap: "wrap" }}>
          <LocalRecorder roomId={roomId} title={room?.title ?? "Live class"} />
          {room?.recording.status === "recording" && (
            <span style={{ color: "#fca5a5", fontWeight: 600 }}>● REC</span>
          )}
          <span className="muted">
            👁 {socket.viewerCount || room?.viewer_count || room?.learner_count || 0}
          </span>
          <span className="muted">
            ❤️ {socket.followerCount || followerCount} followers
          </span>
          {socket.connected ? (
            <span style={{ color: "#34d399", fontSize: 11 }}>● live</span>
          ) : (
            <span style={{ color: "#fcd34d", fontSize: 11 }}>polling</span>
          )}
          {me ? (
            <button
              type="button"
              onClick={async () => {
                try {
                  const r = await liveRoomFollowHost(
                    roomId,
                    me.identity,
                    followingHost,
                  );
                  setFollowingHost(r.following);
                  setFollowerCount(r.follower_count);
                  socket.setFollowerCount(r.follower_count);
                } catch (e) {
                  setError(friendlyError(e, "Follow failed"));
                }
              }}
              style={{
                fontSize: 12,
                padding: "4px 10px",
                borderRadius: 999,
                border: "1px solid var(--border)",
                background: followingHost ? "color-mix(in srgb, var(--accent) 15%, var(--panel))" : "var(--panel)",
                color: "var(--text)",
                cursor: "pointer",
              }}
            >
              {followingHost ? "Following host" : "Follow host"}
            </button>
          ) : null}
        </div>
      </header>

      {socket.presenceToast ? (
        <div
          style={{
            position: "fixed",
            top: 72,
            left: "50%",
            transform: "translateX(-50%)",
            background: "rgba(15,7,32,0.92)",
            border: "1px solid rgba(167,139,250,0.4)",
            borderRadius: 999,
            padding: "8px 16px",
            fontSize: 13,
            zIndex: 50,
          }}
        >
          {socket.presenceToast.kind === "join" ? "👋" : "👋"} {socket.presenceToast.name}{" "}
          {socket.presenceToast.kind === "join" ? "joined" : "left"}
        </div>
      ) : null}

      {socket.giftOverlay ? (
        <div
          style={{
            position: "fixed",
            top: "40%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            fontSize: 64,
            zIndex: 60,
            textAlign: "center",
            pointerEvents: "none",
          }}
        >
          <div>{socket.giftOverlay.emoji}</div>
          <div style={{ fontSize: 14, marginTop: 8, color: "#fce7f3" }}>
            {socket.giftOverlay.label}
          </div>
        </div>
      ) : null}

      <div
        style={{
          position: "fixed",
          inset: 0,
          pointerEvents: "none",
          overflow: "hidden",
          zIndex: 40,
        }}
      >
        {socket.floatingReactions.map((r) => (
          <span
            key={r.id}
            style={{
              position: "absolute",
              left: `${r.x}%`,
              bottom: 80,
              fontSize: 28,
              animation: "live-float-up 2.2s ease-out forwards",
            }}
          >
            {r.emoji}
          </span>
        ))}
      </div>

      <style jsx global>{`
        @keyframes live-float-up {
          0% {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
          100% {
            opacity: 0;
            transform: translateY(-180px) scale(1.2);
          }
        }
        @keyframes floor-mic-pulse {
          0% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(1.5); }
          100% { opacity: 1; transform: scale(1); }
        }
      `}</style>

      {error && (
        <div style={{ background: "rgba(239,68,68,0.2)", border: "1px solid #ef4444", borderRadius: 8, padding: 8, marginBottom: 10 }}>
          {error}
        </div>
      )}

      {/* LiveKit couldn't connect (e.g. media backend unreachable / mis-keyed).
          The class still runs over the AI teacher's narration, chat and Q&A, so
          we show a calm note rather than letting the console fill with failed
          reconnect attempts. */}
      {liveKitFailed && (
        <div
          style={{
            background: "color-mix(in srgb, var(--accent) 8%, var(--panel))",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: "8px 10px",
            marginBottom: 10,
            fontSize: 13,
            color: "var(--muted)",
          }}
        >
          🔇 Live audio/video for participants is unavailable right now — the AI
          teacher’s narration, chat and Q&amp;A continue as normal.
        </div>
      )}

      {/* View toggles: focus the instructor (slide) and show/hide chat. */}
      <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
        <button
          type="button"
          onClick={() => setFocusInstructor((v) => !v)}
          title={focusInstructor ? "Show everyone" : "Focus on the instructor / slides"}
          style={{
            fontSize: 13, padding: "6px 12px", borderRadius: 8, cursor: "pointer",
            border: "1px solid var(--border)",
            background: focusInstructor ? "var(--accent)" : "var(--panel)",
            color: focusInstructor ? "#fff" : "var(--text)",
          }}
        >
          {focusInstructor ? "👥 Show everyone" : "🎓 Focus instructor"}
        </button>
        <button
          type="button"
          onClick={() => setShowChat((v) => !v)}
          title={showChat ? "Hide chat" : "Show chat"}
          style={{
            fontSize: 13, padding: "6px 12px", borderRadius: 8, cursor: "pointer",
            border: "1px solid var(--border)",
            background: showChat ? "var(--panel)" : "var(--accent)",
            color: showChat ? "var(--text)" : "#fff",
          }}
        >
          {showChat ? "💬 Hide chat" : "💬 Show chat"}
        </button>
        <button
          type="button"
          onClick={toggleHostFullscreen}
          title="Fullscreen the host / slide (Esc to exit)"
          style={{
            fontSize: 13, padding: "6px 12px", borderRadius: 8, cursor: "pointer",
            border: "1px solid var(--border)",
            background: isFullscreen ? "var(--accent)" : "var(--panel)",
            color: isFullscreen ? "#fff" : "var(--text)",
          }}
        >
          {isFullscreen ? "⛶ Exit fullscreen" : "⛶ Fullscreen host"}
        </button>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: showChat ? "minmax(0, 1.4fr) minmax(280px, 1fr)" : "1fr",
          gap: 14,
          alignItems: "start",
        }}
      >
        <section>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: focusInstructor ? "1fr" : largeHostColumn(layout.cols),
              gridTemplateRows: focusInstructor ? "minmax(320px, 60vh)" : `repeat(${layout.rows}, minmax(100px, 1fr))`,
              gap: 8,
              marginBottom: 12,
            }}
          >
            {/* Hidden audio sinks so you can HEAR remote participants (video tiles stay muted). */}
            {audioTracks.map((a) => (
              <LiveKitAudio key={a.participantId} track={a.track} />
            ))}
            {host && (
              <div style={{ gridRow: focusInstructor ? "auto" : `span ${layout.rows}`, minHeight: 220 }}>
                <ParticipantTile
                  p={host}
                  large
                  liveKitTrack={trackFor(host.id)}
                  slide={room?.slide}
                  onContainerRef={(el) => { hostTileRef.current = el; }}
                />
              </div>
            )}
            {!focusInstructor && learners.map((p) => (
              <div key={p.id} style={{ position: "relative" }}>
                <ParticipantTile
                  p={p}
                  localStream={p.id === me?.id ? localStream : null}
                  liveKitTrack={trackFor(p.id)}
                  hasFloor={p.id === room?.floor_participant_id}
                />
                {canModerate && p.id !== me?.id ? (
                  <button
                    type="button"
                    onClick={() => void banLearner(p.id, p.name)}
                    disabled={busy}
                    title={`Block ${p.name}`}
                    style={{
                      position: "absolute",
                      top: 6,
                      right: 6,
                      fontSize: 11,
                      padding: "2px 8px",
                      borderRadius: 6,
                      background: "rgba(220,38,38,0.9)",
                      color: "#fff",
                      border: "none",
                      cursor: "pointer",
                    }}
                  >
                    Block
                  </button>
                ) : null}
                {canModerate && p.role !== "host" && p.id !== room?.floor_participant_id ? (
                  <button
                    type="button"
                    onClick={() => void callOn(p.id)}
                    disabled={busy}
                    title={`Request ${p.name} to speak (give them the floor; only they can talk)`}
                    style={{
                      position: "absolute",
                      bottom: 34,
                      right: 6,
                      fontSize: 11,
                      padding: "2px 8px",
                      borderRadius: 6,
                      background: "rgba(13,148,136,0.95)",
                      color: "#fff",
                      border: "none",
                      cursor: "pointer",
                    }}
                  >
                    🎤 Request to speak
                  </button>
                ) : null}
                {p.role !== "host" && p.id !== me?.id ? (
                  <button
                    type="button"
                    onClick={() => void reportLearner(p.id, p.name)}
                    disabled={busy}
                    title={`Report ${p.name}`}
                    style={{
                      position: "absolute",
                      top: 6,
                      left: 6,
                      fontSize: 11,
                      padding: "2px 8px",
                      borderRadius: 6,
                      background: "rgba(245,158,11,0.9)",
                      color: "#1c1917",
                      border: "none",
                      cursor: "pointer",
                    }}
                  >
                    Report
                  </button>
                ) : null}
              </div>
            ))}
            {!focusInstructor && Array.from({ length: emptySlots }).map((_, i) => (
              <div
                key={`empty-${i}`}
                style={{
                  borderRadius: 12,
                  border: "1px dashed var(--border)",
                  minHeight: 110,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "var(--muted)",
                  fontSize: 12,
                }}
              >
                Open seat
              </div>
            ))}
          </div>

          {hasFloor && (
            <div
              style={{
                marginBottom: 12,
                padding: 14,
                borderRadius: 12,
                background: "color-mix(in srgb, var(--accent-2) 12%, var(--panel))",
                border: "2px solid var(--accent-2)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span style={{ fontSize: 15, fontWeight: 700 }}>
                  {listening ? "🎙️ You have the floor — ask your question out loud" : "🎤 You have the floor"}
                </span>
                {listening ? (
                  <span
                    aria-hidden
                    style={{
                      width: 10, height: 10, borderRadius: "50%", background: "#ef4444",
                      animation: "floor-mic-pulse 1.1s ease-in-out infinite",
                    }}
                  />
                ) : null}
              </div>
              <p style={{ margin: "6px 0 10px", fontSize: 13, color: "var(--muted)" }}>
                Theodore is listening. Speak naturally, then tap “Done — ask Theodore”. You can also type it below.
              </p>
              <div
                style={{
                  minHeight: 44,
                  padding: "8px 10px",
                  borderRadius: 8,
                  background: "var(--panel)",
                  border: "1px solid var(--border)",
                  fontSize: 14,
                  color: spokenText ? "var(--text)" : "var(--muted)",
                  fontStyle: spokenText ? "normal" : "italic",
                }}
              >
                {spokenText || (listening ? "Listening…" : "Tap 🎤 Speak to start the mic.")}
              </div>
              {micNote ? (
                <div style={{ marginTop: 8, fontSize: 12, color: "#b45309" }}>{micNote}</div>
              ) : null}
              <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                <button
                  type="button"
                  onClick={() => (listening ? stopListening() : void startListening())}
                  disabled={busy}
                  style={{
                    background: listening ? "var(--panel)" : "var(--accent)",
                    color: listening ? "var(--text)" : "#fff",
                    border: "1px solid var(--border)",
                  }}
                >
                  {listening ? "⏸ Pause mic" : "🎤 Speak"}
                </button>
                <button
                  type="button"
                  onClick={() => void doneSpeaking()}
                  disabled={busy}
                  style={{ background: "#059669", color: "#fff" }}
                >
                  Done — ask Theodore
                </button>
              </div>
            </div>
          )}

          {(room?.speaking_queue?.length ?? 0) > 0 && (
            <div
              style={{
                marginBottom: 12,
                padding: 12,
                borderRadius: 12,
                background: "rgba(52,211,153,0.08)",
                border: "1px solid rgba(52,211,153,0.25)",
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 600, color: "#6ee7b7", marginBottom: 8 }}>
                Q&A queue — take turns
              </div>
              {room?.floor_holder ? (
                <div style={{ fontSize: 13, marginBottom: 8, color: "#a7f3d0" }}>
                  🎤 Now speaking: <strong>{room.floor_holder.name}</strong>
                </div>
              ) : null}
              <ol style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "#d1fae5" }}>
                {(room?.speaking_queue ?? [])
                  .filter((e) => e.status === "waiting")
                  .map((e) => (
                    <li key={e.id} style={{ marginBottom: 4 }}>
                      #{e.position} {e.name}
                      {e.question ? ` — "${e.question}"` : ""}
                    </li>
                  ))}
              </ol>
              {myQueuePos > 0 && !hasFloor ? (
                <div style={{ marginTop: 8, fontSize: 12, color: "#fcd34d" }}>
                  You are #{myQueuePos} in line.
                </div>
              ) : null}
            </div>
          )}

          {room?.slide && (
            <div
              style={{
                background: "var(--panel)",
                border: "1px solid var(--border)",
                borderRadius: 12,
                padding: 14,
              }}
            >
              <div style={{ fontSize: 12, color: "var(--accent)", marginBottom: 4 }}>
                Slide {room.slide.index + 1}
              </div>
              <strong>{room.slide.title}</strong>
              <p style={{ margin: "8px 0 0", color: "var(--muted)", fontSize: 14, lineHeight: 1.5 }}>
                {room.slide.narration || room.slide.body}
              </p>
            </div>
          )}
        </section>

        {showChat && (
        <aside
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 10,
            minHeight: 420,
          }}
        >
          <div
            style={{
              flex: 1,
              background: "var(--panel)",
              borderRadius: 12,
              border: "1px solid var(--border)",
              padding: 10,
              overflowY: "auto",
              maxHeight: 320,
              minHeight: 200,
            }}
          >
            {(room?.chat ?? []).map((m) => (
              <div key={m.id} style={{ marginBottom: 8, fontSize: 13, lineHeight: 1.4 }}>
                <span style={{ color: m.from_id === "system" ? "#a78bfa" : "#fbbf24", fontWeight: 600 }}>
                  {m.from_name}:
                </span>{" "}
                <span style={{ color: "#e2e8f0" }}>{m.text}</span>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>

          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
            {REACTIONS.map((emoji) => (
              <button
                key={emoji}
                type="button"
                disabled={busy || !me}
                onClick={async () => {
                  if (!me) return;
                  socket.pushReaction(emoji);
                  try {
                    applyRoom(await liveRoomReaction(roomId, me.id, emoji));
                  } catch (e) {
                    setError(friendlyError(e, "Reaction failed"));
                  }
                }}
                style={{
                  fontSize: 18,
                  padding: "4px 8px",
                  borderRadius: 8,
                  border: "1px solid var(--border)",
                  background: "var(--panel)",
                  cursor: "pointer",
                }}
              >
                {emoji}
              </button>
            ))}
            <button
              type="button"
              disabled={!me}
              onClick={() => setShowGifts((v) => !v)}
              style={{
                marginLeft: "auto",
                fontSize: 12,
                padding: "6px 12px",
                borderRadius: 8,
                background: "var(--accent-2)",
                color: "#fff",
                border: "none",
                cursor: "pointer",
              }}
            >
              🎁 Gifts ({giftBalance} pts)
            </button>
          </div>

          {showGifts ? (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
                gap: 6,
                padding: 8,
                background: "color-mix(in srgb, var(--accent) 6%, var(--panel))",
                borderRadius: 10,
              }}
            >
              {giftCatalog.map((g) => (
                <button
                  key={g.id}
                  type="button"
                  disabled={busy || !me || giftBalance < g.cost_points}
                  onClick={async () => {
                    if (!me) return;
                    setBusy(true);
                    try {
                      const res = await liveRoomSendGift(roomId, me.id, g.id);
                      applyRoom(res.room);
                      setGiftBalance(res.sender_balance);
                      setShowGifts(false);
                    } catch (e) {
                      setError(friendlyError(e, "Gift failed"));
                    } finally {
                      setBusy(false);
                    }
                  }}
                  style={{
                    padding: 8,
                    borderRadius: 8,
                    border: "1px solid var(--border)",
                    background: "var(--panel)",
                    color: "var(--text)",
                    cursor: "pointer",
                    fontSize: 12,
                  }}
                >
                  <div style={{ fontSize: 22 }}>{g.emoji}</div>
                  {g.name}
                  <div>{g.cost_points} pts</div>
                </button>
              ))}
            </div>
          ) : null}

          <div style={{ display: "flex", gap: 6 }}>
            <input
              value={chatDraft}
              onChange={(e) => setChatDraft(e.target.value)}
              placeholder="Say something…"
              style={{ flex: 1, borderRadius: 8, border: "1px solid var(--border)", padding: "8px 10px", background: "var(--panel)", color: "var(--text)" }}
              onKeyDown={(e) => e.key === "Enter" && void sendChat()}
              disabled={busy || me?.muted || me?.muted_by_host}
            />
            <button onClick={() => void sendChat()} disabled={busy} style={{ background: "var(--accent)", color: "#fff" }}>
              Chat
            </button>
          </div>

          <div style={{ display: "flex", gap: 6 }}>
            <input
              value={askDraft}
              onChange={(e) => setAskDraft(e.target.value)}
              placeholder="Ask Theodore a question…"
              style={{ flex: 1, borderRadius: 8, border: "1px solid var(--border)", padding: "8px 10px", background: "var(--panel)", color: "var(--text)" }}
              onKeyDown={(e) => e.key === "Enter" && void askQuestion()}
              disabled={busy}
            />
            <button onClick={() => void askQuestion()} disabled={busy} style={{ background: "var(--accent-2)", color: "#fff" }}>
              Ask
            </button>
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            <button onClick={() => void toggleHand()} disabled={busy} title="Raise your hand to ask to speak (raise/lower)">
              {hasFloor
                ? "🎤 You're speaking"
                : inQueue
                  ? `✋ Lower your hand (#${myQueuePos})`
                  : "✋ Raise your hand"}
            </button>
            {hasFloor ? (
              <button
                onClick={() => void doneSpeaking()}
                disabled={busy}
                title="Send your spoken (or typed) question to Theodore and hand back the floor"
                style={{ background: "#059669", color: "#fff" }}
              >
                Done — ask Theodore
              </button>
            ) : null}
            {canModerate ? (
              <>
                <button onClick={() => void callNext()} disabled={busy} style={{ background: "#0d9488", color: "#fff" }}>
                  Call next
                </button>
                {room?.floor_participant_id ? (
                  <button onClick={() => void finishTurn()} disabled={busy}>
                    End turn
                  </button>
                ) : null}
              </>
            ) : null}
            <button
              onClick={() => void toggleMute()}
              disabled={busy || (!hasFloor && inQueue)}
              title="Mute or unmute your own microphone. You're only heard once the host gives you the floor (raise your hand)."
            >
              {me?.muted || me?.muted_by_host ? "🔊 Unmute" : "🔇 Mute"}
            </button>
            <button
              onClick={() => setAiAudioOn((v) => { if (v) cancelSpeech(); return !v; })}
              title={aiAudioOn ? "Mute the AI teacher's voice" : "Hear the AI teacher narrate the slides"}
            >
              {aiAudioOn ? "🔊 AI voice" : "🔇 AI voice"}
            </button>
            {canModerate ? (
              !room?.presenting ? (
                <button
                  onClick={(e) => { e.currentTarget.blur(); void startPresentation(); }}
                  disabled={busy}
                  title="Start the class"
                  style={{ background: "var(--accent-2)", color: "#fff" }}
                >
                  🎬 Start class
                </button>
              ) : (
                <button onClick={() => void hostAdvance()} disabled={busy} title="Next slide (the AI advances automatically)">
                  ▶ Next slide
                </button>
              )
            ) : null}
            {canModerate ? (
              <button onClick={() => void toggleRecording()} disabled={busy}>
                {room?.recording.status === "recording" ? "⏹ Stop REC" : "🔴 Record"}
              </button>
            ) : null}
            {canModerate ? (
              <button
                onClick={() => void closeSession()}
                disabled={busy}
                title="Close this session for everyone"
                style={{ background: "#b45309", color: "#fff" }}
              >
                ⛔ Close session
              </button>
            ) : null}
            {isPlatformAdmin ? (
              <button
                onClick={() => void deleteSession()}
                disabled={busy}
                title="Delete this session permanently (admin cleanup)"
                style={{ background: "#b91c1c", color: "#fff" }}
              >
                🗑 Delete
              </button>
            ) : null}
            <button onClick={() => void handleLeave()} disabled={busy} style={{ marginLeft: "auto" }}>
              Leave
            </button>
          </div>

          {canModerate && (room?.reports?.length ?? 0) > 0 ? (
            <div
              style={{
                marginTop: 8,
                padding: 10,
                borderRadius: 10,
                background: "rgba(245,158,11,0.12)",
                border: "1px solid rgba(251,191,36,0.35)",
                fontSize: 12,
              }}
            >
              <strong style={{ color: "#fcd34d" }}>User reports</strong>
              {(room?.reports ?? []).map((rep) => (
                <div
                  key={rep.id}
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginTop: 8,
                    gap: 8,
                  }}
                >
                  <span>
                    <strong>{rep.reported_name}</strong> ({rep.category}) — {rep.reason}
                    <br />
                    <span style={{ opacity: 0.75 }}>from {rep.reporter_name}</span>
                  </span>
                  <span style={{ display: "flex", gap: 6 }}>
                    <button
                      type="button"
                      onClick={() => void banLearner(rep.reported_participant_id, rep.reported_name)}
                      disabled={busy}
                    >
                      Block
                    </button>
                    <button type="button" onClick={() => void dismissReport(rep.id)} disabled={busy}>
                      Dismiss
                    </button>
                  </span>
                </div>
              ))}
            </div>
          ) : null}

          {canModerate && (room?.banned?.length ?? 0) > 0 ? (
            <div
              style={{
                marginTop: 8,
                padding: 10,
                borderRadius: 10,
                background: "rgba(220,38,38,0.12)",
                border: "1px solid rgba(248,113,113,0.35)",
                fontSize: 12,
              }}
            >
              <strong style={{ color: "#fca5a5" }}>Blocked users</strong>
              {(room?.banned ?? []).map((b) => (
                <div key={b.identity} style={{ display: "flex", justifyContent: "space-between", marginTop: 6, gap: 8 }}>
                  <span>{b.name} — {b.reason}</span>
                  <button type="button" onClick={() => void unbanLearner(b.identity)} disabled={busy}>
                    Unblock
                  </button>
                </div>
              ))}
            </div>
          ) : null}
        </aside>
        )}
      </div>
    </main>
  );
}

function largeHostColumn(cols: number): string {
  if (cols <= 2) return "1.2fr 1fr";
  return "1.3fr repeat(2, 1fr)";
}
