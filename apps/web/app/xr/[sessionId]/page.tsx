"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import { ORCHESTRATOR_URL } from "../../lib/api";
import { useFlag } from "../../lib/flags";
import {
  demoNeedsWorkObservations,
  demoPassObservations,
  detectXrCapability,
  normalizeControllerAction,
  requestImmersiveVrSession,
  type XrCapability,
  type XrObservation,
} from "../../lib/xr";

type LabDef = {
  lab_id: string;
  title: string;
  steps?: { step_id: string; title: string; required_action: string; target_id: string }[];
};

type AttemptResult = {
  outcome: string;
  score: number;
  provisional: boolean;
  evidence_summary: string;
  client_kind: string;
};

export default function XrLabPage() {
  const params = useParams();
  const search = useSearchParams();
  const sessionId = String(params?.sessionId || "");
  const roomId = search.get("roomId") || sessionId;
  const participantId = search.get("participantId") || "";
  const moderatorKey = search.get("moderatorKey") || "";
  const studentId = search.get("studentId") || "";

  const xrFlag = useFlag<number | boolean>("access.xr_immersive_class", 0);
  const flagOn = xrFlag === true || (typeof xrFlag === "number" && xrFlag > 0);

  const [cap, setCap] = useState<XrCapability | null>(null);
  const [lab, setLab] = useState<LabDef | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [obs, setObs] = useState<XrObservation[]>([]);
  const [seq, setSeq] = useState(1);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [xrActive, setXrActive] = useState(false);

  const base = useMemo(() => `${ORCHESTRATOR_URL}/api/live-rooms/${encodeURIComponent(roomId)}`, [roomId]);

  useEffect(() => {
    void detectXrCapability().then(setCap);
  }, []);

  const refreshLab = useCallback(async () => {
    try {
      const res = await fetch(`${base}/xr/lab`);
      if (!res.ok) throw new Error(`lab status ${res.status}`);
      const data = await res.json();
      setEnabled(Boolean(data.enabled));
      setLab(data.lab || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load lab");
    }
  }, [base]);

  useEffect(() => {
    void refreshLab();
  }, [refreshLab]);

  async function enableLab() {
    setBusy("enable");
    setError("");
    try {
      const res = await fetch(`${base}/xr/enable`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled: true,
          moderator_key: moderatorKey,
          participant_id: participantId,
          title: "Demonstrate the learned action",
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setEnabled(true);
      setLab(data.lab || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Enable failed");
    } finally {
      setBusy("");
    }
  }

  function pushAction(action: string, targetId: string) {
    const next = normalizeControllerAction(action, targetId, { seq, confidence: 0.9, hold_ms: action === "grab" ? 500 : 0 });
    setObs((prev) => [...prev, next]);
    setSeq((s) => s + 1);
  }

  async function enterXr() {
    setError("");
    try {
      const session = await requestImmersiveVrSession();
      if (!session) {
        setError(cap?.reason || "Immersive VR not available — use fallback controls");
        return;
      }
      setXrActive(true);
      session.addEventListener("end", () => setXrActive(false));
      // Minimal session: keep alive until user exits; actions use on-screen fallback buttons.
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start XR session");
    }
  }

  async function submit(observations: XrObservation[], clientKind: string) {
    setBusy("submit");
    setError("");
    setResult(null);
    try {
      const res = await fetch(`${base}/xr/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          participant_id: participantId,
          student_id: studentId,
          client_kind: clientKind,
          observations,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setResult(data.result as AttemptResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed");
    } finally {
      setBusy("");
    }
  }

  if (!flagOn) {
    return (
      <main style={styles.page}>
        <h1>XR Lab</h1>
        <p>Immersive labs are not enabled for this account yet (feature flag off).</p>
        <Link href={roomId ? `/live-room/${roomId}` : "/group-classes"}>Back to class</Link>
      </main>
    );
  }

  return (
    <main style={styles.page}>
      <header style={styles.header}>
        <div>
          <p style={styles.eyebrow}>Salareen · Immersive lab</p>
          <h1 style={styles.title}>{lab?.title || "XR demonstration"}</h1>
          <p style={styles.sub}>
            Room <code>{roomId}</code>
            {xrActive ? " · XR session active" : ""}
          </p>
        </div>
        <Link href={`/live-room/${roomId}`} style={styles.back}>
          Exit lab
        </Link>
      </header>

      <section style={styles.card}>
        <h2>Capability</h2>
        <p>{cap ? `${cap.immersiveVr ? "Ready for immersive VR" : "Fallback mode"} — ${cap.reason}` : "Checking…"}</p>
        <div style={styles.row}>
          <button type="button" style={styles.btn} onClick={() => void enterXr()} disabled={!cap?.immersiveVr}>
            Enter VR
          </button>
          {!enabled && (
            <button type="button" style={styles.btnSecondary} onClick={() => void enableLab()} disabled={busy === "enable"}>
              Enable lab
            </button>
          )}
        </div>
      </section>

      <section style={styles.card}>
        <h2>Rubric steps</h2>
        <ol>
          {(lab?.steps || [
            { step_id: "approach", title: "Approach", required_action: "approach", target_id: "station" },
            { step_id: "perform", title: "Perform", required_action: "grab", target_id: "tool" },
            { step_id: "confirm", title: "Confirm", required_action: "confirm", target_id: "finish" },
          ]).map((s) => (
            <li key={s.step_id} style={{ marginBottom: 8 }}>
              <strong>{s.title}</strong> — {s.required_action} → {s.target_id}
              <button
                type="button"
                style={{ ...styles.btnSecondary, marginLeft: 8 }}
                onClick={() => pushAction(s.required_action, s.target_id)}
              >
                Record
              </button>
            </li>
          ))}
        </ol>
        <p style={styles.muted}>{obs.length} observation(s) queued</p>
        <div style={styles.row}>
          <button
            type="button"
            style={styles.btn}
            disabled={!participantId || busy === "submit"}
            onClick={() => void submit(obs, cap?.immersiveVr ? "webxr" : "fallback")}
          >
            Submit attempt
          </button>
          <button type="button" style={styles.btnSecondary} onClick={() => void submit(demoPassObservations(), "webxr")}>
            Demo pass
          </button>
          <button type="button" style={styles.btnSecondary} onClick={() => void submit(demoNeedsWorkObservations(), "webxr")}>
            Demo needs work
          </button>
          <button type="button" style={styles.btnSecondary} onClick={() => { setObs([]); setSeq(1); setResult(null); }}>
            Clear
          </button>
        </div>
        {!participantId && <p style={styles.warn}>Open this lab from a live room so participantId is set.</p>}
      </section>

      {error && <p style={styles.warn}>{error}</p>}
      {result && (
        <section style={styles.card}>
          <h2>Result</h2>
          <p>
            <strong>{result.outcome}</strong> · score {(result.score * 100).toFixed(0)}%
            {result.provisional ? " · provisional" : ""}
          </p>
          <p style={styles.muted}>{result.evidence_summary}</p>
        </section>
      )}
    </main>
  );
}

const styles: Record<string, CSSProperties> = {
  page: {
    minHeight: "100vh",
    padding: "24px 20px 48px",
    background: "linear-gradient(160deg, #0f1c24 0%, #1a3344 45%, #0d1418 100%)",
    color: "#e8f1f4",
    fontFamily: '"Segoe UI", system-ui, sans-serif',
  },
  header: { display: "flex", justifyContent: "space-between", gap: 16, marginBottom: 24, alignItems: "flex-start" },
  eyebrow: { letterSpacing: "0.08em", textTransform: "uppercase", fontSize: 12, opacity: 0.7, margin: 0 },
  title: { margin: "6px 0 4px", fontSize: 28, fontWeight: 650 },
  sub: { margin: 0, opacity: 0.75, fontSize: 14 },
  back: { color: "#9ed0e0", textDecoration: "none" },
  card: {
    background: "rgba(255,255,255,0.06)",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
  },
  row: { display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 },
  btn: {
    background: "#2a9d8f",
    color: "#fff",
    border: "none",
    borderRadius: 8,
    padding: "10px 14px",
    cursor: "pointer",
    fontWeight: 600,
  },
  btnSecondary: {
    background: "rgba(255,255,255,0.1)",
    color: "#e8f1f4",
    border: "1px solid rgba(255,255,255,0.15)",
    borderRadius: 8,
    padding: "8px 12px",
    cursor: "pointer",
  },
  muted: { opacity: 0.7, fontSize: 13 },
  warn: { color: "#f4a261" },
};
