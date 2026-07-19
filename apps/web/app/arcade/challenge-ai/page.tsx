"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type Age = "kids" | "tween" | "teen" | "adult";
type Track = "mixed" | "geometry" | "stocks";
type QuestionKind = "geometry" | "stocks";

type Question = {
  kind: QuestionKind;
  prompt: string;
  options: string[];
  answerIndex: number;
  tip: string;
  board?: number[][];
  prices?: number[];
};

type RoundState = {
  index: number;
  question: Question;
  playerAnswer: number | null;
  aiAnswer: number | null;
  playerCorrect: boolean;
  aiCorrect: boolean;
  locked: boolean;
};

const SETTINGS: Record<Age, { timeLimitS: number; aiAccuracy: number; aiDelayMs: [number, number] }> = {
  kids: { timeLimitS: 16, aiAccuracy: 0.55, aiDelayMs: [1800, 3200] },
  tween: { timeLimitS: 14, aiAccuracy: 0.62, aiDelayMs: [1600, 3000] },
  teen: { timeLimitS: 12, aiAccuracy: 0.72, aiDelayMs: [1400, 2800] },
  adult: { timeLimitS: 10, aiAccuracy: 0.8, aiDelayMs: [1200, 2600] },
};

const SHAPES: number[][][] = [
  [[0, 0], [1, 0], [2, 0], [3, 0]],                     // I
  [[0, 0], [1, 0], [0, 1], [1, 1]],                     // O
  [[1, 0], [0, 1], [1, 1], [2, 1]],                     // T
  [[0, 0], [0, 1], [0, 2], [1, 2]],                     // L
  [[1, 0], [2, 0], [0, 1], [1, 1]],                     // S
  [[0, 0], [1, 0], [2, 0], [1, 1], [1, 2]],             // Plus-5
  [[0, 0], [1, 0], [2, 0], [0, 1], [0, 2], [1, 2]],     // Castle-6
];

function randInt(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

function shuffle<T>(arr: T[]): T[] {
  const out = arr.slice();
  for (let i = out.length - 1; i > 0; i--) {
    const j = randInt(0, i);
    const t = out[i];
    out[i] = out[j];
    out[j] = t;
  }
  return out;
}

function makeBoard(cells: number[][]): number[][] {
  const maxX = Math.max(...cells.map((c) => c[0]));
  const maxY = Math.max(...cells.map((c) => c[1]));
  const size = Math.max(6, maxX + 3, maxY + 3);
  const board = Array.from({ length: size }, () => Array.from({ length: size }, () => 0));
  for (const [x, y] of cells) board[y + 1][x + 1] = 1;
  return board;
}

function perimeter(cells: number[][]): number {
  const set = new Set(cells.map((c) => `${c[0]},${c[1]}`));
  let p = 0;
  for (const [x, y] of cells) {
    if (!set.has(`${x + 1},${y}`)) p += 1;
    if (!set.has(`${x - 1},${y}`)) p += 1;
    if (!set.has(`${x},${y + 1}`)) p += 1;
    if (!set.has(`${x},${y - 1}`)) p += 1;
  }
  return p;
}

function makeGeometryQuestion(level: number): Question {
  const shape = SHAPES[randInt(0, SHAPES.length - 1)];
  const board = makeBoard(shape);
  const area = shape.length;
  const per = perimeter(shape);
  const askPerimeter = level >= 1 && Math.random() > 0.35;
  const answer = askPerimeter ? per : area;
  const wrong = new Set<number>();
  while (wrong.size < 3) {
    const delta = randInt(1, 4) * (Math.random() > 0.5 ? 1 : -1);
    const candidate = Math.max(3, answer + delta);
    if (candidate !== answer) wrong.add(candidate);
  }
  const options = shuffle([answer, ...wrong]).map(String);
  return {
    kind: "geometry",
    prompt: askPerimeter
      ? "Tetris geometry: what is the perimeter of this block shape?"
      : "Tetris geometry: how many unit squares are in this block shape?",
    options,
    answerIndex: options.indexOf(String(answer)),
    tip: askPerimeter
      ? "Perimeter is the outside edge length; touching sides inside the piece do not count."
      : "Count each filled square exactly once.",
    board,
  };
}

function makeStocksQuestion(level: number): Question {
  const start = randInt(40, 130);
  const points = randInt(4, 6);
  const prices: number[] = [start];
  for (let i = 1; i < points; i++) {
    const drift = randInt(-6, 8) + (level >= 1 ? randInt(-2, 3) : 0);
    prices.push(Math.max(8, prices[i - 1] + drift));
  }
  const kind = level >= 1 && Math.random() > 0.4 ? "pct" : "trend";
  if (kind === "pct") {
    const pct = Math.round(((prices[prices.length - 1] - prices[0]) / prices[0]) * 100);
    const wrong = new Set<number>();
    while (wrong.size < 3) {
      const candidate = pct + randInt(2, 8) * (Math.random() > 0.5 ? 1 : -1);
      if (candidate !== pct) wrong.add(candidate);
    }
    const options = shuffle([pct, ...wrong]).map((v) => `${v}%`);
    return {
      kind: "stocks",
      prompt: "Stock learning: approximately what is the percent change from first to last price?",
      options,
      answerIndex: options.indexOf(`${pct}%`),
      tip: "Percent change = ((last - first) / first) × 100.",
      prices,
    };
  }
  const first = prices[0];
  const last = prices[prices.length - 1];
  const net = last - first;
  const answer = net > 4 ? "Uptrend" : net < -4 ? "Downtrend" : "Mostly sideways";
  const options = shuffle(["Uptrend", "Downtrend", "Mostly sideways", "Perfectly random"]);
  return {
    kind: "stocks",
    prompt: "Stock learning: which label best describes this short price trend?",
    options,
    answerIndex: options.indexOf(answer),
    tip: "Look at first vs last price and the overall direction, not one noisy jump.",
    prices,
  };
}

function makeQuestion(track: Track, level: number, roundIndex: number): Question {
  const kind: QuestionKind =
    track === "mixed" ? (roundIndex % 2 === 0 ? "geometry" : "stocks") : (track as QuestionKind);
  return kind === "geometry" ? makeGeometryQuestion(level) : makeStocksQuestion(level);
}

export default function ChallengeAiPage() {
  const [age, setAge] = useState<Age>("teen");
  const [track, setTrack] = useState<Track>("mixed");
  const [roundCount, setRoundCount] = useState(8);
  const [running, setRunning] = useState(false);
  const [timer, setTimer] = useState(0);
  const [playerScore, setPlayerScore] = useState(0);
  const [aiScore, setAiScore] = useState(0);
  const [adaptLevel, setAdaptLevel] = useState(0);
  const [round, setRound] = useState<RoundState | null>(null);
  const [history, setHistory] = useState<string[]>([]);
  const aiTimerRef = useRef<number | null>(null);

  const config = SETTINGS[age];

  const aiAccuracy = useMemo(() => {
    return clamp(config.aiAccuracy + adaptLevel * 0.04, 0.4, 0.94);
  }, [config.aiAccuracy, adaptLevel]);

  const clearAiTimer = () => {
    if (aiTimerRef.current !== null) {
      window.clearTimeout(aiTimerRef.current);
      aiTimerRef.current = null;
    }
  };

  const startRound = useCallback((index: number) => {
    const q = makeQuestion(track, adaptLevel, index);
    setRound({
      index,
      question: q,
      playerAnswer: null,
      aiAnswer: null,
      playerCorrect: false,
      aiCorrect: false,
      locked: false,
    });
    setTimer(config.timeLimitS);
    clearAiTimer();
    const [lo, hi] = config.aiDelayMs;
    aiTimerRef.current = window.setTimeout(() => {
      setRound((prev) => {
        if (!prev || prev.locked || prev.aiAnswer !== null) return prev;
        const chooseCorrect = Math.random() < aiAccuracy;
        const aiChoice = chooseCorrect
          ? prev.question.answerIndex
          : (() => {
              const wrong = prev.question.options
                .map((_, i) => i)
                .filter((i) => i !== prev.question.answerIndex);
              return wrong[randInt(0, wrong.length - 1)];
            })();
        return { ...prev, aiAnswer: aiChoice };
      });
    }, randInt(lo, hi));
  }, [track, adaptLevel, config.timeLimitS, config.aiDelayMs, aiAccuracy]);

  const resetAll = () => {
    clearAiTimer();
    setRunning(false);
    setTimer(0);
    setPlayerScore(0);
    setAiScore(0);
    setAdaptLevel(0);
    setRound(null);
    setHistory([]);
  };

  const startGame = () => {
    setPlayerScore(0);
    setAiScore(0);
    setAdaptLevel(0);
    setHistory([]);
    setRunning(true);
    startRound(0);
  };

  const lockRound = useCallback(() => {
    setRound((prev) => {
      if (!prev || prev.locked) return prev;
      const aiChoice = prev.aiAnswer ?? (() => {
        const chooseCorrect = Math.random() < aiAccuracy;
        if (chooseCorrect) return prev.question.answerIndex;
        const wrong = prev.question.options.map((_, i) => i).filter((i) => i !== prev.question.answerIndex);
        return wrong[randInt(0, wrong.length - 1)];
      })();
      const playerCorrect = prev.playerAnswer === prev.question.answerIndex;
      const aiCorrect = aiChoice === prev.question.answerIndex;
      const nextPlayer = playerCorrect ? playerScore + 10 : playerScore;
      const nextAi = aiCorrect ? aiScore + 10 : aiScore;
      setPlayerScore(nextPlayer);
      setAiScore(nextAi);
      setAdaptLevel((lvl) => {
        if (playerCorrect && !aiCorrect) return clamp(lvl + 1, -2, 2);
        if (!playerCorrect && aiCorrect) return clamp(lvl - 1, -2, 2);
        return lvl;
      });
      setHistory((h) => [
        `${prev.question.kind.toUpperCase()} R${prev.index + 1}: you ${playerCorrect ? "✓" : "✗"} · AI ${aiCorrect ? "✓" : "✗"}`,
        ...h,
      ].slice(0, 6));
      return {
        ...prev,
        aiAnswer: aiChoice,
        playerCorrect,
        aiCorrect,
        locked: true,
      };
    });
    clearAiTimer();
  }, [aiAccuracy, playerScore, aiScore]);

  useEffect(() => {
    if (!running || !round || round.locked) return;
    if (timer <= 0) {
      lockRound();
      return;
    }
    const id = window.setTimeout(() => setTimer((t) => t - 1), 1000);
    return () => window.clearTimeout(id);
  }, [running, round, timer, lockRound]);

  useEffect(() => {
    return () => clearAiTimer();
  }, []);

  const isDone = running && round !== null && round.locked && round.index >= roundCount - 1;

  function nextRound() {
    if (!round) return;
    if (round.index >= roundCount - 1) return;
    startRound(round.index + 1);
  }

  return (
    <main style={{ maxWidth: 980, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>🤖 Challenge the AI</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
      </div>
      <p className="muted" style={{ marginTop: 6 }}>
        Dub it: challenge the AI and see if you can beat it. This duel rotates between
        Tetris-style geometry puzzles and stock-trend learning rounds.
      </p>

      {!running && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Set your duel</h3>
          <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
            <label>
              <span className="muted" style={{ marginRight: 6 }}>Age</span>
              <select value={age} onChange={(e) => setAge(e.target.value as Age)}>
                <option value="kids">Kids</option>
                <option value="tween">Tweens</option>
                <option value="teen">Teens</option>
                <option value="adult">Adults</option>
              </select>
            </label>
            <label>
              <span className="muted" style={{ marginRight: 6 }}>Track</span>
              <select value={track} onChange={(e) => setTrack(e.target.value as Track)}>
                <option value="mixed">Mixed (geometry + stocks)</option>
                <option value="geometry">Geometry only</option>
                <option value="stocks">Stocks only</option>
              </select>
            </label>
            <label>
              <span className="muted" style={{ marginRight: 6 }}>Rounds</span>
              <select value={roundCount} onChange={(e) => setRoundCount(Number(e.target.value))}>
                <option value={6}>6</option>
                <option value={8}>8</option>
                <option value={10}>10</option>
              </select>
            </label>
          </div>
          <div className="muted" style={{ marginTop: 10 }}>
            AI starts near {Math.round(config.aiAccuracy * 100)}% accuracy; your results adapt the challenge level.
          </div>
          <button onClick={startGame} style={{ marginTop: 14, background: "#dc2626", color: "#fff", padding: "10px 20px" }}>
            ▶ Start Challenge
          </button>
        </div>
      )}

      {running && round && (
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
            <strong>Round {round.index + 1}/{roundCount}</strong>
            <span style={{ color: timer <= 3 && !round.locked ? "#dc2626" : "inherit" }}>⏱ {round.locked ? 0 : timer}s</span>
          </div>
          <div className="row" style={{ gap: 12, flexWrap: "wrap", marginTop: 8 }}>
            <span>👤 You: <strong>{playerScore}</strong></span>
            <span>🤖 AI: <strong>{aiScore}</strong></span>
            <span className="muted">Adaptive level: {adaptLevel > 0 ? `+${adaptLevel}` : adaptLevel}</span>
          </div>
          <h3 style={{ marginBottom: 8 }}>{round.question.prompt}</h3>

          {round.question.board && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: `repeat(${round.question.board[0].length}, 16px)`,
                gap: 2,
                marginBottom: 12,
                width: "fit-content",
                padding: 8,
                borderRadius: 8,
                border: "1px solid var(--border)",
                background: "#09090b",
              }}
            >
              {round.question.board.flatMap((row, y) =>
                row.map((v, x) => (
                  <div
                    key={`${x}-${y}`}
                    style={{
                      width: 16,
                      height: 16,
                      borderRadius: 3,
                      background: v ? "#7c3aed" : "#27272a",
                      border: v ? "1px solid #c4b5fd" : "1px solid #3f3f46",
                    }}
                  />
                ))
              )}
            </div>
          )}

          {round.question.prices && (
            <div style={{ marginBottom: 12, display: "flex", gap: 6, alignItems: "flex-end", minHeight: 70 }}>
              {round.question.prices.map((p, i) => (
                <div key={`${p}-${i}`} style={{ display: "grid", gap: 4, justifyItems: "center" }}>
                  <div
                    style={{
                      width: 22,
                      height: clamp((p / 150) * 62, 12, 62),
                      background: "#0ea5e9",
                      borderRadius: 6,
                    }}
                    title={`Day ${i + 1}: ${p}`}
                  />
                  <span style={{ fontSize: 11, opacity: 0.8 }}>{p}</span>
                </div>
              ))}
            </div>
          )}

          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            {round.question.options.map((opt, i) => {
              const selected = round.playerAnswer === i;
              const revealCorrect = round.locked && round.question.answerIndex === i;
              const revealWrongPick = round.locked && selected && !revealCorrect;
              return (
                <button
                  key={i}
                  onClick={() => setRound((r) => (r && !r.locked ? { ...r, playerAnswer: i } : r))}
                  disabled={round.locked}
                  style={{
                    border: selected ? "2px solid #7c3aed" : "1px solid var(--border)",
                    background: revealCorrect ? "#dcfce7" : revealWrongPick ? "#fee2e2" : selected ? "#ede9fe" : "transparent",
                    color: revealCorrect ? "#166534" : revealWrongPick ? "#991b1b" : "inherit",
                  }}
                >
                  {opt}
                </button>
              );
            })}
          </div>

          {!round.locked ? (
            <button
              onClick={lockRound}
              style={{ marginTop: 12, background: "#7c3aed", color: "#fff" }}
              disabled={round.playerAnswer === null}
            >
              Lock answer
            </button>
          ) : (
            <div style={{ marginTop: 12 }}>
              <div className="muted">{round.question.tip}</div>
              <div style={{ marginTop: 6 }}>
                You {round.playerCorrect ? "win this round (+10)" : "missed"} · AI {round.aiCorrect ? "scores (+10)" : "missed"}.
              </div>
              {!isDone && (
                <button onClick={nextRound} style={{ marginTop: 10, background: "#16a34a", color: "#fff" }}>
                  Next round
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {isDone && round && (
        <div className="card" style={{ borderColor: "#7c3aed" }}>
          <h3 style={{ marginTop: 0 }}>
            Final: You {playerScore} · AI {aiScore}
          </h3>
          <div style={{ marginBottom: 8 }}>
            {playerScore > aiScore ? "🏆 You beat the AI!" : playerScore < aiScore ? "🤖 AI wins this duel." : "🤝 Draw game."}
          </div>
          <div className="muted" style={{ marginBottom: 8 }}>Recent rounds</div>
          <ul style={{ marginTop: 0 }}>
            {history.map((h) => <li key={h}>{h}</li>)}
          </ul>
          <div className="row" style={{ gap: 10 }}>
            <button onClick={startGame} style={{ background: "#7c3aed", color: "#fff" }}>Play rematch</button>
            <button onClick={resetAll}>Change settings</button>
          </div>
        </div>
      )}
    </main>
  );
}
