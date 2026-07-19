"use client";

// Connect Four Duel vs the AI. Drop discs to line up four in a row. The AI uses
// alpha-beta minimax with a window-scoring heuristic; its search depth (how many
// moves it looks ahead) scales with the chosen difficulty. Fully client-side.

import Link from "next/link";
import { useEffect, useState } from "react";

const ROWS = 6, COLS = 7;
const EMPTY = 0, YOU = 1, AI = 2;
type Board = number[][];
type Level = "easy" | "medium" | "hard";

const DEPTH: Record<Level, number> = { easy: 1, medium: 3, hard: 5 };

const emptyBoard = (): Board => Array.from({ length: ROWS }, () => Array(COLS).fill(EMPTY));
const validCols = (b: Board): number[] => { const r: number[] = []; for (let c = 0; c < COLS; c++) if (b[0][c] === EMPTY) r.push(c); return r; };

function drop(b: Board, col: number, piece: number): { board: Board; row: number } | null {
  for (let row = ROWS - 1; row >= 0; row--) {
    if (b[row][col] === EMPTY) {
      const nb = b.map((r) => [...r]); nb[row][col] = piece;
      return { board: nb, row };
    }
  }
  return null;
}

function isWin(b: Board, piece: number): boolean {
  for (let r = 0; r < ROWS; r++) for (let c = 0; c < COLS; c++) {
    if (b[r][c] !== piece) continue;
    if (c + 3 < COLS && b[r][c + 1] === piece && b[r][c + 2] === piece && b[r][c + 3] === piece) return true;
    if (r + 3 < ROWS && b[r + 1][c] === piece && b[r + 2][c] === piece && b[r + 3][c] === piece) return true;
    if (r + 3 < ROWS && c + 3 < COLS && b[r + 1][c + 1] === piece && b[r + 2][c + 2] === piece && b[r + 3][c + 3] === piece) return true;
    if (r + 3 < ROWS && c - 3 >= 0 && b[r + 1][c - 1] === piece && b[r + 2][c - 2] === piece && b[r + 3][c - 3] === piece) return true;
  }
  return false;
}

function scoreWindow(win: number[]): number {
  const ai = win.filter((v) => v === AI).length;
  const you = win.filter((v) => v === YOU).length;
  const empty = win.filter((v) => v === EMPTY).length;
  if (ai > 0 && you > 0) return 0;
  if (ai === 4) return 100000;
  if (ai === 3 && empty === 1) return 120;
  if (ai === 2 && empty === 2) return 12;
  if (you === 3 && empty === 1) return -150;
  if (you === 2 && empty === 2) return -12;
  return 0;
}

function heuristic(b: Board): number {
  let score = 0;
  for (let r = 0; r < ROWS; r++) if (b[r][3] === AI) score += 6;
  const windows: number[][] = [];
  for (let r = 0; r < ROWS; r++) for (let c = 0; c < COLS; c++) {
    if (c + 3 < COLS) windows.push([b[r][c], b[r][c + 1], b[r][c + 2], b[r][c + 3]]);
    if (r + 3 < ROWS) windows.push([b[r][c], b[r + 1][c], b[r + 2][c], b[r + 3][c]]);
    if (r + 3 < ROWS && c + 3 < COLS) windows.push([b[r][c], b[r + 1][c + 1], b[r + 2][c + 2], b[r + 3][c + 3]]);
    if (r + 3 < ROWS && c - 3 >= 0) windows.push([b[r][c], b[r + 1][c - 1], b[r + 2][c - 2], b[r + 3][c - 3]]);
  }
  for (const w of windows) score += scoreWindow(w);
  return score;
}

function minimax(b: Board, depth: number, alpha: number, beta: number, maximizing: boolean): { score: number; col: number } {
  const cols = validCols(b);
  if (isWin(b, AI)) return { score: 1e7 + depth, col: -1 };
  if (isWin(b, YOU)) return { score: -1e7 - depth, col: -1 };
  if (cols.length === 0) return { score: 0, col: -1 };
  if (depth === 0) return { score: heuristic(b), col: -1 };
  // Prefer center-first ordering for stronger pruning.
  const ordered = [...cols].sort((a, c) => Math.abs(3 - a) - Math.abs(3 - c));
  let bestCol = ordered[0];
  if (maximizing) {
    let value = -Infinity;
    for (const c of ordered) {
      const res = drop(b, c, AI); if (!res) continue;
      const s = minimax(res.board, depth - 1, alpha, beta, false).score;
      if (s > value) { value = s; bestCol = c; }
      alpha = Math.max(alpha, value);
      if (alpha >= beta) break;
    }
    return { score: value, col: bestCol };
  }
  let value = Infinity;
  for (const c of ordered) {
    const res = drop(b, c, YOU); if (!res) continue;
    const s = minimax(res.board, depth - 1, alpha, beta, true).score;
    if (s < value) { value = s; bestCol = c; }
    beta = Math.min(beta, value);
    if (alpha >= beta) break;
  }
  return { score: value, col: bestCol };
}

export default function ConnectFour() {
  const [level, setLevel] = useState<Level>("medium");
  const [board, setBoard] = useState<Board>(emptyBoard());
  const [turn, setTurn] = useState<number>(YOU);
  const [result, setResult] = useState<"you" | "ai" | "draw" | "">("");
  const [record, setRecord] = useState({ w: 0, l: 0, d: 0 });

  useEffect(() => {
    try {
      const r = JSON.parse(localStorage.getItem("aoep_c4_record") || "");
      if (r && typeof r.w === "number") setRecord(r);
    } catch { /* */ }
  }, []);

  const finish = (res: "you" | "ai" | "draw") => {
    setResult(res);
    setRecord((r) => {
      const nr = { ...r };
      if (res === "you") nr.w += 1; else if (res === "ai") nr.l += 1; else nr.d += 1;
      try { localStorage.setItem("aoep_c4_record", JSON.stringify(nr)); } catch { /* */ }
      return nr;
    });
  };

  const playCol = (col: number) => {
    if (result || turn !== YOU) return;
    const res = drop(board, col, YOU);
    if (!res) return;
    setBoard(res.board);
    if (isWin(res.board, YOU)) { finish("you"); return; }
    if (validCols(res.board).length === 0) { finish("draw"); return; }
    setTurn(AI);
  };

  useEffect(() => {
    if (turn !== AI || result) return;
    const t = setTimeout(() => {
      const cols = validCols(board);
      if (cols.length === 0) { finish("draw"); return; }
      const { col } = minimax(board, DEPTH[level], -Infinity, Infinity, true);
      const pick = col >= 0 && cols.includes(col) ? col : cols[Math.floor(Math.random() * cols.length)];
      const res = drop(board, pick, AI);
      if (!res) return;
      setBoard(res.board);
      if (isWin(res.board, AI)) { finish("ai"); return; }
      if (validCols(res.board).length === 0) { finish("draw"); return; }
      setTurn(YOU);
    }, 350);
    return () => clearTimeout(t);
  }, [turn, board, level, result]);

  const reset = () => { setBoard(emptyBoard()); setTurn(YOU); setResult(""); };

  const banner = result === "you" ? "🎉 You beat the AI!"
    : result === "ai" ? "🤖 The AI connected four."
    : result === "draw" ? "🤝 It's a draw."
    : turn === YOU ? "Your move (🔴)" : "AI is thinking…";

  return (
    <main style={{ maxWidth: 560, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>🔴🟡 Connect Four Duel</h1>
        <Link href="/arcade/challenge-ai" style={{ marginLeft: "auto" }}>← Challenge the AI</Link>
      </div>
      <p className="muted">Drop your discs to connect four. Higher difficulty = the AI looks further ahead.</p>

      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
        <span className="muted">Difficulty:</span>
        {(["easy", "medium", "hard"] as Level[]).map((l) => (
          <button key={l} onClick={() => { setLevel(l); reset(); }}
            style={{ opacity: level === l ? 1 : 0.55, fontWeight: level === l ? 700 : 400 }}>
            {l}
          </button>
        ))}
        <span className="muted" style={{ marginLeft: "auto" }}>W {record.w} · L {record.l} · D {record.d}</span>
      </div>

      <div style={{ fontSize: 18, fontWeight: 700, margin: "6px 0 12px", minHeight: 26 }}>{banner}</div>

      <div style={{ background: "#1d4ed8", padding: 8, borderRadius: 12 }}>
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${COLS}, 1fr)`, gap: 6 }}>
          {Array.from({ length: COLS }).map((_, c) => (
            <button key={`h${c}`} onClick={() => playCol(c)} disabled={!!result || turn !== YOU || board[0][c] !== EMPTY}
              style={{ padding: "2px 0", fontSize: 14, background: "rgba(255,255,255,0.15)", color: "#fff", border: 0, borderRadius: 6, cursor: (result || turn !== YOU) ? "default" : "pointer" }}>
              ▼
            </button>
          ))}
          {board.flatMap((row, r) => row.map((cell, c) => (
            <div key={`${r}-${c}`} onClick={() => playCol(c)}
              style={{
                aspectRatio: "1 / 1", borderRadius: "50%", cursor: (result || turn !== YOU) ? "default" : "pointer",
                background: cell === YOU ? "radial-gradient(circle at 35% 30%, #fca5a5, #dc2626)"
                  : cell === AI ? "radial-gradient(circle at 35% 30%, #fde68a, #f59e0b)"
                  : "#0b1220",
              }} />
          )))}
        </div>
      </div>

      <div style={{ marginTop: 16 }}>
        <button onClick={reset} style={{ background: "#0ea5e9", color: "#fff", padding: "10px 22px" }}>
          {result ? "▶ New game" : "↺ Restart"}
        </button>
      </div>
    </main>
  );
}
