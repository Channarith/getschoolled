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
  easy: { min: 4500, max: 6000, acc: 0.45, grace: 3500 },
  medium: { min: 2200, max: 3200, acc: 0.75, grace: 1800 },
  hard: { min: 900, max: 1700, acc: 0.95, grace: 1000 },
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
  const nextTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // A round is resolved exactly once. `roundSeq` is a monotonic counter so every
  // round gets a unique id that is never reused; `liveId` is the id that may
  // currently be resolved (0 once consumed). Any pending resolver (player click
  // OR an AI timer) must present the live id, and resolving clears it so neither
  // the other path nor a stale timer from an earlier round can score again.
  // Scores/level live in refs so nothing reads a stale closure.
  const roundSeqRef = useRef(0);
  const liveIdRef = useRef(0);
  const scoreRef = useRef({ you: 0, ai: 0 });
  const levelRef = useRef<Level>(level);
  levelRef.current = level;
  const beginRoundRef = useRef<() => void>(() => {});
  const resolveRef = useRef<(id: number, endPhase: Phase, message: string) => void>(() => {});

  const clearRoundTimers = () => {
    if (aiTimer.current) { clearTimeout(aiTimer.current); aiTimer.current = null; }
    if (graceTimer.current) { clearTimeout(graceTimer.current); graceTimer.current = null; }
  };
  const stopAll = useCallback(() => {
    clearRoundTimers();
    if (nextTimer.current) { clearTimeout(nextTimer.current); nextTimer.current = null; }
    liveIdRef.current = 0;
  }, []);

  // Resolve the active round once. Idempotent: a stale/duplicate call whose id no
  // longer matches is ignored, so the player and the AI can never both score.
  const resolve = useCallback((id: number, endPhase: Phase, message: string) => {
    if (id === 0 || id !== liveIdRef.current) return;
    liveIdRef.current = 0;
    clearRoundTimers();
    if (endPhase === "youWin") { scoreRef.current.you += 1; setYou(scoreRef.current.you); }
    else { scoreRef.current.ai += 1; setAi(scoreRef.current.ai); }
    setPhase(endPhase); setMsg(message);
    nextTimer.current = setTimeout(() => beginRoundRef.current(), 1300);
  }, []);
  resolveRef.current = resolve;

  // Launch one round. Reads scores/level from refs so it never sees stale state.
  const beginRound = useCallback(() => {
    const { you: yScore, ai: aScore } = scoreRef.current;
    if (yScore >= WIN_AT || aScore >= WIN_AT) {
      setPhase("done");
      setMsg(yScore > aScore ? "🏆 You beat the AI in the match!" : "🤖 The AI takes the match.");
      return;
    }
    const lvl = levelRef.current;
    const id = ++roundSeqRef.current;
    liveIdRef.current = id;
    const r = makeRound(lvl);
    setRound(r); setPhase("live"); setMsg("");
    const p = AI_PARAMS[lvl];
    const t = p.min + Math.random() * (p.max - p.min);
    setBarMs(t); setBarPct(0);
    requestAnimationFrame(() => requestAnimationFrame(() => setBarPct(100)));
    clearRoundTimers();
    aiTimer.current = setTimeout(() => {
      if (Math.random() < p.acc) {
        resolveRef.current(id, "aiWin", "🤖 The AI buzzed in first!");
      } else {
        // AI fumbled — give the player a grace window to steal the point,
        // then the AI recovers so the match can't stall.
        setMsg("🤖 The AI fumbled — quick, answer!");
        graceTimer.current = setTimeout(
          () => resolveRef.current(id, "aiWin", "🤖 The AI recovered and answered."),
          p.grace,
        );
      }
    }, t);
  }, []);
  beginRoundRef.current = beginRound;

  const startMatch = useCallback(() => {
    stopAll();
    scoreRef.current = { you: 0, ai: 0 };
    setYou(0); setAi(0); setMsg("");
    beginRound();
  }, [beginRound, stopAll]);

  const answer = (v: number) => {
    const id = liveIdRef.current;
    if (phase !== "live" || !round || id === 0) return;
    resolve(
      id,
      v === round.answer ? "youWin" : "youWrong",
      v === round.answer ? "⚡ You buzzed in correctly!" : `❌ Wrong — it was ${round.answer}. Point to the AI.`,
    );
  };

  useEffect(() => () => stopAll(), [stopAll]);

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
          <button key={l} onClick={() => { setLevel(l); setPhase("idle"); stopAll(); }} disabled={live}
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
