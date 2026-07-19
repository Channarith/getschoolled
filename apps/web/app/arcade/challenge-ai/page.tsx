"use client";

// Challenge the AI — a hub of "can you beat the computer?" games. Each game ships
// a real AI opponent (not a stub): Tic-Tac-Toe uses perfect minimax (unbeatable on
// Hard — the best you can do is draw), Connect Four uses depth-limited alpha-beta
// minimax with a positional heuristic (beatable, but it defends and sets traps),
// and Quiz Duel races you against a reaction-time + accuracy modelled opponent.
// Pick a difficulty and see if you can beat it.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

type Difficulty = "easy" | "medium" | "hard";
type Game = "menu" | "ttt" | "c4" | "duel";

const DIFF_LABEL: Record<Difficulty, string> = { easy: "Easy", medium: "Medium", hard: "Hard" };

function DifficultyPicker({ value, onChange, disabled }: { value: Difficulty; onChange: (d: Difficulty) => void; disabled?: boolean }) {
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
      <span className="muted">AI difficulty:</span>
      {(["easy", "medium", "hard"] as Difficulty[]).map((d) => (
        <button key={d} onClick={() => onChange(d)} disabled={disabled}
          style={{ opacity: value === d ? 1 : 0.55, fontWeight: value === d ? 700 : 400 }}>
          {DIFF_LABEL[d]}
        </button>
      ))}
    </div>
  );
}

// ============================ Tic-Tac-Toe ====================================
type TCell = "X" | "O" | null;
const T_LINES = [
  [0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 3, 6], [1, 4, 7], [2, 5, 8], [0, 4, 8], [2, 4, 6],
];

function tttWinner(b: TCell[]): "X" | "O" | "draw" | null {
  for (const [a, c, d] of T_LINES) {
    if (b[a] && b[a] === b[c] && b[a] === b[d]) return b[a];
  }
  return b.every((x) => x) ? "draw" : null;
}

function tttMinimax(b: TCell[], isMax: boolean, depth: number): number {
  const w = tttWinner(b);
  if (w === "O") return 10 - depth;
  if (w === "X") return depth - 10;
  if (w === "draw") return 0;
  if (isMax) {
    let best = -Infinity;
    for (let i = 0; i < 9; i++) {
      if (!b[i]) { b[i] = "O"; best = Math.max(best, tttMinimax(b, false, depth + 1)); b[i] = null; }
    }
    return best;
  }
  let best = Infinity;
  for (let i = 0; i < 9; i++) {
    if (!b[i]) { b[i] = "X"; best = Math.min(best, tttMinimax(b, true, depth + 1)); b[i] = null; }
  }
  return best;
}

function tttBestMove(b: TCell[], diff: Difficulty): number {
  const avail = b.map((v, i) => (v ? -1 : i)).filter((i) => i >= 0);
  if (diff === "easy") return avail[Math.floor(Math.random() * avail.length)];
  if (diff === "medium" && Math.random() < 0.45) return avail[Math.floor(Math.random() * avail.length)];
  let best = -Infinity, move = avail[0];
  for (const i of avail) {
    b[i] = "O";
    const score = tttMinimax(b, false, 0);
    b[i] = null;
    if (score > best) { best = score; move = i; }
  }
  return move;
}

function TicTacToe({ diff }: { diff: Difficulty }) {
  const [board, setBoard] = useState<TCell[]>(Array(9).fill(null));
  const [turn, setTurn] = useState<"X" | "O">("X");
  const [record, setRecord] = useState({ w: 0, l: 0, d: 0 });
  const result = tttWinner(board);
  const busy = turn === "O" && !result;

  const play = (i: number) => {
    if (board[i] || result || turn !== "X") return;
    const nb = board.slice();
    nb[i] = "X";
    setBoard(nb);
    setTurn("O");
  };

  useEffect(() => {
    if (turn !== "O") return;
    const r = tttWinner(board);
    if (r) return;
    const id = setTimeout(() => {
      const nb = board.slice();
      const m = tttBestMove(nb, diff);
      nb[m] = "O";
      setBoard(nb);
      setTurn("X");
    }, 450);
    return () => clearTimeout(id);
  }, [turn, board, diff]);

  const scored = useRef<TCell[] | null>(null);
  useEffect(() => {
    if (result && scored.current !== board) {
      scored.current = board;
      setRecord((r) => ({
        w: r.w + (result === "X" ? 1 : 0),
        l: r.l + (result === "O" ? 1 : 0),
        d: r.d + (result === "draw" ? 1 : 0),
      }));
    }
  }, [result, board]);

  const reset = () => { setBoard(Array(9).fill(null)); setTurn("X"); scored.current = null; };

  return (
    <div>
      <p className="muted">You are ❌. {diff === "hard" ? "Hard = perfect play; the best you can do is a draw." : "Get three in a row before the AI does."}</p>
      <div style={{ display: "flex", gap: 16, alignItems: "flex-start", flexWrap: "wrap" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 84px)", gridTemplateRows: "repeat(3, 84px)", gap: 6 }}>
          {board.map((c, i) => (
            <button key={i} onClick={() => play(i)} disabled={!!c || !!result || busy}
              style={{
                fontSize: 40, fontWeight: 800, borderRadius: 12, border: "1px solid var(--border)",
                background: "rgba(124,58,237,0.06)", cursor: c || result ? "default" : "pointer",
                color: c === "X" ? "#7c3aed" : "#0ea5e9",
              }}>
              {c === "X" ? "❌" : c === "O" ? "⭕" : ""}
            </button>
          ))}
        </div>
        <div className="card" style={{ margin: 0, minWidth: 180 }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>
            {result === "X" ? "🎉 You win!" : result === "O" ? "🤖 AI wins" : result === "draw" ? "🤝 Draw" : busy ? "🤖 AI thinking…" : "Your move"}
          </div>
          <div className="muted" style={{ fontSize: 14 }}>Wins {record.w} · Losses {record.l} · Draws {record.d}</div>
          <button onClick={reset} style={{ marginTop: 12, background: "#7c3aed", color: "#fff", width: "100%" }}>New game</button>
        </div>
      </div>
    </div>
  );
}

// ============================ Connect Four ===================================
const C4_ROWS = 6;
const C4_COLS = 7;
type C4Board = number[][]; // 0 empty, 1 player, 2 ai

function c4Empty(): C4Board {
  return Array.from({ length: C4_ROWS }, () => Array<number>(C4_COLS).fill(0));
}
function c4Drop(b: C4Board, col: number, player: number): number {
  for (let r = C4_ROWS - 1; r >= 0; r--) {
    if (b[r][col] === 0) { b[r][col] = player; return r; }
  }
  return -1;
}
function c4ValidCols(b: C4Board): number[] {
  const cols: number[] = [];
  for (let c = 0; c < C4_COLS; c++) if (b[0][c] === 0) cols.push(c);
  return cols;
}
function c4Wins(b: C4Board, player: number): boolean {
  for (let r = 0; r < C4_ROWS; r++) {
    for (let c = 0; c < C4_COLS; c++) {
      if (b[r][c] !== player) continue;
      for (const [dr, dc] of [[0, 1], [1, 0], [1, 1], [1, -1]]) {
        let k = 1;
        while (k < 4) {
          const nr = r + dr * k, nc = c + dc * k;
          if (nr < 0 || nr >= C4_ROWS || nc < 0 || nc >= C4_COLS || b[nr][nc] !== player) break;
          k++;
        }
        if (k === 4) return true;
      }
    }
  }
  return false;
}
function c4ScoreWindow(win: number[]): number {
  const ai = win.filter((x) => x === 2).length;
  const pl = win.filter((x) => x === 1).length;
  const empty = win.filter((x) => x === 0).length;
  if (ai > 0 && pl > 0) return 0;
  if (ai === 4) return 10000;
  if (ai === 3 && empty === 1) return 60;
  if (ai === 2 && empty === 2) return 8;
  if (pl === 4) return -10000;
  if (pl === 3 && empty === 1) return -80; // block player threats aggressively
  if (pl === 2 && empty === 2) return -6;
  return 0;
}
function c4Heuristic(b: C4Board): number {
  let score = 0;
  for (let r = 0; r < C4_ROWS; r++) if (b[r][3] === 2) score += 6; // center control
  const windows: number[][] = [];
  for (let r = 0; r < C4_ROWS; r++) {
    for (let c = 0; c < C4_COLS; c++) {
      for (const [dr, dc] of [[0, 1], [1, 0], [1, 1], [1, -1]]) {
        const win: number[] = [];
        for (let k = 0; k < 4; k++) {
          const nr = r + dr * k, nc = c + dc * k;
          if (nr < 0 || nr >= C4_ROWS || nc < 0 || nc >= C4_COLS) { win.length = 0; break; }
          win.push(b[nr][nc]);
        }
        if (win.length === 4) windows.push(win);
      }
    }
  }
  for (const w of windows) score += c4ScoreWindow(w);
  return score;
}
function c4Minimax(b: C4Board, depth: number, alpha: number, beta: number, maximizing: boolean): number {
  if (c4Wins(b, 2)) return 100000 + depth;
  if (c4Wins(b, 1)) return -100000 - depth;
  const valid = c4ValidCols(b);
  if (depth === 0 || valid.length === 0) return c4Heuristic(b);
  if (maximizing) {
    let value = -Infinity;
    for (const c of valid) {
      const nb = b.map((row) => row.slice());
      c4Drop(nb, c, 2);
      value = Math.max(value, c4Minimax(nb, depth - 1, alpha, beta, false));
      alpha = Math.max(alpha, value);
      if (alpha >= beta) break;
    }
    return value;
  }
  let value = Infinity;
  for (const c of valid) {
    const nb = b.map((row) => row.slice());
    c4Drop(nb, c, 1);
    value = Math.min(value, c4Minimax(nb, depth - 1, alpha, beta, true));
    beta = Math.min(beta, value);
    if (alpha >= beta) break;
  }
  return value;
}
function c4BestCol(b: C4Board, diff: Difficulty): number {
  const valid = c4ValidCols(b);
  if (diff === "easy") return valid[Math.floor(Math.random() * valid.length)];
  if (diff === "medium" && Math.random() < 0.35) return valid[Math.floor(Math.random() * valid.length)];
  const depth = diff === "hard" ? 5 : 3;
  let best = -Infinity, move = valid[0];
  for (const c of valid.sort((a, z) => Math.abs(3 - a) - Math.abs(3 - z))) {
    const nb = b.map((row) => row.slice());
    c4Drop(nb, c, 2);
    const score = c4Minimax(nb, depth - 1, -Infinity, Infinity, false);
    if (score > best) { best = score; move = c; }
  }
  return move;
}

function ConnectFour({ diff }: { diff: Difficulty }) {
  const [board, setBoard] = useState<C4Board>(c4Empty);
  const [turn, setTurn] = useState<1 | 2>(1);
  const [status, setStatus] = useState<"play" | "win" | "lose" | "draw">("play");
  const [record, setRecord] = useState({ w: 0, l: 0, d: 0 });

  const drop = (col: number) => {
    if (status !== "play" || turn !== 1) return;
    const nb = board.map((row) => row.slice());
    if (c4Drop(nb, col, 1) < 0) return;
    if (c4Wins(nb, 1)) { setBoard(nb); setStatus("win"); setRecord((r) => ({ ...r, w: r.w + 1 })); return; }
    if (c4ValidCols(nb).length === 0) { setBoard(nb); setStatus("draw"); setRecord((r) => ({ ...r, d: r.d + 1 })); return; }
    setBoard(nb); setTurn(2);
  };

  useEffect(() => {
    if (turn !== 2 || status !== "play") return;
    const id = setTimeout(() => {
      const nb = board.map((row) => row.slice());
      const c = c4BestCol(nb, diff);
      c4Drop(nb, c, 2);
      if (c4Wins(nb, 2)) { setBoard(nb); setStatus("lose"); setRecord((r) => ({ ...r, l: r.l + 1 })); return; }
      if (c4ValidCols(nb).length === 0) { setBoard(nb); setStatus("draw"); setRecord((r) => ({ ...r, d: r.d + 1 })); return; }
      setBoard(nb); setTurn(1);
    }, 400);
    return () => clearTimeout(id);
  }, [turn, status, board, diff]);

  const reset = () => { setBoard(c4Empty()); setTurn(1); setStatus("play"); };

  return (
    <div>
      <p className="muted">You are 🔴 — drop a disc by clicking a column. Connect four in a row to win. {diff === "hard" ? "Hard looks 5 moves ahead." : ""}</p>
      <div style={{ display: "flex", gap: 16, alignItems: "flex-start", flexWrap: "wrap" }}>
        <div style={{ background: "#1e3a8a", padding: 8, borderRadius: 12, display: "inline-block" }}>
          <div style={{ display: "grid", gridTemplateColumns: `repeat(${C4_COLS}, 44px)`, gap: 4 }}>
            {Array.from({ length: C4_COLS }).map((_, c) => (
              <button key={`h${c}`} onClick={() => drop(c)} disabled={status !== "play" || turn !== 1 || board[0][c] !== 0}
                style={{ height: 22, borderRadius: 6, border: 0, cursor: "pointer", background: "rgba(255,255,255,0.15)", color: "#fff", fontSize: 12 }}>
                ▼
              </button>
            ))}
            {board.flatMap((row, r) => row.map((cell, c) => (
              <div key={`${r}-${c}`} style={{
                width: 44, height: 44, borderRadius: "50%",
                background: cell === 1 ? "radial-gradient(circle at 35% 30%, #fca5a5, #dc2626)"
                  : cell === 2 ? "radial-gradient(circle at 35% 30%, #fde68a, #f59e0b)"
                    : "#0b1e5b",
                boxShadow: "inset 0 2px 4px rgba(0,0,0,0.4)",
              }} />
            )))}
          </div>
        </div>
        <div className="card" style={{ margin: 0, minWidth: 180 }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>
            {status === "win" ? "🎉 You win!" : status === "lose" ? "🤖 AI wins" : status === "draw" ? "🤝 Draw" : turn === 2 ? "🤖 AI thinking…" : "Your move"}
          </div>
          <div className="muted" style={{ fontSize: 14 }}>Wins {record.w} · Losses {record.l} · Draws {record.d}</div>
          <button onClick={reset} style={{ marginTop: 12, background: "#0ea5e9", color: "#fff", width: "100%" }}>New game</button>
        </div>
      </div>
    </div>
  );
}

// ============================ Quiz Duel ======================================
type DuelQ = { q: string; options: string[]; answer: number };
const DUEL_BANK: DuelQ[] = [
  { q: "7 × 8 = ?", options: ["54", "56", "48", "64"], answer: 1 },
  { q: "Capital of Japan?", options: ["Seoul", "Beijing", "Tokyo", "Bangkok"], answer: 2 },
  { q: "H2O is…", options: ["Salt", "Water", "Oxygen", "Gold"], answer: 1 },
  { q: "Angles in a triangle sum to?", options: ["90°", "180°", "270°", "360°"], answer: 1 },
  { q: "Which is a prime number?", options: ["9", "15", "17", "21"], answer: 2 },
  { q: "Largest planet in our solar system?", options: ["Earth", "Saturn", "Jupiter", "Mars"], answer: 2 },
  { q: "12 + 15 = ?", options: ["25", "27", "28", "29"], answer: 1 },
  { q: "Author of Romeo and Juliet?", options: ["Dickens", "Shakespeare", "Twain", "Austen"], answer: 1 },
  { q: "Square root of 144?", options: ["11", "12", "13", "14"], answer: 1 },
  { q: "Speed of light is fastest in…", options: ["Water", "Glass", "Vacuum", "Air"], answer: 2 },
  { q: "How many continents are there?", options: ["5", "6", "7", "8"], answer: 2 },
  { q: "15% of 200 = ?", options: ["25", "30", "35", "40"], answer: 1 },
  { q: "Gas plants absorb?", options: ["Oxygen", "Nitrogen", "CO₂", "Helium"], answer: 2 },
  { q: "A hexagon has how many sides?", options: ["5", "6", "7", "8"], answer: 1 },
  { q: "9 squared = ?", options: ["72", "81", "90", "99"], answer: 1 },
];

const DUEL_TARGET = 5;
const DUEL_PROFILE: Record<Difficulty, { accuracy: number; minMs: number; maxMs: number }> = {
  easy: { accuracy: 0.55, minMs: 2500, maxMs: 5000 },
  medium: { accuracy: 0.75, minMs: 1600, maxMs: 3500 },
  hard: { accuracy: 0.9, minMs: 900, maxMs: 2200 },
};

function shuffle<T>(arr: T[]): T[] {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function QuizDuel({ diff }: { diff: Difficulty }) {
  const [queue, setQueue] = useState<DuelQ[]>(() => shuffle(DUEL_BANK));
  const [qi, setQi] = useState(0);
  const [scores, setScores] = useState({ you: 0, ai: 0 });
  const [locked, setLocked] = useState<{ you: boolean; ai: boolean }>({ you: false, ai: false });
  const [banner, setBanner] = useState("");
  const [phase, setPhase] = useState<"play" | "result" | "over">("play");
  const [winner, setWinner] = useState<"you" | "ai" | null>(null);
  const resolvedRef = useRef(false);
  const aiTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const nextTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const current = queue[qi % queue.length];

  const clearTimers = () => {
    if (aiTimer.current) clearTimeout(aiTimer.current);
    if (nextTimer.current) clearTimeout(nextTimer.current);
  };

  const endRound = useCallback((who: "you" | "ai" | "none") => {
    if (resolvedRef.current) return;
    resolvedRef.current = true;
    if (aiTimer.current) clearTimeout(aiTimer.current);
    setScores((s) => {
      const ns = { you: s.you + (who === "you" ? 1 : 0), ai: s.ai + (who === "ai" ? 1 : 0) };
      if (ns.you >= DUEL_TARGET || ns.ai >= DUEL_TARGET) {
        setWinner(ns.you > ns.ai ? "you" : "ai");
        setPhase("over");
      }
      return ns;
    });
    setBanner(who === "you" ? "✅ You got it first!" : who === "ai" ? "🤖 AI buzzed in first!" : "⏳ Nobody got it.");
    setPhase((p) => (p === "over" ? "over" : "result"));
    nextTimer.current = setTimeout(() => {
      setPhase((p) => {
        if (p === "over") return p;
        setQi((i) => i + 1);
        setLocked({ you: false, ai: false });
        setBanner("");
        resolvedRef.current = false;
        return "play";
      });
    }, 1300);
  }, []);

  // Schedule the AI's attempt for each new question.
  useEffect(() => {
    if (phase !== "play") return;
    resolvedRef.current = false;
    const prof = DUEL_PROFILE[diff];
    const delay = prof.minMs + Math.random() * (prof.maxMs - prof.minMs);
    const willBeCorrect = Math.random() < prof.accuracy;
    aiTimer.current = setTimeout(() => {
      if (resolvedRef.current) return;
      if (willBeCorrect) {
        endRound("ai");
      } else {
        setLocked((l) => ({ ...l, ai: true }));
      }
    }, delay);
    return () => { if (aiTimer.current) clearTimeout(aiTimer.current); };
  }, [qi, phase, diff, endRound]);

  useEffect(() => () => clearTimers(), []);

  const answer = (idx: number) => {
    if (phase !== "play" || locked.you || resolvedRef.current) return;
    if (idx === current.answer) endRound("you");
    else setLocked((l) => ({ ...l, you: true }));
  };

  const restart = () => {
    clearTimers();
    resolvedRef.current = false;
    setQueue(shuffle(DUEL_BANK));
    setQi(0); setScores({ you: 0, ai: 0 }); setLocked({ you: false, ai: false });
    setBanner(""); setPhase("play"); setWinner(null);
  };

  return (
    <div>
      <p className="muted">First to {DUEL_TARGET} points wins. Buzz in faster than the AI — but a wrong answer locks you out of the round. ({DIFF_LABEL[diff]} AI)</p>
      <div style={{ display: "flex", gap: 16, justifyContent: "center", marginBottom: 12 }}>
        <div style={{ textAlign: "center" }}>
          <div className="muted" style={{ fontSize: 12 }}>You</div>
          <div style={{ fontSize: 32, fontWeight: 800, color: "#7c3aed" }}>{scores.you}</div>
        </div>
        <div style={{ alignSelf: "center", fontWeight: 700 }}>vs</div>
        <div style={{ textAlign: "center" }}>
          <div className="muted" style={{ fontSize: 12 }}>🤖 AI</div>
          <div style={{ fontSize: 32, fontWeight: 800, color: "#0ea5e9" }}>{scores.ai}</div>
        </div>
      </div>

      {phase === "over" ? (
        <div className="card" style={{ textAlign: "center", borderColor: winner === "you" ? "#16a34a" : "#dc2626" }}>
          <div style={{ fontSize: 22, fontWeight: 700 }}>
            {winner === "you" ? "🏆 You beat the AI!" : "🤖 The AI won this time."}
          </div>
          <div className="muted" style={{ marginTop: 4 }}>Final score {scores.you} – {scores.ai}</div>
          <button onClick={restart} style={{ marginTop: 12, background: "#7c3aed", color: "#fff" }}>Rematch</button>
        </div>
      ) : (
        <div className="card">
          <div style={{ fontWeight: 700, fontSize: 18, marginBottom: 10 }}>{current.q}</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            {current.options.map((opt, idx) => (
              <button key={idx} onClick={() => answer(idx)} disabled={phase !== "play" || locked.you}
                style={{
                  padding: "12px", textAlign: "left",
                  opacity: locked.you && phase === "play" ? 0.5 : 1,
                  border: phase === "result" && idx === current.answer ? "2px solid #16a34a" : "1px solid var(--border)",
                }}>
                {opt}
              </button>
            ))}
          </div>
          <div style={{ marginTop: 10, minHeight: 22, fontWeight: 600 }}>
            {banner || (locked.you ? "🔒 You're locked out — the AI can still answer." : locked.ai ? "🤖 AI guessed wrong — quick, answer!" : "\u00A0")}
          </div>
        </div>
      )}
    </div>
  );
}

// ============================ Hub ============================================
const GAMES: { id: Game; icon: string; title: string; blurb: string; color: string }[] = [
  { id: "ttt", icon: "⭕", title: "Tic-Tac-Toe", blurb: "Perfect-play minimax. On Hard, a draw is the best you can hope for.", color: "#7c3aed" },
  { id: "c4", icon: "🔴", title: "Connect Four", blurb: "Depth-limited alpha-beta AI that blocks your threats and sets its own.", color: "#0ea5e9" },
  { id: "duel", icon: "⚡", title: "Quiz Duel", blurb: "Race a reaction-timed AI to buzz in with the right answer first.", color: "#f59e0b" },
];

export default function ChallengeAI() {
  const [game, setGame] = useState<Game>("menu");
  const [diff, setDiff] = useState<Difficulty>("medium");

  return (
    <main style={{ maxWidth: 820, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>🤖 Challenge the AI</h1>
        {game !== "menu" && <button onClick={() => setGame("menu")}>← Games</button>}
        <Link href="/arcade" style={{ marginLeft: game === "menu" ? "auto" : 0 }}>← Arcade</Link>
        <Link href="/rewards">Rewards</Link>
      </div>

      {game === "menu" ? (
        <>
          <p className="muted">Real AI opponents — no scripted push-overs. Pick a game and a difficulty, then see if you can beat it.</p>
          <div style={{ marginBottom: 14 }}>
            <DifficultyPicker value={diff} onChange={setDiff} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
            {GAMES.map((g) => (
              <button key={g.id} onClick={() => setGame(g.id)}
                style={{
                  textAlign: "left", padding: 16, borderRadius: 14, cursor: "pointer",
                  border: "1px solid var(--border)",
                  background: `linear-gradient(135deg, ${g.color}22, transparent)`,
                }}>
                <div style={{ fontSize: 30 }}>{g.icon}</div>
                <div style={{ fontWeight: 700, fontSize: 18, marginTop: 6 }}>{g.title}</div>
                <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>{g.blurb}</div>
                <div style={{ marginTop: 10, color: g.color, fontWeight: 600 }}>Play ({DIFF_LABEL[diff]}) →</div>
              </button>
            ))}
          </div>
        </>
      ) : (
        <div style={{ marginTop: 12 }}>
          <div style={{ marginBottom: 14 }}>
            <DifficultyPicker value={diff} onChange={setDiff} />
          </div>
          {game === "ttt" && <TicTacToe key={diff} diff={diff} />}
          {game === "c4" && <ConnectFour key={diff} diff={diff} />}
          {game === "duel" && <QuizDuel key={diff} diff={diff} />}
        </div>
      )}
    </main>
  );
}
