"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  CAMERA_PREF_KEY, WIDGET_POS_KEY, PresenceTracker, cameraWanted, createFaceSource,
  type FaceSource,
} from "../lib/facePresence";

export type PresenceState = "off" | "starting" | "present" | "away" | "denied" | "unsupported";

type Props = {
  /** True once the learner has tapped Start: the camera is never opened before a deliberate tap. */
  active: boolean;
  micOn: boolean;
  micAvailable: boolean;
  listening: boolean;
  onToggleMic: () => void;
  onAway: () => void;
  onBack: () => void;
  onState?: (state: PresenceState) => void;
};

const DOT: Record<PresenceState, string> = {
  off: "#6b7280", starting: "#d4af37", present: "#22c55e", away: "#f59e0b", denied: "#ef4444", unsupported: "#6b7280",
};
const TIP: Record<PresenceState, string> = {
  off: "Camera off. Audio only.",
  starting: "Starting the camera…",
  present: "Camera on. Your video stays on this device.",
  away: "You stepped away. The lesson is paused.",
  denied: "Camera blocked. Audio only. Allow it in your browser to turn this on.",
  unsupported: "Face detection is not available here. Audio only.",
};

/**
 * One small movable widget, top right: camera preview with a status dot, a camera on/off switch and a mic mute.
 * Video frames are analysed by the browser's own detector and never leave the device.
 */
export default function OnTheGoPresence({ active, micOn, micAvailable, listening, onToggleMic, onAway, onBack, onState }: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sourceRef = useRef<FaceSource | null>(null);
  const trackerRef = useRef(new PresenceTracker());
  const cbRef = useRef({ onAway, onBack, onState });
  cbRef.current = { onAway, onBack, onState };
  const [state, setStateRaw] = useState<PresenceState>("off");
  const [wanted, setWanted] = useState(true);
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const drag = useRef<{ dx: number; dy: number } | null>(null);

  const setState = useCallback((s: PresenceState) => { setStateRaw(s); cbRef.current.onState?.(s); }, []);

  useEffect(() => {
    try { setWanted(cameraWanted(window.localStorage)); } catch { /* private mode */ }
    try {
      const raw = window.localStorage.getItem(WIDGET_POS_KEY);
      if (raw) {
        const p = JSON.parse(raw);
        if (Number.isFinite(p?.x) && Number.isFinite(p?.y)) setPos({ x: p.x, y: p.y });
      }
    } catch { /* ignore */ }
  }, []);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    sourceRef.current?.close();
    sourceRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    trackerRef.current.reset();
  }, []);

  // Camera lifecycle: only after Start, only if wanted, and closed whenever the tab is hidden.
  useEffect(() => {
    if (!active || !wanted) { stopCamera(); setState("off"); return; }
    let cancelled = false;
    let timer: number | null = null;
    let busy = false;

    const begin = async () => {
      if (cancelled || streamRef.current) return;
      if (!navigator.mediaDevices?.getUserMedia || !window.isSecureContext) { setState("unsupported"); return; }
      setState("starting");
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "user", width: { ideal: 320 }, height: { ideal: 240 }, frameRate: { ideal: 15, max: 24 } },
          audio: false,
        });
        if (cancelled) { stream.getTracks().forEach((t) => t.stop()); return; }
        streamRef.current = stream;
        const video = videoRef.current;
        if (video) { video.srcObject = stream; await video.play().catch(() => {}); }
      } catch (e) {
        const name = (e as { name?: string })?.name || "";
        setState(name === "NotAllowedError" || name === "SecurityError" ? "denied" : "unsupported");
        return;
      }
      const source = await createFaceSource();
      if (cancelled) { source?.close(); return; }
      if (!source) { setState("unsupported"); return; }
      sourceRef.current = source;
      setState("present");
      timer = window.setInterval(async () => {
        const v = videoRef.current;
        if (busy || !v || v.readyState < 2 || !sourceRef.current) return;
        busy = true;
        try {
          const reading = await sourceRef.current.detect(v, performance.now());
          const ev = trackerRef.current.update(reading.present, performance.now());
          if (ev === "away") { setState("away"); cbRef.current.onAway(); }
          if (ev === "back") { setState("present"); cbRef.current.onBack(); }
        } catch { /* a dropped frame is not an event */ }
        finally { busy = false; }
      }, 250);
    };

    const onVisibility = () => {
      if (document.hidden) {
        if (timer) { window.clearInterval(timer); timer = null; }
        stopCamera();
      } else {
        void begin();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    if (!document.hidden) void begin();
    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onVisibility);
      if (timer) window.clearInterval(timer);
      stopCamera();
    };
  }, [active, wanted, setState, stopCamera]);

  function toggleCamera() {
    const next = !wanted;
    setWanted(next);
    try { window.localStorage.setItem(CAMERA_PREF_KEY, next ? "on" : "off"); } catch { /* private mode */ }
  }

  function onPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    if ((e.target as HTMLElement).closest("button")) return;
    const rect = e.currentTarget.getBoundingClientRect();
    drag.current = { dx: e.clientX - rect.left, dy: e.clientY - rect.top };
    e.currentTarget.setPointerCapture(e.pointerId);
  }
  function onPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    if (!drag.current) return;
    const w = e.currentTarget.offsetWidth, h = e.currentTarget.offsetHeight;
    const x = Math.min(Math.max(4, e.clientX - drag.current.dx), window.innerWidth - w - 4);
    const y = Math.min(Math.max(4, e.clientY - drag.current.dy), window.innerHeight - h - 4);
    setPos({ x, y });
  }
  function onPointerUp() {
    if (!drag.current) return;
    drag.current = null;
    try { if (pos) window.localStorage.setItem(WIDGET_POS_KEY, JSON.stringify(pos)); } catch { /* ignore */ }
  }

  const cameraLive = state === "present" || state === "away" || state === "starting";
  const style: React.CSSProperties = pos
    ? { left: pos.x, top: pos.y }
    : { right: 14, top: 62 };

  return (
    <div
      data-testid="on-the-go-presence"
      data-state={state}
      title={TIP[state]}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      style={{
        position: "fixed", zIndex: 55, ...style, width: 132, touchAction: "none", cursor: "grab",
        background: "#0b1020", border: "1.5px solid rgba(212,175,55,.85)", borderRadius: 14,
        boxShadow: "0 6px 20px rgba(0,0,0,.35)", padding: 6, userSelect: "none",
      }}
    >
      <div style={{ position: "relative", width: 120, height: 90, borderRadius: 9, overflow: "hidden", background: "#070b14" }}>
        <video
          ref={videoRef} muted playsInline aria-hidden
          style={{ width: "100%", height: "100%", objectFit: "cover", transform: "scaleX(-1)", display: cameraLive ? "block" : "none" }}
        />
        {!cameraLive && (
          <div aria-hidden style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", color: "#9fbac2", fontSize: 22 }}>
            {state === "denied" ? "🚫" : "🎧"}
          </div>
        )}
        <span
          data-testid="on-the-go-presence-dot" aria-label={TIP[state]}
          style={{ position: "absolute", left: 6, top: 6, width: 10, height: 10, borderRadius: "50%", background: DOT[state], boxShadow: "0 0 0 2px rgba(11,16,32,.8)" }}
        />
        {cameraLive && (
          <span
            data-testid="on-the-go-camera-on" role="img" aria-label="Camera on" title="Camera on. Your video stays on this device."
            style={{ position: "absolute", right: 7, top: 6, width: 9, height: 9, borderRadius: "50%", background: "#ef4444", boxShadow: "0 0 0 2px rgba(11,16,32,.8)" }}
          />
        )}
      </div>
      <div style={{ display: "flex", gap: 6, marginTop: 6, justifyContent: "space-between" }}>
        <button
          type="button" data-testid="on-the-go-mic-toggle"
          aria-pressed={micOn} disabled={!micAvailable}
          aria-label={micOn ? "Mute microphone" : "Turn microphone on"} title={micAvailable ? (micOn ? "Mic on: say Hey Sala or ask a question. Tap to mute." : "Mic muted. Tap to listen again.") : "Microphone not available here."}
          onClick={onToggleMic}
          style={{ flex: 1, height: 30, borderRadius: 8, border: `1.5px solid ${micOn && listening ? "#22c55e" : "rgba(212,175,55,.7)"}`, background: "#101820", color: micOn ? "#e8ecf6" : "#9ca3af", cursor: "pointer", fontSize: 15 }}
        >{micOn ? "🎙" : "🔇"}</button>
        <button
          type="button" data-testid="on-the-go-camera-toggle"
          aria-pressed={wanted}
          aria-label={wanted ? "Turn the camera off" : "Turn the camera on"} title={wanted ? "Camera on. Tap to turn off." : "Camera off. Tap to turn on."}
          onClick={toggleCamera}
          style={{ flex: 1, height: 30, borderRadius: 8, border: "1.5px solid rgba(212,175,55,.7)", background: "#101820", color: wanted ? "#e8ecf6" : "#9ca3af", cursor: "pointer", fontSize: 15 }}
        >{wanted ? "📷" : "🚫"}</button>
      </div>
    </div>
  );
}
