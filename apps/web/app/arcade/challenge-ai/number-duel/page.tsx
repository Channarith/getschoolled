"use client";

// Number Duel — a mental-math race against the AI. Each round shows an equation
// and four answers; buzz in with the correct one before the AI does. The AI's
// reaction speed and accuracy scale with difficulty. First to 4 points wins the
// match. Fully client-side.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

type Level = "easy" | "medium" | "hard";
type Round = { text: string; answer: number; options: number[] };
type Phase = "idle" | "live" | "youWin" | "aiWin" | "youWrong" | "done";

// min/max = AI buzz-in delay range (ms); acc = chance it answers correctly;
// grace = extra window the player gets to steal the point after the AI fumbles.
const AI_PARAMS: Record<Level, { min: number; max: number; acc: number; grace: number }> = {
  easy: { min: 2800, max: 4200, acc: 0.5, grace: 2800 },
  medium: { min: 1500, max: 2400, acc: 0.8, grace: 1600 },
  hard: { min: 850, max: 1600, acc: 0.95, grace: 900 },
};
const WIN_AT = 4;

function shuffle<T>(a: T[]): T[] {
  const r = [...a];
  for (let i = r.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [r[i], r[j]] = [r[j], r[i]]; }
  return r;
}

function makeRound(level: Level): Round {
  const ri = (a: number, b: number) => a + Math.floor(Math.random() * (b - a + 1));
  let a: number, b: number, op: string, answer: number;
  if (level === "easy") {
    op = Math.random() < 0.5 ? "+" : "−"; a = ri(2, 20); b = ri(1, a);
    answer = op === "+" ? a + b : a - b;
  } else if (level === "medium") {
    const r = Math.random();
    if (r < 0.4) { op = "×"; a = ri(2, 12); b = ri(2, 12); answer = a * b; }
    else { op = Math.random() < 0.5 ? "+" : "−"; a = ri(10, 40); b = ri(1, a); answer = op === "+" ? a + b : a - b; }
  } else {
    const r = Math.random();
    if (r < 0.45) { op = "×"; a = ri(6, 19); b = ri(3, 14); answer = a * b; }
    else if (r < 0.75) { op = "+"; a = ri(30, 90); b = ri(20, 90); answer = a + b; }
    else { op = "−"; a = ri(40, 120); b = ri(10, a); answer = a - b; }
  }
  const opts = new Set<number>([answer]);
  while (opts.size < 4) {
    const delta = (Math.floor(Math.random() * 9) - 4) || (Math.random() < 0.5 ? 5 : -5);
    const v = answer + delta;
    if (v >= 0) opts.add(v);
  }
  return { text: `${a} ${op} ${b}`, answer, options: shuffle([...opts]) };
}

export default function NumberDuel() {
  const [level, setLevel] = useState<Level>("medium");
  const [round, setRound] = useState<Round | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [you, setYou] = useState(0);
  const [ai, setAi] = useState(0);
  const [msg, setMsg] = useState("");
  const [barPct, setBarPct] = useState(0);
  const [barMs, setBarMs] = useState(2000);
  const aiTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const graceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const phaseRef = useRef<Phase>("idle");
  phaseRef.current = phase;

  const clearTimers = () => {
    if (aiTimer.current) { clearTimeout(aiTimer.current); aiTimer.current = null; }
    if (graceTimer.current) { clearTimeout(graceTimer.current); graceTimer.current = null; }
  };

  // Launch one round. Scores are threaded explicitly so recursion never reads
  // stale state, and the round always resolves (win, loss, or AI recovery).
  const beginRound = useCallback((yScore: number, aScore: number) => {
    if (yScore >= WIN_AT || aScore >= WIN_AT) {
      setPhase("done");
      setMsg(yScore > aScore ? "🏆 You beat the AI in the match!" : "🤖 The AI takes the match.");
      return;
    }
    const r = makeRound(level);
    setRound(r); setPhase("live"); setMsg("");
    const p = AI_PARAMS[level];
    const t = p.min + Math.random() * (p.max - p.min);
    setBarMs(t); setBarPct(0);
    requestAnimationFrame(() => requestAnimationFrame(() => setBarPct(100)));
    clearTimers();
    const aiScores = (extraMsg: string) => {
      setPhase("aiWin"); setMsg(extraMsg);
      setAi(aScore + 1);
      setTimeout(() => beginRound(yScore, aScore + 1), 1300);
    };
    aiTimer.current = setTimeout(() => {
      if (phaseRef.current !== "live") return;
      if (Math.random() < p.acc) {
        aiScores("🤖 The AI buzzed in first!");
      } else {
        // AI fumbled — give the player a grace window to steal the point,
        // then the AI recovers so the match can't stall.
        setMsg("🤖 The AI fumbled — quick, answer!");
        graceTimer.current = setTimeout(() => {
          if (phaseRef.current !== "live") return;
          aiScores("🤖 The AI recovered and answered.");
        }, p.grace);
      }
    }, t);
  }, [level]);

  const startMatch = useCallback(() => {
    clearTimers();
    setYou(0); setAi(0); setMsg("");
    beginRound(0, 0);
  }, [beginRound]);

  const answer = (v: number) => {
    if (phaseRef.current !== "live" || !round) return;
    clearTimers();
    if (v === round.answer) {
      setPhase("youWin"); setMsg("⚡ You buzzed in correctly!");
      setYou(you + 1);
      setTimeout(() => beginRound(you + 1, ai), 1300);
    } else {
      setPhase("youWrong"); setMsg(`❌ Wrong — it was ${round.answer}. Point to the AI.`);
      setAi(ai + 1);
      setTimeout(() => beginRound(you, ai + 1), 1300);
    }
  };

  useEffect(() => () => clearTimers(), []);

  const live = phase === "live";

  return (
    <main style={{ maxWidth: 560, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>⚡➗ Number Duel</h1>
        <Link href="/arcade/challenge-ai" style={{ marginLeft: "auto" }}>← Challenge the AI</Link>
      </div>
      <p className="muted">Solve faster than the AI. First to {WIN_AT} points wins. Higher difficulty = a faster, sharper AI.</p>

      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
        <span className="muted">Difficulty:</span>
        {(["easy", "medium", "hard"] as Level[]).map((l) => (
          <button key={l} onClick={() => { setLevel(l); setPhase("idle"); clearTimers(); }} disabled={live}
            style={{ opacity: level === l ? 1 : 0.55, fontWeight: level === l ? 700 : 400 }}>
            {l}
          </button>
        ))}
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", fontWeight: 700, fontSize: 18, margin: "6px 0" }}>
        <span style={{ color: "#7c3aed" }}>You {you}</span>
        <span style={{ color: "#f59e0b" }}>{ai} AI</span>
      </div>

      <div style={{ background: "#0b1220", borderRadius: 14, padding: 20, color: "#fff", textAlign: "center", minHeight: 220 }}>
        {phase === "idle" && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14, paddingTop: 30 }}>
            <div style={{ fontSize: 16, opacity: 0.85 }}>Beat the AI to the buzzer!</div>
            <button onClick={startMatch} style={{ background: "#f59e0b", color: "#111", padding: "12px 28px", fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer", fontWeight: 700 }}>▶ Start duel</button>
          </div>
        )}

        {phase === "done" && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14, paddingTop: 30 }}>
            <div style={{ fontSize: 22, fontWeight: 800 }}>{msg}</div>
            <div style={{ opacity: 0.85 }}>Final: You {you} · AI {ai}</div>
            <button onClick={startMatch} style={{ background: "#f59e0b", color: "#111", padding: "12px 28px", fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer", fontWeight: 700 }}>▶ Rematch</button>
          </div>
        )}

        {round && (phase === "live" || phase === "youWin" || phase === "aiWin" || phase === "youWrong") && (
          <>
            <div style={{ height: 8, background: "rgba(255,255,255,0.12)", borderRadius: 4, overflow: "hidden", marginBottom: 18 }}>
              <div style={{ height: "100%", width: `${barPct}%`, background: "#f59e0b", transition: live ? `width ${barMs}ms linear` : "none" }} />
            </div>
            <div style={{ fontSize: 40, fontWeight: 800, marginBottom: 18 }}>{round.text} = ?</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, maxWidth: 320, margin: "0 auto" }}>
              {round.options.map((o, i) => (
                <button key={i} onClick={() => answer(o)} disabled={!live}
                  style={{ padding: "14px 0", fontSize: 22, fontWeight: 700, borderRadius: 10, border: 0, cursor: live ? "pointer" : "default", background: "#7c3aed", color: "#fff" }}>
                  {o}
                </button>
              ))}
            </div>
            {msg && <div style={{ marginTop: 16, fontSize: 16, fontWeight: 600 }}>{msg}</div>}
          </>
        )}
      </div>
    </main>
  );
}
