"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";

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
  // This dock covers group rooms and the full course pages.
  if (pathname === "/group-classes" || pathname.startsWith("/live-room")) return "group";
  if (pathname.startsWith("/learn/")) return "solo";
  return null;
}

/** xAI Grok voice on group rooms and full course pages. Live Class and On the Go start their own session. */
export function XaiVoiceDock() {
  const pathname = usePathname() || "";
  const mode = voiceMode(pathname);
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
      setHint("Grok voice ended.");
      return;
    }
    try {
      const token = await mintXaiVoiceToken({
        mode: mode || "solo",
        lesson_context: `Salareen ${pathname}`,
      });
      if (!audioRef.current) audioRef.current = new AudioContext({ latencyHint: "playback" });
      const ctx = audioRef.current;
      wsRef.current = connectXaiVoiceSession(token, {
        onOpen: () => {
          setLive(true);
          setHint("Theodore is listening.");
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
        title={ready ? "Talk with Theodore via xAI Grok Voice" : "Set XAI_API_KEY on the speech service to enable Grok Voice"}
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
        {live ? "● Grok voice on" : "Grok voice"}
      </button>
    </div>
  );
}
