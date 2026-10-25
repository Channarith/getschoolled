"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import {
  CAMERA_PREF_KEY, WIDGET_POS_KEY, PresenceTracker, cameraWanted, createFaceSource,
  type FaceSource,
} from "../lib/facePresence";
import OnTheGoAvatar, { type AvatarState } from "./OnTheGoAvatar";

export type PresenceState = "off" | "starting" | "present" | "away" | "denied" | "unsupported";

const MIN_KEY = "salareen.onTheGo.widgetMin.v1";
const LONG_PRESS_MS = 650;

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
  /** Sala head. Tap = ask or listen; long-press = mute or unmute. */
  salaState: AvatarState;
  salaLabel: string;
  salaAriaLabel: string;
  signInHref?: string;
  onSalaActivate: () => void;
  /** Demo timer (anonymous demo only): shown in the widget bar. */
  timer?: { label: string; ended: boolean; ariaLabel: string };
  /** Everything else lives in the three-dot menu. */
  menu: {
    voiceSlot?: ReactNode;
    onFullscreen?: () => void;
    onHelp?: () => void;
    onPrivacy?: () => void;
    headphoneHint: string;
    labels: {
      menu: string; minimize: string; expand: string; mic: string; micOn: string; micMuted: string; camera: string; cameraOn: string; cameraOff: string;
      fullscreen: string; help: string; privacy: string;
    };
  };
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
 * ONE small movable widget, top right: the golden Sala head over a camera preview, a status dot, the demo timer, a minimise button and a
 * three-dot menu (microphone, camera, voice, full screen, help, privacy). There are no standalone mic or camera buttons.
 * Video frames are analysed by the browser's own detector and never leave the device.
 */
export default function OnTheGoPresence({
  active, micOn, micAvailable, listening, onToggleMic, onAway, onBack, onState,
  salaState, salaLabel, salaAriaLabel, signInHref, onSalaActivate, timer, menu,
}: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sourceRef = useRef<FaceSource | null>(null);
  const trackerRef = useRef(new PresenceTracker());
  const cbRef = useRef({ onAway, onBack, onState });
  cbRef.current = { onAway, onBack, onState };
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [state, setStateRaw] = useState<PresenceState>("off");
  const [wanted, setWanted] = useState(true);
  const [minimized, setMinimized] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const drag = useRef<{ dx: number; dy: number } | null>(null);
  const pressTimer = useRef<number | null>(null);
  const longPressed = useRef(false);

  const setState = useCallback((s: PresenceState) => { setStateRaw(s); cbRef.current.onState?.(s); }, []);

  useEffect(() => {
    try { setWanted(cameraWanted(window.localStorage)); } catch { /* private mode */ }
    try { setMinimized(window.localStorage.getItem(MIN_KEY) === "1"); } catch { /* private mode */ }
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
    let timerId: number | null = null;
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
      timerId = window.setInterval(async () => {
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
        if (timerId) { window.clearInterval(timerId); timerId = null; }
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
      if (timerId) window.clearInterval(timerId);
      stopCamera();
    };
  }, [active, wanted, setState, stopCamera]);

  // The menu closes on Escape or a tap outside the widget.
  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setMenuOpen(false); };
    const onDown = (e: PointerEvent) => { if (rootRef.current && !rootRef.current.contains(e.target as Node)) setMenuOpen(false); };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    return () => { document.removeEventListener("keydown", onKey); document.removeEventListener("pointerdown", onDown); };
  }, [menuOpen]);

  function toggleCamera() {
    const next = !wanted;
    setWanted(next);
    try { window.localStorage.setItem(CAMERA_PREF_KEY, next ? "on" : "off"); } catch { /* private mode */ }
  }

  function toggleMinimized() {
    const next = !minimized;
    setMinimized(next);
    try { window.localStorage.setItem(MIN_KEY, next ? "1" : "0"); } catch { /* private mode */ }
  }

  // Drag ONLY from the grip (the dotted handle and the empty part of the bar). Never from the Sala head or the preview: a side-to-side scrub
  // over Sala must make her dance, not move the widget.
  function onPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    if (!(e.target as HTMLElement).closest("[data-grip]") || (e.target as HTMLElement).closest("button, a, select, label, [role=menu]")) return;
    const rect = e.currentTarget.getBoundingClientRect();
    drag.current = { dx: e.clientX - rect.left, dy: e.clientY - rect.top };
    try { e.currentTarget.setPointerCapture(e.pointerId); } catch { /* synthetic or already released pointer */ }
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

  // Sala head: tap = ask or listen, long-press = mute or unmute the microphone.
  const headStart = useRef<{ x: number; y: number } | null>(null);
  function headMove(e: React.PointerEvent) {
    const st = headStart.current;
    if (!st || !pressTimer.current) return;
    if (Math.hypot(e.clientX - st.x, e.clientY - st.y) > 10) { window.clearTimeout(pressTimer.current); pressTimer.current = null; }   // a scrub is not a long-press
  }
  function headDown(e: React.PointerEvent) {
    headStart.current = { x: e.clientX, y: e.clientY };
    longPressed.current = false;
    if (pressTimer.current) window.clearTimeout(pressTimer.current);
    pressTimer.current = window.setTimeout(() => {
      longPressed.current = true;
      if (micAvailable) onToggleMic();
    }, LONG_PRESS_MS);
  }
  function headUp() {
    if (pressTimer.current) { window.clearTimeout(pressTimer.current); pressTimer.current = null; }
  }
  function headActivate() {
    if (longPressed.current) { longPressed.current = false; return; }
    onSalaActivate();
  }

  const cameraLive = state === "present" || state === "away" || state === "starting";
  const style: React.CSSProperties = pos ? { left: pos.x, top: pos.y } : { right: 14, top: 62 };
  const L = menu.labels;
  const itemStyle: React.CSSProperties = {
    width: "100%", minHeight: 40, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, padding: "0 10px", borderRadius: 8,
    border: 0, background: "transparent", color: "#e8ecf6", fontSize: 14, textAlign: "start", cursor: "pointer",
  };
  const barBtn: React.CSSProperties = {
    width: 28, height: 28, borderRadius: 8, border: "1px solid rgba(212,175,55,.55)", background: "#101820", color: "#f4fbff", cursor: "pointer", fontSize: 14, lineHeight: 1, padding: 0,
  };

  return (
    <div
      ref={rootRef}
      data-testid="on-the-go-presence"
      data-widget="combined"
      data-state={state}
      data-minimized={minimized ? "1" : "0"}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      style={{
        position: "fixed", zIndex: 55, ...style, width: minimized ? "auto" : 148, maxWidth: "calc(100vw - 8px)", touchAction: "manipulation",
        background: "#0b1020", border: "1.5px solid rgba(212,175,55,.85)", borderRadius: 14,
        boxShadow: "0 6px 20px rgba(0,0,0,.35)", padding: 6, userSelect: "none",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, minHeight: 28 }}>
        <span aria-hidden data-grip data-testid="on-the-go-widget-grip" style={{ color: "rgba(212,175,55,.8)", fontSize: 12, letterSpacing: -2, cursor: "grab", touchAction: "none", padding: "6px 2px" }}>⋮⋮</span>
        <span
          data-testid="on-the-go-presence-dot" role="img" aria-label={TIP[state]} title={TIP[state]}
          style={{ width: 10, height: 10, borderRadius: "50%", background: DOT[state], boxShadow: "0 0 0 2px rgba(11,16,32,.8)", flexShrink: 0 }}
        />
        {timer && (
          <span
            data-testid="on-the-go-timer" role="timer" aria-live="polite" aria-atomic="true" aria-label={timer.ariaLabel}
            style={{ color: timer.ended ? "#fca5a5" : "rgba(255,255,255,.75)", fontSize: 13, fontWeight: 600, fontVariantNumeric: "tabular-nums" }}
          >{timer.label}</span>
        )}
        <span data-grip aria-hidden style={{ flex: 1, alignSelf: "stretch", minHeight: 28, cursor: "grab", touchAction: "none" }} />
        {menu.onHelp && (
          <button type="button" data-testid="on-the-go-help" aria-label={L.help} title={L.help} onClick={menu.onHelp} style={{ ...barBtn, fontWeight: 800, color: "#fde047" }}>?</button>
        )}
        <button type="button" data-testid="on-the-go-widget-min" aria-label={minimized ? L.expand : L.minimize} title={minimized ? L.expand : L.minimize} aria-pressed={minimized} onClick={toggleMinimized} style={barBtn}>
          {minimized ? "+" : "–"}
        </button>
        <button
          type="button" data-testid="on-the-go-widget-menu" aria-label={L.menu} title={L.menu} aria-haspopup="menu" aria-expanded={menuOpen}
          onClick={() => setMenuOpen((v) => !v)} style={barBtn}
        >⋯</button>
      </div>

      <div
        style={minimized
          ? { display: "flex", alignItems: "center", marginTop: 4 }
          : { position: "relative", width: 136, height: 102, marginTop: 6, borderRadius: 9, overflow: "hidden", background: "#070b14" }}
      >
        <video
          ref={videoRef} muted playsInline aria-hidden
          style={minimized
            ? { position: "absolute", width: 2, height: 2, opacity: 0.01, pointerEvents: "none" }
            : { width: "100%", height: "100%", objectFit: "cover", transform: "scaleX(-1)", display: cameraLive ? "block" : "none" }}
        />
        {!minimized && !cameraLive && (
          <div aria-hidden style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", color: "#9fbac2", fontSize: 22 }}>
            {state === "denied" ? "🚫" : "🎧"}
          </div>
        )}
        {!minimized && cameraLive && (
          <span
            data-testid="on-the-go-camera-on" role="img" aria-label="Camera on" title={TIP.present}
            style={{ position: "absolute", right: 7, top: 6, width: 9, height: 9, borderRadius: "50%", background: "#ef4444", boxShadow: "0 0 0 2px rgba(11,16,32,.8)" }}
          />
        )}
        <div
          onPointerDown={headDown} onPointerMove={headMove} onPointerUp={headUp} onPointerLeave={headUp} onPointerCancel={headUp}
          style={minimized ? { display: "flex" } : { position: "absolute", left: 6, bottom: 6 }}
        >
          <OnTheGoAvatar
            state={salaState} label={salaLabel} ariaLabel={salaAriaLabel} signInHref={signInHref} onActivate={headActivate}
            size={minimized ? 44 : 56} showLabel={false}
          />
        </div>
      </div>

      {menuOpen && (
        <div
          role="menu" aria-label={L.menu} data-testid="on-the-go-widget-menu-list"
          style={{
            position: "absolute", right: 0, top: "calc(100% + 6px)", width: 236, maxWidth: "calc(100vw - 16px)", zIndex: 2, cursor: "default",
            background: "#0b1020", border: "1.5px solid rgba(212,175,55,.85)", borderRadius: 12, padding: 6, boxShadow: "0 12px 30px rgba(0,0,0,.5)",
          }}
        >
          <button
            type="button" role="menuitemcheckbox" aria-checked={micOn} data-testid="on-the-go-mic-toggle" disabled={!micAvailable}
            onClick={onToggleMic} style={{ ...itemStyle, opacity: micAvailable ? 1 : 0.5 }}
          >
            <span>{L.mic}</span>
            <span style={{ color: micOn && listening ? "#86efac" : "#9fbac2" }}>{micOn ? L.micOn : L.micMuted}</span>
          </button>
          <button
            type="button" role="menuitemcheckbox" aria-checked={wanted} data-testid="on-the-go-camera-toggle"
            onClick={toggleCamera} style={itemStyle}
          >
            <span>{L.camera}</span>
            <span style={{ color: wanted ? "#86efac" : "#9fbac2" }}>{wanted ? L.cameraOn : L.cameraOff}</span>
          </button>
          {menu.voiceSlot && (
            <div role="none" style={{ padding: "4px 10px 6px", fontSize: 14 }}>{menu.voiceSlot}</div>
          )}
          {menu.onFullscreen && (
            <button type="button" role="menuitem" data-testid="on-the-go-fullscreen" onClick={() => { setMenuOpen(false); menu.onFullscreen?.(); }} style={itemStyle}>
              <span>{L.fullscreen}</span>
            </button>
          )}
          {menu.onPrivacy && (
            <button type="button" role="menuitem" data-testid="otg-privacy-choices" onClick={() => { setMenuOpen(false); menu.onPrivacy?.(); }} style={itemStyle}>
              <span>{L.privacy}</span>
            </button>
          )}
          <p role="none" style={{ margin: "4px 10px 6px", fontSize: 12, lineHeight: 1.35, color: "#9fbac2" }}>{menu.headphoneHint}</p>
        </div>
      )}
    </div>
  );
}
