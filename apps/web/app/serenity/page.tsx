"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { SERENITY_HERO_PATH, SERENITY_VOICE_INSTRUCTIONS } from "../lib/serenity";
import {
  closeXaiVoiceSession,
  connectXaiVoiceSession,
  getXaiVoiceStatus,
  mintXaiVoiceToken,
  playPcm16Base64,
  resetPcmPlayback,
  sendTextTurn,
} from "../lib/xaiVoice";

const LINES = [
  {
    id: "en",
    label: "English",
    text: "Hello. I am Serenity, your holographic AI teacher. Let's learn together.",
  },
  {
    id: "es",
    label: "Spanish",
    text: "Hola. Soy Serenity, tu profesora holográfica. Aprendamos juntos.",
  },
  {
    id: "ar",
    label: "Arabic",
    text: "مرحبا. أنا سيرينيتي، معلمتك الهولوغرامية. هيا نتعلم معاً.",
  },
  {
    id: "lesson",
    label: "Lesson cue",
    text: "Watch my mouth. When I speak through Salane Voice, these blendshapes follow the audio energy until Wav2ARKit is wired in.",
  },
] as const;

type FaceLive = {
  mouthOpen: number;
  smile: number;
  eyelids: number;
  ears: number;
  headTilt: number;
};

function clamp01(n: number): number {
  return Math.max(0, Math.min(1, n));
}

/** RMS of base64 PCM16 LE — drives jawOpen until Wav2ARKit is connected. */
function pcmRms(base64: string): number {
  try {
    const raw = atob(base64);
    const n = Math.floor(raw.length / 2);
    if (n < 8) return 0;
    let sum = 0;
    let count = 0;
    for (let i = 0; i < n; i += 4) {
      const lo = raw.charCodeAt(i * 2);
      const hi = raw.charCodeAt(i * 2 + 1);
      const s = (hi << 8) | lo;
      const v = s > 32767 ? s - 65536 : s;
      sum += (v / 32768) * (v / 32768);
      count += 1;
    }
    return Math.sqrt(sum / Math.max(1, count));
  } catch {
    return 0;
  }
}

export default function SerenityPage() {
  const [lineId, setLineId] = useState<string>("en");
  const [custom, setCustom] = useState(
    "Hello. I am Serenity, your holographic AI teacher.",
  );
  const [ready, setReady] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [talking, setTalking] = useState(false);
  const [sessionLive, setSessionLive] = useState(false);
  const [hint, setHint] = useState("");
  const [caption, setCaption] = useState("");
  const [live, setLive] = useState<FaceLive>({
    mouthOpen: 0.1,
    smile: 0.35,
    eyelids: 0.05,
    ears: 0.18,
    headTilt: 0,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const audioRef = useRef<AudioContext | null>(null);
  const energyRef = useRef(0);
  const talkingRef = useRef(false);
  const endTimerRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);
  const t0Ref = useRef(0);

  const phrase =
    lineId === "custom"
      ? custom
      : LINES.find((l) => l.id === lineId)?.text || LINES[0].text;

  useEffect(() => {
    let alive = true;
    getXaiVoiceStatus()
      .then((status) => {
        if (!alive) return;
        setReady(Boolean(status.available));
        if (!status.available) {
          setHint(
            status.hint ||
              "Start speech (:8002) with XAI_API_KEY in config/local.env",
          );
        } else {
          setHint(`xAI ready · ${status.model || "grok-voice-latest"} · voice ${status.voice || "ara"}`);
        }
      })
      .catch(() => {
        if (alive) {
          setReady(false);
          setHint("Speech service unreachable at :8002 — run make run-speech");
        }
      });
    return () => {
      alive = false;
      closeXaiVoiceSession(wsRef.current);
      wsRef.current = null;
      void audioRef.current?.close().catch(() => {});
      audioRef.current = null;
      if (endTimerRef.current != null) window.clearTimeout(endTimerRef.current);
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  useEffect(() => {
    t0Ref.current = performance.now();
    const tick = (now: number) => {
      const t = (now - t0Ref.current) / 1000;
      const blinkPhase = (t % 3.2) / 3.2;
      const blink =
        blinkPhase > 0.92
          ? clamp01((blinkPhase - 0.92) / 0.04) *
            (1 - clamp01((blinkPhase - 0.96) / 0.04))
          : 0;

      const energy = energyRef.current;
      energyRef.current *= 0.86;

      let mouth = 0.08 + 0.03 * Math.sin(t * 1.1);
      let smile = 0.32 + 0.05 * Math.sin(t * 0.65);
      let ears = 0.16 + 0.04 * Math.sin(t * 0.85 + 1);
      let eyelids = blink;
      let headTilt = 0.025 * Math.sin(t * 0.5);

      if (talkingRef.current) {
        mouth = clamp01(0.12 + energy * 4.2);
        smile = clamp01(0.38 + energy * 1.2 + 0.08 * Math.sin(t * 2.2));
        ears = clamp01(0.22 + energy * 0.9);
        eyelids = Math.max(eyelids, 0.02 + energy * 0.15);
        headTilt = 0.06 * Math.sin(t * 1.8);
      }

      setLive({
        mouthOpen: clamp01(mouth),
        smile: clamp01(smile),
        eyelids: clamp01(eyelids),
        ears: clamp01(ears),
        headTilt,
      });
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  const markSpeaking = useCallback((on: boolean) => {
    talkingRef.current = on;
    setTalking(on);
    if (endTimerRef.current != null) {
      window.clearTimeout(endTimerRef.current);
      endTimerRef.current = null;
    }
    if (on) {
      endTimerRef.current = window.setTimeout(() => {
        talkingRef.current = false;
        setTalking(false);
        energyRef.current = 0;
      }, 900);
    }
  }, []);

  async function ensureSession(): Promise<WebSocket | null> {
    if (wsRef.current?.readyState === WebSocket.OPEN) return wsRef.current;
    setConnecting(true);
    try {
      const token = await mintXaiVoiceToken({
        mode: "solo",
        lesson_context: "Project Serenity holographic AI teacher avatar",
        instructions:
          SERENITY_VOICE_INSTRUCTIONS +
          " When asked to read a line, speak it warmly and clearly, then stop. Do not ask follow-up questions unless asked.",
        language: "en",
      });
      if (token.use_xai === false || !token.token || !token.session_update) {
        setHint(
          token.spoken_language?.hint ||
            "xAI voice not available for this language.",
        );
        return null;
      }
      if (!audioRef.current) {
        audioRef.current = new AudioContext({ latencyHint: "playback" });
      }
      const ctx = audioRef.current;
      await ctx.resume().catch(() => {});

      let resolveOpen: () => void;
      let rejectOpen: (err: Error) => void;
      const opened = new Promise<void>((resolve, reject) => {
        resolveOpen = resolve;
        rejectOpen = reject;
      });
      const openTimer = window.setTimeout(
        () => rejectOpen(new Error("xAI connect timeout")),
        12000,
      );

      const ws = connectXaiVoiceSession(token, {
        onOpen: () => {
          window.clearTimeout(openTimer);
          setSessionLive(true);
          setHint("Serenity connected via Salane Voice.");
          resolveOpen();
        },
        onClose: () => {
          setSessionLive(false);
          wsRef.current = null;
          markSpeaking(false);
        },
        onError: () => {
          window.clearTimeout(openTimer);
          setHint("xAI voice connection error — check XAI_API_KEY / speech :8002");
          rejectOpen(new Error("xAI websocket error"));
        },
        onAudioDelta: (chunk) => {
          const rms = pcmRms(chunk);
          energyRef.current = Math.max(energyRef.current * 0.55, rms);
          markSpeaking(true);
          void playPcm16Base64(chunk, ctx).catch(() => {});
        },
        onTranscriptDelta: (text) => {
          if (text) setCaption((c) => (c.endsWith(text) ? c : c + text));
        },
        onTranscriptDone: (text) => {
          if (text) setCaption(text);
        },
      });
      wsRef.current = ws;
      await opened;
      await new Promise((r) => setTimeout(r, 250));
      return ws;
    } catch (err) {
      setHint(err instanceof Error ? err.message : "Could not start xAI voice");
      return null;
    } finally {
      setConnecting(false);
    }
  }

  async function talk() {
    const text = phrase.trim();
    if (!text) return;
    setCaption(text);
    const ws = await ensureSession();
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    if (audioRef.current) resetPcmPlayback(audioRef.current);
    energyRef.current = 0.2;
    markSpeaking(true);
    sendTextTurn(
      ws,
      `Read this aloud as Serenity, then stop. Do not ask a question.\n\n${text}`,
    );
  }

  function stop() {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify({ type: "response.cancel" }));
      } catch {
        /* ignore */
      }
    }
    if (audioRef.current) resetPcmPlayback(audioRef.current);
    markSpeaking(false);
    setCaption("");
    energyRef.current = 0;
  }

  function disconnect() {
    stop();
    closeXaiVoiceSession(wsRef.current);
    wsRef.current = null;
    setSessionLive(false);
    setHint(ready ? "Disconnected. Talk will reconnect to xAI." : hint);
  }


  return (
    <main
      style={{
        minHeight: "100vh",
        background: "linear-gradient(160deg, #07101c 0%, #0d2137 45%, #122a22 100%)",
        color: "#e8f1f8",
        padding: "28px 20px 64px",
        fontFamily: "Georgia, 'Times New Roman', serif",
      }}
    >
      <div style={{ maxWidth: 1080, margin: "0 auto" }}>
        <p style={{ margin: "0 0 8px", fontSize: 13, opacity: 0.7 }}>
          <Link href="/" style={{ color: "#7dd3c0" }}>
            Salareen
          </Link>
          {" · Project Serenity"}
        </p>
        <h1 style={{ margin: "0 0 8px", fontSize: 36, fontWeight: 700, letterSpacing: "-0.02em" }}>
          Serenity
        </h1>
        <p style={{ margin: "0 0 20px", maxWidth: 560, lineHeight: 1.45, opacity: 0.85 }}>
          Holographic AI teacher — Gemini keyframe face (real lips + blinks, no oval
          mouth stickers). Voice via xAI Grok on the speech gateway. Course Studio
          uses the same Serenity keyframes for demo and full lessons.
        </p>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 1.1fr) minmax(280px, 0.9fr)",
            gap: 20,
            alignItems: "start",
          }}
        >
          <section
            style={{
              position: "relative",
              borderRadius: 12,
              overflow: "hidden",
              border: "1px solid rgba(125, 211, 192, 0.35)",
              background: "#0a1624",
              aspectRatio: "3 / 4",
              transform: `perspective(900px) rotateY(${live.headTilt * 14}deg)`,
            }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={SERENITY_HERO_PATH}
              alt="Serenity holographic AI teacher"
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                objectPosition: "center top",
                filter: talking ? "brightness(1.03)" : "none",
              }}
            />
            <div
              style={{
                position: "absolute",
                left: 12,
                bottom: 12,
                padding: "6px 10px",
                borderRadius: 8,
                background: "rgba(7,16,28,0.82)",
                border: "1px solid rgba(125,211,192,0.4)",
                fontSize: 12,
                fontFamily: "ui-sans-serif, system-ui, sans-serif",
              }}
            >
              {talking ? "● Speaking (xAI)" : sessionLive ? "Connected" : "Idle"}
            </div>
          </section>

          <aside
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 14,
              fontFamily: "ui-sans-serif, system-ui, sans-serif",
            }}
          >
            <div
              style={{
                padding: 16,
                borderRadius: 12,
                background: "rgba(10,22,36,0.9)",
                border: "1px solid rgba(125,211,192,0.28)",
              }}
            >
              <h2 style={{ margin: "0 0 12px", fontSize: 16 }}>Talk with Sala</h2>
              <label style={{ display: "block", fontSize: 12, opacity: 0.75, marginBottom: 6 }}>
                Line
              </label>
              <select
                value={lineId}
                onChange={(e) => setLineId(e.target.value)}
                style={{
                  width: "100%",
                  marginBottom: 10,
                  padding: "8px 10px",
                  borderRadius: 8,
                  border: "1px solid #2a4a5c",
                  background: "#0d1b2a",
                  color: "#e8f1f8",
                }}
              >
                {LINES.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.label}
                  </option>
                ))}
                <option value="custom">Custom</option>
              </select>
              {lineId === "custom" ? (
                <textarea
                  value={custom}
                  onChange={(e) => setCustom(e.target.value)}
                  rows={3}
                  style={{
                    width: "100%",
                    marginBottom: 10,
                    padding: 10,
                    borderRadius: 8,
                    border: "1px solid #2a4a5c",
                    background: "#0d1b2a",
                    color: "#e8f1f8",
                    resize: "vertical",
                  }}
                />
              ) : null}
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                <button
                  type="button"
                  onClick={() => void talk()}
                  disabled={!ready || connecting}
                  style={{
                    padding: "10px 16px",
                    borderRadius: 999,
                    border: "none",
                    fontWeight: 700,
                    cursor: ready && !connecting ? "pointer" : "not-allowed",
                    background: "#14b8a6",
                    color: "#042f2e",
                    opacity: !ready || connecting ? 0.5 : 1,
                  }}
                >
                  {connecting ? "Connecting…" : "Talk"}
                </button>
                <button
                  type="button"
                  onClick={stop}
                  disabled={!talking}
                  style={{
                    padding: "10px 16px",
                    borderRadius: 999,
                    border: "1px solid #5eead4",
                    background: "transparent",
                    color: "#99f6e4",
                    fontWeight: 600,
                    cursor: talking ? "pointer" : "not-allowed",
                    opacity: talking ? 1 : 0.4,
                  }}
                >
                  Stop
                </button>
                <button
                  type="button"
                  onClick={disconnect}
                  disabled={!sessionLive}
                  style={{
                    padding: "10px 16px",
                    borderRadius: 999,
                    border: "1px solid #475569",
                    background: "transparent",
                    color: "#cbd5e1",
                    fontWeight: 600,
                    cursor: sessionLive ? "pointer" : "not-allowed",
                    opacity: sessionLive ? 1 : 0.4,
                  }}
                >
                  Disconnect
                </button>
              </div>
              <p style={{ margin: "12px 0 0", fontSize: 12, lineHeight: 1.4, opacity: 0.8 }}>
                {hint}
              </p>
              {caption ? (
                <p style={{ margin: "10px 0 0", fontSize: 14, lineHeight: 1.4 }}>
                  {caption}
                </p>
              ) : null}
            </div>

            <div
              style={{
                padding: 16,
                borderRadius: 12,
                background: "rgba(10,22,36,0.9)",
                border: "1px solid rgba(125,211,192,0.28)",
              }}
            >
              <h2 style={{ margin: "0 0 10px", fontSize: 16 }}>Live blendshapes</h2>
              {(
                [
                  ["jawOpen", live.mouthOpen],
                  ["mouthSmile", live.smile],
                  ["eyeBlink", live.eyelids],
                  ["earFlex", live.ears],
                ] as const
              ).map(([name, value]) => (
                <div key={name} style={{ marginBottom: 10 }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: 12,
                      marginBottom: 4,
                    }}
                  >
                    <span>{name}</span>
                    <span>{value.toFixed(2)}</span>
                  </div>
                  <div
                    style={{
                      height: 6,
                      borderRadius: 3,
                      background: "rgba(148,163,184,0.25)",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${Math.round(value * 100)}%`,
                        height: "100%",
                        background: "#2dd4bf",
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </aside>
        </div>
      </div>
    </main>
  );
}
