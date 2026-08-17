"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";

import {
  getLiveRoom,
  getLiveGiftCatalog,
  getMe,
  getToken,
  getLearningExperience,
  joinLiveRoom,
  leaveLiveRoom,
  listStudents,
  liveRoomBan,
  liveRoomUnban,
  liveRoomReport,
  liveRoomDismissReport,
  liveRoomAdvance,
  liveRoomStartPresentation,
  liveRoomEnd,
  liveRoomTick,
  liveRoomAsk,
  liveRoomAskStream,
  liveRoomChat,
  liveRoomRaiseHand,
  liveRoomCallNext,
  liveRoomCallOn,
  liveRoomMediaToken,
  liveRoomFinishTurn,
  liveRoomLeaveQueue,
  liveRoomReaction,
  liveRoomSendGift,
  liveRoomFollowHost,
  liveRoomPlayGame,
  liveRoomStartGame,
  identifyEmbedding,
  reportLiveRoomPresence,
  type LiveGiftCatalogItem,
  type LiveGroupGame,
  type LiveParticipant,
  type LiveRoomJoin,
  type LiveRoomState,
} from "../../lib/api";
import { useFlag, useVoicePauseSubmitMs } from "../../lib/flags";
import { createVoicePauseSubmitter } from "../../lib/voiceCommands";
import Link from "next/link";
import { friendlyError } from "../../lib/errors";
import { LiveKitAudio, LiveKitVideoTile, useLiveKitRoom } from "../../components/LiveKitRoomGrid";
import { useLiveRoomSocket } from "../../lib/liveRoomSocket";
import Whiteboard, { type WhiteboardStroke } from "./Whiteboard";
import { useT } from "../../lib/i18n";
import { buildNarrationSpeakOptions } from "../../lib/narrationTts";
import { speakNaturally, cancelSpeech } from "../../lib/tts";
import { resumeSharedAudioContext, unlockWebAudio } from "../../lib/webAudioUnlock";
import { createVisionEngine, type VisionEngine } from "../../lib/vision";
import CameraLightingScreener from "../../components/CameraLightingScreener";
import CameraQualityGateOverlay from "../../components/CameraQualityGateOverlay";
import {
  DEFAULT_LIGHTING_THRESHOLDS,
  analyzeLuminanceGrid,
  luminanceGridFromImageData,
  tickSustainedQuality,
  verdictFromMetrics,
  type LightingVerdict,
  type SustainedQualityState,
} from "../../lib/cameraLighting";

const REACTIONS = ["❤️", "👏", "🔥", "😂", "🎉", "👍"] as const;
// Design A "calm studio" primary CTA color — a warm gold used for the key
// actions (Raise your hand / Done, send message) to match the mockup.
const STUDIO_GOLD = "#c8981f";

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
const ATTENDEE_CODE_KEY = "salareen-attendee-code";

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
function ClassCompleteOverlay({ onDone, primaryLang, exitLabel = "Group Classes" }: { onDone: () => void; primaryLang?: string; exitLabel?: string }) {
  const [remaining, setRemaining] = useState(CLASS_END_COUNTDOWN);
  const [msgIdx, setMsgIdx] = useState(0);
  const messages = useMemo(() => orderedFarewell(primaryLang), [primaryLang]);

  // Hard-stop Theodore the moment the farewell overlay appears — leaving must
  // not leave slide/Q&A narration still playing under the "Class complete" UI.
  useEffect(() => {
    cancelSpeech();
  }, []);

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
        Returning to {exitLabel} in {remaining}s…
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

/** Solo 1:1 Salareen room (AI host + one learner). */
function isSoloLiveRoom(roomId: string, room?: LiveRoomState | null): boolean {
  if (roomId.startsWith("solo-")) return true;
  if (!room) return false;
  return room.room_size <= 2 || room.learner_capacity <= 1;
}

function soloExitHref(roomId: string, room?: LiveRoomState | null): string {
  return isSoloLiveRoom(roomId, room) ? "/class" : "/group-classes";
}

type LearnerJoinContext = {
  studentId: string;
  readinessScore: number;
  readinessBand: string;
  primaryStyle: string;
  learnerCategory: string;
  lxScore: number | null;
};

async function fetchLearnerJoinContext(): Promise<LearnerJoinContext | null> {
  if (!getToken()) return null;
  try {
    const { students } = await listStudents();
    const student = students[0];
    if (!student) return null;
    const lx = await getLearningExperience(student.id);
    return {
      studentId: student.id,
      readinessScore: Number(lx.readiness_score ?? 0),
      readinessBand: (lx.readiness_band || "").trim(),
      primaryStyle: (lx.primary_style || student.primary_style || "mixed").trim() || "mixed",
      learnerCategory: (student.learner_category || "").trim(),
      lxScore: lx.lx_score_ema ?? null,
    };
  } catch {
    return null;
  }
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
  fullscreen,
  localStream,
  liveKitTrack,
  hasFloor,
  slide,
  onContainerRef,
  fullscreenControls,
  isMe,
  cameraOn,
  onToggleCamera,
  audioMuted,
  onToggleAudio,
  fill,
  showAdminProfile,
  presenceFaceCount,
  aiHost = true,
}: {
  p: LiveParticipant;
  large?: boolean;
  fullscreen?: boolean;
  localStream?: MediaStream | null;
  liveKitTrack?: MediaStreamTrack | null;
  hasFloor?: boolean;
  slide?: { index: number; title: string; body: string; narration: string } | null;
  // Lets the parent grab this tile's element (e.g. to fullscreen the host).
  onContainerRef?: (el: HTMLDivElement | null) => void;
  // Native fullscreen only renders descendants of the fullscreen element, so
  // Q&A controls must live inside the host tile to remain available.
  fullscreenControls?: ReactNode;
  isMe?: boolean;
  cameraOn?: boolean;
  onToggleCamera?: () => void;
  /** Local playback mute; does not affect anyone else in the room. */
  audioMuted?: boolean;
  onToggleAudio?: () => void;
  /** Fill the grid cell vertically (used by the maximized solo layout). */
  fill?: boolean;
  /** Private readiness details; only set for a verified room moderator/admin. */
  showAdminProfile?: boolean;
  /** Face count from on-device presence probe; -1 = not probed, 0 = absent, >0 = present. Only set for isMe tile. */
  presenceFaceCount?: number;
  /** False when a person teaches this class, so the host tile must never show Theodore. */
  aiHost?: boolean;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const isHost = p.role === "host";

  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    if (liveKitTrack) {
      el.srcObject = new MediaStream([liveKitTrack]);
    } else if (localStream) {
      el.srcObject = localStream;
    } else {
      return;
    }
    // autoPlay only fires when the element first mounts; explicitly call play()
    // so video resumes whenever srcObject is swapped (e.g. camera toggle).
    void el.play().catch(() => undefined);
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
        borderRadius: large ? 20 : 14,
        overflow: "hidden",
        // Calm studio backdrop (Design A): a deep plum "stage" with a soft accent
        // glow instead of a loud full-saturation blue→teal billboard, so the
        // presenter reads as a professional broadcast studio on the warm page.
        background: isHost
          ? "radial-gradient(130% 105% at 50% -12%, color-mix(in srgb, var(--accent) 32%, #2a2040) 0%, #1b1528 66%)"
          : "color-mix(in srgb, var(--accent) 6%, var(--panel))",
        border: hasFloor
          ? "2px solid var(--accent-2)"
          : p.hand_raised
            ? "2px solid #d99a1c"
            : isHost
              ? "1px solid color-mix(in srgb, #ffffff 12%, transparent)"
              : "1px solid var(--border)",
        boxShadow: isHost && large ? "0 18px 48px rgba(27, 21, 40, 0.28)" : undefined,
        minHeight: fill ? "100%" : large ? 220 : 110,
        height: fill ? "100%" : undefined,
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
            ...(isMe && { transform: "scaleX(-1)" }),
          }}
        />
      ) : isHost && slide ? (
        // The AI instructor has no camera — its "video feed" IS the current slide.
        // Design A: a Theodore presence (AI-teacher avatar, not a stock human) next
        // to a bright white slide card, framed by the plum studio backdrop.
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            gap: fullscreen ? 0 : large ? 16 : 10,
            padding: fullscreen ? "clamp(20px, 5vw, 72px)" : large ? 16 : 10,
            overflow: "hidden",
          }}
        >
          {!fullscreen && large ? (
            <div
              style={{
                flex: "0 0 32%",
                minWidth: 0,
                borderRadius: 18,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 10,
                background: "radial-gradient(120% 90% at 50% 0%, color-mix(in srgb, var(--accent-2) 34%, transparent), transparent)",
              }}
            >
              <div
                style={{
                  width: 104,
                  height: 104,
                  borderRadius: 999,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 50,
                  background: "radial-gradient(120% 120% at 50% 20%, color-mix(in srgb, var(--accent-2) 42%, #241b34) 0%, #241b34 100%)",
                  border: "1px solid rgba(255,255,255,0.22)",
                  boxShadow: "0 14px 34px rgba(0,0,0,0.38)",
                }}
              >
                {aiHost ? "🎓" : (p.name || "?").trim().charAt(0).toUpperCase()}
              </div>
              <div style={{ color: "#fff", fontWeight: 700, fontSize: 16 }}>
                {aiHost ? "Theodore" : p.name}
              </div>
              <div style={{ color: "rgba(255,255,255,0.72)", fontSize: 12 }}>
                {aiHost ? "AI teacher" : "Instructor · camera off"}
              </div>
            </div>
          ) : null}
          <div
            style={{
              flex: 1,
              minWidth: 0,
              borderRadius: fullscreen ? 24 : 18,
              background: "#fbf9f4",
              color: "#1b1528",
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              gap: fullscreen ? "clamp(16px, 2.6vh, 30px)" : 12,
              padding: fullscreen ? "clamp(28px, 6vw, 88px)" : large ? "30px 34px" : "16px 18px",
              overflowY: "auto",
              boxShadow: fullscreen ? "none" : "0 10px 30px rgba(0,0,0,0.22)",
            }}
          >
            <div
              style={{
                fontSize: fullscreen ? "clamp(11px, 1.4vw, 16px)" : 11,
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: 0.8,
                color: "#8a6d1f",
              }}
            >
              Slide {slide.index + 1}
            </div>
            <div
              style={{
                fontSize: fullscreen ? "clamp(32px, 7vw, 88px)" : large ? 30 : 20,
                fontWeight: 800,
                lineHeight: fullscreen ? 1.08 : 1.18,
                textWrap: "balance",
              }}
            >
              {slide.title}
            </div>
            <div
              aria-hidden
              style={{
                width: 54,
                height: 4,
                borderRadius: 999,
                background: STUDIO_GOLD,
              }}
            />
            <div
              style={{
                fontSize: fullscreen ? "clamp(19px, 3.4vw, 42px)" : large ? 15 : 13,
                lineHeight: fullscreen ? 1.4 : 1.55,
                color: "#443b52",
                overflow: fullscreen ? "visible" : "hidden",
                maxWidth: fullscreen ? "30em" : undefined,
              }}
            >
              {slide.narration || slide.body}
            </div>
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
      {isMe && cameraOn && hasVideo ? (() => {
        const detected = presenceFaceCount !== undefined && presenceFaceCount > 0;
        const notYetProbed = presenceFaceCount === undefined || presenceFaceCount === -1;
        const color = notYetProbed ? "rgba(255,255,255,0.25)" : detected ? "#22c55e" : "#f59e0b";
        const pulseStyle = !detected && !notYetProbed ? {
          animation: "presence-pulse 1.5s ease-in-out infinite",
        } : {};
        return (
          <div
            aria-hidden
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              pointerEvents: "none",
              zIndex: 5,
            }}
          >
            <svg
              viewBox="0 0 60 90"
              width={large ? 72 : 48}
              height={large ? 108 : 72}
              fill="none"
              style={{ opacity: detected ? 0.35 : 0.75, ...pulseStyle, transition: "opacity 0.4s" }}
            >
              <circle cx="30" cy="20" r="13" stroke={color} strokeWidth="2.5" />
              <path
                d="M6 78 C6 56 15 46 30 46 C45 46 54 56 54 78"
                stroke={color}
                strokeWidth="2.5"
                strokeLinecap="round"
              />
            </svg>
            {!detected && !notYetProbed ? (
              <div style={{
                marginTop: 4,
                fontSize: 10,
                fontWeight: 700,
                color: "#f59e0b",
                background: "rgba(0,0,0,0.6)",
                borderRadius: 6,
                padding: "2px 8px",
                letterSpacing: 0.3,
              }}>
                Keep your face in view 👁
              </div>
            ) : null}
          </div>
        );
      })() : null}
      {onToggleAudio ? (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onToggleAudio(); }}
          title={audioMuted ? `Hear ${p.name} on this device` : `Mute ${p.name} on this device`}
          aria-label={audioMuted ? `Unmute ${p.name} locally` : `Mute ${p.name} locally`}
          style={{
            position: "absolute",
            zIndex: 18,
            top: 10,
            right: fullscreen ? 88 : 10,
            width: 36,
            height: 36,
            borderRadius: 999,
            background: audioMuted ? "rgba(239,68,68,0.92)" : "rgba(0,0,0,0.58)",
            color: "#fff",
            border: "1px solid rgba(255,255,255,.45)",
            cursor: "pointer",
            fontSize: 16,
            boxShadow: "0 4px 12px rgba(0,0,0,.28)",
          }}
        >
          {audioMuted ? "🔇" : "🔊"}
        </button>
      ) : null}
      {fullscreen && fullscreenControls ? fullscreenControls : null}
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
        <span style={{ display: "grid", gap: 1, minWidth: 0 }}>
          <span style={{ fontWeight: 600 }}>
            {isHost ? "Host · " : ""}
            {p.name}
          </span>
          {showAdminProfile && !isHost ? (
            <span
              title="Private learner profile — visible only to administrators"
              style={{ color: "#d8b4fe", fontSize: 10, fontWeight: 600 }}
            >
              {p.student_id
                ? `Readiness ${Math.round(Number(p.readiness_score ?? 0))}/100 · ${p.readiness_band || "unrated"} · ${p.primary_style || "mixed"}`
                : "Profile score not completed"}
            </span>
          ) : null}
        </span>
        <span style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {hasFloor && <span title="Speaking now">🎤</span>}
          {p.hand_raised && !hasFloor && <span title="In Q&A queue">✋</span>}
          {(p.muted || p.muted_by_host) && <span title="Muted">🔇</span>}
          {isMe ? (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onToggleCamera?.(); }}
              title={cameraOn && hasVideo ? "Turn camera off" : "Turn camera on"}
              aria-label={cameraOn && hasVideo ? "Turn camera off" : "Turn camera on"}
              style={{
                background: cameraOn && hasVideo ? "rgba(16,185,129,0.85)" : "rgba(239,68,68,0.85)",
                color: "#fff", border: "none",
                borderRadius: 6, cursor: "pointer", fontSize: 12, lineHeight: 1,
                padding: "3px 7px", fontWeight: 700,
              }}
            >
              {cameraOn && hasVideo ? "📹" : "📷"}
            </button>
          ) : null}
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
  // Benign, informational messages (e.g. "no hands are up", "you're #2 in the
  // queue"). Kept separate from `error` so normal states never render as a red
  // "something broke" banner — a common source of the page looking broken.
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  // Auto-dismiss transient banners so they behave like toasts instead of
  // sticking around and cluttering the stage.
  useEffect(() => {
    if (!error) return;
    const t = setTimeout(() => setError(""), 6000);
    return () => clearTimeout(t);
  }, [error]);
  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(""), 4000);
    return () => clearTimeout(t);
  }, [notice]);
  const [chatDraft, setChatDraft] = useState("");
  const [askDraft, setAskDraft] = useState("");
  // The "Ask Theodore" tab keeps its own persistent Q&A thread so a learner's
  // questions and Theodore's answers stay in that tab instead of only living in
  // the shared class chat. (The backend still mirrors Q&A into room.chat; we
  // filter this learner's own Q&A back out of the Chat tab via askMineRef.)
  const [askThread, setAskThread] = useState<
    { id: string; question: string; answer: string; done: boolean; queued?: boolean }[]
  >([]);
  const askMineRef = useRef<Set<string>>(new Set());
  const askEndRef = useRef<HTMLDivElement>(null);
  const [localStream, setLocalStream] = useState<MediaStream | null>(null);
  const [cameraOn, setCameraOn] = useState(true);
  const [cameraNote, setCameraNote] = useState("");
  const [insecureOrigin, setInsecureOrigin] = useState(false);
  // Pre-class gate: dark/blurry rooms cannot enter solo or group live class.
  const [lightingReady, setLightingReady] = useState(false);
  const [qualityVerdict, setQualityVerdict] = useState<LightingVerdict | null>(null);
  const [qualitySecondsLeft, setQualitySecondsLeft] = useState<number | null>(null);
  const qualityStateRef = useRef<SustainedQualityState>({
    badSinceMs: null,
    countdownStartedMs: null,
    lastVerdict: null,
  });
  const qualityDisconnectedRef = useRef(false);
  const [moderatorKey, setModeratorKey] = useState("");
  const [isPlatformAdmin, setIsPlatformAdmin] = useState(false);
  // Can this viewer moderate the room? The room's first-joiner admin (has the
  // moderator key) OR the platform admin (admin@salareen.com), who moderates any
  // room via their Bearer token — the moderator endpoints accept either.
  const canModerate = Boolean(moderatorKey) || isPlatformAdmin;
  const xrRollout = useFlag<number | boolean>("access.xr_immersive_class", 0);
  const xrEnabled = xrRollout === true || (typeof xrRollout === "number" && Number(xrRollout) > 0);
  const [wasRemoved, setWasRemoved] = useState(false);
  const [giftBalance, setGiftBalance] = useState(0);
  const [giftCatalog, setGiftCatalog] = useState<LiveGiftCatalogItem[]>([]);
  const [showGifts, setShowGifts] = useState(false);
  const [giftRecipientId, setGiftRecipientId] = useState("");
  const [showGame, setShowGame] = useState(false);
  const [gameType, setGameType] = useState<LiveGroupGame["type"]>("quiz_race");
  const [gamePrompt, setGamePrompt] = useState("What does AI stand for?");
  const [gameAnswer, setGameAnswer] = useState("artificial intelligence");
  const [gameResponse, setGameResponse] = useState("");
  const [learnerCtx, setLearnerCtx] = useState<LearnerJoinContext | null>(null);
  // Which side-panel tab is active: the class chat, or asking Theodore directly.
  const [panelTab, setPanelTab] = useState<"chat" | "ask">("chat");
  // Selected learner in the participant strip (moderator quick-actions target).
  const [selectedParticipant, setSelectedParticipant] = useState("");
  // Whiteboard: when a student is called on (holds the floor) they can draw to
  // demonstrate; everyone else watches. Toggled on by the instructor. NOTE:
  // whiteboardOn / whiteboardStrokes are currently client-local — the real-time
  // broadcast is a small backend addition (see docs/whiteboard-backend-spec.txt).
  const [whiteboardOn, setWhiteboardOn] = useState(false);
  const [whiteboardStrokes, setWhiteboardStrokes] = useState<WhiteboardStroke[]>([]);
  // Lets the instructor preview the read-only "watch" view a student sees.
  const [previewAsStudent, setPreviewAsStudent] = useState(false);
  const [screenSharing, setScreenSharing] = useState(false);
  // Design A shows everyone via the participant strip; "focus instructor" mode
  // is retired, so this stays false (kept as a const for the layout branches).
  const focusInstructor = false;
  // Per-device playback mute. Unlike the old room-wide mute endpoint, this
  // only changes what the current viewer hears.
  const [locallyMutedIds, setLocallyMutedIds] = useState<Set<string>>(() => new Set());
  const [followingHost, setFollowingHost] = useState(false);
  const [followerCount, setFollowerCount] = useState(0);
  // Chrome blocks LiveKit's AudioContext until a user gesture. Manual join unlocks
  // in the click handler; auto-joined signed-in users must tap once to connect A/V.
  const [liveKitConnectEnabled, setLiveKitConnectEnabled] = useState(false);
  // Fullscreen the host presenter (the slide fills the screen). Tracks the
  // native fullscreen state so the toggle label/icon stays in sync (Esc exits).
  const hostTileRef = useRef<HTMLDivElement | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  // AI teacher audio: Theodore narrates each slide out loud (neural TTS with an
  // on-device fallback) while presenting. On by default; a toggle lets you mute.
  const [aiAudioOn, setAiAudioOn] = useState(true);
  // Browsers often block TTS until a gesture. After Start / Enable audio we mark
  // unlocked so the slide effect can narrate; otherwise show a "Tap to hear" CTA.
  const [aiAudioUnlocked, setAiAudioUnlocked] = useState(false);
  const spokenSlideRef = useRef<number | null>(null);
  const welcomeSpokenRef = useRef("");
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
  // Confirmation loop: after Theodore answers, keep the mic open so the learner
  // can confirm ("yes") or ask a follow-up before the floor is released.
  const [awaitingConfirmation, setAwaitingConfirmation] = useState(false);
  const confirmationTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Separate timer for narration-context cleanup — must NOT cancel the floor-release confirmationTimer
  const narrationContextTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pauseSubmitterRef = useRef<ReturnType<typeof createVoicePauseSubmitter> | null>(null);
  const triggerPauseSubmitRef = useRef<((spoken: string) => void) | null>(null);
  const doneSpeakingRef = useRef<() => void>(() => {});
  const pauseSubmitMs = useVoicePauseSubmitMs();
  // Guard so the floor-granted cue is spoken only once per floor grant, not on
  // every dep change (narrationLocale, startListening, etc.) while holding it.
  const floorCueSpokenRef = useRef(false);
  // Pause state for solo classes — the class keeps the session alive but stops
  // narration and auto-advance until the learner resumes.
  const [paused, setPaused] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const viewerSetterRef = useRef<(n: number) => void>(() => {});
  const presenceProbeVideoRef = useRef<HTMLVideoElement | null>(null);
  const presenceEngineRef = useRef<VisionEngine | null>(null);
  const screenShareStreamRef = useRef<MediaStream | null>(null);
  // Ref kept in sync with localStream state so the unmount cleanup can stop
  // camera tracks without capturing a stale closure value.
  const localStreamRef = useRef<MediaStream | null>(null);
  const pipVideoRef = useRef<HTMLVideoElement>(null);
  const presenceProbeBusyRef = useRef(false);
  const [presenceFaceCount, setPresenceFaceCount] = useState<number>(-1);

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
    setRoom((previous) => {
      // WebSocket and ordinary action responses are intentionally public. Once
      // an authorized GET/tick supplied private profile scores, retain them
      // across those public snapshots without ever exposing them to learners.
      const previousById = new Map(
        (previous?.participants ?? []).map((p) => [p.id, p]),
      );
      const merged: LiveRoomState = {
        ...next,
        participants: next.participants.map((participant) => {
          const old = previousById.get(participant.id);
          if (participant.readiness_score !== undefined || !old) return participant;
          return {
            ...participant,
            student_id: old.student_id,
            readiness_score: old.readiness_score,
            readiness_band: old.readiness_band ?? participant.readiness_band,
            primary_style: old.primary_style,
          };
        }),
      };
      const sig = JSON.stringify(merged);
      if (sig === lastRoomSigRef.current) return previous;
      lastRoomSigRef.current = sig;
      return merged;
    });
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

  const { tiles: liveKitTiles, audioTracks, connectFailed: liveKitFailed, needsAudioUnlock, unlockPlayback, setCameraEnabled: setLiveKitCamera } =
    useLiveKitRoom(
      liveMedia ?? joinInfo?.media,
      room?.participants ?? joinInfo?.room.participants ?? [],
      Boolean(hasFloor && me?.can_publish),
      liveKitConnectEnabled,
    );

  const trackFor = useCallback(
    (participantId: string) =>
      liveKitTiles.find((t) => t.participantId === participantId)?.track ?? null,
    [liveKitTiles],
  );

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
    if (typeof window === "undefined") return;
    if (!window.isSecureContext) {
      setInsecureOrigin(true);
      setCameraNote(
        "Camera needs https://salareen.com (or localhost) — Chrome blocks the webcam on plain http:// IP links like this page.",
      );
      setCameraOn(false);
    }
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [room?.chat.length]);

  useEffect(() => {
    askEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [askThread]);

  async function enableCamera() {
    setCameraNote("");
    if (typeof window !== "undefined" && !window.isSecureContext) {
      setCameraNote(
        "Camera needs https://salareen.com (or localhost) — Chrome blocks the webcam on plain http:// IP links like this page.",
      );
      setCameraOn(false);
      return false;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraNote("This browser can't access the camera.");
      setCameraOn(false);
      return false;
    }
    try {
      // Video-first for self-view; audio is optional (mic is gated by floor anyway).
      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      } catch {
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      }
      setLocalStream((prev) => {
        prev?.getTracks().forEach((t) => t.stop());
        return stream;
      });
      setCameraOn(true);
      void setLiveKitCamera?.(true);
      return true;
    } catch {
      setCameraNote(
        "Camera access blocked — allow the camera (address-bar lock/camera icon), then tap 📹 Camera.",
      );
      setCameraOn(false);
      return false;
    }
  }

  async function stopCamera() {
    // Disable LiveKit camera track before stopping the raw MediaStream so the SDK
    // doesn't try to access tracks we've already torn down.
    await setLiveKitCamera?.(false).catch(() => undefined);
    localStream?.getTracks().forEach((t) => t.stop());
    setLocalStream(null);
    setCameraOn(false);
  }

  async function toggleCamera() {
    const hasPreview = Boolean(localStream) || liveKitTiles.some((t) => t.isLocal);
    if (cameraOn && hasPreview) {
      await stopCamera();
      return;
    }
    await enableCamera();
  }

  async function handleScreenShare() {
    if (screenSharing) {
      screenShareStreamRef.current?.getTracks().forEach((t) => t.stop());
      screenShareStreamRef.current = null;
      setScreenSharing(false);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
      screenShareStreamRef.current = stream;
      setScreenSharing(true);
      stream.getTracks()[0]?.addEventListener("ended", () => {
        screenShareStreamRef.current = null;
        setScreenSharing(false);
      });
    } catch { /* user cancelled the picker */ }
  }

  useEffect(() => {
    const el = presenceProbeVideoRef.current;
    if (!el) return;
    if (!localStream) {
      try { el.pause(); } catch {}
      el.srcObject = null;
      return;
    }
    el.srcObject = localStream;
    el.muted = true;
    el.playsInline = true;
    void el.play().catch(() => undefined);
  }, [localStream]);

  // Attach localStream to the PiP video element (shown when host is presenting slides).
  useEffect(() => {
    const el = pipVideoRef.current;
    if (!el) return;
    if (!localStream) {
      el.srcObject = null;
      return;
    }
    el.srcObject = localStream;
    void el.play().catch(() => undefined);
  }, [localStream]);

  useEffect(() => {
    const participantId = joinInfo?.participant?.id || "";
    const presenceEnabled = Boolean(room?.presence_policy?.enabled);
    const maxFacesAllowed = Math.max(1, Number(room?.presence_policy?.max_faces_allowed || 1));
    const requireLiveness = room?.presence_policy?.require_liveness ?? true;
    const enabled = Boolean(
      participantId &&
      room?.status === "live" &&
      room?.presenting &&
      presenceEnabled &&
      cameraOn &&
      localStream
    );
    if (!enabled) {
      setPresenceFaceCount(-1);
      return;
    }
    let cancelled = false;
    const run = async () => {
      if (cancelled || presenceProbeBusyRef.current) return;
      const source = presenceProbeVideoRef.current;
      if (!source || source.readyState < 2) return;
      presenceProbeBusyRef.current = true;
      try {
        if (!presenceEngineRef.current) {
          presenceEngineRef.current = await createVisionEngine();
        }
        const faces = presenceEngineRef.current.detectAndEmbed(source);
        setPresenceFaceCount(faces.length);
        let present = faces.length > 0;
        let livenessState: "live" | "unknown" | "spoof" | "absent" = present ? "unknown" : "absent";
        let livenessScore = 0;
        let reason = present ? "face_detected" : "no_face";
        if (present) {
          if (faces.length > maxFacesAllowed) {
            livenessState = "spoof";
            reason = "too_many_faces";
          } else {
            const analysis = await identifyEmbedding(faces.slice(0, 1), []);
            const first = analysis.faces?.[0];
            const attention = Number(first?.attention || 0);
            const frontal = Number(first?.gaze_frontal || 0);
            livenessScore = Math.max(0, Math.min(1, attention * 0.55 + frontal * 0.45));
            if (requireLiveness && livenessScore < 0.35) {
              livenessState = "unknown";
              reason = "liveness_low";
            } else {
              livenessState = "live";
              reason = "verified";
            }
          }
        }
        const res = await reportLiveRoomPresence(roomId, {
          participantId,
          present,
          faceCount: faces.length,
          livenessState,
          livenessScore,
          reason,
          source: "web-on-device",
        });
        applyRoom(res.room);
      } catch {
        /* best effort; tick keeps room alive */
      } finally {
        presenceProbeBusyRef.current = false;
      }
    };
    void run();
    const timer = setInterval(() => { void run(); }, 5000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [
    applyRoom,
    cameraOn,
    joinInfo?.participant?.id,
    localStream,
    room?.presence_policy?.enabled,
    room?.presence_policy?.max_faces_allowed,
    room?.presence_policy?.require_liveness,
    room?.presenting,
    room?.status,
    roomId,
  ]);

  useEffect(() => () => {
    try {
      presenceEngineRef.current?.dispose();
    } catch {
      /* best effort */
    }
    presenceEngineRef.current = null;
  }, []);

  // Keep the ref in sync with localStream state so unmount cleanup sees the
  // current stream even after React has torn down closure scope.
  useEffect(() => { localStreamRef.current = localStream; }, [localStream]);

  // Stop camera tracks on unmount to release the camera indicator light.
  // Also stop any active screen share stream.
  useEffect(() => () => {
    localStreamRef.current?.getTracks().forEach((t) => t.stop());
    screenShareStreamRef.current?.getTracks().forEach((t) => t.stop());
    screenShareStreamRef.current = null;
  }, []);

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
      const profile = getToken() ? await fetchLearnerJoinContext() : null;
      if (profile) setLearnerCtx(profile);
      const classId = roomId.startsWith("class-") ? roomId.slice("class-".length) : "";
      const attendeeCode = (
        sessionStorage.getItem(`${ATTENDEE_CODE_KEY}:${roomId}`)
        || (classId ? sessionStorage.getItem(`${ATTENDEE_CODE_KEY}:${classId}`) : "")
        || ""
      ).trim();
      const info = await joinLiveRoom(roomId, name, identity || fallbackIdentity, locale, profile ? {
        studentId: profile.studentId,
        readinessScore: profile.readinessScore,
        readinessBand: profile.readinessBand,
        primaryStyle: profile.primaryStyle,
        attendeeCode,
      } : { attendeeCode });
      setJoinInfo(info);
      setRoom(info.room);
      // The admin (first joiner) receives the moderator key so their client can
      // start the class and advance slides.
      if (info.is_admin && info.moderator_key) {
        setModeratorKey(info.moderator_key);
        sessionStorage.setItem(`${MODERATOR_STORAGE_KEY}:${roomId}`, info.moderator_key);
      }
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
    if (!lightingReady) return;
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
  }, [roomId, joinInfo, lightingReady]);

  async function enableLiveKitAv() {
    unlockWebAudio();
    await resumeSharedAudioContext();
    setLiveKitConnectEnabled(true);
    setAiAudioUnlocked(true);
    if (cameraOn) void enableCamera();
  }

  // The class hit the end of its allotted time. After the farewell countdown,
  // excuse the learner: leave the room (best-effort) and return to the class list.
  const excuseFromClass = useCallback(() => {
    leftVoluntarily.current = true;
    cancelSpeech();
    setAiAudioOn(false);
    const pid = joinInfo?.participant.id;
    localStream?.getTracks().forEach((t) => t.stop());
    sessionStorage.removeItem(`${ROOM_STORAGE_KEY}:${roomId}`);
    const go = () => { window.location.href = soloExitHref(roomId, roomRef.current); };
    if (pid) {
      void leaveLiveRoom(roomId, pid).then(go).catch(go);
    } else {
      go();
    }
  }, [joinInfo, roomId, localStream]);

  // Mid-class lighting/blur gate: recognition needs a usable frame. Sustained
  // dark or blurry video shows a friendly fix message, then a 10s disconnect.
  useEffect(() => {
    if (!lightingReady || !cameraOn || !localStream || qualityDisconnectedRef.current) {
      qualityStateRef.current = {
        badSinceMs: null,
        countdownStartedMs: null,
        lastVerdict: null,
      };
      setQualityVerdict(null);
      setQualitySecondsLeft(null);
      return;
    }
    let cancelled = false;
    const canvas = document.createElement("canvas");
    const tick = () => {
      if (cancelled || qualityDisconnectedRef.current) return;
      const source = presenceProbeVideoRef.current;
      if (!source || source.readyState < 2 || !source.videoWidth) return;
      const w = 64;
      const h = 36;
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      if (!ctx) return;
      try {
        ctx.drawImage(source, 0, 0, w, h);
        const { data } = ctx.getImageData(0, 0, w, h);
        const grid = luminanceGridFromImageData(data, w, h, w, h);
        const metrics = analyzeLuminanceGrid(grid, DEFAULT_LIGHTING_THRESHOLDS);
        const mid = grid.slice(8, 28).flatMap((row) => row.slice(16, 48));
        const mean = mid.reduce((a, b) => a + b, 0) / Math.max(1, mid.length);
        const varSum =
          mid.reduce((a, b) => a + (b - mean) ** 2, 0) / Math.max(1, mid.length);
        const facePresent = varSum > 0.004 && mean > 0.08 && mean < 0.92;
        const readiness = verdictFromMetrics(metrics, {
          facePresent,
          nightVision: false,
          thresholds: DEFAULT_LIGHTING_THRESHOLDS,
        });
        const next = tickSustainedQuality(
          qualityStateRef.current,
          readiness,
          Date.now(),
        );
        qualityStateRef.current = {
          badSinceMs: next.badSinceMs,
          countdownStartedMs: next.countdownStartedMs,
          lastVerdict: next.lastVerdict,
        };
        if (next.countdownStartedMs != null) {
          setQualityVerdict(next.lastVerdict);
          setQualitySecondsLeft(next.secondsLeft);
          if (next.shouldDisconnect) {
            qualityDisconnectedRef.current = true;
            excuseFromClass();
          }
        } else {
          setQualityVerdict(null);
          setQualitySecondsLeft(null);
        }
      } catch {
        /* sample failures are non-fatal; next tick retries */
      }
    };
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [cameraOn, excuseFromClass, lightingReady, localStream]);

  async function handleLeave() {
    if (!me) return;
    leftVoluntarily.current = true;
    cancelSpeech();
    setAiAudioOn(false);
    setBusy(true);
    try {
      // For solo classes, leaving = ending: close the session so it doesn't linger.
      if (isSolo && canModerate) {
        await liveRoomEnd(roomId, moderatorKey);
      } else {
        await leaveLiveRoom(roomId, me.id);
      }
      window.location.href = soloExitHref(roomId, room);
    } catch (e) {
      setError(friendlyError(e, "Could not leave"));
    } finally {
      sessionStorage.removeItem(`${ROOM_STORAGE_KEY}:${roomId}`);
      localStream?.getTracks().forEach((t) => t.stop());
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

  async function sendGift(gift: LiveGiftCatalogItem) {
    if (!me) return;
    setBusy(true);
    try {
      const res = await liveRoomSendGift(
        roomId,
        me.id,
        gift.id,
        giftRecipientId,
      );
      applyRoom(res.room);
      setGiftBalance(res.sender_balance);
      setShowGifts(false);
    } catch (e) {
      setError(friendlyError(e, "Gift failed"));
    } finally {
      setBusy(false);
    }
  }

  async function startGroupGame() {
    if (!canModerate || !gamePrompt.trim() || !gameAnswer.trim()) return;
    setBusy(true);
    try {
      const res = await liveRoomStartGame(
        roomId, moderatorKey, gameType, gamePrompt.trim(), gameAnswer.trim(), 25,
      );
      applyRoom(res.room);
      setShowGame(true);
      setGameResponse("");
    } catch (e) {
      setError(friendlyError(e, "Could not start group game"));
    } finally {
      setBusy(false);
    }
  }

  async function playGroupGame(cell = -1) {
    if (!me || !room?.group_game) return;
    setBusy(true);
    try {
      const game = room.group_game;
      const action = game.type === "hangman"
        ? { letter: gameResponse.trim().slice(0, 1) }
        : { answer: gameResponse.trim(), cell };
      const res = await liveRoomPlayGame(roomId, me.id, action);
      applyRoom(res.room);
      setGameResponse("");
      // A win is not an error — the red role="alert" box scared learners.
      if (res.event.points) setNotice(`Correct! You earned ${res.event.points} points.`);
    } catch (e) {
      setError(friendlyError(e, "Game action failed"));
    } finally {
      setBusy(false);
    }
  }

  async function askQuestion() {
    if (!me || !askDraft.trim()) return;
    const q = askDraft.trim();
    const entryId = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    setBusy(true);
    // Show the question immediately in the Ask Theodore thread and remember it so
    // its mirror copy in room.chat is hidden from the Chat tab.
    setAskThread((prev) => [...prev, { id: entryId, question: q, answer: "", done: false }]);
    askMineRef.current.add(q);
    setAskDraft("");
    try {
      // Stream Theodore's answer (SSE) so the reply appears/plays live; other
      // participants receive it over the room WebSocket (host_delta frames).
      const res = await liveRoomAskStream(roomId, me.id, q, {
        language: locale,
        onDelta: (chunk) =>
          setAskThread((prev) =>
            prev.map((e) => (e.id === entryId ? { ...e, answer: e.answer + chunk } : e)),
          ),
      });
      if (res.queued) {
        if (res.room) setRoom(res.room);
        setAskThread((prev) =>
          prev.map((e) =>
            e.id === entryId
              ? { ...e, done: true, queued: true, answer: e.answer || `${hostLabel} will call on you in turn.` }
              : e,
          ),
        );
        setNotice(`You're #${res.queue_position ?? myQueuePos} in the Q&A queue. ${hostLabel} will call on you in turn.`);
      } else {
        const finalText = res.text || res.host_message?.text || "";
        // Record the mirrored chat copies BEFORE applying the room so Theodore's
        // reply ("@Name answer") is filtered out of the Chat tab on the very
        // first render — it lives only in the Ask Theodore thread.
        if (res.host_message?.text) askMineRef.current.add(res.host_message.text);
        if (me?.name && finalText) askMineRef.current.add(`@${me.name} ${finalText}`);
        if (res.room) setRoom(res.room);
        setAskThread((prev) =>
          prev.map((e) => (e.id === entryId ? { ...e, done: true, answer: finalText || e.answer } : e)),
        );
        setNotice("");
      }
      setError("");
    } catch (e) {
      setError(friendlyError(e, "Question failed"));
      setAskThread((prev) =>
        prev.map((e) =>
          e.id === entryId ? { ...e, done: true, answer: e.answer || `Couldn't reach ${hostLabel} — try again.` } : e,
        ),
      );
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
      setNotice("");
    } catch (e) {
      // An empty Q&A queue is a normal state, not an error — calling "next" when
      // no hands are up should read as a calm note, never a red alert banner.
      const msg = friendlyError(e, "Could not call next");
      if (/queue is empty|no one|empty/i.test(msg)) {
        setNotice("No hands are up right now.");
      } else {
        setError(msg);
      }
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
    pauseSubmitterRef.current?.cancelPending();
    pauseSubmitterRef.current = null;
    triggerPauseSubmitRef.current = null;
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
    pauseSubmitterRef.current?.cancelPending();
    const submitter = createVoicePauseSubmitter(pauseSubmitMs, (text) => {
      spokenFinalRef.current = text;
      setSpokenText(text);
      if (triggerPauseSubmitRef.current) {
        const handler = triggerPauseSubmitRef.current;
        triggerPauseSubmitRef.current = null;
        handler(text);
        return;
      }
      void doneSpeakingRef.current();
    });
    pauseSubmitterRef.current = submitter;
    rec.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        const txt = r[0]?.transcript ?? "";
        if (r.isFinal) spokenFinalRef.current = `${spokenFinalRef.current} ${txt}`.trim();
        else interim += txt;
      }
      const combined = `${spokenFinalRef.current} ${interim}`.trim();
      setSpokenText(combined);
      submitter.updateTranscript(combined);
    };
    // Whether the session ended intentionally (stopListening) vs. by the browser.
    let intentionalStop = false;
    rec.onerror = (ev) => {
      const code = ev?.error || "";
      if (code === "not-allowed" || code === "service-not-allowed") {
        setMicNote("Microphone is blocked — allow it (address-bar icon) and use https://. You can type instead.");
        intentionalStop = true;
        stopListening();
      } else if (code === "audio-capture") {
        setMicNote("No microphone found — check your device, or type your question below.");
        intentionalStop = true;
        stopListening();
      } else if (code !== "no-speech" && code !== "aborted") {
        // network / service-unavailable / bad-grammar / language-not-supported:
        // non-transient — stop rather than loop.
        intentionalStop = true;
        stopListening();
      }
      // "no-speech"/"aborted" are transient — onend will auto-restart below.
    };
    rec.onend = () => {
      // If the browser killed the session due to a no-speech timeout or a
      // transient abort (not a real error), restart automatically so the user
      // stays in "listening" mode until they explicitly tap "Done speaking".
      if (!intentionalStop && recognitionRef.current === rec) {
        try {
          rec.start();
          return; // keep listening — don't flush or clear state
        } catch {
          // Can't restart (e.g. permission revoked mid-session). Fall through.
        }
      }
      submitter.flush();
      setListening(false);
      recognitionRef.current = null;
      pauseSubmitterRef.current = null;
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
  }, [narrationLocale, pauseSubmitMs, stopListening]);

  // Learner is done speaking: send whatever we heard (or typed) to Theodore as a
  // question — the server answers a floor-holder immediately and releases the
  // floor. With nothing captured, just hand the floor back.
  async function doneSpeaking() {
    if (!me) return;
    const spoken = (spokenFinalRef.current || spokenText || askDraft).trim();
    stopListening();
    if (confirmationTimerRef.current) {
      clearTimeout(confirmationTimerRef.current);
      confirmationTimerRef.current = null;
    }

    // If we're in the confirmation loop, check whether the learner said yes/no.
    if (awaitingConfirmation) {
      const affirm = /\b(yes|yeah|yep|yup|got it|thanks|thank you|that.?s right|perfect|great|sure|ok|okay|confirmed|correct)\b/i;
      if (!spoken || affirm.test(spoken)) {
        // Confirmed — release the floor and resume slides.
        // Clear awaitingConfirmation AFTER finish_turn so the hasFloor effect
        // doesn't replay the floor cue between now and when the floor releases.
        setBusy(true);
        try {
          const pid = room?.floor_participant_id || me.id;
          const updated = await liveRoomFinishTurn(roomId, pid, moderatorKey);
          setAwaitingConfirmation(false);
          setRoom(updated);
        } catch (e) {
          setAwaitingConfirmation(false);
          setError(friendlyError(e, "Couldn't release the floor"));
        } finally {
          setBusy(false);
        }
        return;
      }
      // Didn't confirm — treat what they said as a follow-up question.
      setAwaitingConfirmation(false);
    }

    setBusy(true);
    try {
      if (spoken) {
        const res = await liveRoomAskStream(roomId, me.id, spoken, { language: narrationLocale });
        if (res.room) setRoom(res.room);
        setAskDraft("");
        setSpokenText("");
        spokenFinalRef.current = "";
        setError("");
      } else {
        const pid = room?.floor_participant_id || me.id;
        setRoom(await liveRoomFinishTurn(roomId, pid, moderatorKey));
      }
    } catch (e) {
      setError(friendlyError(e, `Couldn't send your question to ${hostLabel}`));
    } finally {
      setBusy(false);
    }
  }
  doneSpeakingRef.current = () => { void doneSpeaking(); };

  const toggleLocalAudio = useCallback((participantId: string) => {
    setLocallyMutedIds((current) => {
      const next = new Set(current);
      if (next.has(participantId)) next.delete(participantId);
      else next.add(participantId);
      return next;
    });
  }, []);

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
    // Unlock audio INSIDE the click gesture — otherwise speakNaturally (which
    // runs after the await / in a useEffect) is blocked by autoplay policy and
    // "Start class" looks like it did nothing.
    unlockWebAudio();
    setAiAudioUnlocked(true);
    setAiAudioOn(true);
    setBusy(true);
    try {
      const next = await liveRoomStartPresentation(roomId, moderatorKey);
      setRoom(next);
      lastRoomSigRef.current = JSON.stringify(next);
      // Narrate the current slide immediately (don't wait for the effect).
      const s = next.slide;
      const text = `${s?.title ? s.title + ". " : ""}${(s?.body || s?.narration || "").trim()}`.trim();
      if (text && next.presenting && s) {
        spokenSlideRef.current = s.index;
        cancelSpeech();
        void buildNarrationSpeakOptions(narrationLocale).then((base) => {
          // Session may have ended while voice options were loading.
          if (leftVoluntarily.current || roomRef.current?.status === "ended") return;
          speakNaturally(text, {
            ...base,
            onend: () => {
              const r = roomRef.current;
              if (
                canModerate &&
                Boolean(r?.presenting) &&
                r?.status !== "ended" &&
                spokenSlideRef.current === s.index &&
                !r?.floor_participant_id &&
                !(r?.speaking_queue?.some((e) => e.status === "waiting"))
              ) {
                void liveRoomAdvance(roomId, moderatorKey).then((adv) => setRoom(adv)).catch(() => undefined);
              }
            },
          });
        });
      }
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
    const tick = () => {
      void liveRoomTick(roomId, joinInfo.participant.id, moderatorKey)
        .then((r) => applyRoom(r))
        .catch(() => undefined);
    };
    // Tick immediately on entry. Solo rooms are full with one learner, so the
    // server begins the class automatically as soon as its short AI-introduction
    // window has elapsed — no Start/Call-next button is required.
    tick();
    const t = window.setInterval(tick, 3000);  // also drives auto-advance + presence
    return () => window.clearInterval(t);
  }, [joinInfo, roomId, moderatorKey, applyRoom]);

  // Before the first slide, Theodore welcomes learners and explicitly identifies
  // himself as an AI host. Joining is a user gesture, so audio is already unlocked.
  useEffect(() => {
    if (!room) return;
    if (room.status === "ended") return;
    const welcome = room.welcome_message?.trim();
    if (!welcome || room.presenting || !aiAudioOn || !aiAudioUnlocked || canModerate) return;
    if (welcomeSpokenRef.current === room.room_id) return;
    welcomeSpokenRef.current = room.room_id;
    void buildNarrationSpeakOptions(narrationLocale).then((base) => {
      if (leftVoluntarily.current || roomRef.current?.status === "ended" || !aiAudioOn) return;
      cancelSpeech();
      speakNaturally(welcome, base);
    });
  }, [room, aiAudioOn, aiAudioUnlocked, narrationLocale, canModerate]);

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
    // Self-hosted class: the teacher presents the slides themselves — Theodore
    // must NOT read them aloud. Cancel any in-progress speech and stay silent.
    if (!aiAudioOn || !aiAudioUnlocked || !classLive || slideIdx == null || paused || canModerate) {
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
      // Detect interactive prompts embedded in the slide narration. When Theodore
      // says "Say it out loud", "Repeat after me", or "Your turn", pause the
      // auto-advance and open the learner's mic instead.
      const triggerPhrases = /\b(say it out loud|repeat after me|your turn|speak it back|say this out loud)\b/i;
      const hasTrigger = triggerPhrases.test(text);
      void buildNarrationSpeakOptions(narrationLocale).then((base) => {
        if (leftVoluntarily.current || roomRef.current?.status === "ended" || !classLive) return;
        speakNaturally(text, {
          ...base,
          onend: () => {
            if (hasTrigger && isSoloLiveRoom(roomId, roomRef.current)) {
              // Open the mic for the learner to speak the prompted phrase.
              triggerPauseSubmitRef.current = (spoken) => {
                stopListening();
                if (confirmationTimerRef.current) {
                  clearTimeout(confirmationTimerRef.current);
                  confirmationTimerRef.current = null;
                }
                if (spoken) {
                  void liveRoomAskStream(roomId, me?.id ?? "", spoken, { language: narrationLocale })
                    .then((res) => { if (res.room) setRoom(res.room); })
                    .catch(() => undefined);
                } else {
                  const r = roomRef.current;
                  if (canModerate && r?.presenting && r?.status !== "ended" && spokenSlideRef.current === spokenFor) {
                    void liveRoomAdvance(roomId, moderatorKey).then((next) => setRoom(next)).catch(() => undefined);
                  }
                }
              };
              void startListening();
              // Fallback if the learner never speaks — advance after 15 s.
              confirmationTimerRef.current = setTimeout(() => {
                confirmationTimerRef.current = null;
                const handler = triggerPauseSubmitRef.current;
                triggerPauseSubmitRef.current = null;
                if (handler) handler("");
                else stopListening();
              }, 15_000);
              return;
            }
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
      });
    }
    return () => {
      // Clear the narration-context timer only — NOT confirmationTimerRef which
      // is owned by the hostAnswer floor-release flow and must not be cancelled here.
      if (narrationContextTimerRef.current) {
        clearTimeout(narrationContextTimerRef.current);
        narrationContextTimerRef.current = null;
      }
    };
  }, [aiAudioOn, aiAudioUnlocked, classLive, slideIdx, slideTitle, slideNarration, slideBody, narrationLocale,
      canModerate, moderatorKey, roomId, paused, me?.id, startListening, stopListening]);

  // Theodore's streamed answer (from the room WebSocket host_delta frames):
  // speak it out loud once, when it finishes, for every participant (including
  // the asker). When awaiting_confirmation is set, the floor holder's mic is
  // kept open after speaking so they can say yes/no before the floor releases.
  const hostAnswer = socket.hostAnswer;
  const spokenAnswerIdRef = useRef(0);
  useEffect(() => {
    if (!hostAnswer || !hostAnswer.done || !hostAnswer.text) return;
    if (spokenAnswerIdRef.current === hostAnswer.id) return;
    spokenAnswerIdRef.current = hostAnswer.id;
    if (!aiAudioOn || !aiAudioUnlocked) return;
    if (roomRef.current?.status === "ended" || leftVoluntarily.current) return;
    const text = hostAnswer.text;
    const needsConfirmation = hostAnswer.awaitingConfirmation;
    // A chat reply (awaitingConfirmation=false) arriving while the floor holder
    // is in the confirmation loop must not speak over the prompt or reset the
    // confirmation timer. Skip TTS for the floor holder in that case.
    if (!needsConfirmation && confirmationTimerRef.current) return;
    const myId = me?.id;
    let alive = true;
    void buildNarrationSpeakOptions(narrationLocale).then((base) => {
      if (leftVoluntarily.current || roomRef.current?.status === "ended") return;
      cancelSpeech();
      speakNaturally(text, {
        ...base,
        onend: () => {
          if (!alive) return;
          // Re-read from the ref at onend time so a floor transfer during TTS
          // doesn't open the mic on the wrong client.
          const isFloorHolder = roomRef.current?.floor_participant_id === myId;
          if (!needsConfirmation || !isFloorHolder) return;
          // Floor holder: open mic for yes/no confirmation.
          setAwaitingConfirmation(true);
          void startListening();
          // Auto-release the floor after 15 s if no response.
          confirmationTimerRef.current = setTimeout(() => {
            confirmationTimerRef.current = null;
            stopListening();
            setAwaitingConfirmation(false);
            const pid = roomRef.current?.floor_participant_id || me?.id || "";
            if (pid) {
              liveRoomFinishTurn(roomId, pid, moderatorKey)
                .then((r) => setRoom(r))
                .catch(() => undefined);
            }
          }, 15_000);
        },
      });
    });
    return () => { alive = false; };
  }, [hostAnswer, aiAudioOn, aiAudioUnlocked, narrationLocale, me?.id,
      startListening, stopListening, roomId, moderatorKey]);

  // Session ended (Close / timer): mute AI and kill any in-flight narration so
  // the farewell overlay is silent.
  useEffect(() => {
    if (room?.status !== "ended") return;
    setAiAudioOn(false);
    cancelSpeech();
  }, [room?.status]);

  // Always stop narration when leaving the room.
  useEffect(() => () => { cancelSpeech(); stopListening(); }, [stopListening]);

  // When this learner is granted the floor (and not already in the confirmation
  // loop), Theodore speaks their name then opens the mic in the onend callback.
  // awaitingConfirmation is intentionally NOT in this dep array — the mic
  // is managed by a separate effect below so that a re-render triggered by
  // setAwaitingConfirmation(true) does not run this effect's cleanup
  // (stopListening) and kill the mic that onend just opened.
  useEffect(() => {
    if (hasFloor && !floorCueSpokenRef.current) {
      floorCueSpokenRef.current = true;
      const firstName = (me?.name || "").split(" ")[0] || "there";
      const cue = `${firstName}, please ask your question.`;
      cancelSpeech();
      void buildNarrationSpeakOptions(narrationLocale).then((base) => {
        if (!roomRef.current?.floor_participant_id) return;
        if (leftVoluntarily.current) return;
        speakNaturally(cue, { ...base, onend: () => { void startListening(); } });
      });
    } else if (!hasFloor) {
      floorCueSpokenRef.current = false;
      stopListening();
      setSpokenText("");
      spokenFinalRef.current = "";
      setMicNote("");
      setAwaitingConfirmation(false);
      if (confirmationTimerRef.current) {
        clearTimeout(confirmationTimerRef.current);
        confirmationTimerRef.current = null;
      }
    }
    // No cleanup stopListening() here — that would kill the mic opened by onend
    // whenever any dep changes (e.g. awaitingConfirmation flipping to true).
  }, [hasFloor, me?.name, narrationLocale, startListening, stopListening]);

  async function banLearner(participantId: string, name: string) {
    if (!canModerate) return;
    const reason = window.prompt(`Block ${name}? Optional reason:`);
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
    cancelSpeech();
    setAiAudioOn(false);
    setBusy(true);
    try {
      setRoom(await liveRoomEnd(roomId, moderatorKey));
    } catch (e) {
      setError(friendlyError(e, "Could not close session"));
    } finally {
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
        <button onClick={() => {
          cancelSpeech();
          window.location.href = soloExitHref(roomId, room);
        }}>
          {isSoloLiveRoom(roomId, room) ? "Back to class" : "Back to Group Classes"}
        </button>
      </main>
    );
  }

  if (!joinInfo) {
    return (
      <main className="container" style={{ maxWidth: 480 }}>
        <h1>Salareen Live Room</h1>
        <p className="muted">
          {room?.human_taught && isSoloLiveRoom(roomId, room)
            ? `Your private 1:1 session with ${room?.human_host_name || "your instructor"}. It starts when your instructor begins the class.`
            : isSoloLiveRoom(roomId, room)
            ? "Your private 1:1 session with Theodore. The class starts automatically once you enter."
            : room?.human_taught
              ? `Join ${room?.human_host_name || "your instructor"}'s live class — up to ${room?.room_size ?? 6} seats in the grid.`
              : `Join Theodore's multi-user class — up to ${room?.room_size ?? 6} seats in the grid.`}
        </p>
        {room && (
          <div className="card" style={{ marginBottom: 12 }}>
            <strong>{room.title}</strong>
            {!isSoloLiveRoom(roomId, room) ? (
              <div className="muted">
                {room.learner_count}/{room.learner_capacity} learners · {room.seats_left} seats left
              </div>
            ) : (
              <div className="muted">
                {room?.human_taught
                  ? `Just you and ${room?.human_host_name || "your instructor"} — camera and mic ready when you join.`
                  : "Just you and Theodore — camera and mic ready when you join."}
              </div>
            )}
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
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  unlockWebAudio();
                  setLiveKitConnectEnabled(true);
                  void handleJoin();
                }
              }}
            />
          </label>
          <button
            onClick={() => {
              unlockWebAudio();
              setLiveKitConnectEnabled(true);
              void handleJoin();
            }}
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
  // Am I the actual on-camera presenter? Only the room host presents; a mere
  // moderator/admin previewing a Theodore-led class is a participant, not the
  // presenter. (`learners` already excludes whoever is the host.)
  const iAmHost = Boolean(me?.id && host?.id === me?.id);
  // "Teach a class": a person presents, so Theodore is absent from the room
  // entirely and the instructor owns the main tile.
  const humanTaught = Boolean(room?.human_taught);
  const hostLabel = humanTaught ? (room?.human_host_name || host?.name || "Instructor") : "Theodore";
  const isSolo = isSoloLiveRoom(roomId, room);
  // In a group class the human teacher (the moderator) belongs in the main host
  // tile, not in the student strip. Filter them out so only actual students appear
  // in the participant row.
  // Students shown in the bottom "seat" row. A moderator/admin previewing the
  // class is excluded here — they see their own camera as the corner self-cam
  // PiP on the slide instead of taking a seat (matches the deployed layout).
  const studentLearners = canModerate ? learners.filter((p) => p.id !== me?.id) : learners;
  const emptySlots = Math.max(0, (room?.learner_capacity ?? 0) - learners.length);
  const toggleHostAudio = () => {
    if (!host) return;
    const hostId = host.id;
    // Derive currentlyMuted inside the functional updater so rapid double-taps
    // always see the real current set rather than the render-time snapshot.
    setLocallyMutedIds((current) => {
      const currentlyMuted = current.has(hostId) || !aiAudioOn;
      const next = new Set(current);
      if (currentlyMuted) {
        next.delete(hostId);
        // Unmute side-effects — schedule after state update settles.
        setTimeout(() => {
          unlockWebAudio();
          setAiAudioUnlocked(true);
          setAiAudioOn(true);
          spokenSlideRef.current = null;
        }, 0);
      } else {
        next.add(hostId);
        setTimeout(() => {
          setAiAudioOn(false);
          cancelSpeech();
        }, 0);
      }
      return next;
    });
  };
  const renderGamePanel = (fullscreen = false) => {
    if (!showGame) return null;
    const game = room?.group_game;
    return (
      <div style={{
        position: fullscreen ? "absolute" : "fixed",
        zIndex: fullscreen ? 24 : 65,
        left: "50%",
        top: fullscreen ? "48%" : "50%",
        transform: "translate(-50%, -50%)",
        width: "min(92vw, 620px)",
        maxHeight: "78vh",
        overflowY: "auto",
        padding: 18,
        borderRadius: 18,
        background: "rgba(10,18,32,.96)",
        border: "2px solid #7c3aed",
        boxShadow: "0 20px 60px rgba(0,0,0,.65)",
        color: "#fff",
      }}>
        <button
          type="button"
          onClick={() => setShowGame(false)}
          style={{ position: "absolute", right: 10, top: 8, background: "transparent", color: "#fff", border: 0, fontSize: 22 }}
        >×</button>
        {!game ? (
          canModerate ? (
            <div style={{ display: "grid", gap: 10 }}>
              <h2 style={{ margin: 0 }}>
                🎮 Start {isSolo ? "a solo learning game" : "a learning game"}
              </h2>
              <select value={gameType} onChange={(e) => setGameType(e.target.value as LiveGroupGame["type"])} style={{ padding: 10 }}>
                <option value="quiz_race">⚡ First answer race</option>
                <option value="tic_tac_toe">⭕ Learning tic-tac-toe</option>
                <option value="hangman">🔤 Learning hangman</option>
                <option value="multiple_choice">🔢 Multiple choice dash</option>
                <option value="true_false">✅ True or false</option>
                <option value="word_scramble">🔀 Word scramble</option>
                <option value="fill_blank">✍️ Fill the blank</option>
                <option value="emoji_decode">🧩 Emoji decode</option>
                <option value="lightning_round">🌩️ Lightning round</option>
                <option value="team_buzzer">🔔 Team buzzer</option>
                <option value="hot_seat">🔥 Hot seat</option>
                <option value="jeopardy">💎 Jeopardy challenge</option>
              </select>
              <input value={gamePrompt} onChange={(e) => setGamePrompt(e.target.value)} placeholder="Question or clue" style={{ padding: 10 }} />
              <input value={gameAnswer} onChange={(e) => setGameAnswer(e.target.value)} placeholder="Correct answer" style={{ padding: 10 }} />
              <button type="button" onClick={() => void startGroupGame()} disabled={busy} style={{ padding: 12, background: "#7c3aed", color: "#fff" }}>
                {isSolo ? "Start game" : "Start for everyone"} · 25 points
              </button>
            </div>
          ) : <p>Waiting for {hostLabel} or the class admin to start a game.</p>
        ) : (
          <div style={{ display: "grid", gap: 12, textAlign: "center" }}>
            <div style={{ fontSize: 13, color: "#c4b5fd", textTransform: "uppercase" }}>
              {game.type.replaceAll("_", " ")} · {game.points} points
            </div>
            <h2 style={{ margin: 0, fontSize: "clamp(22px,5vw,38px)" }}>{game.prompt}</h2>
            {game.type === "hangman" ? (
              <div style={{ fontSize: "clamp(26px,7vw,52px)", letterSpacing: 5 }}>{game.masked}</div>
            ) : null}
            {game.type === "word_scramble" ? (
              <div style={{ fontSize: "clamp(26px,7vw,52px)", letterSpacing: 5, color: "#fbbf24" }}>
                {game.scrambled}
              </div>
            ) : null}
            {game.type === "tic_tac_toe" ? (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 7, maxWidth: 310, margin: "0 auto", width: "100%" }}>
                {(game.board ?? Array(9).fill("")).map((mark, i) => (
                  <button key={i} type="button" disabled={Boolean(mark) || game.status !== "active" || busy} onClick={() => void playGroupGame(i)}
                    style={{ aspectRatio: "1", fontSize: 34, borderRadius: 10, background: "#1f2937", color: "#fff" }}>
                    {mark || "·"}
                  </button>
                ))}
              </div>
            ) : null}
            {game.status === "active" ? (
              <div style={{ display: "flex", gap: 8 }}>
                <input
                  value={gameResponse}
                  onChange={(e) => setGameResponse(e.target.value)}
                  placeholder={game.type === "hangman" ? "Guess one letter" : "Answer correctly to play"}
                  maxLength={game.type === "hangman" ? 1 : 200}
                  style={{ flex: 1, padding: 12, borderRadius: 9 }}
                  onKeyDown={(e) => e.key === "Enter" && game.type !== "tic_tac_toe" && void playGroupGame()}
                />
                {game.type !== "tic_tac_toe" ? (
                  <button type="button" onClick={() => void playGroupGame()} disabled={!gameResponse.trim() || busy}
                    style={{ padding: "10px 16px", background: "#059669", color: "#fff" }}>Play</button>
                ) : null}
              </div>
            ) : (
              <div style={{ fontSize: 24, fontWeight: 800 }}>
                {game.status === "won" ? `🏆 ${game.winner_name} wins!` : "Game complete"}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  // Underline tab style for the side panel (Chat / Ask Theodore) — Design A.
  const panelTabStyle = (active: boolean): CSSProperties => ({
    flex: 1,
    fontSize: 14,
    fontWeight: 700,
    padding: "8px 10px",
    cursor: "pointer",
    border: "none",
    borderBottom: active ? `2px solid ${STUDIO_GOLD}` : "2px solid transparent",
    marginBottom: -1,
    lineHeight: 1.2,
    background: "transparent",
    color: active ? "var(--text)" : "var(--muted)",
  });
  // Design A control-bar button styles: stacked square "device" buttons for
  // camera/mic/fullscreen, and bordered pills for the instructor/leave rail.
  const deviceBtnStyle: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: 3,
    width: 64,
    height: 56,
    borderRadius: 12,
    border: "1px solid var(--border)",
    background: "var(--panel)",
    color: "var(--text)",
    cursor: "pointer",
    fontSize: 11,
    fontWeight: 600,
  };
  const railBtnStyle: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "10px 14px",
    borderRadius: 12,
    border: "1px solid var(--border)",
    background: "var(--panel)",
    color: "var(--text)",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 600,
    whiteSpace: "nowrap",
    textDecoration: "none",
  };

  return (
    <main
      style={{
        minHeight: "100vh",
        // Design A "calm studio": a warm cream page with a faint gold wash rather
        // than a cool blue tint, so the room matches the mockup palette.
        background:
          "linear-gradient(180deg, var(--bg) 0%, color-mix(in srgb, var(--bg) 90%, " + STUDIO_GOLD + ") 100%)",
        color: "var(--text)",
        padding: "12px 16px 24px",
      }}
    >
      {!lightingReady && (
        <div style={{ maxWidth: 560, margin: "24px auto" }}>
          <CameraLightingScreener
            title="Camera and lighting check before class"
            onReady={() => setLightingReady(true)}
          />
          <p className="muted" style={{ fontSize: 13, marginTop: 12 }}>
            Solo and group classes need a clear, well-lit camera for presence,
            attention, and integrity tracking. Practice anytime in{" "}
            <a href="/account/camera-check">Account → Camera check</a>.
          </p>
        </div>
      )}
      {lightingReady && qualityVerdict && qualitySecondsLeft != null && (
        <CameraQualityGateOverlay
          verdict={qualityVerdict}
          secondsLeft={qualitySecondsLeft}
          onLeaveNow={excuseFromClass}
        />
      )}
      {lightingReady && room?.status === "ended" && (
        <ClassCompleteOverlay
          onDone={excuseFromClass}
          primaryLang={me?.language || locale}
          exitLabel={isSolo ? "Live Class" : "Group Classes"}
        />
      )}
      {lightingReady && (
      <>
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
          {room?.recording.status === "recording" && (
            <span style={{ color: "#fca5a5", fontWeight: 600 }}>● REC</span>
          )}
          {!isSolo ? (
            <>
              <span className="muted">
                👁 {socket.viewerCount || room?.viewer_count || room?.learner_count || 0}
              </span>
              <span className="muted">
                ❤️ {socket.followerCount || followerCount} followers
              </span>
            </>
          ) : null}
          {socket.connected ? (
            <span style={{ color: "#34d399", fontSize: 11 }}>● live</span>
          ) : (
            <span style={{ color: "#fcd34d", fontSize: 11 }}>polling</span>
          )}
          {me && !isSolo ? (
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
          key={socket.giftOverlay.id}
          style={{
            position: "fixed",
            top: "45%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            fontSize: "clamp(96px, 20vw, 220px)",
            zIndex: 60,
            textAlign: "center",
            pointerEvents: "none",
            animation: "live-gift-spectacular 4.1s cubic-bezier(.2,.8,.2,1) forwards",
            filter: "drop-shadow(0 18px 28px rgba(0,0,0,.55))",
          }}
        >
          <div>{socket.giftOverlay.emoji}</div>
          <div style={{
            fontSize: "clamp(16px, 3vw, 30px)",
            marginTop: 8,
            color: "#fff",
            fontWeight: 800,
            textShadow: "0 2px 8px #000",
          }}>
            {socket.giftOverlay.label}
          </div>
        </div>
      ) : null}
      {!isSolo ? <button
        type="button"
        onClick={() => setShowGame((v) => !v)}
        style={{
          position: "fixed", right: 18, bottom: 84, zIndex: 55,
          width: 58, height: 58, borderRadius: 999, border: "2px solid #c4b5fd",
          background: "#6d28d9", color: "#fff", fontSize: 27,
          boxShadow: "0 10px 30px rgba(0,0,0,.4)",
        }}
        title="Play a learning game"
      >🎮</button> : null}
      {renderGamePanel(false)}

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
        @media (max-width: 760px) {
          .solo-live-video-grid {
            grid-template-columns: 1fr !important;
            grid-template-rows: repeat(2, minmax(300px, 42vh)) !important;
          }
          .solo-live-video-grid > div {
            min-height: 300px !important;
          }
        }
        /* Design A "calm studio": stage on the left, chat panel docked on the
           right. Stacks to a single column on narrow screens. */
        .live-stage-grid {
          grid-template-columns: 1fr;
        }
        @media (min-width: 981px) {
          .live-stage-grid {
            grid-template-columns: minmax(0, 1fr) 360px !important;
          }
        }
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
        @keyframes live-gift-spectacular {
          0% { opacity: 0; transform: translate(-50%, -35%) scale(.15) rotate(-14deg); }
          18% { opacity: 1; transform: translate(-50%, -50%) scale(1.15) rotate(8deg); }
          32% { transform: translate(-50%, -50%) scale(.92) rotate(-4deg); }
          48% { transform: translate(-50%, -50%) scale(1.05) rotate(2deg); }
          78% { opacity: 1; transform: translate(-50%, -55%) scale(1); }
          100% { opacity: 0; transform: translate(-50%, -90%) scale(1.35); }
        }
        @keyframes presence-pulse {
          0%, 100% { opacity: 0.75; }
          50% { opacity: 0.35; }
        }
      `}</style>

      {error && (
        <div
          role="alert"
          style={{
            background: "color-mix(in srgb, #ef4444 12%, var(--panel))",
            border: "1px solid color-mix(in srgb, #ef4444 45%, transparent)",
            color: "var(--text)",
            borderRadius: 10,
            padding: "8px 12px",
            marginBottom: 10,
            fontSize: 13,
          }}
        >
          {error}
        </div>
      )}

      {notice && (
        <div
          style={{
            background: "color-mix(in srgb, var(--accent) 10%, var(--panel))",
            border: "1px solid var(--border)",
            color: "var(--muted)",
            borderRadius: 10,
            padding: "8px 12px",
            marginBottom: 10,
            fontSize: 13,
          }}
        >
          {notice}
        </div>
      )}

      {/* Instructor insights — host-only, anonymous class aggregates. Collapsed
          by default so this internal telemetry never clutters the class stage
          (it used to sit as a loud purple bar in the main view). */}
      {canModerate && Number(room?.audience_profile?.learner_count ?? 0) > 0 ? (
        <details
          style={{
            background: "var(--panel)",
            border: "1px solid var(--border)",
            borderRadius: 10,
            padding: "6px 12px",
            marginBottom: 10,
            color: "var(--muted)",
            fontSize: 12,
            lineHeight: 1.45,
          }}
        >
          <summary style={{ cursor: "pointer", fontWeight: 600, listStyle: "none" }}>
            📊 Instructor insights
            <span style={{ opacity: 0.7, fontWeight: 400 }}>
              {" · class mean "}
              {Math.round(Number(room?.audience_profile?.mean_readiness ?? 0))}/100
            </span>
          </summary>
          <div style={{ marginTop: 6 }}>
            <div>
              <strong>Readiness:</strong>{" "}
              {Math.round(Number(room?.audience_profile?.mean_readiness ?? 0))}/100
              {" · "}
              <strong>styles:</strong>{" "}
              {(room?.audience_profile?.dominant_styles ?? []).join(", ") || "mixed"}
              {(room?.audience_profile?.adaptation_hints ?? []).length
                ? ` · ${(room?.audience_profile?.adaptation_hints ?? []).join(" · ")}`
                : ""}
            </div>
            <div style={{ opacity: 0.78, marginTop: 4 }}>
              Private administrator view. {hostLabel} uses anonymous class aggregates
              when adapting explanations and Q&amp;A; authored slide text itself is
              unchanged.
            </div>
          </div>
        </details>
      ) : null}

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
          🔇 Live audio/video for participants is unavailable right now —{" "}
          {humanTaught ? "chat and Q&A continue as normal." : "the AI teacher’s narration, chat and Q&A continue as normal."}
        </div>
      )}

      {needsAudioUnlock && !liveKitFailed && (
        <div
          style={{
            background: "color-mix(in srgb, var(--accent) 12%, var(--panel))",
            border: "1px solid var(--accent)",
            borderRadius: 8,
            padding: "8px 10px",
            marginBottom: 10,
            fontSize: 13,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 10,
            flexWrap: "wrap",
          }}
        >
          <span>🔊 Tap to enable live participant audio (browser autoplay policy).</span>
          <button
            type="button"
            onClick={() => void unlockPlayback()}
            style={{ background: "var(--accent)", color: "#fff", padding: "6px 12px", borderRadius: 8 }}
          >
            Enable audio
          </button>
        </div>
      )}

      {classLive && aiAudioOn && !aiAudioUnlocked && (
        <div
          style={{
            background: "color-mix(in srgb, var(--accent-2) 18%, var(--panel))",
            border: "1px solid var(--accent-2)",
            borderRadius: 8,
            padding: "8px 10px",
            marginBottom: 10,
            fontSize: 13,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 10,
            flexWrap: "wrap",
          }}
        >
          <span>🎓 Tap to hear {hostLabel} narrate this slide (browser blocks autoplay until you interact).</span>
          <button
            type="button"
            onClick={() => {
              unlockWebAudio();
              setAiAudioUnlocked(true);
              spokenSlideRef.current = null; // force the narration effect to re-speak
            }}
            style={{ background: "var(--accent-2)", color: "#fff", padding: "6px 12px", borderRadius: 8 }}
          >
            Hear the teacher
          </button>
        </div>
      )}

      {insecureOrigin && joinInfo ? (
        <div
          style={{
            background: "#b91c1c",
            border: "1px solid #ef4444",
            borderRadius: 8,
            padding: "10px 12px",
            marginBottom: 10,
            fontSize: 14,
            color: "#fff",
          }}
        >
          Webcam is blocked on this URL. Open the class at{" "}
          <a href="https://salareen.com/group-classes" style={{ color: "#fff", fontWeight: 700 }}>
            https://salareen.com
          </a>{" "}
          (HTTPS) — browsers refuse camera access on plain <code>http://</code> IP addresses.
        </div>
      ) : null}

      {cameraNote ? (
        <div
          style={{
            background: "#92400e",
            border: "1px solid #f59e0b",
            borderRadius: 8,
            padding: "8px 10px",
            marginBottom: 10,
            fontSize: 13,
            color: "#fef3c7",
          }}
        >
          {cameraNote}
        </div>
      ) : null}

      {room?.presence?.hold_active ? (
        <div
          style={{
            background: "rgba(251,191,36,0.16)",
            border: "1px solid rgba(251,191,36,0.55)",
            borderRadius: 8,
            padding: "10px 12px",
            marginBottom: 10,
            fontSize: 14,
            color: "#fde68a",
          }}
        >
          <strong>Presence hold active.</strong>{" "}
          {room.presence.hold_participant_name || "A learner"} is not visually present
          {room.presence.hold_reason ? ` (${room.presence.hold_reason.replace(/_/g, " ")}).` : "."}
          {" "}Class resumes automatically when presence is verified.
        </div>
      ) : null}

      {!liveKitConnectEnabled && joinInfo?.media?.url && (
        <div
          role="dialog"
          aria-label="Enable live audio and video"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 1000,
            background: "rgba(15,23,42,0.55)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 24,
          }}
        >
          <div
            className="card"
            style={{ maxWidth: 420, textAlign: "center", padding: "24px 20px" }}
          >
            <h2 style={{ marginTop: 0 }}>Ready to join live audio &amp; video?</h2>
            <p className="muted" style={{ marginBottom: 16 }}>
              Your browser requires a tap before WebRTC audio can start. {humanTaught ? "Your instructor" : "The AI teacher"},
              chat and slides are already running — tap below to hear other participants.
            </p>
            <button
              type="button"
              onClick={() => void enableLiveKitAv()}
              style={{ background: "var(--accent)", color: "#fff", width: "100%", padding: "10px 16px" }}
            >
              Enable live audio &amp; video
            </button>
          </div>
        </div>
      )}


      <div
        className={isSolo ? undefined : "live-stage-grid"}
        style={{
          display: "grid",
          gridTemplateColumns: "1fr",
          gap: 14,
          alignItems: "start",
        }}
      >
        <section>
          <div
            className={isSolo ? "solo-live-video-grid" : undefined}
            style={{
              display: "grid",
              gridTemplateColumns: isSolo
                ? "repeat(2, minmax(0, 1fr))"
                : focusInstructor
                  ? "1fr"
                  : "repeat(auto-fit, minmax(min(220px, 100%), 1fr))",
              gridTemplateRows: isSolo
                ? "minmax(420px, calc(100vh - 285px))"
                : undefined,
              gap: 8,
              marginBottom: 12,
            }}
          >
            {/* Hidden audio sinks so you can HEAR remote participants (video tiles stay muted). */}
            {audioTracks.map((a) => (
              <LiveKitAudio
                key={a.participantId}
                track={a.track}
                muted={locallyMutedIds.has(a.participantId)}
              />
            ))}
            {host && (
              <div style={{
                gridColumn: isSolo ? "auto" : "1 / -1",
                minHeight: isSolo
                  ? 420
                  : focusInstructor
                    ? "min(76vh, 820px)"
                    : "clamp(440px, 62vh, 720px)",
                position: "relative",
              }}>
                {whiteboardOn ? (
                  <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: "inherit", gap: 8 }}>
                    {hasFloor && !canModerate ? (
                      <div style={{ padding: "12px 16px", borderRadius: 14, textAlign: "center", fontSize: 15, fontWeight: 700, color: "#7a5c12", background: "color-mix(in srgb, " + STUDIO_GOLD + " 16%, var(--panel))", border: "1px solid color-mix(in srgb, " + STUDIO_GOLD + " 45%, var(--border))" }}>
                        ✍️ You&apos;re up! Solve on the whiteboard — everyone can see you
                      </div>
                    ) : null}
                    <div style={{ flex: 1, minHeight: "min(62vh, 640px)", padding: 12, borderRadius: 14, border: "1px solid var(--border)", background: "var(--panel)" }}>
                      <Whiteboard
                        canDraw={(canModerate || hasFloor) && !previewAsStudent}
                        strokes={whiteboardStrokes}
                        drawerName={learners.find((p) => p.id === room?.floor_participant_id)?.name || host?.name}
                        onStroke={(s) => setWhiteboardStrokes((prev) => [...prev, s])}
                        onClear={() => setWhiteboardStrokes([])}
                        onUndo={() => setWhiteboardStrokes((prev) => prev.slice(0, -1))}
                        onExit={canModerate ? () => setWhiteboardOn(false) : undefined}
                      />
                    </div>
                  </div>
                ) : null}
                {!whiteboardOn && (
                <ParticipantTile
                  p={host}
                  large
                  fill
                  aiHost={!humanTaught}
                  fullscreen={isFullscreen}
                  localStream={iAmHost && cameraOn ? localStream : null}
                  liveKitTrack={iAmHost && cameraOn ? null : trackFor(host.id)}
                  slide={!room?.presenting && room?.welcome_message ? {
                    index: 0,
                    title: humanTaught ? `Welcome to ${room.title}` : "Welcome to Transparent AI",
                    body: room.welcome_message,
                    narration: room.welcome_message,
                  } : room?.slide}
                  audioMuted={locallyMutedIds.has(host.id) || !aiAudioOn}
                  onToggleAudio={toggleHostAudio}
                  onContainerRef={(el) => { hostTileRef.current = el; }}
                  fullscreenControls={
                    <>
                    <button
                      type="button"
                      onClick={() => setShowGame((v) => !v)}
                      style={{
                        position: "absolute", zIndex: 25, right: 18, top: 18,
                        width: 58, height: 58, borderRadius: 999,
                        border: "2px solid #c4b5fd", background: "#6d28d9",
                        color: "#fff", fontSize: 27,
                      }}
                      title="Play a learning game"
                    >🎮</button>
                    {renderGamePanel(true)}
                    {socket.giftOverlay ? (
                      <div
                        key={`fs-${socket.giftOverlay.id}`}
                        style={{
                          position: "absolute",
                          zIndex: 30,
                          top: "45%",
                          left: "50%",
                          transform: "translate(-50%, -50%)",
                          fontSize: "clamp(110px, 24vw, 260px)",
                          textAlign: "center",
                          pointerEvents: "none",
                          animation: "live-gift-spectacular 4.1s cubic-bezier(.2,.8,.2,1) forwards",
                          filter: "drop-shadow(0 18px 30px rgba(0,0,0,.6))",
                        }}
                      >
                        <div>{socket.giftOverlay.emoji}</div>
                        <div style={{
                          fontSize: "clamp(16px, 3vw, 30px)",
                          fontWeight: 800,
                          color: "#fff",
                          textShadow: "0 2px 8px #000",
                        }}>
                          {socket.giftOverlay.label}
                        </div>
                      </div>
                    ) : null}
                    <div
                      onClick={(e) => e.stopPropagation()}
                      onDoubleClick={(e) => e.stopPropagation()}
                      style={{
                        position: "absolute",
                        zIndex: 12,
                        left: "50%",
                        bottom: "clamp(64px, 9vh, 104px)",
                        transform: "translateX(-50%)",
                        width: "min(92vw, 680px)",
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        gap: 10,
                        padding: "12px 16px",
                        borderRadius: 18,
                        background: "rgba(8, 15, 24, 0.88)",
                        border: "1px solid rgba(255,255,255,0.22)",
                        boxShadow: "0 12px 40px rgba(0,0,0,0.45)",
                        backdropFilter: "blur(14px)",
                      }}
                    >
                      {hasFloor ? (
                        <>
                          <div style={{ fontSize: "clamp(14px, 2.8vw, 20px)", fontWeight: 700, textAlign: "center" }}>
                            {listening ? `🎙️ Listening — ask ${hostLabel} out loud` : "🎤 You have the floor"}
                          </div>
                          {spokenText ? (
                            <div
                              aria-live="polite"
                              style={{
                                maxHeight: "16vh",
                                overflowY: "auto",
                                fontSize: "clamp(14px, 2.5vw, 19px)",
                                lineHeight: 1.4,
                                textAlign: "center",
                                opacity: 0.95,
                              }}
                            >
                              “{spokenText}”
                            </div>
                          ) : null}
                          {micNote ? (
                            <div style={{ color: "#fbbf24", fontSize: 13, textAlign: "center" }}>{micNote}</div>
                          ) : null}
                          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "center" }}>
                            {!listening ? (
                              <button
                                type="button"
                                onClick={() => void startListening()}
                                disabled={busy}
                                style={{
                                  minHeight: 48, padding: "10px 18px", borderRadius: 999,
                                  background: "#2563eb", color: "#fff", fontWeight: 800,
                                }}
                              >
                                🎤 Start microphone
                              </button>
                            ) : null}
                            <button
                              type="button"
                              onClick={() => void doneSpeaking()}
                              disabled={busy}
                              style={{
                                minHeight: 48, padding: "10px 18px", borderRadius: 999,
                                background: "#059669", color: "#fff", fontWeight: 800,
                              }}
                            >
                              ✓ Done — ask {hostLabel}
                            </button>
                          </div>
                        </>
                      ) : (
                        <>
                          <button
                            type="button"
                            onClick={() => void toggleHand()}
                            disabled={busy || !me}
                            style={{
                              minHeight: 52,
                              padding: "12px 22px",
                              borderRadius: 999,
                              border: "1px solid rgba(255,255,255,0.3)",
                              background: inQueue ? "#b45309" : "#7c3aed",
                              color: "#fff",
                              fontSize: "clamp(15px, 3vw, 20px)",
                              fontWeight: 800,
                              boxShadow: "0 8px 24px rgba(0,0,0,0.35)",
                            }}
                          >
                            {inQueue ? `✋ Lower hand · #${myQueuePos}` : "✋ Raise hand to ask by voice"}
                          </button>
                          {inQueue ? (
                            <div style={{ fontSize: 13, opacity: 0.9, textAlign: "center" }}>
                              Stay fullscreen. Your microphone opens when {hostLabel} gives you the floor.
                            </div>
                          ) : null}
                        </>
                      )}
                      <button
                        type="button"
                        onClick={() => setShowGifts((v) => !v)}
                        disabled={busy || !me}
                        style={{
                          position: "absolute",
                          right: 12,
                          top: 12,
                          minWidth: 48,
                          minHeight: 44,
                          borderRadius: 999,
                          border: "1px solid rgba(255,255,255,.3)",
                          background: "#be185d",
                          color: "#fff",
                          fontWeight: 800,
                        }}
                        title="Send an animated gift"
                      >
                        🎁
                      </button>
                      {showGifts ? (
                        <div style={{
                          display: "grid",
                          gridTemplateColumns: "repeat(3, minmax(72px, 1fr))",
                          gap: 8,
                          width: "100%",
                          maxHeight: "32vh",
                          overflowY: "auto",
                          paddingTop: 8,
                          borderTop: "1px solid rgba(255,255,255,.18)",
                        }}>
                          <select
                            value={giftRecipientId || host.id}
                            onChange={(e) => setGiftRecipientId(e.target.value)}
                            style={{
                              gridColumn: "1 / -1",
                              padding: "9px 10px",
                              borderRadius: 9,
                              background: "#111827",
                              color: "#fff",
                              border: "1px solid rgba(255,255,255,.25)",
                            }}
                            aria-label="Gift recipient"
                          >
                            <option value={host.id}>🎓 {host.name}</option>
                            {learners.filter((p) => p.id !== me?.id).map((p) => (
                              <option key={p.id} value={p.id}>👤 {p.name}</option>
                            ))}
                          </select>
                          {giftCatalog.map((g) => (
                            <button
                              key={`fs-gift-${g.id}`}
                              type="button"
                              disabled={busy || giftBalance < g.cost_points}
                              onClick={() => void sendGift(g)}
                              style={{
                                padding: 8,
                                borderRadius: 10,
                                border: "1px solid rgba(255,255,255,.2)",
                                background: "rgba(255,255,255,.1)",
                                color: "#fff",
                              }}
                            >
                              <div style={{ fontSize: 30 }}>{g.emoji}</div>
                              <div style={{ fontSize: 11 }}>{g.name}</div>
                              <div style={{ fontSize: 10 }}>{g.cost_points} pts</div>
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </div>
                    </>
                  }
                />
                )}
              </div>
            )}
            {isSolo && learners.map((p) => (
              <div
                key={p.id}
                style={{ position: "relative", minHeight: isSolo ? 420 : 220 }}
              >
                <ParticipantTile
                  p={p}
                  showAdminProfile={canModerate}
                  fill
                  localStream={p.id === me?.id && cameraOn && !canModerate ? localStream : null}
                  liveKitTrack={p.id === me?.id && (!cameraOn || canModerate) ? null : trackFor(p.id)}
                  hasFloor={p.id === room?.floor_participant_id}
                  isMe={p.id === me?.id}
                  presenceFaceCount={p.id === me?.id ? presenceFaceCount : undefined}
                  cameraOn={p.id === me?.id ? cameraOn : undefined}
                  onToggleCamera={p.id === me?.id ? () => void toggleCamera() : undefined}
                  audioMuted={locallyMutedIds.has(p.id)}
                  onToggleAudio={p.id !== me?.id ? () => toggleLocalAudio(p.id) : undefined}
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
                {/* Prominent mute/unmute button for host — visible on every learner tile */}
                {canModerate && p.id !== me?.id ? (
                  <button
                    type="button"
                    onClick={() => toggleLocalAudio(p.id)}
                    title={locallyMutedIds.has(p.id) ? `Unmute ${p.name}` : `Mute ${p.name}`}
                    style={{
                      position: "absolute",
                      bottom: 6,
                      right: 6,
                      fontSize: 11,
                      padding: "2px 8px",
                      borderRadius: 6,
                      background: locallyMutedIds.has(p.id)
                        ? "rgba(239,68,68,0.92)"
                        : "rgba(30,30,60,0.85)",
                      color: "#fff",
                      border: "1px solid rgba(255,255,255,0.3)",
                      cursor: "pointer",
                    }}
                  >
                    {locallyMutedIds.has(p.id) ? "🔇 Muted" : "🔊 Unmute"}
                  </button>
                ) : null}
                {/* Hand-raise badge — visible only to the host so they know who wants to speak */}
                {canModerate && p.hand_raised ? (
                  <div
                    style={{
                      position: "absolute",
                      top: 30,
                      left: 6,
                      fontSize: 11,
                      padding: "3px 8px",
                      borderRadius: 6,
                      background: "rgba(217,154,28,0.95)",
                      color: "#1c1917",
                      fontWeight: 700,
                      pointerEvents: "none",
                    }}
                  >
                    ✋ Hand raised
                  </div>
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
          </div>

          {!isSolo ? (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 10,
                padding: "12px 14px",
                marginTop: 8,
                marginBottom: 12,
                borderRadius: 16,
                border: "1px solid var(--border)",
                background: "var(--panel)",
              }}
            >
              {/* Count on its own line so it doesn't compete with the scrollable
                  seat row for horizontal space (which caused a scrollbar). */}
              <div style={{ fontSize: 12, fontWeight: 600, color: "var(--muted)" }}>
                {learners.length > 0 ? `${learners.length} in class` : "Waiting for participants…"}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1, minWidth: 0, overflowX: "auto", paddingBottom: 2 }}>
                  {studentLearners.slice(0, 8).map((p) => {
                    const onFloor = p.id === room?.floor_participant_id;
                    const selected = selectedParticipant === p.id;
                    const clickable = canModerate && p.id !== me?.id;
                    return (
                      <div
                        key={p.id}
                        onClick={() => (clickable ? setSelectedParticipant(selected ? "" : p.id) : undefined)}
                        title={`${p.name}${p.hand_raised ? " — hand raised" : onFloor ? " — speaking" : ""}`}
                        style={{
                          position: "relative",
                          width: 168,
                          height: 96,
                          flex: "0 0 auto",
                          borderRadius: 12,
                          overflow: "hidden",
                          outline: selected ? `2px solid ${STUDIO_GOLD}` : "none",
                          outlineOffset: 1,
                          cursor: clickable ? "pointer" : "default",
                        }}
                      >
                        <ParticipantTile
                          p={p}
                          showAdminProfile={canModerate}
                          fill
                          localStream={p.id === me?.id && cameraOn ? localStream : null}
                          liveKitTrack={p.id === me?.id && cameraOn ? null : trackFor(p.id)}
                          hasFloor={onFloor}
                          isMe={p.id === me?.id}
                          presenceFaceCount={p.id === me?.id ? presenceFaceCount : undefined}
                          cameraOn={p.id === me?.id ? cameraOn : undefined}
                          onToggleCamera={p.id === me?.id ? () => void toggleCamera() : undefined}
                          audioMuted={locallyMutedIds.has(p.id)}
                          onToggleAudio={p.id !== me?.id ? () => toggleLocalAudio(p.id) : undefined}
                        />
                      </div>
                    );
                  })}
                  {studentLearners.length > 8 ? (
                    <span style={{ fontSize: 12, fontWeight: 700, color: "var(--muted)", flex: "0 0 auto" }}>
                      +{studentLearners.length - 8}
                    </span>
                  ) : null}
                  {Array.from({ length: Math.min(emptySlots, Math.max(0, 8 - studentLearners.length)) }).map((_, i) => (
                    <span
                      key={`ph-${i}`}
                      aria-hidden
                      style={{
                        width: 168,
                        height: 96,
                        flex: "0 0 auto",
                        borderRadius: 12,
                        border: "1px dashed var(--border)",
                        background: "color-mix(in srgb, var(--accent) 3%, var(--panel))",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        color: "var(--muted)",
                        fontSize: 12,
                        fontWeight: 600,
                      }}
                    >
                      ＋ Open seat
                    </span>
                  ))}
                </div>
              </div>
              {canModerate && selectedParticipant
                ? (() => {
                    const sel = learners.find((p) => p.id === selectedParticipant);
                    if (!sel) return null;
                    return (
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center", borderTop: "1px solid var(--border)", paddingTop: 8 }}>
                        <span style={{ fontSize: 12, fontWeight: 700 }}>{sel.name}</span>
                        {sel.id !== room?.floor_participant_id ? (
                          <button
                            type="button"
                            onClick={() => void callOn(sel.id)}
                            disabled={busy}
                            style={{ fontSize: 12, padding: "4px 10px", borderRadius: 8, background: "#0d9488", color: "#fff", border: "none", cursor: "pointer" }}
                          >
                            🎤 Call on
                          </button>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => void reportLearner(sel.id, sel.name)}
                          disabled={busy}
                          style={{ fontSize: 12, padding: "4px 10px", borderRadius: 8, background: "color-mix(in srgb, #f59e0b 18%, var(--panel))", color: "var(--text)", border: "1px solid var(--border)", cursor: "pointer" }}
                        >
                          Report
                        </button>
                        <button
                          type="button"
                          onClick={() => void banLearner(sel.id, sel.name)}
                          disabled={busy}
                          style={{ fontSize: 12, padding: "4px 10px", borderRadius: 8, background: "color-mix(in srgb, #dc2626 18%, var(--panel))", color: "var(--text)", border: "1px solid var(--border)", cursor: "pointer" }}
                        >
                          Block
                        </button>
                        <button
                          type="button"
                          onClick={() => setSelectedParticipant("")}
                          style={{ fontSize: 12, padding: "4px 10px", borderRadius: 8, background: "transparent", color: "var(--muted)", border: "1px solid var(--border)", cursor: "pointer", marginLeft: "auto" }}
                        >
                          Close
                        </button>
                      </div>
                    );
                  })()
                : null}
            </div>
          ) : null}

          {!isSolo && hasFloor && (
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
                {hostLabel} is listening. Speak naturally, then tap “Done — ask {hostLabel}”. You can also type it below.
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
                  Done — ask {hostLabel}
                </button>
              </div>
            </div>
          )}

          {!isSolo && (room?.speaking_queue?.length ?? 0) > 0 && (
            <div
              style={{
                marginBottom: 12,
                padding: 12,
                borderRadius: 12,
                background: "color-mix(in srgb, var(--accent-2) 12%, var(--panel))",
                border: "1px solid color-mix(in srgb, var(--accent-2) 45%, var(--border))",
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 700, color: "#0f766e", marginBottom: 8 }}>
                Q&A queue — take turns
              </div>
              {room?.floor_holder ? (
                <div style={{ fontSize: 13, marginBottom: 8, color: "var(--text)" }}>
                  🎤 Now speaking: <strong>{room.floor_holder.name}</strong>
                </div>
              ) : null}
              <ol style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "var(--text)" }}>
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
                <div style={{ marginTop: 8, fontSize: 12, fontWeight: 700, color: "#b45309" }}>
                  You are #{myQueuePos} in line.
                </div>
              ) : null}
            </div>
          )}

        </section>

        {!isSolo && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12, minWidth: 0, alignSelf: "stretch" }}>
          {/* Large self-view docked above the chat (Layout A). This is the biggest
              consistently-visible feed of the local user's face — sized ~3:2 at the
              full column width so a future presence/expression model has ample
              pixels. Shown for the moderator/host, who has no seat in the row. */}
          {canModerate && me ? (
            <div
              title="You"
              style={{
                position: "relative",
                width: "100%",
                aspectRatio: "3 / 2",
                flex: "0 0 auto",
                borderRadius: 16,
                overflow: "hidden",
                border: `2px solid ${STUDIO_GOLD}`,
                background: "#0d0a16",
                boxShadow: "0 8px 24px rgba(27,21,40,0.18)",
              }}
            >
              <ParticipantTile
                p={me}
                fill
                localStream={cameraOn ? localStream : null}
                liveKitTrack={cameraOn ? null : trackFor(me.id)}
                hasFloor={me.id === room?.floor_participant_id}
                isMe
                presenceFaceCount={presenceFaceCount}
                cameraOn={cameraOn}
                onToggleCamera={() => void toggleCamera()}
              />
              <span
                style={{
                  position: "absolute",
                  left: 10,
                  top: 8,
                  fontSize: 11,
                  fontWeight: 700,
                  color: "#1b1528",
                  padding: "2px 9px",
                  borderRadius: 999,
                  background: STUDIO_GOLD,
                  pointerEvents: "none",
                }}
              >
                You
              </span>
            </div>
          ) : null}
        <aside
          aria-label="Group class chat and questions"
          style={{
            // The chat's content is an ABSOLUTE inner layer so a long conversation
            // doesn't inflate the grid row: the stage column drives the height and
            // the chat fills it and scrolls internally (no gap under the strip).
            position: "relative",
            overflow: "hidden",
            minHeight: 280,
            flex: "1 1 auto",
            background: "var(--panel)",
            borderRadius: 16,
            border: "1px solid var(--border)",
            alignSelf: "stretch",
          }}
        >
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              flexDirection: "column",
              gap: 10,
              padding: 14,
              overflowY: "auto",
            }}
          >
          {/* Underline tabs: class chat vs. asking Theodore directly (Design A). */}
          <div
            role="tablist"
            aria-label={humanTaught ? `Chat or Ask ${hostLabel}` : "Chat or Ask Theodore"}
            style={{
              display: "flex",
              gap: 8,
              borderBottom: "1px solid var(--border)",
            }}
          >
            <button
              type="button"
              role="tab"
              aria-selected={panelTab === "chat"}
              onClick={() => setPanelTab("chat")}
              style={panelTabStyle(panelTab === "chat")}
            >
              💬 Chat
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={panelTab === "ask"}
              onClick={() => setPanelTab("ask")}
              style={panelTabStyle(panelTab === "ask")}
            >
              🎓 Ask {hostLabel}
            </button>
          </div>

          {panelTab === "chat" ? (
            <>
          <div
            style={{
              flex: 1,
              borderRadius: 12,
              padding: "6px 2px",
              overflowY: "auto",
              minHeight: 0,
              display: "flex",
              flexDirection: "column",
              gap: 12,
            }}
          >
            {(room?.chat ?? [])
              .filter((m) => {
                // Hide only THIS learner's own Ask-Theodore mirror copies: their
                // question (from me) and Theodore's reply (from the host). Scoping
                // by sender avoids hiding another learner's coincidentally
                // identical chat text.
                if (!askMineRef.current.has(m.text)) return true;
                const fromMe = m.from_id === me?.id;
                const fromTheodore = !humanTaught && /theodore|teacher|host/i.test(`${m.from_id} ${m.from_name}`);
                return !(fromMe || fromTheodore);
              })
              .map((m) => {
              const isSystem = m.from_id === "system";
              // In a human-taught class nobody is Theodore — and the instructor's
              // placeholder id ("human-host") would otherwise match this heuristic.
              const isTheodore =
                !humanTaught && !isSystem && /theodore|teacher|host/i.test(`${m.from_id} ${m.from_name}`);
              return (
                <div key={m.id} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                  <span
                    style={{
                      flex: "0 0 auto",
                      width: 28,
                      height: 28,
                      borderRadius: 999,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 12,
                      fontWeight: 700,
                      background: isTheodore
                        ? "color-mix(in srgb, var(--accent-2) 20%, var(--panel))"
                        : "color-mix(in srgb, var(--accent) 12%, var(--panel))",
                      color: "var(--text)",
                      border: "1px solid var(--border)",
                    }}
                  >
                    {isTheodore ? "🎓" : initials(m.from_name || "?")}
                  </span>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text)" }}>
                      {m.from_name}
                      {isTheodore ? " · AI teacher" : ""}
                    </div>
                    <div
                      style={{
                        marginTop: 2,
                        fontSize: 13,
                        lineHeight: 1.45,
                        color: isSystem ? "var(--muted)" : "var(--text)",
                        background: isSystem ? "transparent" : "color-mix(in srgb, var(--accent) 5%, var(--panel))",
                        border: isSystem ? "none" : "1px solid var(--border)",
                        borderRadius: 10,
                        padding: isSystem ? 0 : "7px 10px",
                        display: "inline-block",
                        fontStyle: isSystem ? "italic" : "normal",
                      }}
                    >
                      {m.text}
                    </div>
                  </div>
                </div>
              );
            })}
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
              <label style={{ gridColumn: "1 / -1", display: "grid", gap: 4, fontSize: 12 }}>
                Send to
                <select
                  value={giftRecipientId || host?.id || ""}
                  onChange={(e) => setGiftRecipientId(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 10px",
                    borderRadius: 8,
                    border: "1px solid var(--border)",
                    background: "var(--panel)",
                    color: "var(--text)",
                  }}
                >
                  {host ? <option value={host.id}>🎓 {host.name}</option> : null}
                  {learners.filter((p) => p.id !== me?.id).map((p) => (
                    <option key={p.id} value={p.id}>👤 {p.name}</option>
                  ))}
                </select>
              </label>
              {giftCatalog.map((g) => (
                <button
                  key={g.id}
                  type="button"
                  disabled={busy || !me || giftBalance < g.cost_points}
                  onClick={() => void sendGift(g)}
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

          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input
              value={chatDraft}
              onChange={(e) => setChatDraft(e.target.value)}
              placeholder="Type your message…"
              style={{ flex: 1, borderRadius: 999, border: "1px solid var(--border)", padding: "10px 14px", background: "var(--panel)", color: "var(--text)" }}
              onKeyDown={(e) => e.key === "Enter" && void sendChat()}
              disabled={busy || me?.muted || me?.muted_by_host}
            />
            <button
              onClick={() => void sendChat()}
              disabled={busy}
              aria-label="Send message"
              title="Send"
              style={{
                flex: "0 0 auto",
                width: 42,
                height: 42,
                borderRadius: 999,
                background: STUDIO_GOLD,
                color: "#fff",
                border: "none",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 16,
              }}
            >
              ➤
            </button>
          </div>
            </>
          ) : (
            <>
          <div
            style={{
              flex: 1,
              minHeight: 0,
              overflowY: "auto",
              display: "flex",
              flexDirection: "column",
              gap: 14,
              padding: "6px 2px",
            }}
          >
            {askThread.length === 0 ? (
              <p className="muted" style={{ fontSize: 12.5, margin: "4px 0", lineHeight: 1.5 }}>
                Ask {hostLabel} anything about the lesson — your questions and the answers
                stay here in this tab. You can also raise your hand on your tile to ask by voice.
              </p>
            ) : (
              askThread.map((e) => (
                <div key={e.id} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <div
                    style={{
                      alignSelf: "flex-end",
                      maxWidth: "88%",
                      background: "color-mix(in srgb, var(--accent) 12%, var(--panel))",
                      border: "1px solid var(--border)",
                      borderRadius: 12,
                      padding: "7px 11px",
                      fontSize: 13,
                      lineHeight: 1.45,
                    }}
                  >
                    {e.question}
                  </div>
                  <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                    <span
                      style={{
                        flex: "0 0 auto",
                        width: 28,
                        height: 28,
                        borderRadius: 999,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 14,
                        background: "color-mix(in srgb, var(--accent-2) 20%, var(--panel))",
                        border: "1px solid var(--border)",
                      }}
                    >
                      🎓
                    </span>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: 700 }}>
                        {humanTaught ? hostLabel : "Theodore · AI teacher"}
                        {!e.done ? " · answering…" : ""}
                      </div>
                      <div
                        style={{
                          marginTop: 2,
                          fontSize: 13,
                          lineHeight: 1.5,
                          color: "var(--text)",
                          background: "color-mix(in srgb, var(--accent-2) 8%, var(--panel))",
                          border: "1px solid var(--border)",
                          borderRadius: 10,
                          padding: "7px 10px",
                          display: "inline-block",
                        }}
                      >
                        {e.answer || (e.done ? "…" : "Answering…")}
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
            <div ref={askEndRef} />
          </div>

          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input
              value={askDraft}
              onChange={(e) => setAskDraft(e.target.value)}
              placeholder={humanTaught ? `Ask ${hostLabel} a question…` : "Ask Theodore a question…"}
              style={{ flex: 1, borderRadius: 999, border: "1px solid var(--border)", padding: "10px 14px", background: "var(--panel)", color: "var(--text)" }}
              onKeyDown={(e) => e.key === "Enter" && void askQuestion()}
              disabled={busy}
            />
            <button
              onClick={() => void askQuestion()}
              disabled={busy}
              aria-label={humanTaught ? `Ask ${hostLabel}` : "Ask Theodore"}
              title={humanTaught ? `Ask ${hostLabel}` : "Ask Theodore"}
              style={{
                flex: "0 0 auto",
                width: 42,
                height: 42,
                borderRadius: 999,
                background: STUDIO_GOLD,
                color: "#fff",
                border: "none",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 16,
              }}
            >
              ➤
            </button>
          </div>
            </>
          )}

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
          </div>
        </aside>
        </div>
        )}
      </div>

      {isSolo ? (
        <aside
          aria-label="Solo class chat and actions"
          style={{
            display: "grid",
            gap: 8,
            padding: 10,
            border: "1px solid var(--border)",
            borderRadius: 12,
            background: "var(--panel)",
            boxShadow: "0 8px 24px rgba(0,0,0,.08)",
          }}
        >
          {learnerCtx && (learnerCtx.readinessBand || learnerCtx.primaryStyle !== "mixed") ? (
            <div
              style={{
                fontSize: 12,
                lineHeight: 1.45,
                padding: "8px 10px",
                borderRadius: 9,
                background: "color-mix(in srgb, var(--accent-2) 10%, var(--panel))",
                border: "1px solid color-mix(in srgb, var(--accent-2) 35%, var(--border))",
              }}
            >
              <strong style={{ color: "var(--accent-2)" }}>How you learn</strong>
              {" · "}
              {(learnerCtx.primaryStyle || "mixed").replace(/_/g, " ")}
              {learnerCtx.readinessBand ? (
                <>
                  {" · readiness "}
                  {Math.round(learnerCtx.readinessScore)}
                  {" ("}
                  {learnerCtx.readinessBand.replace(/_/g, " ")}
                  {")"}
                </>
              ) : null}
              {learnerCtx.lxScore != null ? ` · LX ${Math.round(learnerCtx.lxScore)}` : null}
              {learnerCtx.learnerCategory && learnerCtx.learnerCategory !== "skipped" ? (
                <> · {learnerCtx.learnerCategory.replace(/_/g, " ")}</>
              ) : null}
              <span className="muted"> — {hostLabel} uses this to adapt your Q&amp;A.</span>
            </div>
          ) : null}
          {/* A short horizontal transcript preserves vertical space for video. */}
          <div
            style={{
              display: "flex",
              gap: 8,
              minHeight: 48,
              maxHeight: 72,
              overflowX: "auto",
              overflowY: "hidden",
              alignItems: "stretch",
              scrollSnapType: "x proximity",
            }}
          >
            {(room?.chat ?? []).length ? (room?.chat ?? []).slice(-8).map((m) => (
              <div
                key={`solo-${m.id}`}
                style={{
                  flex: "0 0 min(300px, 72vw)",
                  scrollSnapAlign: "end",
                  padding: "7px 10px",
                  borderRadius: 9,
                  border: "1px solid var(--border)",
                  background: "color-mix(in srgb, var(--accent) 5%, var(--panel))",
                  fontSize: 12,
                  lineHeight: 1.35,
                  overflow: "hidden",
                }}
              >
                <strong style={{ color: "var(--accent)" }}>{m.from_name}:</strong>{" "}
                <span>{m.text}</span>
              </div>
            )) : (
              <span className="muted" style={{ alignSelf: "center", fontSize: 12 }}>
                Chat and {hostLabel}’s answers appear here.
              </span>
            )}
            <div ref={chatEndRef} />
          </div>

          <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
            {REACTIONS.map((emoji) => (
              <button
                key={`solo-${emoji}`}
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
                style={{ padding: "5px 8px", minWidth: 34 }}
              >
                {emoji}
              </button>
            ))}
            <button
              type="button"
              disabled={!me}
              onClick={() => setShowGifts((v) => !v)}
              title="Send a gift"
              style={{ background: "#be185d", color: "#fff" }}
            >
              🎁 Gift
            </button>
            <button
              type="button"
              disabled={!me}
              onClick={() => setShowGame((v) => !v)}
              title="Play a solo learning game"
              aria-expanded={showGame}
              style={{ background: "#6d28d9", color: "#fff" }}
            >
              🎮 Game
            </button>
            <input
              value={chatDraft}
              onChange={(e) => setChatDraft(e.target.value)}
              placeholder="Chat…"
              aria-label="Chat message"
              onKeyDown={(e) => e.key === "Enter" && void sendChat()}
              disabled={busy || me?.muted || me?.muted_by_host}
              style={{ flex: "1 1 150px", minWidth: 120, padding: "7px 9px" }}
            />
            <button onClick={() => void sendChat()} disabled={busy} style={{ background: "var(--accent)", color: "#fff" }}>
              Send
            </button>
            <input
              value={askDraft}
              onChange={(e) => setAskDraft(e.target.value)}
              placeholder={humanTaught ? `Ask ${hostLabel}…` : "Ask Theodore…"}
              aria-label={humanTaught ? `Question for ${hostLabel}` : "Question for Theodore"}
              onKeyDown={(e) => e.key === "Enter" && void askQuestion()}
              disabled={busy}
              style={{ flex: "1 1 180px", minWidth: 150, padding: "7px 9px" }}
            />
            <button onClick={() => void askQuestion()} disabled={busy} style={{ background: "var(--accent-2)", color: "#fff" }}>
              Ask
            </button>
          </div>

          {showGifts ? (
            <div style={{ display: "flex", gap: 6, overflowX: "auto", paddingTop: 6, borderTop: "1px solid var(--border)" }}>
              {giftCatalog.map((g) => (
                <button
                  key={`solo-gift-${g.id}`}
                  type="button"
                  disabled={busy || !me || giftBalance < g.cost_points}
                  onClick={() => void sendGift(g)}
                  style={{ flex: "0 0 auto", padding: "6px 10px" }}
                >
                  {g.emoji} {g.name} · {g.cost_points}
                </button>
              ))}
            </div>
          ) : null}

          {hostAnswer && (hostAnswer.text || !hostAnswer.done) ? (
            <div style={{ fontSize: 12, padding: "6px 9px", borderRadius: 8, background: "rgba(99,102,241,.10)" }}>
              <strong>🎓 Theodore{hostAnswer.asker ? ` → ${hostAnswer.asker}` : ""}:</strong>{" "}
              {hostAnswer.text || "Answering…"}
            </div>
          ) : null}
        </aside>
      ) : null}

      {/* Design A control-bar card. Three groups: device controls (camera/mic/
          fullscreen) on the left, the primary gold CTA (Raise your hand / Done) in
          the center, and the instructor rail + Leave on the right. Role-aware:
          students only see device controls, the CTA, and Leave. */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
          marginTop: 12,
          padding: "12px 14px",
          position: "sticky",
          bottom: 0,
          zIndex: 45,
          background: "color-mix(in srgb, var(--panel) 96%, transparent)",
          backdropFilter: "blur(14px)",
          border: "1px solid var(--border)",
          borderRadius: 16,
          boxShadow: "0 -8px 24px rgba(27,21,40,.08)",
        }}
      >
        {/* Left: device controls */}
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => void toggleCamera()}
            disabled={busy}
            title={cameraOn ? "Turn your webcam off" : "Turn your webcam on"}
            style={{ ...deviceBtnStyle, borderColor: cameraOn ? "var(--accent)" : "var(--border)" }}
          >
            <span style={{ fontSize: 18 }}>{cameraOn ? "📹" : "📷"}</span>
            Camera
          </button>
          <button
            onClick={() => {
              if (!hasFloor) setNotice("You can speak when the teacher calls on you — raise your hand.");
            }}
            title={hasFloor ? "Your mic is live (you have the floor)" : "You can speak when the teacher calls on you"}
            style={{ ...deviceBtnStyle, borderColor: hasFloor ? "var(--accent-2)" : "var(--border)", opacity: hasFloor ? 1 : 0.7 }}
          >
            <span style={{ fontSize: 18 }}>{hasFloor ? "🎙️" : "🔇"}</span>
            Mic
          </button>
          <button
            onClick={toggleHostFullscreen}
            title="Fullscreen (Esc to exit)"
            style={{ ...deviceBtnStyle, borderColor: isFullscreen ? "var(--accent)" : "var(--border)" }}
          >
            <span style={{ fontSize: 18 }}>⛶</span>
            Fullscreen
          </button>
          <button
            onClick={() => void handleScreenShare()}
            disabled={busy}
            title={screenSharing ? "Stop screen share" : "Share your screen"}
            style={{ ...deviceBtnStyle, borderColor: screenSharing ? "#ef4444" : "var(--border)", background: screenSharing ? "rgba(239,68,68,0.1)" : "var(--panel)" }}
          >
            <span style={{ fontSize: 18 }}>🖥</span>
            {screenSharing ? "Stop" : "Share"}
          </button>
          {screenSharing && (
            <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: "#ef4444", fontWeight: 600, whiteSpace: "nowrap" }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#ef4444", display: "inline-block" }} />
              Sharing screen
            </div>
          )}
        </div>

        {/* Center: primary CTA */}
        <div style={{ flex: 1, display: "flex", justifyContent: "center", minWidth: 200 }}>
          {hasFloor ? (
            <button
              onClick={() => void doneSpeaking()}
              disabled={busy}
              title={`Send your spoken (or typed) question to ${hostLabel} and hand back the floor`}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "13px 30px",
                borderRadius: 999,
                border: "none",
                background: STUDIO_GOLD,
                color: "#fff",
                cursor: "pointer",
                fontSize: 16,
                fontWeight: 800,
              }}
            >
              ✓ Done
            </button>
          ) : (
            <button
              onClick={() => void toggleHand()}
              disabled={busy}
              title="Raise your hand to ask to speak (raise/lower)"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "13px 30px",
                borderRadius: 999,
                border: inQueue ? "1px solid var(--border)" : "none",
                background: inQueue ? "var(--panel)" : STUDIO_GOLD,
                color: inQueue ? "var(--text)" : "#fff",
                cursor: "pointer",
                fontSize: 16,
                fontWeight: 800,
              }}
            >
              {inQueue ? `✋ Lower your hand (#${myQueuePos})` : "🖐 Raise your hand"}
            </button>
          )}
        </div>

        {/* Right: instructor rail + Leave */}
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          {canModerate ? (
            <>
              {!isSolo ? (
                <button
                  type="button"
                  onClick={() => setWhiteboardOn((v) => !v)}
                  title="Open a shared whiteboard; the student you call on can draw on it"
                  style={{ ...railBtnStyle, ...(whiteboardOn ? { background: "var(--accent)", color: "#fff", borderColor: "var(--accent)" } : {}) }}
                >
                  🧑‍🏫 Whiteboard
                </button>
              ) : null}
              {whiteboardOn ? (
                <button
                  type="button"
                  onClick={() => setPreviewAsStudent((v) => !v)}
                  title="Preview the read-only view a student sees"
                  style={{ ...railBtnStyle, ...(previewAsStudent ? { background: "var(--accent-2)", color: "#fff", borderColor: "var(--accent-2)" } : {}) }}
                >
                  👁 {previewAsStudent ? "Exit preview" : "Preview as student"}
                </button>
              ) : null}
              {!isSolo ? (
                <>
                  <button
                    onClick={() => void callNext()}
                    disabled={busy}
                    style={{ ...railBtnStyle, background: "#0d9488", color: "#fff", borderColor: "#0d9488" }}
                  >
                    ⏭ Call next
                  </button>
                  {room?.floor_participant_id ? (
                    <button onClick={() => void finishTurn()} disabled={busy} style={railBtnStyle}>
                      End turn
                    </button>
                  ) : null}
                </>
              ) : null}
              {!isSolo ? (
                !room?.presenting ? (
                  <button
                    onClick={(e) => { e.currentTarget.blur(); void startPresentation(); }}
                    disabled={busy}
                    title="Start the class"
                    style={{ ...railBtnStyle, background: STUDIO_GOLD, color: "#fff", borderColor: STUDIO_GOLD }}
                  >
                    🎬 Start class
                  </button>
                ) : (
                  <button onClick={() => void hostAdvance()} disabled={busy} title="Next slide (the AI advances automatically)" style={railBtnStyle}>
                    ▶ Next slide
                  </button>
                )
              ) : null}
              {isSolo ? (
                <button
                  onClick={() => {
                    if (paused) {
                      setPaused(false);
                      spokenSlideRef.current = null; // re-trigger narration on resume
                    } else {
                      cancelSpeech();
                      setPaused(true);
                    }
                  }}
                  disabled={busy}
                  title={paused ? "Resume the class" : "Pause the class and come back later"}
                  style={{ ...railBtnStyle, background: paused ? "#15803d" : "#6d28d9", color: "#fff", borderColor: paused ? "#15803d" : "#6d28d9" }}
                >
                  {paused ? "▶ Resume" : "⏸ Pause"}
                </button>
              ) : (
                <button
                  onClick={() => void closeSession()}
                  disabled={busy}
                  title="Close this session for everyone"
                  style={{ ...railBtnStyle, background: "#b45309", color: "#fff", borderColor: "#b45309" }}
                >
                  ⛔ Close session
                </button>
              )}
            </>
          ) : null}
          {xrEnabled && joinInfo?.participant?.id ? (
            <Link
              href={`/xr/${encodeURIComponent(roomId)}?roomId=${encodeURIComponent(roomId)}&participantId=${encodeURIComponent(joinInfo.participant.id)}&moderatorKey=${encodeURIComponent(moderatorKey)}`}
              style={railBtnStyle}
              title="Open the immersive XR demonstration lab"
            >
              Enter VR lab
            </Link>
          ) : null}
          <button
            onClick={() => void handleLeave()}
            disabled={busy}
            style={{ ...railBtnStyle, color: "#b91c1c", borderColor: "color-mix(in srgb, #b91c1c 40%, var(--border))" }}
          >
            ⇥ Leave
          </button>
        </div>
      </div>
      </>
      )}
      <video
        ref={presenceProbeVideoRef}
        autoPlay
        muted
        playsInline
        aria-hidden="true"
        style={{ position: "fixed", width: 1, height: 1, opacity: 0, pointerEvents: "none" }}
      />
    </main>
  );
}
