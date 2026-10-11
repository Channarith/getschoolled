"use client";

import { useEffect, useRef, useState } from "react";

const POS_KEY = "aoep.driveVoice.pos";

function connectionChime(ok: boolean) {
  try {
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = ok ? 880 : 196;
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.08, ctx.currentTime + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + (ok ? 0.16 : 0.28));
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.3);
    osc.onended = () => { void ctx.close(); };
  } catch { /* a silent page still shows the status line */ }
}

/** Small xAI control for On the Go. Drag it off the page. The × hides it. */
export default function DriveVoiceChip({
  live,
  hidden,
  dismissed,
  onToggle,
  onHide,
  onShow,
}: {
  live: boolean;
  hidden: boolean;
  dismissed: boolean;
  onToggle: () => void;
  onHide: () => void;
  onShow: () => void;
}) {
  const chipRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);
  const drag = useRef<{ id: number; x: number; y: number; left: number; top: number; moved: boolean } | null>(null);
  const swallowClick = useRef(false);
  const heard = useRef(false);

  useEffect(() => {
    if (!heard.current) {
      heard.current = true;
      return;
    }
    connectionChime(live);
  }, [live]);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(POS_KEY) || "null") as { left?: number; top?: number } | null;
      if (saved && Number.isFinite(saved.left) && Number.isFinite(saved.top)) {
        setPos({ left: saved.left as number, top: saved.top as number });
      }
    } catch { /* keep the default corner */ }
  }, []);

  function place(left: number, top: number) {
    const chip = chipRef.current;
    const width = chip?.offsetWidth || 132;
    const height = chip?.offsetHeight || 48;
    const x = Math.max(8, Math.min(window.innerWidth - width - 8, left));
    const y = Math.max(8, Math.min(window.innerHeight - height - 8, top));
    setPos({ left: x, top: y });
    try { localStorage.setItem(POS_KEY, JSON.stringify({ left: x, top: y })); } catch { /* private mode */ }
  }

  if (hidden) return null;
  if (dismissed) {
    return (
      <button
        type="button"
        onClick={onShow}
        style={{
          position: "fixed",
          zIndex: 40,
          left: 12,
          bottom: "max(18px, env(safe-area-inset-bottom))",
          minHeight: 40,
          padding: "0 14px",
          borderRadius: 14,
          border: "1px solid #5eead4",
          background: "#07111ef2",
          color: "#e7fbff",
          fontWeight: 700,
          cursor: "pointer",
        }}
      >
        Show xAI
      </button>
    );
  }

  return (
    <div
      ref={chipRef}
      title="Drag the xAI voice. Tap the microphone to start or stop."
      onPointerDown={(event) => {
        if (event.button !== 0) return;
        if ((event.target as HTMLElement).closest("button.close")) return;
        const rect = chipRef.current?.getBoundingClientRect();
        drag.current = {
          id: event.pointerId,
          x: event.clientX,
          y: event.clientY,
          left: rect?.left ?? 12,
          top: rect?.top ?? window.innerHeight - 66,
          moved: false,
        };
      }}
      onPointerMove={(event) => {
        const current = drag.current;
        if (!current || event.pointerId !== current.id) return;
        const dx = event.clientX - current.x;
        const dy = event.clientY - current.y;
        if (!current.moved && Math.hypot(dx, dy) < 8) return;
        current.moved = true;
        place(current.left + dx, current.top + dy);
        event.preventDefault();
      }}
      onPointerUp={(event) => {
        const current = drag.current;
        if (!current || event.pointerId !== current.id) return;
        const moved = current.moved;
        drag.current = null;
        if (moved) swallowClick.current = true;
      }}
      style={{
        position: "fixed",
        zIndex: 80,
        left: pos?.left ?? 12,
        top: pos?.top,
        bottom: pos ? undefined : 18,
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "4px 8px 4px 4px",
        borderRadius: 18,
        width: "min(260px, calc(100vw - 24px))",
        minHeight: 56,
        height: "auto",
        flexWrap: "wrap",
        border: "1px solid #5eead4",
        background: "rgba(7,17,30,.95)",
        color: "#e7fbff",
        boxShadow: "0 8px 18px #0008",
        touchAction: "none",
        cursor: "grab",
      }}
    >
      <button
        type="button"
        aria-label={live ? "Stop xAI voice" : "Start xAI voice"}
        onClick={() => {
          if (swallowClick.current) {
            swallowClick.current = false;
            return;
          }
          onToggle();
        }}
        style={{
          width: 40,
          height: 40,
          border: 0,
          borderRadius: "50%",
          background: live ? "#065f46" : "#102029",
          color: "#e7fbff",
          cursor: "pointer",
          fontSize: 18,
        }}
      >
        {live ? "🔊" : "🎤"}
      </button>
      <span style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
        <span style={{ fontWeight: 700, fontSize: 13 }}>xAI voice</span>
        <span style={{ color: "#99f6e4", fontSize: 12, fontWeight: 600 }}>
          {live ? "Using xAI. Connected." : "xAI not connected. Tap the microphone."}
        </span>
      </span>
      <button
        type="button"
        className="close"
        aria-label="Hide live audio control"
        title="Hide live audio control"
        onClick={onHide}
        style={{
          width: 28,
          height: 28,
          border: 0,
          borderRadius: "50%",
          background: "#172033",
          color: "#fff",
          cursor: "pointer",
          fontWeight: 700,
        }}
      >
        ×
      </button>
    </div>
  );
}
