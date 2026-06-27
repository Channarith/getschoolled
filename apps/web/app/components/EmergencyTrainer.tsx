"use client";

import { useEffect, useRef, useState } from "react";

import {
  listTrainingScenarios,
  startTraining,
  trainingDecide,
  trainingForecast,
  type PhaseBrief,
  type TrainingDecisionResult,
  type TrainingScenario,
  type TrainingSummary,
} from "../lib/api";
import SignInToUse from "./SignInToUse";
import { getToken } from "../lib/api";

function scoreColor(s: number): string {
  if (s >= 0.7) return "#16a34a";
  if (s >= 0.4) return "#ca8a04";
  return "#dc2626";
}

function toneStyle(tone: string): { background: string; color: string; border: string } {
  if (tone === "supportive") return { background: "#ecfeff", color: "#155e75", border: "1px solid #06b6d4" };
  if (tone === "challenging") return { background: "#eef2ff", color: "#3730a3", border: "1px solid #6366f1" };
  return { background: "#f8fafc", color: "#334155", border: "1px solid #cbd5e1" };
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div style={{ margin: "4px 0" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
        <span>{label.replace(/_/g, " ")}</span>
        <span style={{ fontWeight: 600 }}>{Math.round(value * 100)}%</span>
      </div>
      <div style={{ height: 8, background: "#e2e8f0", borderRadius: 999 }}>
        <div style={{ width: `${Math.round(value * 100)}%`, height: 8, background: scoreColor(value), borderRadius: 999 }} />
      </div>
    </div>
  );
}

export default function EmergencyTrainer() {
  const [scenarios, setScenarios] = useState<TrainingScenario[]>([]);
  const [loggedIn, setLoggedIn] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [sessionId, setSessionId] = useState("");
  const [scenarioTitle, setScenarioTitle] = useState("");
  const [phasesTotal, setPhasesTotal] = useState(0);
  const [phaseIndex, setPhaseIndex] = useState(0);
  const [brief, setBrief] = useState<PhaseBrief | null>(null);
  const [result, setResult] = useState<TrainingDecisionResult | null>(null);
  const [summary, setSummary] = useState<TrainingSummary | null>(null);

  const [elapsed, setElapsed] = useState(0);
  const [rationale, setRationale] = useState("");
  const [noticed, setNoticed] = useState("");
  const [saScore, setSaScore] = useState<number | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    setLoggedIn(Boolean(getToken()));
    listTrainingScenarios().then(setScenarios).catch((e) => setError(String(e)));
  }, []);

  // Split-second clock: counts up while a decision is pending.
  useEffect(() => {
    if (timer.current) { clearInterval(timer.current); timer.current = null; }
    if (brief && !result && !summary) {
      timer.current = setInterval(() => setElapsed((e) => Math.round((e + 0.1) * 10) / 10), 100);
    }
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [brief, result, summary]);

  function resetPhaseInputs() {
    setElapsed(0);
    setRationale("");
    setNoticed("");
    setSaScore(null);
  }

  async function onStart(scenarioId: string) {
    if (!getToken()) { setLoggedIn(false); return; }
    setError(""); setBusy(true); setResult(null); setSummary(null);
    try {
      const v = await startTraining(scenarioId, "solo");
      setSessionId(v.session_id);
      setScenarioTitle(v.scenario_title);
      setPhasesTotal(v.phases_total);
      setPhaseIndex(v.phase_index);
      setBrief(v.brief);
      resetPhaseInputs();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onCheckCues() {
    if (!sessionId || !noticed.trim()) return;
    setBusy(true);
    try {
      const cues = noticed.split(/[,\n;]+/).map((s) => s.trim()).filter(Boolean);
      const v = await trainingForecast(sessionId, cues);
      setBrief(v.brief);
      setSaScore(v.brief?.situation_picture.sa_score ?? null);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onDecide(optionId: string) {
    if (!sessionId || !brief || result) return;
    if (timer.current) { clearInterval(timer.current); timer.current = null; }
    setBusy(true);
    try {
      const res = await trainingDecide({ sessionId, optionId, elapsedS: elapsed, rationale });
      setResult(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  function onContinue() {
    if (!result) return;
    if (result.done) {
      setSummary(result.summary);
      setBrief(null);
    } else {
      setBrief(result.next_brief);
      setPhaseIndex(result.phase_index);
      setResult(null);
      resetPhaseInputs();
    }
  }

  function onRestart() {
    setSessionId(""); setBrief(null); setResult(null); setSummary(null);
    setScenarioTitle(""); resetPhaseInputs();
  }

  const remaining = brief ? Math.max(0, brief.decision_window_s - elapsed) : 0;
  const clockColor = remaining > 3 ? "#16a34a" : remaining > 0 ? "#ca8a04" : "#dc2626";

  return (
    <main className="container">
      <h1>Critical-Thinking & Emergency Drills</h1>
      <p className="muted" style={{ marginTop: 0 }}>
        Train how you think under pressure: situational awareness, pre-mortem forecasting,
        split-second decisions, and reasoning — with a coach that adapts to you.
      </p>

      {error && (
        <div className="card" style={{ borderColor: "#ff6b6b" }}>
          <strong>Could not reach the trainer.</strong>
          <div className="muted">{error}</div>
        </div>
      )}

      {!sessionId && !loggedIn && <SignInToUse />}

      {/* Scenario picker */}
      {!sessionId && (
        <div className="grid">
          {scenarios.map((s) => (
            <div className="card" key={s.id}>
              <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0 }}>{s.title}</h3>
                <span style={{ fontSize: 12, padding: "2px 8px", borderRadius: 999, border: "1px solid #94a3b8" }}>
                  {s.difficulty}
                </span>
              </div>
              <p className="muted">{s.summary}</p>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
                {s.skills.slice(0, 5).map((sk) => (
                  <span key={sk} style={{ fontSize: 11, padding: "1px 8px", borderRadius: 999, background: "#eef2ff", color: "#3730a3" }}>
                    {sk.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
              <button onClick={() => onStart(s.id)} disabled={busy}
                style={{ background: "#111", color: "#fff" }}
                title={!loggedIn ? "Sign in to run drills" : undefined}>
                Start drill ({s.phases} phases) →
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Active phase */}
      {brief && !summary && (
        <>
          <div className="slide">
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
              <div className="muted">
                {scenarioTitle} · Phase {phaseIndex + 1} of {phasesTotal}
              </div>
              {!result && (
                <div title="Decision window — decide before it runs out"
                  style={{ fontWeight: 700, fontVariantNumeric: "tabular-nums", color: clockColor }}>
                  ⏱ {remaining.toFixed(1)}s {remaining === 0 ? "(overtime!)" : ""}
                </div>
              )}
            </div>
            <h2 style={{ marginBottom: 6 }}>{brief.title}</h2>
            <p>{brief.situation}</p>

            {/* Situational awareness + pre-mortem forecast */}
            <div className="row" style={{ alignItems: "stretch", gap: 12 }}>
              <div className="card" style={{ flex: 1, minWidth: 240, background: "#f0f9ff", borderColor: "#7dd3fc" }}>
                <strong>🧭 Situational picture</strong>
                <div className="muted" style={{ marginTop: 6 }}>Notice now</div>
                <ul style={{ margin: "4px 0 8px 18px" }}>
                  {brief.situation_picture.perception.map((c, i) => <li key={i}>{c}</li>)}
                </ul>
                <div className="muted">Likely to come</div>
                <ul style={{ margin: "4px 0 0 18px" }}>
                  {brief.situation_picture.projection.map((c, i) => <li key={i}>{c}</li>)}
                </ul>
              </div>
              <div className="card" style={{ flex: 1, minWidth: 240, background: "#fff7ed", borderColor: "#fdba74" }}>
                <strong>🔮 Pre-mortem (forecast)</strong>
                <p className="muted" style={{ marginTop: 6 }}>{brief.premortem.headline}</p>
                {brief.premortem.risks.map((r, i) => (
                  <div key={i} style={{ marginBottom: 6 }}>
                    <div><b>{r.likelihood.toUpperCase()}</b> · {r.risk}</div>
                    <div className="muted" style={{ fontSize: 13 }}>→ {r.mitigation}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Optional: self-test situational awareness */}
            {!result && (
              <div style={{ marginTop: 12 }}>
                <label className="muted">What do you notice? (optional — scored for situational awareness)</label>
                <div className="row" style={{ marginTop: 4 }}>
                  <input style={{ flex: 1, minWidth: 240 }} placeholder="e.g. engine quiet, altitude, field into wind"
                    value={noticed} onChange={(e) => setNoticed(e.target.value)} />
                  <button onClick={onCheckCues} disabled={busy || !noticed.trim()}>Check</button>
                </div>
                {saScore !== null && (
                  <div className="muted" style={{ marginTop: 4 }}>
                    Situational-awareness recall: <b style={{ color: scoreColor(saScore) }}>{Math.round(saScore * 100)}%</b>
                    {brief.situation_picture.missed_cues.length > 0 &&
                      ` · missed: ${brief.situation_picture.missed_cues.join("; ")}`}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Decision */}
          {!result && (
            <div className="card">
              <h3 style={{ marginTop: 0 }}>{brief.prompt}</h3>
              <label className="muted">Why? (optional — your reasoning is critiqued)</label>
              <textarea rows={2} style={{ width: "100%", marginTop: 4 }}
                placeholder="Explain your reasoning…"
                value={rationale} onChange={(e) => setRationale(e.target.value)} />
              <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 10 }}>
                {brief.options.map((o) => (
                  <button key={o.id} onClick={() => onDecide(o.id)} disabled={busy}
                    style={{ textAlign: "left", padding: "10px 12px", borderRadius: 8, border: "1px solid #cbd5e1", background: "#fff", cursor: "pointer" }}>
                    {o.text}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Decision feedback */}
          {result && (
            <div className="card" style={{ borderColor: result.correct ? "#16a34a" : "#dc2626" }}>
              <h3 style={{ marginTop: 0, color: result.correct ? "#16a34a" : "#dc2626" }}>
                {result.correct ? "✓ Good decision" : "✗ Suboptimal"} · decision score {Math.round(result.score * 100)}%
              </h3>
              <p><b>What happened:</b> {result.consequence}</p>
              <p className="muted">{result.feedback}</p>

              <div className="row" style={{ alignItems: "stretch", gap: 12 }}>
                <div className="card" style={{ flex: 1, minWidth: 240 }}>
                  <strong>⚡ Rapid decision (OODA)</strong>
                  <ScoreBar label="quality" value={result.rapid.quality} />
                  <ScoreBar label="timeliness" value={result.rapid.timeliness} />
                  <p className="muted" style={{ fontSize: 13 }}>{result.rapid.note}</p>
                </div>
                <div className="card" style={{ flex: 1, minWidth: 240 }}>
                  <strong>🧠 Reasoning critique</strong>
                  {Object.entries(result.reasoning.rubric).map(([k, v]) => (
                    <ScoreBar key={k} label={k} value={v} />
                  ))}
                  {result.reasoning.detected_issues.length > 0 && (
                    <div style={{ color: "#b45309", fontSize: 13, marginTop: 6 }}>
                      ⚠ {result.reasoning.detected_issues.join(" · ")}
                    </div>
                  )}
                  <p className="muted" style={{ fontSize: 13, marginTop: 6 }}>❓ {result.reasoning.socratic_probe}</p>
                </div>
              </div>

              <div className="card" style={{ marginTop: 12, ...toneStyle(result.behavior.tone) }}>
                <strong>🎚 Coach (adapts to you)</strong>
                <div style={{ fontSize: 13, margin: "4px 0" }}>
                  style: <b>{result.behavior.coaching_style}</b> · tone: <b>{result.behavior.tone}</b>
                  {result.behavior.flags.length > 0 && <> · {result.behavior.flags.map((f) => f.replace(/_/g, " ")).join(", ")}</>}
                </div>
                <div>{result.behavior.recommendation}</div>
              </div>

              {!result.correct && (
                <p style={{ marginTop: 10 }}><b>Recommended:</b> {result.recommended}</p>
              )}
              <button onClick={onContinue} disabled={busy} style={{ marginTop: 12, background: "#111", color: "#fff" }}>
                {result.done ? "See debrief →" : "Next phase →"}
              </button>
            </div>
          )}
        </>
      )}

      {/* Debrief */}
      {summary && (
        <div className="card" style={{ borderColor: summary.passed ? "#16a34a" : "#ca8a04" }}>
          <h2 style={{ marginTop: 0 }}>
            {summary.passed ? "✅ Drill passed" : "⚠️ Keep training"} · {Math.round(summary.overall_score * 100)}%
          </h2>
          <p>{summary.debrief}</p>
          <div className="row" style={{ gap: 16, flexWrap: "wrap" }}>
            <div className="muted">Decision quality: <b>{Math.round(summary.avg_quality * 100)}%</b></div>
            <div className="muted">Timeliness: <b>{Math.round(summary.avg_timeliness * 100)}%</b></div>
            <div className="muted">Reasoning: <b>{Math.round(summary.avg_reasoning * 100)}%</b></div>
          </div>
          <h3>Per-skill</h3>
          {Object.entries(summary.per_skill).map(([k, v]) => <ScoreBar key={k} label={k} value={v} />)}
          {summary.growth_areas.length > 0 && (
            <p className="muted" style={{ marginTop: 10 }}>Focus next: {summary.growth_areas.map((g) => g.replace(/_/g, " ")).join(", ")}</p>
          )}
          <button onClick={onRestart} style={{ marginTop: 12, background: "#111", color: "#fff" }}>
            Run another drill ↻
          </button>
        </div>
      )}
    </main>
  );
}
