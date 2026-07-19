"use client";

// Geometry Tetris — Tetris-style board where falling pieces are geometric
// shapes (triangles, squares, pentagons, hexagons, circles). Each piece
// brings a geometry question. Answer correctly for bonus points + score
// multiplier; wrong answer speeds up the fall. Full canvas game loop.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { GameLoop, Particles, Starfield, Surface, clamp, rand, roundRect } from "../../lib/gameEngine2d";

// ─── Types ───────────────────────────────────────────────────────────────────

type Age = "kids" | "tween" | "teen" | "adult";

type GeoShape = "triangle" | "square" | "pentagon" | "hexagon" | "circle";

type Question = {
  prompt: string;
  options: string[];
  answerIdx: number;
  explain: string;
};

type FallingPiece = {
  shape: GeoShape;
  color: string;
  x: number;   // board column (0..COLS-1)
  y: number;   // vertical position in px (from top of board)
  vy: number;  // fall speed px/s
  size: number; // radius/half-size in px
  question: Question | null;
  answered: boolean;
  correct: boolean | null;
  lockedAt: number | null;
};

type Cell = { shape: GeoShape; color: string } | null;

// ─── Constants ───────────────────────────────────────────────────────────────

const COLS = 7;
const ROWS = 12;
const SHAPE_COLORS: Record<GeoShape, string> = {
  triangle: "#f59e0b",
  square:   "#3b82f6",
  pentagon: "#a855f7",
  hexagon:  "#10b981",
  circle:   "#ef4444",
};

// ─── Question bank ───────────────────────────────────────────────────────────

type QuestionEntry = Question & { shapes: GeoShape[]; ages: Age[] };

const QUESTION_BANK: QuestionEntry[] = [
  // Kids
  { shapes: ["triangle"], ages: ["kids","tween","teen","adult"], prompt: "How many sides does a triangle have?", options: ["2","3","4","5"], answerIdx: 1, explain: "A triangle has 3 sides." },
  { shapes: ["square"], ages: ["kids","tween","teen","adult"], prompt: "How many sides does a square have?", options: ["3","4","5","6"], answerIdx: 1, explain: "A square has 4 equal sides." },
  { shapes: ["pentagon"], ages: ["kids","tween","teen","adult"], prompt: "How many sides does a pentagon have?", options: ["4","5","6","7"], answerIdx: 1, explain: "A pentagon has 5 sides." },
  { shapes: ["hexagon"], ages: ["kids","tween","teen","adult"], prompt: "How many sides does a hexagon have?", options: ["5","6","7","8"], answerIdx: 1, explain: "A hexagon has 6 sides." },
  { shapes: ["circle"], ages: ["kids","tween","teen","adult"], prompt: "What shape has no corners?", options: ["Triangle","Square","Circle","Pentagon"], answerIdx: 2, explain: "A circle has no corners or sides." },
  // Tween
  { shapes: ["triangle"], ages: ["tween","teen","adult"], prompt: "Sum of angles in a triangle?", options: ["90°","180°","270°","360°"], answerIdx: 1, explain: "All triangle angles sum to 180°." },
  { shapes: ["square"], ages: ["tween","teen","adult"], prompt: "Each angle in a square is?", options: ["45°","90°","120°","180°"], answerIdx: 1, explain: "Squares have four 90° right angles." },
  { shapes: ["pentagon"], ages: ["tween","teen","adult"], prompt: "Sum of interior angles in a pentagon?", options: ["360°","450°","540°","630°"], answerIdx: 2, explain: "Pentagon interior angles sum to 540°." },
  { shapes: ["hexagon"], ages: ["tween","teen","adult"], prompt: "Sum of interior angles in a hexagon?", options: ["540°","620°","720°","810°"], answerIdx: 2, explain: "Hexagon interior angles sum to 720°." },
  { shapes: ["circle"], ages: ["tween","teen","adult"], prompt: "What is π (pi) approximately?", options: ["2.14","3.14","4.14","5.14"], answerIdx: 1, explain: "Pi ≈ 3.14159…" },
  // Teen
  { shapes: ["triangle"], ages: ["teen","adult"], prompt: "Area formula for a triangle?", options: ["b×h","½×b×h","b²","π×r²"], answerIdx: 1, explain: "Area = ½ × base × height." },
  { shapes: ["square"], ages: ["teen","adult"], prompt: "Area of a square with side 5?", options: ["10","20","25","30"], answerIdx: 2, explain: "Area = side² = 5² = 25." },
  { shapes: ["circle"], ages: ["teen","adult"], prompt: "Area of a circle with radius 3? (use π≈3)", options: ["9","18","27","36"], answerIdx: 2, explain: "Area = π×r² ≈ 3×9 = 27." },
  { shapes: ["pentagon"], ages: ["teen","adult"], prompt: "Each interior angle of a regular pentagon?", options: ["100°","108°","112°","120°"], answerIdx: 1, explain: "Regular pentagon interior angle = 108°." },
  { shapes: ["hexagon"], ages: ["teen","adult"], prompt: "Each interior angle of a regular hexagon?", options: ["100°","110°","120°","130°"], answerIdx: 2, explain: "Regular hexagon interior angle = 120°." },
  // Adult
  { shapes: ["triangle"], ages: ["adult"], prompt: "In a 3-4-5 right triangle, which side is the hypotenuse?", options: ["3","4","5","All equal"], answerIdx: 2, explain: "The hypotenuse is 5 (longest side)." },
  { shapes: ["circle"], ages: ["adult"], prompt: "Circumference of a circle with radius 7? (use π≈3.14)", options: ["22","43.96","44.22","87.92"], answerIdx: 1, explain: "C = 2πr ≈ 2×3.14×7 = 43.96." },
  { shapes: ["hexagon"], ages: ["adult"], prompt: "A regular hexagon has how many lines of symmetry?", options: ["3","4","6","8"], answerIdx: 2, explain: "A regular hexagon has 6 lines of symmetry." },
  { shapes: ["square","pentagon","hexagon","triangle","circle"], ages: ["teen","adult"], prompt: "Which has the most sides?", options: ["Triangle","Square","Pentagon","Hexagon"], answerIdx: 3, explain: "Hexagon has 6 sides — the most listed." },
  { shapes: ["square","pentagon","hexagon","triangle","circle"], ages: ["tween","teen","adult"], prompt: "Which shape tiles a floor perfectly alone?", options: ["Pentagon","Hexagon","Circle","Triangle"], answerIdx: 1, explain: "Regular hexagons tessellate a plane perfectly." },
];

function pickQuestion(shape: GeoShape, age: Age): Question {
  const pool = QUESTION_BANK.filter((q) => q.shapes.includes(shape) && q.ages.includes(age));
  const fallback = QUESTION_BANK.filter((q) => q.ages.includes(age));
  const q = pool.length ? pool[Math.floor(Math.random() * pool.length)] : fallback[Math.floor(Math.random() * fallback.length)];
  // Shuffle options keeping answerIdx correct
  const paired = q.options.map((o, i) => ({ o, correct: i === q.answerIdx }));
  for (let i = paired.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [paired[i], paired[j]] = [paired[j], paired[i]];
  }
  return {
    prompt: q.prompt,
    options: paired.map((p) => p.o),
    answerIdx: paired.findIndex((p) => p.correct),
    explain: q.explain,
  };
}

const ALL_SHAPES: GeoShape[] = ["triangle", "square", "pentagon", "hexagon", "circle"];

// ─── Shape drawing ────────────────────────────────────────────────────────────

function drawShape(ctx: CanvasRenderingContext2D, shape: GeoShape, x: number, y: number, size: number, color: string, glow = false): void {
  ctx.save();
  if (glow) { ctx.shadowColor = color; ctx.shadowBlur = 20; }
  ctx.fillStyle = color;
  ctx.strokeStyle = "rgba(255,255,255,0.6)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  switch (shape) {
    case "circle":
      ctx.arc(x, y, size, 0, Math.PI * 2);
      break;
    case "square":
      ctx.rect(x - size, y - size, size * 2, size * 2);
      break;
    case "triangle": {
      const h = size * 1.15;
      ctx.moveTo(x, y - h);
      ctx.lineTo(x + size, y + h * 0.5);
      ctx.lineTo(x - size, y + h * 0.5);
      ctx.closePath();
      break;
    }
    default: {
      const sides = shape === "pentagon" ? 5 : 6;
      const startAngle = shape === "pentagon" ? -Math.PI / 2 : 0;
      for (let i = 0; i < sides; i++) {
        const a = startAngle + (i * 2 * Math.PI) / sides;
        if (i === 0) ctx.moveTo(x + size * Math.cos(a), y + size * Math.sin(a));
        else ctx.lineTo(x + size * Math.cos(a), y + size * Math.sin(a));
      }
      ctx.closePath();
    }
  }
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function GeometryTetris() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [age, setAge] = useState<Age>("tween");
  const [running, setRunning] = useState(false);
  const [over, setOver] = useState(false);
  const [score, setScore] = useState(0);
  const [best, setBest] = useState(0);
  const [lines, setLines] = useState(0);
  const [level, setLevel] = useState(1);
  const [questionUI, setQuestionUI] = useState<Question | null>(null);
  const [lastExplain, setLastExplain] = useState("");
  const [streak, setStreak] = useState(0);

  // Ref holding mutable question callback so canvas loop can trigger UI
  const questionCallbackRef = useRef<((idx: number) => void) | null>(null);

  useEffect(() => {
    try { setBest(Number(localStorage.getItem("aoep_geotris_best") || 0)); } catch { /* */ }
    const q = new URLSearchParams(window.location.search).get("age");
    if (q === "kids" || q === "tween" || q === "teen" || q === "adult") setAge(q as Age);
  }, []);

  const start = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    setRunning(true); setOver(false); setScore(0); setLines(0); setLevel(1);
    setQuestionUI(null); setLastExplain(""); setStreak(0);
    questionCallbackRef.current = null;

    const surface = new Surface(canvas);
    const particles = new Particles();
    const stars = new Starfield(80);

    // Board: grid of locked cells
    const board: Cell[][] = Array.from({ length: ROWS }, () => Array(COLS).fill(null));

    let score_ = 0;
    let lines_ = 0;
    let level_ = 1;
    let streak_ = 0;
    let gameOver_ = false;
    let t_ = 0;
    let current: FallingPiece | null = null;
    let pendingQuestion: Question | null = null;
    let questionOpen = false;
    let baseSpeed = 80; // px/s

    const ageNow = age;

    function spawnPiece() {
      const shape = ALL_SHAPES[Math.floor(Math.random() * ALL_SHAPES.length)];
      const col = Math.floor(COLS / 2);
      current = {
        shape, color: SHAPE_COLORS[shape],
        x: col, y: -40, vy: baseSpeed + level_ * 12,
        size: 22, question: null, answered: false, correct: null, lockedAt: null,
      };
      // Attach question
      if (!questionOpen) {
        current.question = pickQuestion(shape, ageNow);
        pendingQuestion = current.question;
        questionOpen = true;
        setQuestionUI(pendingQuestion);
        // Register callback so UI buttons can feed answers back
        questionCallbackRef.current = (chosenIdx: number) => {
          if (!current || current.answered) return;
          current.answered = true;
          const correct = chosenIdx === current.question!.answerIdx;
          current.correct = correct;
          setLastExplain(current.question!.explain);
          if (correct) {
            streak_ += 1; setStreak(streak_);
            const bonus = 20 + streak_ * 5;
            score_ += bonus; setScore(score_);
          } else {
            streak_ = 0; setStreak(0);
            // Speed up as penalty
            if (current) current.vy = Math.min(current.vy * 2, 340);
          }
          setQuestionUI(null);
          questionOpen = false;
          questionCallbackRef.current = null;
        };
      }
    }

    function cellSize(): number {
      return Math.floor(surface.width / COLS);
    }

    function boardX(col: number): number {
      return col * cellSize() + cellSize() / 2;
    }

    function lockPiece(p: FallingPiece) {
      const cs = cellSize();
      const boardTop = 60;
      const row = Math.round((p.y - boardTop) / cs);
      const col = clamp(p.x, 0, COLS - 1);
      if (row < 0) {
        // Locked above board — game over
        gameOver_ = true;
        return;
      }
      const r = clamp(row, 0, ROWS - 1);
      board[r][col] = { shape: p.shape, color: p.color };
      particles.burst(boardX(col), boardTop + r * cs + cs / 2, p.color, 14, { speed: 120 });
      // Clear full rows
      let cleared = 0;
      for (let ri = ROWS - 1; ri >= 0; ri--) {
        if (board[ri].every((c) => c !== null)) {
          board.splice(ri, 1);
          board.unshift(Array(COLS).fill(null));
          cleared += 1;
          ri++; // re-check same index after splice
        }
      }
      if (cleared > 0) {
        lines_ += cleared; setLines(lines_);
        const bonus = cleared === 1 ? 100 : cleared === 2 ? 300 : cleared === 3 ? 600 : 1000;
        score_ += bonus * level_; setScore(score_);
        level_ = Math.floor(lines_ / 5) + 1; setLevel(level_);
        baseSpeed = 80 + level_ * 15;
      }
    }

    spawnPiece();

    // Input: arrow keys to move, down to drop
    let leftHeld = false, rightHeld = false, downHeld = false;
    let moveTimer = 0;
    const kd = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") { leftHeld = true; if (current) current.x = clamp(current.x - 1, 0, COLS - 1); }
      if (e.key === "ArrowRight") { rightHeld = true; if (current) current.x = clamp(current.x + 1, 0, COLS - 1); }
      if (e.key === "ArrowDown") downHeld = true;
    };
    const ku = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") leftHeld = false;
      if (e.key === "ArrowRight") rightHeld = false;
      if (e.key === "ArrowDown") downHeld = false;
    };
    window.addEventListener("keydown", kd);
    window.addEventListener("keyup", ku);

    // Touch/swipe support
    let touchStartX = 0;
    const ts = (e: TouchEvent) => { if (e.touches[0]) touchStartX = e.touches[0].clientX; };
    const te = (e: TouchEvent) => {
      if (!e.changedTouches[0] || !current) return;
      const dx = e.changedTouches[0].clientX - touchStartX;
      if (Math.abs(dx) > 30) current.x = clamp(current.x + (dx > 0 ? 1 : -1), 0, COLS - 1);
    };
    canvas.addEventListener("touchstart", ts, { passive: true });
    canvas.addEventListener("touchend", te, { passive: true });

    const loop = new GameLoop((dt) => {
      if (gameOver_) return;
      t_ += dt;
      moveTimer += dt;

      // Auto-repeat horizontal movement
      if (moveTimer > 0.18) {
        moveTimer = 0;
        if (leftHeld && current) current.x = clamp(current.x - 1, 0, COLS - 1);
        if (rightHeld && current) current.x = clamp(current.x + 1, 0, COLS - 1);
      }

      const { ctx } = surface;
      const W = surface.width, H = surface.height;
      const cs = cellSize();
      const boardTop = 60;
      const boardH = ROWS * cs;

      // Update falling piece
      if (current) {
        const dropSpeed = downHeld ? current.vy * 4 : current.vy;
        current.y += dropSpeed * dt;
        // Check landing: bottom of board or occupied cell
        const col = clamp(current.x, 0, COLS - 1);
        const row = Math.round((current.y - boardTop) / cs);
        const landed =
          current.y + current.size >= boardTop + boardH ||
          (row >= 0 && row < ROWS && board[row][col] !== null);
        if (landed) {
          if (current.question && !current.answered && questionOpen) {
            // Close question panel without answer
            setQuestionUI(null);
            questionOpen = false;
            questionCallbackRef.current = null;
            streak_ = 0; setStreak(0);
          }
          lockPiece(current);
          if (gameOver_) {
            loop.stop();
            cleanup();
            try {
              const b = Math.max(score_, Number(localStorage.getItem("aoep_geotris_best") || 0));
              localStorage.setItem("aoep_geotris_best", String(b));
              setBest(b);
            } catch { /* */ }
            setOver(true); setRunning(false);
            return;
          }
          current = null;
          spawnPiece();
        }
      }

      // ── render ──────────────────────────────────────────────────────────────
      // Background
      const grad = ctx.createLinearGradient(0, 0, 0, H);
      grad.addColorStop(0, "#0f0c29"); grad.addColorStop(1, "#302b63");
      ctx.fillStyle = grad; ctx.fillRect(0, 0, W, H);
      stars.draw(ctx, W, H, t_);

      // Board background
      ctx.fillStyle = "rgba(255,255,255,0.04)";
      ctx.fillRect(0, boardTop, W, boardH);

      // Grid lines
      ctx.strokeStyle = "rgba(255,255,255,0.06)";
      ctx.lineWidth = 1;
      for (let r = 0; r <= ROWS; r++) {
        ctx.beginPath(); ctx.moveTo(0, boardTop + r * cs); ctx.lineTo(W, boardTop + r * cs); ctx.stroke();
      }
      for (let c = 0; c <= COLS; c++) {
        ctx.beginPath(); ctx.moveTo(c * cs, boardTop); ctx.lineTo(c * cs, boardTop + boardH); ctx.stroke();
      }

      // Locked cells
      for (let r = 0; r < ROWS; r++) {
        for (let c = 0; c < COLS; c++) {
          const cell = board[r][c];
          if (cell) {
            drawShape(ctx, cell.shape, c * cs + cs / 2, boardTop + r * cs + cs / 2, cs * 0.38, cell.color, false);
          }
        }
      }

      // Falling piece
      if (current) {
        const px = clamp(current.x, 0, COLS - 1) * cs + cs / 2;
        // Ghost: show where it will land
        let ghostY = current.y;
        const col_ = clamp(current.x, 0, COLS - 1);
        while (ghostY + current.size < boardTop + boardH) {
          const testRow = Math.round((ghostY + current.size - boardTop) / cs);
          if (testRow >= 0 && testRow < ROWS && board[testRow][col_] !== null) break;
          ghostY += 4;
        }
        ctx.globalAlpha = 0.22;
        drawShape(ctx, current.shape, px, ghostY, current.size, current.color, false);
        ctx.globalAlpha = 1;
        drawShape(ctx, current.shape, px, current.y, current.size, current.color, true);
      }

      particles.update(dt); particles.draw(ctx);

      // HUD
      ctx.fillStyle = "#c4b5fd"; ctx.font = `bold ${clamp(W * 0.045, 13, 17)}px system-ui`;
      ctx.textAlign = "left"; ctx.textBaseline = "top";
      ctx.fillText(`Score ${score_}`, 8, 4);
      ctx.textAlign = "center";
      ctx.fillText(`Lv ${level_}  Lines ${lines_}`, W / 2, 4);
      ctx.textAlign = "right";
      ctx.fillText(`🔥 ×${streak_}`, W - 8, 4);
    });

    const cleanup = () => {
      loop.stop();
      surface.dispose();
      window.removeEventListener("keydown", kd);
      window.removeEventListener("keyup", ku);
      canvas.removeEventListener("touchstart", ts);
      canvas.removeEventListener("touchend", te);
    };
    (canvas as unknown as { __cleanup?: () => void }).__cleanup = cleanup;
    loop.start();
  }, [age]);

  useEffect(() => () => {
    const c = canvasRef.current as unknown as { __cleanup?: () => void } | null;
    c?.__cleanup?.();
  }, []);

  const handleAnswer = useCallback((idx: number) => {
    questionCallbackRef.current?.(idx);
  }, []);

  return (
    <main style={{ maxWidth: 520, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 8 }}>
        <h1 style={{ margin: 0 }}>📐 Geometry Tetris</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
      </div>
      <p className="muted" style={{ marginTop: 0 }}>Shapes fall like Tetris. Answer the geometry question for a bonus — wrong answers speed up the fall!</p>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
        <span className="muted">Age:</span>
        {(["kids","tween","teen","adult"] as Age[]).map((a) => (
          <button key={a} onClick={() => setAge(a)} disabled={running}
            style={{ opacity: age === a ? 1 : 0.55, fontWeight: age === a ? 700 : 400 }}>
            {a}
          </button>
        ))}
        <span className="muted" style={{ marginLeft: "auto" }}>Best: {best}</span>
      </div>

      <div style={{ position: "relative", width: "100%", aspectRatio: "3/4", borderRadius: 14, overflow: "hidden", border: "2px solid #4c1d95" }}>
        <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block", touchAction: "none" }} />

        {/* Question overlay */}
        {running && questionUI && (
          <div style={{
            position: "absolute", bottom: 0, left: 0, right: 0,
            background: "rgba(15,12,41,0.93)", borderTop: "2px solid #7c3aed",
            padding: "10px 12px",
          }}>
            <div style={{ color: "#e9d5ff", fontWeight: 700, fontSize: 13, marginBottom: 6 }}>{questionUI.prompt}</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {questionUI.options.map((opt, i) => (
                <button key={i} onClick={() => handleAnswer(i)}
                  style={{ background: "#7c3aed", color: "#fff", fontSize: 12, padding: "5px 12px", borderRadius: 8, border: 0, cursor: "pointer" }}>
                  {opt}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Explain flash */}
        {running && !questionUI && lastExplain && (
          <div style={{
            position: "absolute", bottom: 0, left: 0, right: 0,
            background: "rgba(16,185,129,0.18)", borderTop: "1px solid #10b981",
            padding: "6px 12px", color: "#6ee7b7", fontSize: 12,
          }}>
            {lastExplain}
          </div>
        )}

        {/* Start / Game-over overlay */}
        {!running && (
          <div style={{
            position: "absolute", inset: 0, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", gap: 14,
            background: "rgba(15,12,41,0.78)", color: "#fff",
          }}>
            {over && (
              <>
                <div style={{ fontSize: 22, fontWeight: 700 }}>Game Over!</div>
                <div>Score: {score} · Lines: {lines}</div>
                <div className="muted" style={{ fontSize: 13 }}>Best: {best}</div>
              </>
            )}
            {!over && (
              <div style={{ textAlign: "center", padding: "0 20px" }}>
                <div style={{ fontSize: 28, marginBottom: 8 }}>📐</div>
                <div style={{ fontWeight: 700, fontSize: 16 }}>Geometry Tetris</div>
                <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>Arrow keys or swipe to move. Answer questions for bonuses!</div>
              </div>
            )}
            <button onClick={start}
              style={{ background: "#7c3aed", color: "#fff", padding: "12px 28px", fontSize: 17, borderRadius: 10, border: 0, cursor: "pointer" }}>
              {over ? "Play again" : "▶ Play"}
            </button>
          </div>
        )}
      </div>

      {/* Streak indicator below canvas */}
      {running && streak > 0 && (
        <div style={{ textAlign: "center", marginTop: 8, color: "#fbbf24", fontWeight: 700, fontSize: 14 }}>
          🔥 {streak} streak! +{20 + streak * 5} bonus per correct answer
        </div>
      )}

      <div className="muted" style={{ fontSize: 12, marginTop: 10 }}>
        Controls: ← → arrow keys to move · ↓ to drop faster · Touch: swipe left/right
      </div>
    </main>
  );
}
