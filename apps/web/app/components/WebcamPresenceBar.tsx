"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getWebcamPresence, type PresenceSummary } from "../lib/api";

type Props = {
  sessionId: string | null;
  classType?: "solo" | "group";
  /** Poll interval in ms. Default 3000. */
  pollIntervalMs?: number;
};

/** Compact presence status bar shown inside the live-room / lesson UI. */
export default function WebcamPresenceBar({
  sessionId,
  classType = "solo",
  pollIntervalMs = 3000,
}: Props) {
  const [summary, setSummary] = useState<PresenceSummary | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetch = useCallback(async () => {
    if (!sessionId) return;
    try {
      const s = await getWebcamPresence(sessionId);
      setSummary(s);
    } catch {
      // non-fatal
    }
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) {
      setSummary(null);
      return;
    }
    void fetch();
    timerRef.current = setInterval(() => void fetch(), pollIntervalMs);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [sessionId, pollIntervalMs, fetch]);

  if (!summary) return null;

  if (classType === "solo" && summary.solo_status) {
    const { state, attention, away_duration_s } = summary.solo_status;
    return <SoloBar state={state} attention={attention} awayS={away_duration_s} />;
  }

  if (classType === "group" && summary.group_summary) {
    return <GroupBar summary={summary} />;
  }

  return null;
}

// -------------------------------------------------------------------------- //
// Solo bar
// -------------------------------------------------------------------------- //

const STATE_COLOR: Record<string, string> = {
  present: "#22c55e",
  away: "#f59e0b",
  absent: "#ef4444",
  unknown: "#9ca3af",
};

function SoloBar({
  state,
  attention,
  awayS,
}: {
  state: string;
  attention: number;
  awayS: number;
}) {
  const color = STATE_COLOR[state] ?? "#9ca3af";
  const pct = Math.round((attention ?? 0) * 100);
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "10px",
        padding: "5px 10px",
        background: "rgba(0,0,0,0.5)",
        borderRadius: "8px",
        fontSize: "12px",
        color: "#fff",
      }}
    >
      <span
        style={{
          width: "8px",
          height: "8px",
          borderRadius: "50%",
          background: color,
          flexShrink: 0,
        }}
      />
      <span style={{ textTransform: "capitalize" }}>{state}</span>
      {state === "present" && (
        <>
          <span style={{ color: "#9ca3af" }}>·</span>
          <span>Attention {pct}%</span>
        </>
      )}
      {(state === "away" || state === "absent") && awayS > 0 && (
        <>
          <span style={{ color: "#9ca3af" }}>·</span>
          <span>Away {Math.round(awayS)}s</span>
        </>
      )}
    </div>
  );
}

// -------------------------------------------------------------------------- //
// Group bar
// -------------------------------------------------------------------------- //

function GroupBar({ summary }: { summary: PresenceSummary }) {
  const g = summary.group_summary!;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "12px",
        padding: "5px 12px",
        background: "rgba(0,0,0,0.5)",
        borderRadius: "8px",
        fontSize: "12px",
        color: "#fff",
      }}
    >
      <ParticipantDots statuses={summary.participant_statuses} />
      <span>
        {g.present_count}/{g.total_participants} present
      </span>
      {!g.quorum_met && (
        <span style={{ color: "#f59e0b" }}>Low attendance</span>
      )}
      {g.average_attention > 0 && (
        <>
          <span style={{ color: "#9ca3af" }}>·</span>
          <span>Avg attention {Math.round(g.average_attention * 100)}%</span>
        </>
      )}
    </div>
  );
}

function ParticipantDots({
  statuses,
}: {
  statuses: PresenceSummary["participant_statuses"];
}) {
  return (
    <div style={{ display: "flex", gap: "3px", alignItems: "center" }}>
      {statuses.slice(0, 8).map((s) => (
        <span
          key={s.participant_id}
          title={`${s.participant_id}: ${s.state}`}
          style={{
            width: "8px",
            height: "8px",
            borderRadius: "50%",
            background: STATE_COLOR[s.state] ?? "#9ca3af",
            display: "inline-block",
          }}
        />
      ))}
      {statuses.length > 8 && (
        <span style={{ fontSize: "10px", color: "#9ca3af" }}>
          +{statuses.length - 8}
        </span>
      )}
    </div>
  );
}
