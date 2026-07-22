"use client";

import { useCallback, useEffect, useRef, useState, type CSSProperties, type PointerEvent as ReactPointerEvent } from "react";

// A single freehand stroke. Points are stored in NORMALIZED coordinates (0..1)
// relative to the board so a stroke drawn on a phone renders in the same place
// on a laptop, regardless of the actual pixel size of each viewer's canvas.
export type WhiteboardStroke = {
  id: string;
  color: string;
  width: number; // normalized to board width (0..1 * base) — see WIDTHS
  erase?: boolean;
  points: { x: number; y: number }[];
};

const PALETTE = ["#0f172a", "#dc2626", "#2563eb", "#16a34a", "#d97706", "#7c3aed"];
const WIDTHS: { label: string; value: number }[] = [
  { label: "S", value: 3 },
  { label: "M", value: 6 },
  { label: "L", value: 12 },
];

type WhiteboardProps = {
  // May this viewer draw? True for the student who's been called on (holds the
  // floor) and for the instructor. Everyone else is in read-only "watch" mode.
  canDraw: boolean;
  // Shared strokes from the class (broadcast over the live-room socket). When the
  // sync backend isn't live yet this stays empty and the drawer still sees their
  // own strokes locally.
  // Single source of truth for committed strokes. The parent owns this list
  // (updates it via onStroke/onClear/onUndo and, once the sync backend lands,
  // from socket broadcasts) so the drawer and watchers render the exact same
  // set — no local duplicate that would double-paint or survive an undo.
  strokes: WhiteboardStroke[];
  // Name shown in the "watching" badge for non-drawers.
  drawerName?: string;
  onStroke?: (stroke: WhiteboardStroke) => void;
  onClear?: () => void;
  onUndo?: () => void;
  onExit?: () => void;
};

export default function Whiteboard({
  canDraw,
  strokes,
  drawerName,
  onStroke,
  onClear,
  onUndo,
  onExit,
}: WhiteboardProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const surfaceRef = useRef<HTMLDivElement | null>(null);
  const [color, setColor] = useState(PALETTE[0]);
  const [width, setWidth] = useState(WIDTHS[1].value);
  const [erasing, setErasing] = useState(false);
  const drawingRef = useRef<WhiteboardStroke | null>(null);
  const [, forceTick] = useState(0);

  const allStrokes = strokes;

  const redraw = useCallback(() => {
    const canvas = canvasRef.current;
    const surface = surfaceRef.current;
    if (!canvas || !surface) return;
    const rect = surface.getBoundingClientRect();
    const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
    const w = Math.max(1, Math.round(rect.width));
    const h = Math.max(1, Math.round(rect.height));
    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr;
      canvas.height = h * dpr;
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    const paint = (s: WhiteboardStroke) => {
      if (s.points.length === 0) return;
      ctx.strokeStyle = s.erase ? "#f8fafc" : s.color;
      ctx.lineWidth = s.width;
      ctx.beginPath();
      s.points.forEach((p, i) => {
        const x = p.x * w;
        const y = p.y * h;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    };
    allStrokes.forEach(paint);
    if (drawingRef.current) paint(drawingRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strokes]);

  useEffect(() => {
    redraw();
  }, [redraw]);

  useEffect(() => {
    const surface = surfaceRef.current;
    if (!surface || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => redraw());
    ro.observe(surface);
    return () => ro.disconnect();
  }, [redraw]);

  const pointFromEvent = (e: ReactPointerEvent<HTMLCanvasElement>) => {
    const surface = surfaceRef.current;
    if (!surface) return { x: 0, y: 0 };
    const rect = surface.getBoundingClientRect();
    return {
      x: Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width)),
      y: Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height)),
    };
  };

  const onPointerDown = (e: ReactPointerEvent<HTMLCanvasElement>) => {
    if (!canDraw) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    drawingRef.current = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      color,
      width,
      erase: erasing,
      points: [pointFromEvent(e)],
    };
    forceTick((n) => n + 1);
  };

  const onPointerMove = (e: ReactPointerEvent<HTMLCanvasElement>) => {
    if (!canDraw || !drawingRef.current) return;
    drawingRef.current.points.push(pointFromEvent(e));
    redraw();
  };

  const endStroke = () => {
    const stroke = drawingRef.current;
    drawingRef.current = null;
    if (!stroke || stroke.points.length === 0) return;
    // Commit to the parent-owned list; the re-render redraws from `strokes`.
    onStroke?.(stroke);
    forceTick((n) => n + 1);
  };

  const clearBoard = () => {
    onClear?.();
  };

  const undo = () => onUndo?.();

  // Square icon button for the vertical tool rail (Design A).
  const railBtn = (active: boolean): CSSProperties => ({
    width: 40,
    height: 40,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 18,
    borderRadius: 10,
    cursor: "pointer",
    border: active ? "1px solid var(--accent)" : "1px solid var(--border)",
    background: active ? "color-mix(in srgb, var(--accent) 14%, var(--panel))" : "var(--panel)",
    color: "var(--text)",
  });

  return (
    <div style={{ display: "flex", gap: 10, height: "100%" }}>
      {canDraw ? (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 8,
            padding: 8,
            borderRadius: 14,
            border: "1px solid var(--border)",
            background: "var(--panel)",
            alignSelf: "flex-start",
          }}
        >
          <button
            type="button"
            onClick={() => setErasing(false)}
            style={railBtn(!erasing)}
            title="Pen"
            aria-label="Pen"
          >
            ✏️
          </button>
          {PALETTE.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => {
                setColor(c);
                setErasing(false);
              }}
              aria-label={`Pen color ${c}`}
              title="Pen color"
              style={{
                width: 26,
                height: 26,
                borderRadius: 999,
                cursor: "pointer",
                background: c,
                border: color === c && !erasing ? "3px solid var(--accent)" : "2px solid #fff",
                boxShadow: "0 0 0 1px var(--border)",
              }}
            />
          ))}
          <div style={{ display: "flex", gap: 3 }}>
            {WIDTHS.map((wOpt) => (
              <button
                key={wOpt.label}
                type="button"
                onClick={() => setWidth(wOpt.value)}
                title={`Pen size ${wOpt.label}`}
                style={{
                  width: 22,
                  height: 22,
                  fontSize: 10,
                  fontWeight: 700,
                  borderRadius: 6,
                  cursor: "pointer",
                  border: width === wOpt.value ? "1px solid var(--accent)" : "1px solid var(--border)",
                  background: width === wOpt.value ? "color-mix(in srgb, var(--accent) 14%, var(--panel))" : "var(--panel)",
                  color: "var(--text)",
                }}
              >
                {wOpt.label}
              </button>
            ))}
          </div>
          <button type="button" onClick={() => setErasing((v) => !v)} style={railBtn(erasing)} title="Eraser" aria-label="Eraser">
            🩹
          </button>
          <button type="button" onClick={undo} style={railBtn(false)} title="Undo last stroke" aria-label="Undo">
            ↶
          </button>
          <button type="button" onClick={clearBoard} style={railBtn(false)} title="Clear the whole board" aria-label="Clear board">
            🗑
          </button>
        </div>
      ) : null}

      <div style={{ position: "relative", flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
        {(!canDraw || onExit) ? (
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, minHeight: 30 }}>
            {!canDraw ? (
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: "var(--muted)",
                  background: "var(--panel)",
                  border: "1px solid var(--border)",
                  padding: "3px 10px",
                  borderRadius: 999,
                }}
              >
                👀 Watching{drawerName ? ` — ${drawerName} is drawing` : ""}
              </span>
            ) : null}
            <span style={{ flex: 1 }} aria-hidden />
            {onExit ? (
              <button
                type="button"
                onClick={onExit}
                title="Close the whiteboard"
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  padding: "5px 12px",
                  borderRadius: 999,
                  cursor: "pointer",
                  border: "1px solid var(--border)",
                  background: "var(--panel)",
                  color: "var(--text)",
                }}
              >
                ✕ Close
              </button>
            ) : null}
          </div>
        ) : null}

        <div
          ref={surfaceRef}
          style={{
            position: "relative",
            flex: 1,
            minHeight: 320,
            borderRadius: 16,
            border: "1px solid var(--border)",
            background: "#ffffff",
            overflow: "hidden",
            boxShadow: "inset 0 1px 3px rgba(0,0,0,0.06)",
          }}
        >
          <canvas
            ref={canvasRef}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={endStroke}
            onPointerLeave={endStroke}
            onPointerCancel={endStroke}
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              touchAction: "none",
              cursor: canDraw ? "crosshair" : "default",
            }}
          />
          {!canDraw && allStrokes.length === 0 ? (
            <div
              style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#94a3b8",
                fontSize: 14,
                pointerEvents: "none",
              }}
            >
              The whiteboard is blank — the presenter hasn’t drawn yet.
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
