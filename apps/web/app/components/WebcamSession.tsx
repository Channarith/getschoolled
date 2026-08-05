"use client";

import { useRef } from "react";
import { useWebcamSession } from "../hooks/useWebcamSession";
import type { VoiceAgentResponse } from "../lib/api";

type Props = {
  classType?: "solo" | "group";
  studentIds?: string[];
  lessonContext?: string;
  participantId?: string;
  agentType?: "teacher" | "self_teach";
  fps?: number;
  /** Show the local camera preview tile. Default true. */
  showPreview?: boolean;
  /** Callback when Theodore (or the self-teach coach) speaks. */
  onVoiceResponse?: (resp: VoiceAgentResponse) => void;
  /** Callback when absence is detected. */
  onAbsent?: (awaySeconds: number) => void;
  /** Callback when the student returns. */
  onReturned?: () => void;
};

const PRESENCE_COLORS: Record<string, string> = {
  present: "#22c55e",
  away: "#f59e0b",
  absent: "#ef4444",
  unknown: "#6b7280",
};

const PRESENCE_LABELS: Record<string, string> = {
  present: "Present",
  away: "Away",
  absent: "Absent",
  unknown: "Detecting…",
};

export default function WebcamSession({
  classType = "solo",
  studentIds = [],
  lessonContext = "",
  participantId = "student",
  agentType = "teacher",
  fps = 2,
  showPreview = true,
  onVoiceResponse,
  onAbsent,
  onReturned,
}: Props) {
  const { state, videoRef, canvasRef, start, stop, askAgent } = useWebcamSession({
    classType,
    studentIds,
    lessonContext,
    participantId,
    agentType,
    fps,
    onVoiceResponse,
    onAbsent,
    onReturned,
  });

  const inputRef = useRef<HTMLInputElement>(null);

  const handleAsk = async () => {
    const text = inputRef.current?.value?.trim();
    if (!text || !state.isActive) return;
    if (inputRef.current) inputRef.current.value = "";
    await askAgent(text, false);
  };

  const presenceColor = PRESENCE_COLORS[state.presenceState] ?? "#6b7280";
  const presenceLabel = PRESENCE_LABELS[state.presenceState] ?? "Unknown";

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "12px",
        fontFamily: "system-ui, sans-serif",
        maxWidth: "400px",
      }}
    >
      {/* Camera preview */}
      {showPreview && (
        <div
          style={{
            position: "relative",
            borderRadius: "12px",
            overflow: "hidden",
            background: "#111",
            aspectRatio: "4/3",
          }}
        >
          <video
            ref={videoRef}
            playsInline
            muted
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: "scaleX(-1)", // mirror
              display: state.cameraReady ? "block" : "none",
            }}
          />
          {/* Silhouette placeholder when camera off */}
          {!state.cameraReady && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                height: "100%",
                color: "#555",
                fontSize: "14px",
                gap: "8px",
              }}
            >
              <SilhouetteIcon />
              <span>Camera inactive</span>
            </div>
          )}
          {/* Absence overlay */}
          {state.presenceState === "absent" && state.cameraReady && (
            <div
              style={{
                position: "absolute",
                inset: 0,
                background: "rgba(0,0,0,0.7)",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                color: "#fff",
                gap: "8px",
              }}
            >
              <SilhouetteIcon color="#888" size={48} />
              <span style={{ fontSize: "14px" }}>Student absent</span>
              <span style={{ fontSize: "12px", color: "#aaa" }}>
                Away {Math.round(state.awayDurationS)}s
              </span>
            </div>
          )}
          {/* Presence badge */}
          {state.isActive && (
            <div
              style={{
                position: "absolute",
                top: "8px",
                right: "8px",
                background: "rgba(0,0,0,0.6)",
                borderRadius: "20px",
                padding: "3px 10px",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                fontSize: "12px",
                color: "#fff",
              }}
            >
              <span
                style={{
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  background: presenceColor,
                  display: "inline-block",
                }}
              />
              {presenceLabel}
            </div>
          )}
          {/* Hidden canvas for frame capture */}
          <canvas ref={canvasRef} style={{ display: "none" }} />
        </div>
      )}

      {/* Attention bar */}
      {state.isActive && state.presenceState === "present" && state.attention !== null && (
        <AttentionBar attention={state.attention} />
      )}

      {/* Controls */}
      <div style={{ display: "flex", gap: "8px" }}>
        {!state.isActive ? (
          <button
            onClick={start}
            disabled={state.isLoading}
            style={btnStyle("primary")}
          >
            {state.isLoading ? "Starting…" : "Start Session"}
          </button>
        ) : (
          <button onClick={stop} style={btnStyle("danger")}>
            End Session
          </button>
        )}
      </div>

      {state.error && (
        <div
          style={{
            background: "#fef2f2",
            border: "1px solid #fca5a5",
            borderRadius: "8px",
            padding: "8px 12px",
            fontSize: "13px",
            color: "#dc2626",
          }}
        >
          {state.error}
        </div>
      )}

      {/* Voice agent input */}
      {state.isActive && (
        <div style={{ display: "flex", gap: "8px" }}>
          <input
            ref={inputRef}
            placeholder={
              agentType === "teacher"
                ? "Ask Theodore…"
                : "Ask the coach…"
            }
            onKeyDown={(e) => e.key === "Enter" && void handleAsk()}
            style={{
              flex: 1,
              padding: "8px 12px",
              borderRadius: "8px",
              border: "1px solid #d1d5db",
              fontSize: "14px",
              outline: "none",
            }}
          />
          <button onClick={() => void handleAsk()} style={btnStyle("primary")}>
            Ask
          </button>
        </div>
      )}

      {/* Last voice response */}
      {state.lastVoiceResponse && (
        <div
          style={{
            background: "#f0f9ff",
            border: "1px solid #bae6fd",
            borderRadius: "8px",
            padding: "10px 12px",
            fontSize: "13px",
            color: "#0369a1",
            lineHeight: 1.5,
          }}
        >
          <strong>
            {agentType === "teacher" ? "Theodore: " : "Coach: "}
          </strong>
          {state.lastVoiceResponse.text}
          {state.lastVoiceResponse.fallback && (
            <span style={{ fontSize: "11px", color: "#94a3b8", marginLeft: "6px" }}>
              (offline)
            </span>
          )}
        </div>
      )}

      {/* Frame counter (debug) */}
      {state.isActive && (
        <div
          style={{ fontSize: "11px", color: "#9ca3af", textAlign: "right" }}
        >
          Frames analyzed: {state.frameCount}
        </div>
      )}
    </div>
  );
}

// -------------------------------------------------------------------------- //
// Sub-components
// -------------------------------------------------------------------------- //

function AttentionBar({ attention }: { attention: number }) {
  const pct = Math.round(attention * 100);
  const color =
    pct >= 70 ? "#22c55e" : pct >= 40 ? "#f59e0b" : "#ef4444";
  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: "12px",
          color: "#6b7280",
          marginBottom: "4px",
        }}
      >
        <span>Attention</span>
        <span style={{ color }}>{pct}%</span>
      </div>
      <div
        style={{
          height: "6px",
          borderRadius: "3px",
          background: "#e5e7eb",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: color,
            borderRadius: "3px",
            transition: "width 0.5s ease",
          }}
        />
      </div>
    </div>
  );
}

function SilhouetteIcon({
  color = "#444",
  size = 36,
}: {
  color?: string;
  size?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="7" r="4" />
      <path d="M5.5 21a7 7 0 0 1 13 0" />
    </svg>
  );
}

function btnStyle(variant: "primary" | "danger"): React.CSSProperties {
  const base: React.CSSProperties = {
    padding: "8px 16px",
    borderRadius: "8px",
    border: "none",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: 500,
    transition: "opacity 0.15s",
  };
  if (variant === "primary") {
    return { ...base, background: "#3b82f6", color: "#fff" };
  }
  return { ...base, background: "#ef4444", color: "#fff" };
}
