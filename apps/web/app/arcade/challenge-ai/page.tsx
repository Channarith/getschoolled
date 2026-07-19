"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  GameLoop, Particles, Starfield, Surface, clamp, rand, roundRect,
} from "../../lib/gameEngine2d";

type Mode = "geometry" | "stocks";
type Action = "buy" | "hold" | "sell";
type Tetromino = "I" | "L" | "T" | "S" | "O";

type Piece = {
  lane: number;
  y: number;
  speed: number;
  value: number;
  correct: boolean;
  shape: Tetromino;
  claimed: boolean;
};

type Wave = {
  prompt: string;
  pieces: Piece[];
  correctLane: number;
  aiAimLane: number;
};

type MarketScenario = {
  prices: number[];
  next: number;
  optimal: Action;
  headline: string;
};

const TOTAL_ROUNDS = 10;
const LANES = 4;

const SHAPES: Record<Tetromino, Array<[number, number]>> = {
  I: [[0, 1], [1, 1], [2, 1], [3, 1]],
  L: [[0, 0], [0, 1], [1, 1], [2, 1]],
  T: [[1, 0], [0, 1], [1, 1], [2, 1]],
  S: [[1, 0], [2, 0], [0, 1], [1, 1]],
  O: [[0, 0], [1, 0], [0, 1], [1, 1]],
};

function laneCenter(lane: number): number {
  return (lane + 0.5) / LANES;
}

function randomShape(): Tetromino {
  const opts: Tetromino[] = ["I", "L", "T", "S", "O"];
  return opts[Math.floor(rand(0, opts.length))];
}

function makeGeometryQuestion(): { prompt: string; answer: number } {
  const kind = Math.floor(rand(0, 4));
  if (kind === 0) {
    const w = Math.round(rand(3, 13));
    const h = Math.round(rand(3, 11));
    return { prompt: `Area of rectangle ${w} × ${h}`, answer: w * h };
  }
  if (kind === 1) {
    const w = Math.round(rand(3, 14));
    const h = Math.round(rand(3, 12));
    return { prompt: `Perimeter of rectangle ${w} × ${h}`, answer: (w + h) * 2 };
  }
  if (kind === 2) {
    const n = Math.round(rand(3, 8));
    return { prompt: `Interior angle sum of ${n}-gon`, answer: (n - 2) * 180 };
  }
  const b = Math.round(rand(4, 15));
  const h = Math.round(rand(2, 8)) * 2;
  return { prompt: `Area of triangle base ${b}, height ${h}`, answer: (b * h) / 2 };
}

function buildWave(round: number): Wave {
  const q = makeGeometryQuestion();
  const values = new Set<number>([q.answer]);
  while (values.size < LANES) {
    const delta = Math.round(rand(-18, 18)) || 3;
    const candidate = Math.max(1, q.answer + delta);
    if (candidate !== q.answer) values.add(candidate);
  }
  const answers = [...values].sort(() => Math.random() - 0.5);
  const correctLane = answers.findIndex((v) => v === q.answer);
  const aiMistakeChance = Math.max(0.12, 0.32 - round * 0.016);
  let aiAimLane = correctLane;
  if (Math.random() < aiMistakeChance) {
    const wrongLanes = [0, 1, 2, 3].filter((i) => i !== correctLane);
    aiAimLane = wrongLanes[Math.floor(rand(0, wrongLanes.length))];
  }
  const pieces = answers.map((value, lane) => ({
    lane,
    y: rand(-0.45, -0.05),
    speed: rand(68 + round * 5, 88 + round * 7),
    value,
    correct: lane === correctLane,
    shape: randomShape(),
    claimed: false,
  }));
  return { prompt: q.prompt, pieces, correctLane, aiAimLane };
}

function drawTetromino(
  ctx: CanvasRenderingContext2D,
  shape: Tetromino,
  x: number,
  y: number,
  unit: number,
  fill: string,
): void {
  const cells = SHAPES[shape];
  for (const [cx, cy] of cells) {
    const px = x + cx * unit;
    const py = y + cy * unit;
    ctx.fillStyle = fill;
    roundRect(ctx, px, py, unit - 2, unit - 2, 4);
    ctx.fill();
    ctx.strokeStyle = "rgba(12, 16, 32, 0.4)";
    ctx.lineWidth = 1;
    ctx.stroke();
  }
}

function makeMarketScenario(round: number): MarketScenario {
  const start = rand(82, 128);
  const volatility = 1.6 + round * 0.2;
  const momentum = rand(-2.8, 2.8);
  const prices = [start];
  for (let i = 1; i < 8; i++) {
    const prev = prices[i - 1];
    const next = Math.max(25, prev + momentum * 0.45 + rand(-volatility, volatility));
    prices.push(next);
  }
  const last = prices[prices.length - 1];
  const next = Math.max(25, last + momentum + rand(-volatility * 0.9, volatility * 0.9));
  const delta = next - last;
  const optimal: Action = delta > 1.2 ? "buy" : delta < -1.2 ? "sell" : "hold";
  const headline = delta > 1.2
    ? "Positive earnings signal"
    : delta < -1.2
      ? "Risk alert in sector"
      : "Market moves sideways";
  return { prices, next, optimal, headline };
}

function aiMarketAction(s: MarketScenario): Action {
  if (Math.random() < 0.72) return s.optimal;
  const all: Action[] = ["buy", "hold", "sell"];
  const wrong = all.filter((a) => a !== s.optimal);
  return wrong[Math.floor(rand(0, wrong.length))];
}

function scoreAction(action: Action, optimal: Action): number {
  if (action === optimal) return 2;
  if (optimal === "hold") return 0;
  if (action === "hold") return 1;
  return 0;
}

function actionLabel(action: Action): string {
  if (action === "buy") return "Buy";
  if (action === "sell") return "Sell";
  return "Hold";
}

function Sparkline({ prices }: { prices: number[] }) {
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = Math.max(1, max - min);
  const points = prices.map((p, i) => {
    const x = (i / (prices.length - 1)) * 100;
    const y = 100 - ((p - min) / span) * 100;
    return `${x},${y}`;
  }).join(" ");
  const last = prices[prices.length - 1];
  return (
    <div style={{ background: "#0f172a", borderRadius: 12, padding: 10, border: "1px solid #334155" }}>
      <svg viewBox="0 0 100 100" style={{ width: "100%", height: 140, display: "block" }}>
        <polyline
          fill="none"
          stroke="#22d3ee"
          strokeWidth="2.5"
          points={points}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        <line x1="0" y1="70" x2="100" y2="70" stroke="rgba(148,163,184,0.35)" strokeDasharray="4 3" />
      </svg>
      <div className="muted" style={{ fontSize: 13 }}>
        Last price: {last.toFixed(1)}
      </div>
    </div>
  );
}

export default function ChallengeAiPage() {
  const [mode, setMode] = useState<Mode>("geometry");

  const geoCanvasRef = useRef<HTMLCanvasElement>(null);
  const [geoRunning, setGeoRunning] = useState(false);
  const [geoOver, setGeoOver] = useState(false);
  const [geoRound, setGeoRound] = useState(1);
  const [geoPlayer, setGeoPlayer] = useState(0);
  const [geoAi, setGeoAi] = useState(0);
  const [geoNote, setGeoNote] = useState("Catch the right tetromino answer first.");
  const geoRef = useRef({
    wave: null as Wave | null,
    playerX: 0.5,
    targetX: 0.5,
    aiX: 0.5,
    round: 1,
    player: 0,
    ai: 0,
  });

  const [marketRound, setMarketRound] = useState(1);
  const [marketPlayer, setMarketPlayer] = useState(0);
  const [marketAi, setMarketAi] = useState(0);
  const [marketDone, setMarketDone] = useState(false);
  const [marketFeedback, setMarketFeedback] = useState("Read the chart and challenge the AI trader.");
  const [marketScenario, setMarketScenario] = useState<MarketScenario>(() => makeMarketScenario(1));

  const marketWinner = useMemo(() => {
    if (!marketDone) return "";
    if (marketPlayer === marketAi) return "Draw";
    return marketPlayer > marketAi ? "You beat the AI 🎉" : "AI wins this duel";
  }, [marketDone, marketPlayer, marketAi]);

  const startGeometry = useCallback(() => {
    const canvas = geoCanvasRef.current;
    if (!canvas) return;
    const state = geoRef.current;
    state.playerX = 0.5;
    state.targetX = 0.5;
    state.aiX = 0.5;
    state.round = 1;
    state.player = 0;
    state.ai = 0;
    state.wave = buildWave(1);
    setGeoRound(1);
    setGeoPlayer(0);
    setGeoAi(0);
    setGeoOver(false);
    setGeoRunning(true);
    setGeoNote("Round 1. Beat the AI to the correct geometry answer.");

    const surface = new Surface(canvas);
    const particles = new Particles();
    const stars = new Starfield(95);

    const advanceRound = (message: string, playerDelta: number, aiDelta: number, burstX: number, burstY: number, color: string) => {
      state.player += playerDelta;
      state.ai += aiDelta;
      setGeoPlayer(state.player);
      setGeoAi(state.ai);
      setGeoNote(message);
      particles.burst(burstX, burstY, color, 22, { speed: 220 });
      state.round += 1;
      if (state.round > TOTAL_ROUNDS) {
        setGeoRunning(false);
        setGeoOver(true);
        setGeoNote(state.player === state.ai ? "Duel ended in a draw." : state.player > state.ai ? "You beat the AI." : "AI wins this round.");
        cleanup();
        return;
      }
      setGeoRound(state.round);
      state.wave = buildWave(state.round);
    };

    const onMove = (clientX: number) => {
      const rect = canvas.getBoundingClientRect();
      state.targetX = clamp((clientX - rect.left) / rect.width, 0.08, 0.92);
    };

    const mm = (e: MouseEvent) => onMove(e.clientX);
    const tm = (e: TouchEvent) => { if (e.touches[0]) onMove(e.touches[0].clientX); };
    const kd = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") state.targetX = clamp(state.targetX - 0.08, 0.08, 0.92);
      if (e.key === "ArrowRight") state.targetX = clamp(state.targetX + 0.08, 0.08, 0.92);
    };
    canvas.addEventListener("mousemove", mm);
    canvas.addEventListener("touchmove", tm, { passive: true });
    window.addEventListener("keydown", kd);

    let elapsed = 0;
    const loop = new GameLoop((dt) => {
      const { ctx } = surface;
      const W = surface.width;
      const H = surface.height;
      const playerY = H - 46;
      const aiY = H * 0.24;
      const paddleW = clamp(W * 0.2, 78, 160);

      elapsed += dt;
      state.playerX = clamp(state.playerX + (state.targetX - state.playerX) * Math.min(1, dt * 12), 0.08, 0.92);
      const wave = state.wave;
      if (!wave) return;
      const aiTarget = laneCenter(wave.aiAimLane);
      state.aiX = clamp(state.aiX + (aiTarget - state.aiX) * Math.min(1, dt * 4.5), 0.08, 0.92);

      for (const p of wave.pieces) p.y += (p.speed * dt) / H;
      for (const p of wave.pieces) {
        if (p.claimed) continue;
        const px = laneCenter(p.lane) * W;
        const py = p.y * H;
        const playerHit = py >= playerY - 16 && py <= playerY + 20 && Math.abs(px - state.playerX * W) <= paddleW * 0.5;
        const aiHit = py >= aiY - 14 && py <= aiY + 18 && Math.abs(px - state.aiX * W) <= paddleW * 0.42;
        if (playerHit) {
          p.claimed = true;
          if (p.correct) {
            advanceRound("Great catch. You take the point.", 1, 0, px, py, "#34d399");
          } else {
            advanceRound("Wrong block. AI takes the point.", 0, 1, px, py, "#f87171");
          }
          return;
        }
        if (aiHit) {
          p.claimed = true;
          if (p.correct) {
            advanceRound("AI answered first.", 0, 1, px, py, "#fb923c");
            return;
          }
        }
        if (py > H + 24 && p.correct) {
          p.claimed = true;
          advanceRound("Missed the answer. No point this round.", 0, 0, px, H - 14, "#fbbf24");
          return;
        }
      }

      const bg = ctx.createLinearGradient(0, 0, 0, H);
      bg.addColorStop(0, "#090f1f");
      bg.addColorStop(1, "#1b1140");
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, W, H);
      stars.draw(ctx, W, H, elapsed);

      ctx.strokeStyle = "rgba(148,163,184,0.28)";
      for (let i = 1; i < LANES; i++) {
        const x = (i / LANES) * W;
        ctx.beginPath();
        ctx.moveTo(x, 58);
        ctx.lineTo(x, H - 12);
        ctx.stroke();
      }

      ctx.fillStyle = "#e2e8f0";
      ctx.font = `bold ${clamp(W * 0.034, 15, 23)}px system-ui, sans-serif`;
      ctx.textAlign = "center";
      ctx.fillText(wave.prompt, W / 2, 28);

      for (const p of wave.pieces) {
        if (p.claimed) continue;
        const px = laneCenter(p.lane) * W;
        const py = p.y * H;
        drawTetromino(ctx, p.shape, px - 20, py - 20, 12, p.correct ? "#22d3ee" : "#a78bfa");
        ctx.fillStyle = "#f8fafc";
        ctx.font = "bold 17px system-ui, sans-serif";
        ctx.fillText(String(p.value), px, py + 26);
      }

      particles.update(dt);
      particles.draw(ctx);

      ctx.fillStyle = "#38bdf8";
      roundRect(ctx, state.aiX * W - paddleW * 0.5, aiY, paddleW, 12, 7);
      ctx.fill();
      ctx.fillStyle = "#22c55e";
      roundRect(ctx, state.playerX * W - paddleW * 0.5, playerY, paddleW, 14, 7);
      ctx.fill();

      ctx.fillStyle = "#bfdbfe";
      ctx.textAlign = "left";
      ctx.font = "bold 14px system-ui, sans-serif";
      ctx.fillText(`You ${state.player}`, 12, H - 14);
      ctx.textAlign = "center";
      ctx.fillText(`Round ${state.round}/${TOTAL_ROUNDS}`, W / 2, H - 14);
      ctx.textAlign = "right";
      ctx.fillText(`AI ${state.ai}`, W - 12, H - 14);
    });

    const cleanup = () => {
      loop.stop();
      surface.dispose();
      canvas.removeEventListener("mousemove", mm);
      canvas.removeEventListener("touchmove", tm);
      window.removeEventListener("keydown", kd);
    };
    (canvas as unknown as { __cleanup?: () => void }).__cleanup = cleanup;
    loop.start();
  }, []);

  useEffect(() => () => {
    const c = geoCanvasRef.current as unknown as { __cleanup?: () => void } | null;
    c?.__cleanup?.();
  }, []);

  const restartMarket = useCallback(() => {
    setMarketRound(1);
    setMarketPlayer(0);
    setMarketAi(0);
    setMarketDone(false);
    setMarketFeedback("Read the chart and challenge the AI trader.");
    setMarketScenario(makeMarketScenario(1));
  }, []);

  const onMarketPick = useCallback((choice: Action) => {
    if (marketDone) return;
    const aiChoice = aiMarketAction(marketScenario);
    const playerGain = scoreAction(choice, marketScenario.optimal);
    const aiGain = scoreAction(aiChoice, marketScenario.optimal);
    const nextPlayer = marketPlayer + playerGain;
    const nextAi = marketAi + aiGain;
    setMarketPlayer(nextPlayer);
    setMarketAi(nextAi);
    const delta = marketScenario.next - marketScenario.prices[marketScenario.prices.length - 1];
    setMarketFeedback(
      `Next move ${delta >= 0 ? "▲" : "▼"} ${Math.abs(delta).toFixed(2)}. ` +
      `Optimal: ${actionLabel(marketScenario.optimal)}. ` +
      `You: ${actionLabel(choice)} (+${playerGain}) · AI: ${actionLabel(aiChoice)} (+${aiGain}).`,
    );
    const nextRound = marketRound + 1;
    if (nextRound > TOTAL_ROUNDS) {
      setMarketDone(true);
      return;
    }
    setMarketRound(nextRound);
    setMarketScenario(makeMarketScenario(nextRound));
  }, [marketAi, marketDone, marketPlayer, marketRound, marketScenario]);

  return (
    <main style={{ maxWidth: 920, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>🤖 Challenge the AI</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
        <Link href="/rewards">Rewards</Link>
      </div>
      <p className="muted">
        Two head-to-head learning games: a Tetris-style geometry duel and a stocks strategy duel.
      </p>

      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        <button
          onClick={() => setMode("geometry")}
          style={{ opacity: mode === "geometry" ? 1 : 0.58, background: mode === "geometry" ? "#7c3aed" : undefined, color: mode === "geometry" ? "#fff" : undefined }}
        >
          📐 Geometry Drop Duel
        </button>
        <button
          onClick={() => setMode("stocks")}
          style={{ opacity: mode === "stocks" ? 1 : 0.58, background: mode === "stocks" ? "#0ea5e9" : undefined, color: mode === "stocks" ? "#fff" : undefined }}
        >
          📈 Market Sprint Duel
        </button>
      </div>

      {mode === "geometry" && (
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontWeight: 700 }}>Tetris-style geometry blocks vs AI</div>
            <div className="muted">Round {geoRound}/{TOTAL_ROUNDS}</div>
          </div>
          <div style={{ position: "relative", width: "100%", aspectRatio: "16 / 10", borderRadius: 14, overflow: "hidden", border: "1px solid #2d1b4e", background: "#090f1f" }}>
            <canvas ref={geoCanvasRef} style={{ width: "100%", height: "100%", display: "block", touchAction: "none" }} />
            {!geoRunning && (
              <div style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexDirection: "column",
                gap: 10,
                background: "rgba(2,6,23,0.7)",
                color: "#fff",
              }}>
                <div style={{ fontWeight: 700, fontSize: 21 }}>
                  {geoOver ? (geoPlayer === geoAi ? "Draw with AI" : geoPlayer > geoAi ? "You beat the AI 🎉" : "AI wins this duel") : "Ready to challenge?"}
                </div>
                <button
                  onClick={startGeometry}
                  style={{ background: "#7c3aed", color: "#fff", border: 0, borderRadius: 10, padding: "10px 24px", fontWeight: 700, cursor: "pointer" }}
                >
                  {geoOver ? "Play again" : "▶ Start duel"}
                </button>
              </div>
            )}
          </div>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span>🧑 You: <b>{geoPlayer}</b></span>
            <span>🤖 AI: <b>{geoAi}</b></span>
          </div>
          <div className="muted">{geoNote}</div>
        </div>
      )}

      {mode === "stocks" && (
        <div className="card" style={{ display: "grid", gap: 12 }}>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontWeight: 700 }}>Stocks learning adaptation vs AI trader</div>
            <div className="muted">Round {marketRound}/{TOTAL_ROUNDS}</div>
          </div>
          <div className="muted">{marketScenario.headline}</div>
          <Sparkline prices={marketScenario.prices} />
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <button onClick={() => onMarketPick("buy")} disabled={marketDone} style={{ background: "#16a34a", color: "#fff" }}>
              Buy
            </button>
            <button onClick={() => onMarketPick("hold")} disabled={marketDone} style={{ background: "#475569", color: "#fff" }}>
              Hold
            </button>
            <button onClick={() => onMarketPick("sell")} disabled={marketDone} style={{ background: "#dc2626", color: "#fff" }}>
              Sell
            </button>
            {marketDone && (
              <button onClick={restartMarket} style={{ marginLeft: "auto", background: "#0ea5e9", color: "#fff" }}>
                Restart market duel
              </button>
            )}
          </div>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span>🧑 You: <b>{marketPlayer}</b></span>
            <span>🤖 AI: <b>{marketAi}</b></span>
          </div>
          <div className="muted">{marketDone ? marketWinner : marketFeedback}</div>
        </div>
      )}
    </main>
  );
}
