"use client";

// Geo Blocks — a real Tetris-style falling-block game fused with a geometry quiz.
// Stack the tetrominoes and clear lines the classic way, but every few pieces the
// lab throws a GEOMETRY question at you: answer correctly to detonate a "geo bomb"
// that clears the bottom row and banks bonus points; miss it and the blocks speed
// up for a moment. Difficulty (question depth + fall speed) scales with age group
// (?age=kids|tween|teen|adult). Fully client-side (localStorage best score).

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { GameLoop, Particles, Surface, roundRect } from "../../lib/gameEngine2d";

type Age = "kids" | "tween" | "teen" | "adult";

const COLS = 10;
const ROWS = 20;

// Standard tetromino rotation states (each state = four [x,y] cells in a spawn box).
type Piece = { color: string; states: [number, number][][] };
const PIECES: Record<string, Piece> = {
  I: { color: "#22d3ee", states: [
    [[0, 1], [1, 1], [2, 1], [3, 1]], [[2, 0], [2, 1], [2, 2], [2, 3]],
    [[0, 2], [1, 2], [2, 2], [3, 2]], [[1, 0], [1, 1], [1, 2], [1, 3]],
  ] },
  O: { color: "#facc15", states: [
    [[1, 0], [2, 0], [1, 1], [2, 1]], [[1, 0], [2, 0], [1, 1], [2, 1]],
    [[1, 0], [2, 0], [1, 1], [2, 1]], [[1, 0], [2, 0], [1, 1], [2, 1]],
  ] },
  T: { color: "#a855f7", states: [
    [[1, 0], [0, 1], [1, 1], [2, 1]], [[1, 0], [1, 1], [2, 1], [1, 2]],
    [[0, 1], [1, 1], [2, 1], [1, 2]], [[1, 0], [0, 1], [1, 1], [1, 2]],
  ] },
  S: { color: "#34d399", states: [
    [[1, 0], [2, 0], [0, 1], [1, 1]], [[1, 0], [1, 1], [2, 1], [2, 2]],
    [[1, 1], [2, 1], [0, 2], [1, 2]], [[0, 0], [0, 1], [1, 1], [1, 2]],
  ] },
  Z: { color: "#f87171", states: [
    [[0, 0], [1, 0], [1, 1], [2, 1]], [[2, 0], [1, 1], [2, 1], [1, 2]],
    [[0, 1], [1, 1], [1, 2], [2, 2]], [[1, 0], [0, 1], [1, 1], [0, 2]],
  ] },
  J: { color: "#60a5fa", states: [
    [[0, 0], [0, 1], [1, 1], [2, 1]], [[1, 0], [2, 0], [1, 1], [1, 2]],
    [[0, 1], [1, 1], [2, 1], [2, 2]], [[1, 0], [1, 1], [0, 2], [1, 2]],
  ] },
  L: { color: "#fb923c", states: [
    [[2, 0], [0, 1], [1, 1], [2, 1]], [[1, 0], [1, 1], [1, 2], [2, 2]],
    [[0, 1], [1, 1], [2, 1], [0, 2]], [[0, 0], [1, 0], [1, 1], [1, 2]],
  ] },
};
const PIECE_KEYS = Object.keys(PIECES);

type Profile = { fall: number; fallPerLevel: number; quizEvery: number; depth: number };
const PROFILES: Record<Age, Profile> = {
  kids: { fall: 1.0, fallPerLevel: 0.06, quizEvery: 5, depth: 0 },
  tween: { fall: 0.8, fallPerLevel: 0.07, quizEvery: 4, depth: 1 },
  teen: { fall: 0.6, fallPerLevel: 0.08, quizEvery: 3, depth: 2 },
  adult: { fall: 0.5, fallPerLevel: 0.08, quizEvery: 3, depth: 3 },
};

type Quiz = { q: string; options: string[]; answer: number };

const SHAPE_SIDES: [string, number][] = [
  ["triangle", 3], ["square", 4], ["rectangle", 4], ["pentagon", 5],
  ["hexagon", 6], ["heptagon", 7], ["octagon", 8],
];

function shuffle<T>(a: T[]): T[] {
  const r = [...a];
  for (let i = r.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [r[i], r[j]] = [r[j], r[i]];
  }
  return r;
}

function mcq(q: string, correct: string | number, decoys: (string | number)[]): Quiz {
  const opts = shuffle([String(correct), ...decoys.map(String)]);
  return { q, options: opts, answer: opts.indexOf(String(correct)) };
}

// Age-scaled geometry question bank. depth 0=shapes, 1=+perimeter/angles,
// 2=+area/triangle facts, 3=+circle/polygon angle sums.
function makeQuiz(depth: number): Quiz {
  const pool: (() => Quiz)[] = [];
  pool.push(() => {
    const [name, sides] = SHAPE_SIDES[Math.floor(Math.random() * (depth === 0 ? 4 : SHAPE_SIDES.length))];
    return mcq(`How many sides does a ${name} have?`, sides, [sides + 1, sides - 1, sides + 2]);
  });
  pool.push(() => {
    const [name, sides] = SHAPE_SIDES[Math.floor(Math.random() * (depth === 0 ? 4 : SHAPE_SIDES.length))];
    const wrong = shuffle(SHAPE_SIDES.filter((s) => s[1] !== sides)).slice(0, 3).map((s) => s[0]);
    return mcq(`Which shape has ${sides} sides?`, name, wrong);
  });
  if (depth >= 1) {
    pool.push(() => {
      const s = 2 + Math.floor(Math.random() * 9);
      return mcq(`Perimeter of a square with side ${s}?`, s * 4, [s * 3, s * 4 + 2, s * 2]);
    });
    pool.push(() => mcq("How many degrees are in a right angle?", 90, [45, 180, 60]));
    pool.push(() => mcq("How many degrees in a full turn (circle)?", 360, [180, 270, 90]));
  }
  if (depth >= 2) {
    pool.push(() => {
      const w = 2 + Math.floor(Math.random() * 8), h = 2 + Math.floor(Math.random() * 8);
      return mcq(`Area of a ${w}×${h} rectangle?`, w * h, [w + h, w * h + w, (w * h) - h]);
    });
    pool.push(() => mcq("Interior angles of a triangle add up to?", 180, [90, 360, 270]));
    pool.push(() => mcq("A triangle with all 3 sides equal is…", "equilateral", ["isosceles", "scalene", "right"]));
  }
  if (depth >= 3) {
    pool.push(() => {
      const r = 2 + Math.floor(Math.random() * 6);
      return mcq(`Circumference of a circle radius ${r}? (π≈3.14)`, +(2 * 3.14 * r).toFixed(2),
        [+(3.14 * r).toFixed(2), +(3.14 * r * r).toFixed(2), +(4 * 3.14 * r).toFixed(2)]);
    });
    pool.push(() => {
      const n = 4 + Math.floor(Math.random() * 4);
      return mcq(`Sum of interior angles of a ${n}-gon?`, (n - 2) * 180,
        [(n - 1) * 180, n * 180, (n - 2) * 90]);
    });
  }
  return pool[Math.floor(Math.random() * pool.length)]();
}

type Cell = string | 0;
type Active = { key: string; rot: number; x: number; y: number };

const emptyGrid = (): Cell[][] => Array.from({ length: ROWS }, () => Array<Cell>(COLS).fill(0));
const cellsOf = (a: Active): [number, number][] =>
  PIECES[a.key].states[a.rot % 4].map(([cx, cy]) => [a.x + cx, a.y + cy]);
const collides = (a: Active, grid: Cell[][]): boolean =>
  cellsOf(a).some(([x, y]) => x < 0 || x >= COLS || y >= ROWS || (y >= 0 && grid[y][x] !== 0));

export default function GeoBlocks() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [age, setAge] = useState<Age>("teen");
  const [running, setRunning] = useState(false);
  const [over, setOver] = useState(false);
  const [score, setScore] = useState(0);
  const [lines, setLines] = useState(0);
  const [level, setLevel] = useState(1);
  const [best, setBest] = useState(0);
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [quizMsg, setQuizMsg] = useState("");
  const s = useRef({
    grid: [] as Cell[][], active: null as Active | null, next: "T",
    dropAcc: 0, score: 0, lines: 0, level: 1, placed: 0, speedBoost: 0,
    paused: false, over: false, age: "teen" as Age,
  });

  useEffect(() => {
    try { setBest(Number(localStorage.getItem("aoep_geoblocks_best") || 0)); } catch { /* */ }
    const q = new URLSearchParams(window.location.search).get("age");
    if (q === "kids" || q === "tween" || q === "teen" || q === "adult") setAge(q);
  }, []);

  const spawn = useCallback((): boolean => {
    const key = s.current.next;
    s.current.next = PIECE_KEYS[Math.floor(Math.random() * PIECE_KEYS.length)];
    const a: Active = { key, rot: 0, x: 3, y: 0 };
    if (collides(a, s.current.grid)) return false;
    s.current.active = a;
    return true;
  }, []);

  const lockAndClear = useCallback(() => {
    const st = s.current;
    if (!st.active) return;
    for (const [x, y] of cellsOf(st.active)) if (y >= 0) st.grid[y][x] = PIECES[st.active.key].color;
    let cleared = 0;
    for (let y = ROWS - 1; y >= 0; y--) {
      if (st.grid[y].every((c) => c !== 0)) {
        st.grid.splice(y, 1);
        st.grid.unshift(Array<Cell>(COLS).fill(0));
        cleared += 1; y += 1;
      }
    }
    if (cleared > 0) {
      const table = [0, 100, 300, 500, 800];
      st.score += table[cleared] * st.level;
      st.lines += cleared;
      st.level = 1 + Math.floor(st.lines / 10);
      setScore(st.score); setLines(st.lines); setLevel(st.level);
    }
    st.active = null;
    st.placed += 1;
    if (st.placed % PROFILES[st.age].quizEvery === 0) {
      st.paused = true;
      setQuizMsg("");
      setQuiz(makeQuiz(PROFILES[st.age].depth));
    } else if (!spawn()) {
      st.over = true;
    }
  }, [spawn]);

  const answerQuiz = useCallback((idx: number) => {
    const st = s.current;
    const q = quiz;
    if (!q) return;
    if (idx === q.answer) {
      let target = -1;
      for (let y = ROWS - 1; y >= 0; y--) if (st.grid[y].some((c) => c !== 0)) { target = y; break; }
      if (target >= 0) {
        st.grid.splice(target, 1);
        st.grid.unshift(Array<Cell>(COLS).fill(0));
      }
      st.score += 120 * st.level; setScore(st.score);
      setQuizMsg("✅ Correct! Geo bomb cleared the bottom row (+" + 120 * st.level + ").");
    } else {
      st.speedBoost = 4;
      setQuizMsg(`❌ It was "${q.options[q.answer]}". Blocks speed up briefly!`);
    }
    setTimeout(() => {
      setQuiz(null);
      st.paused = false;
      if (!spawn()) { st.over = true; }
    }, 950);
  }, [quiz, spawn]);

  const start = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const st = s.current;
    st.grid = emptyGrid();
    st.active = null; st.next = PIECE_KEYS[Math.floor(Math.random() * PIECE_KEYS.length)];
    st.dropAcc = 0; st.score = 0; st.lines = 0; st.level = 1; st.placed = 0;
    st.speedBoost = 0; st.paused = false; st.over = false; st.age = age;
    setScore(0); setLines(0); setLevel(1); setOver(false); setQuiz(null); setRunning(true);
    spawn();

    const surface = new Surface(canvas);
    const particles = new Particles();

    const tryMove = (dx: number, dy: number): boolean => {
      if (!st.active || st.paused) return false;
      const moved = { ...st.active, x: st.active.x + dx, y: st.active.y + dy };
      if (!collides(moved, st.grid)) { st.active = moved; return true; }
      return false;
    };
    const rotate = () => {
      if (!st.active || st.paused) return;
      for (const kick of [0, -1, 1, -2, 2]) {
        const r = { ...st.active, rot: (st.active.rot + 1) % 4, x: st.active.x + kick };
        if (!collides(r, st.grid)) { st.active = r; return; }
      }
    };
    const hardDrop = () => {
      if (!st.active || st.paused) return;
      while (tryMove(0, 1)) st.score += 2;
      setScore(st.score);
      lockAndClear();
    };
    const kd = (e: KeyboardEvent) => {
      if (st.paused || st.over) return;
      if (e.key === "ArrowLeft") tryMove(-1, 0);
      else if (e.key === "ArrowRight") tryMove(1, 0);
      else if (e.key === "ArrowDown") { if (tryMove(0, 1)) { st.score += 1; setScore(st.score); } }
      else if (e.key === "ArrowUp") rotate();
      else if (e.key === " ") { e.preventDefault(); hardDrop(); }
    };
    window.addEventListener("keydown", kd);
    (canvas as unknown as { __ctrl?: Record<string, () => void> }).__ctrl = {
      left: () => tryMove(-1, 0), right: () => tryMove(1, 0),
      down: () => { if (tryMove(0, 1)) { st.score += 1; setScore(st.score); } },
      rotate, drop: hardDrop,
    };

    const loop = new GameLoop((dt) => {
      const { ctx } = surface;
      const W = surface.width, H = surface.height;
      const prof = PROFILES[st.age];
      if (!st.paused && !st.over && st.active) {
        let interval = Math.max(0.08, prof.fall - (st.level - 1) * prof.fallPerLevel);
        if (st.speedBoost > 0) { st.speedBoost -= dt; interval *= 0.35; }
        st.dropAcc += dt;
        if (st.dropAcc >= interval) {
          st.dropAcc = 0;
          if (!tryMove(0, 1)) lockAndClear();
        }
      }
      if (st.over && running) {
        loop.stop();
        try {
          const b = Math.max(st.score, Number(localStorage.getItem("aoep_geoblocks_best") || 0));
          localStorage.setItem("aoep_geoblocks_best", String(b)); setBest(b);
        } catch { /* */ }
        setOver(true); setRunning(false);
        cleanup();
        return;
      }

      // ---- layout: board on the left, side panel on the right ----
      const pad = 10;
      const boardW = Math.min(W * 0.62, (H - pad * 2) * (COLS / ROWS));
      const cell = Math.floor((H - pad * 2) / ROWS);
      const bw = cell * COLS, bh = cell * ROWS;
      const bx = pad, by = pad;

      ctx.fillStyle = "#0b0720"; ctx.fillRect(0, 0, W, H);
      // board frame
      ctx.fillStyle = "#150c2e"; roundRect(ctx, bx - 4, by - 4, bw + 8, bh + 8, 10); ctx.fill();
      // grid cells
      for (let y = 0; y < ROWS; y++) {
        for (let x = 0; x < COLS; x++) {
          const c = st.grid[y][x];
          const px = bx + x * cell, py = by + y * cell;
          if (c) { ctx.fillStyle = c as string; roundRect(ctx, px + 1, py + 1, cell - 2, cell - 2, 4); ctx.fill(); }
          else { ctx.strokeStyle = "rgba(148,163,184,0.08)"; ctx.strokeRect(px, py, cell, cell); }
        }
      }
      // ghost + active piece
      if (st.active) {
        const ghost = { ...st.active };
        while (!collides({ ...ghost, y: ghost.y + 1 }, st.grid)) ghost.y += 1;
        ctx.fillStyle = "rgba(255,255,255,0.12)";
        for (const [x, y] of cellsOf(ghost)) if (y >= 0) { roundRect(ctx, bx + x * cell + 1, by + y * cell + 1, cell - 2, cell - 2, 4); ctx.fill(); }
        ctx.fillStyle = PIECES[st.active.key].color;
        for (const [x, y] of cellsOf(st.active)) if (y >= 0) { roundRect(ctx, bx + x * cell + 1, by + y * cell + 1, cell - 2, cell - 2, 4); ctx.fill(); }
      }
      void boardW;

      // ---- side panel ----
      const sx = bx + bw + 18;
      ctx.textAlign = "left"; ctx.textBaseline = "top";
      ctx.fillStyle = "#e9d5ff"; ctx.font = "bold 18px system-ui, sans-serif";
      ctx.fillText("SCORE", sx, by + 4);
      ctx.fillStyle = "#fff"; ctx.font = "bold 26px system-ui, sans-serif";
      ctx.fillText(String(st.score), sx, by + 26);
      ctx.fillStyle = "#a5b4fc"; ctx.font = "14px system-ui, sans-serif";
      ctx.fillText(`Lines ${st.lines}   ·   Level ${st.level}`, sx, by + 62);
      ctx.fillStyle = "#c4b5fd"; ctx.font = "bold 13px system-ui, sans-serif";
      ctx.fillText("NEXT", sx, by + 96);
      const np = PIECES[st.next].states[0];
      ctx.fillStyle = PIECES[st.next].color;
      const ncell = Math.min(22, cell);
      for (const [x, y] of np) { roundRect(ctx, sx + x * ncell, by + 116 + y * ncell, ncell - 2, ncell - 2, 4); ctx.fill(); }
      const quizIn = PROFILES[st.age].quizEvery - (st.placed % PROFILES[st.age].quizEvery);
      ctx.fillStyle = "#94a3b8"; ctx.font = "12px system-ui, sans-serif";
      ctx.fillText(`Geo quiz in ${quizIn} piece${quizIn === 1 ? "" : "s"}`, sx, by + 210);

      particles.update(dt); particles.draw(ctx);
    });

    const cleanup = () => {
      loop.stop(); surface.dispose();
      window.removeEventListener("keydown", kd);
    };
    (canvas as unknown as { __cleanup?: () => void }).__cleanup = cleanup;
    loop.start();
  }, [age, lockAndClear, spawn, running]);

  useEffect(() => () => {
    const c = canvasRef.current as unknown as { __cleanup?: () => void } | null;
    c?.__cleanup?.();
  }, []);

  const ctrl = (name: "left" | "right" | "down" | "rotate" | "drop") => {
    const c = canvasRef.current as unknown as { __ctrl?: Record<string, () => void> } | null;
    c?.__ctrl?.[name]?.();
  };

  return (
    <main style={{ maxWidth: 820, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>📐 Geo Blocks</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
        <Link href="/rewards">Rewards</Link>
      </div>
      <p className="muted">
        Classic falling blocks meets a geometry quiz. Move with ← →, rotate with ↑,
        soft-drop with ↓, hard-drop with Space. Answer the geometry pop quiz to fire a
        row-clearing geo bomb.
      </p>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
        <span className="muted">Age:</span>
        {(["kids", "tween", "teen", "adult"] as Age[]).map((a) => (
          <button key={a} onClick={() => setAge(a)} disabled={running}
            style={{ opacity: age === a ? 1 : 0.55, fontWeight: age === a ? 700 : 400 }}>
            {a}
          </button>
        ))}
        <span className="muted" style={{ marginLeft: "auto" }}>Best: {best}</span>
      </div>

      <div style={{ position: "relative", width: "100%", aspectRatio: "4 / 3", borderRadius: 14, overflow: "hidden", border: "1px solid #2d1b4e" }}>
        <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block", touchAction: "none" }} />

        {quiz && (
          <div style={{
            position: "absolute", inset: 0, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", gap: 12, padding: 20,
            background: "rgba(11,7,32,0.86)", color: "#fff", textAlign: "center",
          }}>
            <div style={{ fontSize: 13, letterSpacing: 2, color: "#c4b5fd" }}>📐 GEOMETRY POP QUIZ</div>
            <div style={{ fontSize: 20, fontWeight: 700, maxWidth: 460 }}>{quiz.q}</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 10, justifyContent: "center", maxWidth: 460 }}>
              {quiz.options.map((o, i) => (
                <button key={i} onClick={() => !quizMsg && answerQuiz(i)} disabled={!!quizMsg}
                  style={{ background: "#4c1d95", color: "#fff", padding: "10px 18px", borderRadius: 10, border: 0, cursor: quizMsg ? "default" : "pointer", fontSize: 16 }}>
                  {o}
                </button>
              ))}
            </div>
            {quizMsg && <div style={{ fontSize: 15, marginTop: 6, maxWidth: 460 }}>{quizMsg}</div>}
          </div>
        )}

        {!running && !quiz && (
          <div style={{
            position: "absolute", inset: 0, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", gap: 12,
            background: "rgba(11,7,32,0.7)", color: "#fff",
          }}>
            {over && <div style={{ fontSize: 22, fontWeight: 700 }}>Game over · Score {score} · Lines {lines}</div>}
            <button onClick={start} style={{ background: "#7c3aed", color: "#fff", padding: "12px 28px", fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer" }}>
              {over ? "Play again" : "▶ Play"}
            </button>
          </div>
        )}
      </div>

      {/* Touch controls */}
      {running && (
        <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 10, flexWrap: "wrap" }}>
          <button onClick={() => ctrl("left")} style={{ padding: "10px 16px" }}>◀</button>
          <button onClick={() => ctrl("rotate")} style={{ padding: "10px 16px" }}>⟳</button>
          <button onClick={() => ctrl("right")} style={{ padding: "10px 16px" }}>▶</button>
          <button onClick={() => ctrl("down")} style={{ padding: "10px 16px" }}>▼</button>
          <button onClick={() => ctrl("drop")} style={{ padding: "10px 16px", background: "#7c3aed", color: "#fff" }}>⤓ Drop</button>
        </div>
      )}
    </main>
  );
}
