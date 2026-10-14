"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";

import { useT } from "../lib/i18n";

import { SERENITY_VOICE_INSTRUCTIONS } from "../lib/serenity";
import {
  closeXaiVoiceSession,
  connectXaiVoiceSession,
  getXaiVoiceStatus,
  mintXaiVoiceToken,
  playPcm16Base64,
  type XaiVoiceMode,
} from "../lib/xaiVoice";

function voiceMode(pathname: string): XaiVoiceMode | null {
  // Live Class and On the Go already run their own Grok session.
  // This dock covers group rooms, full courses, and free course demos
  // (Serenity teacher + xAI Grok voice).
  if (pathname === "/group-classes" || pathname.startsWith("/live-room")) return "group";
  if (pathname.startsWith("/learn/")) return "solo";
  if (pathname.startsWith("/demo/drivers-ed") || pathname.startsWith("/demo/course-studio")) {
    return "solo";
  }
  if (pathname === "/serenity") return "solo";
  return null;
}

/** xAI Grok voice on group rooms and full course pages. Live Class and On the Go start their own session. */
export function XaiVoiceDock() {
  const pathname = usePathname() || "";
  const mode = voiceMode(pathname);
  const { locale } = useT();
  const [ready, setReady] = useState(false);
  const [live, setLive] = useState(false);
  const [hint, setHint] = useState("");
  const wsRef = useRef<WebSocket | null>(null);
  const audioRef = useRef<AudioContext | null>(null);

  useEffect(() => {
    if (!mode) return;
    let alive = true;
    getXaiVoiceStatus()
      .then((status) => {
        if (!alive) return;
        setReady(Boolean(status.available));
        if (!status.available && status.hint) setHint(status.hint);
      })
      .catch(() => {
        if (alive) setReady(false);
      });
    return () => {
      alive = false;
      closeXaiVoiceSession(wsRef.current);
      wsRef.current = null;
      void audioRef.current?.close().catch(() => {});
      audioRef.current = null;
    };
  }, [mode]);

  if (!mode) return null;

  async function toggle() {
    if (live) {
      closeXaiVoiceSession(wsRef.current);
      wsRef.current = null;
      setLive(false);
      setHint("Salane Voice ended.");
      return;
    }
    try {
      const token = await mintXaiVoiceToken({
        mode: mode || "solo",
        lesson_context: `Salareen ${pathname}`,
        language: locale,
        instructions: SERENITY_VOICE_INSTRUCTIONS,
      });
      if (token.engine === "salane" || token.display_name === "Salane Voice") {
        setLive(true);
        setHint("Sala is using Salane Voice.");
        return;
      }
      if (token.use_xai === false || !token.token || !token.session_update) {
        setHint(token.spoken_language?.hint || "This language uses the lesson voice, not Grok.");
        return;
      }
      if (!audioRef.current) audioRef.current = new AudioContext({ latencyHint: "playback" });
      const ctx = audioRef.current;
      wsRef.current = connectXaiVoiceSession(token, {
        onOpen: () => {
          setLive(true);
          setHint("Sala is listening.");
        },
        onClose: () => {
          setLive(false);
          wsRef.current = null;
        },
        onError: () => setHint("Grok voice connection error."),
        onAudioDelta: (chunk) => {
          void playPcm16Base64(chunk, ctx).catch(() => {});
        },
      });
    } catch (err) {
      setHint(err instanceof Error ? err.message : "Could not start Grok voice.");
    }
  }

  return (
    <div
      style={{
        position: "fixed",
        right: 16,
        bottom: 16,
        zIndex: 80,
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-end",
        gap: 6,
      }}
    >
      {hint ? (
        <span style={{
          maxWidth: 260,
          fontSize: 12,
          color: "#e2e8f0",
          background: "rgba(7,17,30,.92)",
          border: "1px solid #5eead4",
          borderRadius: 10,
          padding: "6px 8px",
        }}
        >
          {hint}
        </span>
      ) : null}
      <button
        type="button"
        onClick={() => { void toggle(); }}
        disabled={!ready && !live}
        title={ready ? "Talk with Serenity via Salane Voice" : "Salane Voice uses CosyVoice on the speech service"}
        style={{
          border: "1px solid #0d6e6e",
          borderRadius: 999,
          padding: "10px 14px",
          fontWeight: 800,
          cursor: ready || live ? "pointer" : "not-allowed",
          background: live ? "#0d6e6e" : "#fff",
          color: live ? "#f7faf9" : "#0d6e6e",
          opacity: !ready && !live ? 0.55 : 1,
        }}
      >
        {live ? "● Sala" : "Sala"}
      </button>
    </div>
  );
}
