"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  GameLoop, Particles, Starfield, Surface, clamp, roundRect,
} from "../../lib/gameEngine2d";

type ModeKey = "geometry" | "stocks";
type Phase = "intro" | "playing" | "over";
type ChoiceSource = "player" | "ai" | "timeout";

type ChallengeQuestion = {
  prompt: string;
  options: string[];
  answer: number;
  teaching: string;
  shape?: "triangle" | "rectangle" | "circle" | "angle" | "prism";
  series?: number[];
  marketMove?: "up" | "flat" | "down";
};

const MODES: Record<ModeKey, {
  title: string;
  short: string;
  subtitle: string;
  instructions: string;
  aiName: string;
  timeLimit: number;
  aiTime: number;
  aiAccuracy: number;
  accent: string;
  bestKey: string;
}> = {
  geometry: {
    title: "Geometry Stack",
    short: "Tetris-style geometry quiz",
    subtitle: "Drop answer blocks faster than the AI can solve them.",
    instructions: "Pick the correct answer before the block lands. Correct answers build your stack and clear rows; misses hand momentum to the AI.",
    aiName: "ProofBot",
    timeLimit: 12,
    aiTime: 8.2,
    aiAccuracy: 0.68,
    accent: "#7c3aed",
    bestKey: "aoep_challenge_ai_geometry_best",
  },
  stocks: {
    title: "Market Sprint",
    short: "Stocks learning adaptation",
    subtitle: "Read the market cue and beat the AI portfolio coach.",
    instructions: "Choose buy, hold, or sell from the headline and chart. Strong risk decisions beat the AI's simulated trade.",
    aiName: "TickerMind",
    timeLimit: 12,
    aiTime: 8.6,
    aiAccuracy: 0.66,
    accent: "#0ea5e9",
    bestKey: "aoep_challenge_ai_stocks_best",
  },
};

const DECKS: Record<ModeKey, ChallengeQuestion[]> = {
  geometry: [
    {
      prompt: "A triangle has base 8 and height 5. What is its area?",
      options: ["20 square units", "40 square units", "13 square units"],
      answer: 0,
      teaching: "Triangle area is base x height / 2, so 8 x 5 / 2 = 20.",
      shape: "triangle",
    },
    {
      prompt: "A rectangle is 6 by 9. Which perimeter clears the row?",
      options: ["15", "30", "54"],
      answer: 1,
      teaching: "Perimeter is 2 x (length + width), so 2 x (6 + 9) = 30.",
      shape: "rectangle",
    },
    {
      prompt: "A circle has radius 4. Which expression gives its area?",
      options: ["8 pi", "16 pi", "4 pi"],
      answer: 1,
      teaching: "Circle area is pi r^2. With radius 4, area is 16 pi.",
      shape: "circle",
    },
    {
      prompt: "Two angles in a triangle are 45 and 65 degrees. Find the third.",
      options: ["70 degrees", "90 degrees", "110 degrees"],
      answer: 0,
      teaching: "Triangle angles sum to 180 degrees. 180 - 45 - 65 = 70.",
      shape: "angle",
    },
    {
      prompt: "A rectangular prism is 3 x 4 x 5. What is the volume?",
      options: ["12", "60", "94"],
      answer: 1,
      teaching: "Volume is length x width x height, so 3 x 4 x 5 = 60.",
      shape: "prism",
    },
    {
      prompt: "A square has area 81. What is one side length?",
      options: ["9", "18", "40.5"],
      answer: 0,
      teaching: "A square's side is the square root of its area. sqrt(81) = 9.",
      shape: "rectangle",
    },
    {
      prompt: "A right triangle has legs 5 and 12. What is the hypotenuse?",
      options: ["13", "17", "60"],
      answer: 0,
      teaching: "The 5-12-13 triangle follows a^2 + b^2 = c^2.",
      shape: "triangle",
    },
    {
      prompt: "A straight line is split into angles of 112 and x degrees. What is x?",
      options: ["58 degrees", "68 degrees", "112 degrees"],
      answer: 1,
      teaching: "Angles on a straight line sum to 180 degrees. 180 - 112 = 68.",
      shape: "angle",
    },
  ],
  stocks: [
    {
      prompt: "A diversified index fund dips after strong earnings and stable guidance.",
      options: ["Buy", "Hold", "Sell"],
      answer: 0,
      teaching: "A temporary dip with strong fundamentals can be a buy opportunity for long-term investors.",
      series: [42, 44, 43, 45, 47, 46, 43],
      marketMove: "up",
    },
    {
      prompt: "A meme stock spikes 80 percent on rumors but revenue keeps shrinking.",
      options: ["Buy", "Hold", "Sell"],
      answer: 2,
      teaching: "A hype spike without fundamentals raises downside risk; selling or avoiding protects capital.",
      series: [20, 23, 29, 38, 52, 61, 58],
      marketMove: "down",
    },
    {
      prompt: "A company beats sales estimates but warns next quarter costs will jump.",
      options: ["Buy", "Hold", "Sell"],
      answer: 1,
      teaching: "Mixed signals often call for holding while watching margins and future guidance.",
      series: [31, 32, 34, 33, 35, 35, 34],
      marketMove: "flat",
    },
    {
      prompt: "You already hold one tech stock that is now 55 percent of your portfolio.",
      options: ["Buy", "Hold", "Sell"],
      answer: 2,
      teaching: "Selling some shares can rebalance concentration risk and protect diversification.",
      series: [48, 51, 56, 59, 63, 66, 68],
      marketMove: "down",
    },
    {
      prompt: "A low-cost bond fund rises while your target allocation is underweight bonds.",
      options: ["Buy", "Hold", "Sell"],
      answer: 0,
      teaching: "Buying the underweight asset helps rebalance toward the plan instead of chasing one winner.",
      series: [25, 25, 26, 26, 27, 28, 28],
      marketMove: "up",
    },
    {
      prompt: "A stock drops after a product recall and management cannot estimate the cost.",
      options: ["Buy", "Hold", "Sell"],
      answer: 2,
      teaching: "Unknown liability can impair future cash flow; reducing exposure is prudent.",
      series: [64, 61, 58, 50, 44, 39, 37],
      marketMove: "down",
    },
    {
      prompt: "A profitable dividend stock is flat while the whole market is nervous.",
      options: ["Buy", "Hold", "Sell"],
      answer: 1,
      teaching: "Stable fundamentals during volatility can justify patience instead of overtrading.",
      series: [36, 36, 35, 36, 37, 36, 36],
      marketMove: "flat",
    },
    {
      prompt: "An ETF tracks thousands of stocks and you are investing for retirement decades away.",
      options: ["Buy", "Hold", "Sell"],
      answer: 0,
      teaching: "Broad diversification and a long horizon support steady buying through volatility.",
      series: [30, 32, 31, 33, 35, 34, 36],
      marketMove: "up",
    },
  ],
};

const BOARD_GAMES = [
  {
    href: "/arcade/challenge-ai/tic-tac-toe",
    icon: "❌⭕",
    name: "Tic-Tac-Toe Duel",
    desc: "Classic 3×3. On Hard the AI plays a perfect game.",
    color: "#7c3aed",
  },
  {
    href: "/arcade/challenge-ai/connect-four",
    icon: "🔴🟡",
    name: "Connect Four Duel",
    desc: "Drop discs to line up four. Alpha-beta search AI.",
    color: "#0ea5e9",
  },
  {
    href: "/arcade/challenge-ai/number-duel",
    icon: "⚡➗",
    name: "Number Duel",
    desc: "A mental-math race. Answer before the AI buzzes in.",
    color: "#f59e0b",
  },
];

type ViewState = {
  mode: ModeKey;
  phase: Phase;
  playerScore: number;
  aiScore: number;
  streak: number;
  index: number;
  timeLeft: number;
  aiLeft: number;
  lastMessage: string;
  question: ChallengeQuestion;
};

const buttonBase = {
  border: 0,
  borderRadius: 12,
  cursor: "pointer",
  fontWeight: 800,
} as const;

function nextAiAnswer(q: ChallengeQuestion, accuracy: number): number {
  if (Math.random() < accuracy) return q.answer;
  const misses = q.options.map((_, i) => i).filter((i) => i !== q.answer);
  return misses[Math.floor(Math.random() * misses.length)] ?? q.answer;
}

function drawShape(ctx: CanvasRenderingContext2D, shape: ChallengeQuestion["shape"], x: number, y: number, size: number, color: string): void {
  ctx.save();
  ctx.strokeStyle = color;
  ctx.fillStyle = `${color}33`;
  ctx.lineWidth = 4;
  ctx.shadowColor = color;
  ctx.shadowBlur = 14;
  if (shape === "triangle") {
    ctx.beginPath();
    ctx.moveTo(x, y - size * 0.55);
    ctx.lineTo(x - size * 0.6, y + size * 0.5);
    ctx.lineTo(x + size * 0.6, y + size * 0.5);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  } else if (shape === "circle") {
    ctx.beginPath();
    ctx.arc(x, y, size * 0.48, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  } else if (shape === "angle") {
    ctx.beginPath();
    ctx.moveTo(x - size * 0.45, y + size * 0.45);
    ctx.lineTo(x - size * 0.1, y - size * 0.45);
    ctx.lineTo(x + size * 0.55, y + size * 0.4);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(x - size * 0.1, y - size * 0.45, size * 0.2, 0.65, 1.95);
    ctx.stroke();
  } else if (shape === "prism") {
    roundRect(ctx, x - size * 0.46, y - size * 0.32, size * 0.76, size * 0.55, 6);
    ctx.fill();
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x - size * 0.18, y - size * 0.52);
    ctx.lineTo(x + size * 0.52, y - size * 0.34);
    ctx.lineTo(x + size * 0.3, y + size * 0.24);
    ctx.stroke();
  } else {
    roundRect(ctx, x - size * 0.5, y - size * 0.36, size, size * 0.72, 8);
    ctx.fill();
    ctx.stroke();
  }
  ctx.restore();
}

function drawMarket(ctx: CanvasRenderingContext2D, q: ChallengeQuestion, x: number, y: number, w: number, h: number, accent: string): void {
  const series = q.series ?? [30, 31, 32, 33, 34, 35, 36];
  const lo = Math.min(...series);
  const hi = Math.max(...series);
  ctx.save();
  ctx.strokeStyle = "#334155";
  ctx.lineWidth = 1;
  for (let i = 0; i < 4; i++) {
    const yy = y + (h / 3) * i;
    ctx.beginPath();
    ctx.moveTo(x, yy);
    ctx.lineTo(x + w, yy);
    ctx.stroke();
  }
  ctx.strokeStyle = accent;
  ctx.lineWidth = 5;
  ctx.shadowColor = accent;
  ctx.shadowBlur = 14;
  ctx.beginPath();
  series.forEach((value, i) => {
    const px = x + (w / (series.length - 1)) * i;
    const py = y + h - ((value - lo) / Math.max(1, hi - lo)) * h;
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  });
  ctx.stroke();
  ctx.restore();
}

export default function ChallengeAiPage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [mode, setMode] = useState<ModeKey>("geometry");
  const [phase, setPhase] = useState<Phase>("intro");
  const [index, setIndex] = useState(0);
  const [playerScore, setPlayerScore] = useState(0);
  const [aiScore, setAiScore] = useState(0);
  const [streak, setStreak] = useState(0);
  const [timeLeft, setTimeLeft] = useState(MODES.geometry.timeLimit);
  const [aiLeft, setAiLeft] = useState(MODES.geometry.aiTime);
  const [lastMessage, setLastMessage] = useState("Start a run to challenge the AI.");
  const [awaitingNext, setAwaitingNext] = useState(false);
  const [best, setBest] = useState(0);
  const answeredRef = useRef(false);
  const currentRef = useRef({
    mode,
    phase,
    index,
    streak,
    timeLeft,
    awaitingNext,
  });
  const viewRef = useRef<ViewState>({
    mode,
    phase,
    playerScore,
    aiScore,
    streak,
    index,
    timeLeft,
    aiLeft,
    lastMessage,
    question: DECKS[mode][0],
  });

  const config = MODES[mode];
  const deck = DECKS[mode];
  const question = deck[Math.min(index, deck.length - 1)];
  const winner = playerScore === aiScore ? "Tie game" : playerScore > aiScore ? "You beat the AI" : `${config.aiName} wins`;

  useEffect(() => {
    try {
      setBest(Number(localStorage.getItem(config.bestKey) || 0));
    } catch {
      setBest(0);
    }
  }, [config.bestKey]);

  useEffect(() => {
    currentRef.current = { mode, phase, index, streak, timeLeft, awaitingNext };
    viewRef.current = {
      mode, phase, playerScore, aiScore, streak, index, timeLeft, aiLeft, lastMessage, question,
    };
  }, [mode, phase, playerScore, aiScore, streak, index, timeLeft, aiLeft, lastMessage, question, awaitingNext]);

  const finishRun = useCallback((modeForRun: ModeKey, nextPlayerScore: number) => {
    currentRef.current = { ...currentRef.current, phase: "over" };
    setPhase("over");
    try {
      const nextBest = Math.max(nextPlayerScore, Number(localStorage.getItem(MODES[modeForRun].bestKey) || 0));
      localStorage.setItem(MODES[modeForRun].bestKey, String(nextBest));
      setBest(nextBest);
    } catch {
      setBest((b) => Math.max(b, nextPlayerScore));
    }
  }, []);

  const resolveTurn = useCallback((
    source: ChoiceSource,
    answerIndex: number | null,
    visibleMode?: ModeKey,
    visibleIndex?: number,
    visibleTimeLeft?: number,
  ) => {
    const current = currentRef.current;
    if (answeredRef.current || current.phase !== "playing" || current.awaitingNext) return;
    answeredRef.current = true;
    const modeNow = visibleMode ?? current.mode;
    const indexNow = visibleIndex ?? current.index;
    if (source === "player" && (modeNow !== current.mode || indexNow !== current.index)) {
      answeredRef.current = false;
      return;
    }
    const streakNow = current.streak;
    const timeNow = visibleTimeLeft ?? current.timeLeft;
    const cfg = MODES[modeNow];
    const q = DECKS[modeNow][indexNow];
    const aiAnswer = source === "ai" ? nextAiAnswer(q, cfg.aiAccuracy) : null;
    const playerCorrect = source === "player" && answerIndex === q.answer;
    const aiCorrect = source === "ai" ? aiAnswer === q.answer : Math.random() < cfg.aiAccuracy;

    let playerDelta = 0;
    let aiDelta = 0;
    const nextStreak = source === "player" && playerCorrect ? streakNow + 1 : 0;
    let message = "";

    if (playerCorrect) {
      playerDelta = 120 + nextStreak * 15 + Math.round(timeNow * 5);
      aiDelta = aiCorrect ? 70 : 25;
      message = `Correct. ${q.teaching}`;
    } else if (source === "player") {
      playerDelta = -20;
      aiDelta = aiCorrect ? 105 : 35;
      message = `Missed. ${q.teaching}`;
    } else if (aiCorrect) {
      aiDelta = 110;
      playerDelta = 15;
      message = `Time expired. ${cfg.aiName} takes the point. ${q.teaching}`;
    } else {
      aiDelta = 20;
      playerDelta = 45;
      message = `Time expired, but ${cfg.aiName} missed too. ${q.teaching}`;
    }

    setStreak(nextStreak);
    setLastMessage(message);
    const nextIndex = indexNow + 1;
    const finalRound = nextIndex >= DECKS[modeNow].length;
    setPlayerScore((score) => {
      const nextScore = Math.max(0, score + playerDelta);
      if (finalRound) finishRun(modeNow, nextScore);
      return nextScore;
    });
    setAiScore((score) => Math.max(0, score + aiDelta));

    currentRef.current = {
      ...currentRef.current,
      awaitingNext: true,
    };
    if (!finalRound) setAwaitingNext(true);
  }, [finishRun]);

  useEffect(() => {
    if (phase !== "playing" || awaitingNext) return;
    answeredRef.current = false;
    setTimeLeft(config.timeLimit);
    setAiLeft(config.aiTime + (Math.random() - 0.5) * 1.2);
    const timer = window.setInterval(() => {
      setTimeLeft((left) => {
        const next = Math.max(0, left - 0.1);
        if (next <= 0.01) resolveTurn("timeout", null);
        return next;
      });
      setAiLeft((left) => {
        return Math.max(0, left - 0.1);
      });
    }, 100);
    return () => window.clearInterval(timer);
  }, [awaitingNext, config.aiTime, config.timeLimit, index, mode, phase, resolveTurn]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const surface = new Surface(canvas);
    const particles = new Particles();
    const stars = new Starfield(120);
    let pulse = 0;
    const loop = new GameLoop((dt) => {
      pulse += dt;
      const { ctx } = surface;
      const W = surface.width;
      const H = surface.height;
      const view = viewRef.current;
      const cfg = MODES[view.mode];
      const q = view.question;
      const progress = clamp(1 - view.timeLeft / cfg.timeLimit, 0, 1);
      const aiProgress = clamp(1 - view.aiLeft / cfg.aiTime, 0, 1);

      const bg = ctx.createLinearGradient(0, 0, W, H);
      bg.addColorStop(0, "#070617");
      bg.addColorStop(0.58, view.mode === "geometry" ? "#1f1147" : "#082f49");
      bg.addColorStop(1, "#020617");
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, W, H);
      stars.draw(ctx, W, H, pulse);

      ctx.fillStyle = "#fff";
      ctx.font = `800 ${clamp(W * 0.045, 24, 42)}px system-ui, sans-serif`;
      ctx.textAlign = "left";
      ctx.fillText(cfg.title, 22, 44);
      ctx.font = "700 15px system-ui, sans-serif";
      ctx.fillStyle = "#cbd5e1";
      ctx.fillText(`Round ${Math.min(view.index + 1, DECKS[view.mode].length)} / ${DECKS[view.mode].length}`, 24, 70);

      const barY = 92;
      const barW = Math.max(120, W * 0.34);
      ctx.fillStyle = "rgba(15,23,42,0.75)";
      roundRect(ctx, 24, barY, barW, 42, 12);
      ctx.fill();
      roundRect(ctx, W - barW - 24, barY, barW, 42, 12);
      ctx.fill();
      ctx.fillStyle = cfg.accent;
      roundRect(ctx, 30, barY + 26, clamp(view.playerScore / 1200, 0, 1) * (barW - 12), 8, 6);
      ctx.fill();
      ctx.fillStyle = "#f97316";
      roundRect(ctx, W - barW - 18, barY + 26, clamp(view.aiScore / 1200, 0, 1) * (barW - 12), 8, 6);
      ctx.fill();
      ctx.fillStyle = "#fff";
      ctx.font = "800 16px system-ui, sans-serif";
      ctx.fillText(`You ${view.playerScore}`, 36, barY + 20);
      ctx.textAlign = "right";
      ctx.fillText(`${cfg.aiName} ${view.aiScore}`, W - 36, barY + 20);

      ctx.textAlign = "center";
      ctx.font = "800 16px system-ui, sans-serif";
      ctx.fillStyle = "#e0f2fe";
      ctx.fillText(`Timer ${Math.ceil(view.timeLeft)}s`, W / 2, barY + 12);
      ctx.fillStyle = "#fed7aa";
      ctx.fillText(`AI ${Math.round(aiProgress * 100)}%`, W / 2, barY + 34);

      const panelY = 154;
      ctx.fillStyle = "rgba(15,23,42,0.68)";
      roundRect(ctx, 24, panelY, W - 48, 72, 16);
      ctx.fill();
      ctx.fillStyle = "#f8fafc";
      ctx.font = `800 ${clamp(W * 0.024, 15, 22)}px system-ui, sans-serif`;
      ctx.textAlign = "center";
      const words = q.prompt.split(" ");
      let line = "";
      let yy = panelY + 28;
      for (const word of words) {
        const test = line ? `${line} ${word}` : word;
        if (ctx.measureText(test).width > W - 92) {
          ctx.fillText(line, W / 2, yy);
          line = word;
          yy += 24;
        } else {
          line = test;
        }
      }
      ctx.fillText(line, W / 2, yy);

      if (view.mode === "geometry") {
        const wellW = Math.min(260, W * 0.34);
        const cell = wellW / 8;
        const wellH = cell * 10;
        const leftX = W * 0.17;
        const rightX = W * 0.66;
        const top = H - wellH - 34;
        for (const [x, color, label, score] of [
          [leftX, cfg.accent, "YOUR STACK", view.playerScore],
          [rightX, "#f97316", "AI STACK", view.aiScore],
        ] as const) {
          ctx.fillStyle = "rgba(2,6,23,0.7)";
          roundRect(ctx, x, top, wellW, wellH, 12);
          ctx.fill();
          ctx.strokeStyle = "#475569";
          ctx.lineWidth = 1;
          for (let r = 1; r < 10; r++) {
            ctx.beginPath();
            ctx.moveTo(x, top + r * cell);
            ctx.lineTo(x + wellW, top + r * cell);
            ctx.stroke();
          }
          const rows = Math.min(9, Math.floor(score / 135));
          ctx.fillStyle = color;
          for (let r = 0; r < rows; r++) {
            for (let c = 0; c < 8; c++) {
              if ((r + c) % 5 === 0 && r < rows - 1) continue;
              roundRect(ctx, x + c * cell + 2, top + wellH - (r + 1) * cell + 2, cell - 4, cell - 4, 5);
              ctx.fill();
            }
          }
          ctx.fillStyle = "#cbd5e1";
          ctx.font = "800 12px system-ui, sans-serif";
          ctx.textAlign = "center";
          ctx.fillText(label, x + wellW / 2, top - 10);
        }
        drawShape(ctx, q.shape, W / 2, top + 42 + progress * (wellH - 82), clamp(W * 0.09, 50, 78), cfg.accent);
      } else {
        drawMarket(ctx, q, 42, H - 220, W - 84, 145, cfg.accent);
        ctx.fillStyle = q.marketMove === "up" ? "#22c55e" : q.marketMove === "down" ? "#fb7185" : "#facc15";
        ctx.font = "900 40px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(q.marketMove === "up" ? "BUY SIGNAL?" : q.marketMove === "down" ? "RISK ALERT" : "WAIT AND WATCH", W / 2, H - 34);
      }

      particles.update(dt);
      if (view.phase === "playing" && Math.random() < 0.04) {
        particles.burst(W / 2, 120, cfg.accent, 1, { speed: 60, gravity: 20, life: 0.7, size: 2 });
      }
      particles.draw(ctx);
    });
    loop.start();
    return () => {
      loop.stop();
      surface.dispose();
    };
  }, []);

  function startRun(nextMode = mode): void {
    setMode(nextMode);
    setPhase("playing");
    setIndex(0);
    setPlayerScore(0);
    setAiScore(0);
    setStreak(0);
    setTimeLeft(MODES[nextMode].timeLimit);
    setAiLeft(MODES[nextMode].aiTime);
    setLastMessage(`Beat ${MODES[nextMode].aiName} across ${DECKS[nextMode].length} rounds.`);
    setAwaitingNext(false);
    answeredRef.current = false;
  }

  function switchMode(nextMode: ModeKey): void {
    if (phase === "playing") return;
    setMode(nextMode);
    setIndex(0);
    setTimeLeft(MODES[nextMode].timeLimit);
    setAiLeft(MODES[nextMode].aiTime);
    setLastMessage(MODES[nextMode].instructions);
    setAwaitingNext(false);
  }

  function advanceRound(): void {
    const current = currentRef.current;
    if (phase !== "playing" || !awaitingNext) return;
    const nextIndex = current.index + 1;
    const cfg = MODES[current.mode];
    setIndex(nextIndex);
    setTimeLeft(cfg.timeLimit);
    setAiLeft(cfg.aiTime);
    setAwaitingNext(false);
    currentRef.current = {
      ...current,
      index: nextIndex,
      timeLeft: cfg.timeLimit,
      awaitingNext: false,
    };
    answeredRef.current = false;
  }

  const optionButtons = useMemo(() => question.options.map((option, optionIndex) => (
    <button
      key={option}
      onClick={() => resolveTurn("player", optionIndex, mode, index, timeLeft)}
      disabled={phase !== "playing" || answeredRef.current || awaitingNext}
      style={{
        ...buttonBase,
        padding: "13px 16px",
        background: phase === "playing" ? config.accent : "#334155",
        color: "#fff",
        opacity: phase === "playing" ? 1 : 0.6,
        minWidth: 118,
      }}
    >
      {option}
    </button>
  )), [awaitingNext, config.accent, index, mode, phase, question.options, resolveTurn, timeLeft]);

  return (
    <main style={{ maxWidth: 980, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>🤖 Challenge the AI</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
        <Link href="/rewards">Rewards</Link>
      </div>
      <p className="muted" style={{ maxWidth: 760 }}>
        Beat an AI rival in fast learning games: a Tetris-style geometry quiz and a stocks decision sprint.
      </p>

      <div className="card" style={{ background: "linear-gradient(135deg, rgba(15,23,42,0.96), rgba(30,41,59,0.88))", color: "#fff" }}>
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 290px", gap: 16 }}>
          <div>
            <canvas
              ref={canvasRef}
              style={{
                width: "100%",
                aspectRatio: "16 / 10",
                display: "block",
                borderRadius: 16,
                border: "1px solid rgba(148,163,184,0.35)",
                background: "#020617",
              }}
            />
          </div>
          <aside style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <div className="muted" style={{ color: "#cbd5e1", fontSize: 13 }}>Mode</div>
              {(Object.keys(MODES) as ModeKey[]).map((m) => (
                <button
                  key={m}
                  onClick={() => switchMode(m)}
                  disabled={phase === "playing"}
                  style={{
                    ...buttonBase,
                    display: "block",
                    width: "100%",
                    textAlign: "left",
                    marginTop: 8,
                    padding: "12px 14px",
                    background: mode === m ? MODES[m].accent : "rgba(15,23,42,0.82)",
                    color: "#fff",
                    border: "1px solid rgba(148,163,184,0.3)",
                    opacity: phase === "playing" && mode !== m ? 0.55 : 1,
                  }}
                >
                  <span style={{ display: "block" }}>{MODES[m].title}</span>
                  <span style={{ display: "block", fontSize: 12, opacity: 0.82 }}>{MODES[m].short}</span>
                </button>
              ))}
            </div>
            <div style={{ padding: 12, borderRadius: 14, background: "rgba(15,23,42,0.72)", border: "1px solid rgba(148,163,184,0.3)" }}>
              <h2 style={{ margin: "0 0 6px", fontSize: 20 }}>{config.title}</h2>
              <p style={{ margin: "0 0 8px", color: "#cbd5e1", fontSize: 14 }}>{config.subtitle}</p>
              <p style={{ margin: 0, color: "#94a3b8", fontSize: 13 }}>{config.instructions}</p>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <div style={{ padding: 10, borderRadius: 12, background: "rgba(2,6,23,0.7)" }}>
                <div style={{ fontSize: 12, color: "#cbd5e1" }}>You</div>
                <strong>{playerScore}</strong>
              </div>
              <div style={{ padding: 10, borderRadius: 12, background: "rgba(2,6,23,0.7)" }}>
                <div style={{ fontSize: 12, color: "#cbd5e1" }}>{config.aiName}</div>
                <strong>{aiScore}</strong>
              </div>
            </div>
            <div style={{ fontSize: 13, color: "#cbd5e1" }}>
              Best score: <strong style={{ color: "#fff" }}>{best}</strong> {streak > 1 && <>- streak x{streak}</>}
            </div>
            <button
              onClick={() => startRun()}
              style={{
                ...buttonBase,
                padding: "13px 18px",
                background: phase === "playing" ? "#475569" : config.accent,
                color: "#fff",
                fontSize: 16,
              }}
            >
              {phase === "playing" ? "Restart challenge" : phase === "over" ? "Play again" : "Start challenge"}
            </button>
          </aside>
        </div>
      </div>

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
          <div>
            <h3 style={{ margin: "0 0 6px" }}>
              {phase === "over" ? winner : `${config.title} - Round ${Math.min(index + 1, deck.length)} of ${deck.length}`}
            </h3>
            <p className="muted" style={{ margin: 0 }}>{lastMessage}</p>
          </div>
          {phase === "playing" && (
            <div style={{ fontWeight: 800, color: timeLeft < 2 ? "#dc2626" : config.accent }}>
              {Math.ceil(timeLeft)}s left
            </div>
          )}
        </div>
        <div style={{ marginTop: 14, fontWeight: 800 }}>{question.prompt}</div>
        <div className="row" style={{ flexWrap: "wrap", gap: 10, marginTop: 12 }}>
          {optionButtons}
        </div>
        {awaitingNext && phase === "playing" && (
          <button
            onClick={advanceRound}
            style={{
              ...buttonBase,
              marginTop: 14,
              padding: "12px 18px",
              background: config.accent,
              color: "#fff",
            }}
          >
            Next round
          </button>
        )}
      </div>

      <h2 style={{ marginTop: 32 }}>More Challenge Games</h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14 }}>
        {BOARD_GAMES.map((g) => (
          <Link key={g.href} href={g.href} style={{ textDecoration: "none" }}>
            <div className="card" style={{ height: "100%", borderTop: `4px solid ${g.color}` }}>
              <div style={{ fontSize: 28 }}>{g.icon}</div>
              <h3 style={{ margin: "8px 0 4px" }}>{g.name}</h3>
              <p className="muted" style={{ margin: 0, fontSize: 14 }}>{g.desc}</p>
              <div style={{ marginTop: 10, color: g.color, fontWeight: 700 }}>Play →</div>
            </div>
          </Link>
        ))}
      </div>
    </main>
  );
}
