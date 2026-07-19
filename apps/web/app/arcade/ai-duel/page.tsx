"use client";

// Challenge the AI — Head-to-head quiz duel. You and the AI race to answer
// the same questions. The AI has a randomised reaction time per difficulty
// (easy AI is slow; hard AI is fast). Score points by answering faster and
// correctly. Best of N rounds wins. No backend needed — all client-side.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

// ─── Types ────────────────────────────────────────────────────────────────────

type Difficulty = "rookie" | "scholar" | "genius";

type DuelQuestion = {
  prompt: string;
  options: string[];
  answerIdx: number;
  subject: string;
  explain: string;
};

type RoundResult = {
  question: DuelQuestion;
  playerAnswerIdx: number | null;
  aiAnswerIdx: number;
  playerMs: number | null;   // null = timeout
  aiMs: number;
  playerCorrect: boolean;
  aiCorrect: boolean;
  playerPoints: number;
  aiPoints: number;
};

type DuelState = "idle" | "countdown" | "question" | "reveal" | "gameover";

// ─── AI timing per difficulty ─────────────────────────────────────────────────

const AI_TIMING: Record<Difficulty, { minMs: number; maxMs: number; mistakeRate: number }> = {
  rookie:  { minMs: 3500, maxMs: 8000, mistakeRate: 0.35 },
  scholar: { minMs: 1800, maxMs: 4500, mistakeRate: 0.18 },
  genius:  { minMs: 800,  maxMs: 2200, mistakeRate: 0.07 },
};

const QUESTION_TIME_MS = 10_000;
const TOTAL_ROUNDS = 7;

// ─── Question bank ────────────────────────────────────────────────────────────

const QUESTION_POOL: DuelQuestion[] = [
  // Math
  { subject: "Math", prompt: "What is 12 × 8?", options: ["84","96","104","112"], answerIdx: 1, explain: "12 × 8 = 96." },
  { subject: "Math", prompt: "What is √144?", options: ["10","11","12","14"], answerIdx: 2, explain: "√144 = 12." },
  { subject: "Math", prompt: "What is 15% of 200?", options: ["20","25","30","35"], answerIdx: 2, explain: "15% of 200 = 30." },
  { subject: "Math", prompt: "If x + 7 = 15, what is x?", options: ["6","7","8","9"], answerIdx: 2, explain: "x = 15 - 7 = 8." },
  { subject: "Math", prompt: "What is 2⁵?", options: ["10","16","32","64"], answerIdx: 2, explain: "2⁵ = 32." },
  { subject: "Math", prompt: "What is the perimeter of a square with side 6?", options: ["12","18","24","36"], answerIdx: 2, explain: "Perimeter = 4×6 = 24." },
  { subject: "Math", prompt: "Which is prime?", options: ["21","27","29","33"], answerIdx: 2, explain: "29 is prime." },
  // Science
  { subject: "Science", prompt: "What planet is closest to the Sun?", options: ["Venus","Earth","Mars","Mercury"], answerIdx: 3, explain: "Mercury is closest to the Sun." },
  { subject: "Science", prompt: "What gas do plants absorb?", options: ["Oxygen","Nitrogen","CO₂","Hydrogen"], answerIdx: 2, explain: "Plants absorb CO₂ during photosynthesis." },
  { subject: "Science", prompt: "What is H₂O?", options: ["Hydrogen","Oxygen","Water","Salt"], answerIdx: 2, explain: "H₂O is the chemical formula for water." },
  { subject: "Science", prompt: "How many bones in the adult human body?", options: ["186","196","206","216"], answerIdx: 2, explain: "Adults have 206 bones." },
  { subject: "Science", prompt: "What is the powerhouse of the cell?", options: ["Nucleus","Ribosome","Mitochondria","Vacuole"], answerIdx: 2, explain: "The mitochondria produces ATP (energy)." },
  { subject: "Science", prompt: "Speed of light (approx)?", options: ["300,000 km/s","3,000 km/s","30,000 km/s","3,000,000 km/s"], answerIdx: 0, explain: "Speed of light ≈ 300,000 km/s." },
  // History
  { subject: "History", prompt: "In which year did World War II end?", options: ["1943","1944","1945","1946"], answerIdx: 2, explain: "WWII ended in 1945." },
  { subject: "History", prompt: "Who was the first US president?", options: ["Jefferson","Adams","Lincoln","Washington"], answerIdx: 3, explain: "George Washington was the first US president." },
  { subject: "History", prompt: "The Great Wall of China was built mainly against?", options: ["Floods","Mongol invasions","Typhoons","Trade rivals"], answerIdx: 1, explain: "Primarily to keep out Mongol invaders." },
  { subject: "History", prompt: "Which civilization built the Machu Picchu?", options: ["Aztec","Maya","Inca","Olmec"], answerIdx: 2, explain: "Machu Picchu was built by the Inca Empire." },
  // Tech & Programming
  { subject: "Tech", prompt: "What does CPU stand for?", options: ["Central Power Unit","Core Processing Unit","Central Processing Unit","Computer Program Unit"], answerIdx: 2, explain: "CPU = Central Processing Unit." },
  { subject: "Tech", prompt: "Which language runs natively in browsers?", options: ["Python","Java","JavaScript","C++"], answerIdx: 2, explain: "JavaScript is the native browser language." },
  { subject: "Tech", prompt: "What does HTML stand for?", options: ["Hyper Tool Markup Language","HyperText Markup Language","Hyper Transfer Method Language","High Text Markup Language"], answerIdx: 1, explain: "HTML = HyperText Markup Language." },
  { subject: "Tech", prompt: "In binary, 1010 equals what in decimal?", options: ["8","9","10","12"], answerIdx: 2, explain: "1010₂ = 8+2 = 10₁₀." },
  // Word / General
  { subject: "Wordplay", prompt: "Which word is a synonym for 'happy'?", options: ["Somber","Elated","Anxious","Weary"], answerIdx: 1, explain: "Elated means very happy." },
  { subject: "Wordplay", prompt: "What is the antonym of 'ancient'?", options: ["Old","Historic","Modern","Classic"], answerIdx: 2, explain: "Modern is the antonym of ancient." },
  { subject: "Art", prompt: "Who painted the Mona Lisa?", options: ["Raphael","Michelangelo","Da Vinci","Botticelli"], answerIdx: 2, explain: "Leonardo da Vinci painted the Mona Lisa." },
  { subject: "Art", prompt: "Which artist cut off part of his own ear?", options: ["Monet","Picasso","Van Gogh","Dalí"], answerIdx: 2, explain: "Vincent van Gogh famously cut off part of his ear." },
];

function shufflePool(pool: DuelQuestion[]): DuelQuestion[] {
  const a = [...pool];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function genAiAnswer(q: DuelQuestion, mistakeRate: number): { idx: number; msDelay: number; minMs: number; maxMs: number } {
  const { minMs, maxMs } = AI_TIMING["rookie"]; // unused, will be overridden
  void minMs; void maxMs;
  const correct = Math.random() > mistakeRate;
  let idx = q.answerIdx;
  if (!correct) {
    const wrong = q.options.map((_, i) => i).filter((i) => i !== q.answerIdx);
    idx = wrong[Math.floor(Math.random() * wrong.length)];
  }
  return { idx, msDelay: 0, minMs: 0, maxMs: 0 };
}

const DIFFICULTY_LABELS: Record<Difficulty, string> = {
  rookie: "🤖 Rookie AI (slow & clumsy)",
  scholar: "🧠 Scholar AI (steady)",
  genius: "⚡ Genius AI (lightning-fast)",
};

const SUBJECT_ICON: Record<string, string> = {
  Math: "➗", Science: "🔬", History: "🏛️", Tech: "💻", Wordplay: "🔤", Art: "🎨",
};

// ─── Component ────────────────────────────────────────────────────────────────

export default function AIDuel() {
  const [difficulty, setDifficulty] = useState<Difficulty>("scholar");
  const [duelState, setDuelState] = useState<DuelState>("idle");
  const [countdown, setCountdown] = useState(3);
  const [roundIdx, setRoundIdx] = useState(0);
  const [questions, setQuestions] = useState<DuelQuestion[]>([]);
  const [currentQ, setCurrentQ] = useState<DuelQuestion | null>(null);
  const [timeMs, setTimeMs] = useState(QUESTION_TIME_MS);
  const [playerScore, setPlayerScore] = useState(0);
  const [aiScore, setAiScore] = useState(0);
  const [results, setResults] = useState<RoundResult[]>([]);
  const [lastResult, setLastResult] = useState<RoundResult | null>(null);
  const [aiThinking, setAiThinking] = useState(false);

  // Refs for async timing
  const startMsRef = useRef(0);
  const aiTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const qTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const aiAnswerRef = useRef<{ idx: number } | null>(null);
  const playerAnsweredRef = useRef(false);

  const clearTimers = useCallback(() => {
    if (aiTimerRef.current) { clearTimeout(aiTimerRef.current); aiTimerRef.current = null; }
    if (qTimerRef.current) { clearTimeout(qTimerRef.current); qTimerRef.current = null; }
    if (tickRef.current) { clearInterval(tickRef.current); tickRef.current = null; }
  }, []);

  useEffect(() => () => clearTimers(), [clearTimers]);

  const endRound = useCallback((playerAns: number | null, playerMs: number | null, qs: DuelQuestion[]) => {
    clearTimers();
    const q = qs[roundIdx] ?? qs[0];
    if (!q) return;
    const ai = genAiAnswer(q, AI_TIMING[difficulty].mistakeRate);
    const aiMs = Math.floor(Math.random() * (AI_TIMING[difficulty].maxMs - AI_TIMING[difficulty].minMs) + AI_TIMING[difficulty].minMs);
    const aiCorrect = ai.idx === q.answerIdx;
    const playerCorrect = playerAns !== null && playerAns === q.answerIdx;

    // Scoring: correct = 100pts base, speed bonus (max 50), beat-AI bonus
    const speedBonus = playerMs !== null ? Math.max(0, Math.floor(50 * (1 - playerMs / QUESTION_TIME_MS))) : 0;
    const playerPoints = playerCorrect ? 100 + speedBonus : 0;
    const aiSpeedBonus = Math.max(0, Math.floor(50 * (1 - aiMs / QUESTION_TIME_MS)));
    const aiPoints = aiCorrect ? 100 + aiSpeedBonus : 0;

    const r: RoundResult = {
      question: q, playerAnswerIdx: playerAns, aiAnswerIdx: ai.idx,
      playerMs, aiMs, playerCorrect, aiCorrect, playerPoints, aiPoints,
    };
    setLastResult(r);
    setResults((prev) => [...prev, r]);
    setPlayerScore((s) => s + playerPoints);
    setAiScore((s) => s + aiPoints);
    setAiThinking(false);
    setDuelState("reveal");
  }, [roundIdx, difficulty, clearTimers]);

  const startRound = useCallback((qs: DuelQuestion[], ri: number) => {
    clearTimers();
    const q = qs[ri];
    if (!q) return;
    setCurrentQ(q);
    setTimeMs(QUESTION_TIME_MS);
    setAiThinking(true);
    playerAnsweredRef.current = false;
    aiAnswerRef.current = null;
    startMsRef.current = Date.now();
    setDuelState("question");

    // Tick timer
    tickRef.current = setInterval(() => {
      const elapsed = Date.now() - startMsRef.current;
      setTimeMs(Math.max(0, QUESTION_TIME_MS - elapsed));
    }, 100);

    // AI timer
    const aiDelay = Math.floor(
      Math.random() * (AI_TIMING[difficulty].maxMs - AI_TIMING[difficulty].minMs) + AI_TIMING[difficulty].minMs
    );
    const clampedAiDelay = Math.min(aiDelay, QUESTION_TIME_MS - 200);
    aiTimerRef.current = setTimeout(() => {
      setAiThinking(false);
      if (!playerAnsweredRef.current) {
        // AI answered; player still thinking
        const aiAns = genAiAnswer(q, AI_TIMING[difficulty].mistakeRate);
        aiAnswerRef.current = aiAns;
      }
    }, clampedAiDelay);

    // Question timeout
    qTimerRef.current = setTimeout(() => {
      if (!playerAnsweredRef.current) {
        endRound(null, null, qs);
      }
    }, QUESTION_TIME_MS);
  }, [difficulty, clearTimers, endRound]);

  const startGame = useCallback(() => {
    clearTimers();
    setResults([]); setLastResult(null);
    setPlayerScore(0); setAiScore(0);
    setRoundIdx(0); setCountdown(3);
    const qs = shufflePool(QUESTION_POOL).slice(0, TOTAL_ROUNDS);
    setQuestions(qs);
    setDuelState("countdown");

    let c = 3;
    const iv = setInterval(() => {
      c -= 1;
      setCountdown(c);
      if (c <= 0) {
        clearInterval(iv);
        startRound(qs, 0);
      }
    }, 1000);
  }, [clearTimers, startRound]);

  const handleAnswer = useCallback((idx: number) => {
    if (playerAnsweredRef.current || duelState !== "question" || !currentQ) return;
    playerAnsweredRef.current = true;
    const elapsed = Date.now() - startMsRef.current;
    endRound(idx, elapsed, questions);
  }, [duelState, currentQ, endRound, questions]);

  const nextRound = useCallback(() => {
    const nextIdx = roundIdx + 1;
    if (nextIdx >= TOTAL_ROUNDS) {
      setDuelState("gameover");
      return;
    }
    setRoundIdx(nextIdx);
    setLastResult(null);
    setCurrentQ(null);
    startRound(questions, nextIdx);
  }, [roundIdx, questions, startRound]);

  const timeBarPct = (timeMs / QUESTION_TIME_MS) * 100;
  const timeColor = timeMs < 3000 ? "#ef4444" : timeMs < 6000 ? "#f59e0b" : "#22c55e";
  const won = playerScore > aiScore;
  const tied = playerScore === aiScore;

  return (
    <main style={{ maxWidth: 680, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 8 }}>
        <h1 style={{ margin: 0 }}>⚔️ Challenge the AI</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
      </div>
      <p className="muted" style={{ marginTop: 0, marginBottom: 12 }}>
        Go head-to-head against the AI. Answer questions faster and more accurately to win!
      </p>

      {/* Idle / setup */}
      {duelState === "idle" && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Choose AI difficulty</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 16 }}>
            {(["rookie", "scholar", "genius"] as Difficulty[]).map((d) => (
              <button key={d} onClick={() => setDifficulty(d)}
                style={{
                  padding: "12px 16px", borderRadius: 10, textAlign: "left",
                  border: difficulty === d ? "2px solid #7c3aed" : "1px solid var(--border)",
                  background: difficulty === d ? "rgba(124,58,237,0.15)" : "transparent",
                  color: "var(--text)", cursor: "pointer", fontWeight: difficulty === d ? 700 : 400,
                }}>
                {DIFFICULTY_LABELS[d]}
                <div style={{ fontSize: 12, opacity: 0.65, fontWeight: 400, marginTop: 3 }}>
                  {d === "rookie" && "AI answers in 3.5–8 s and makes many mistakes"}
                  {d === "scholar" && "AI answers in 1.8–4.5 s with moderate accuracy"}
                  {d === "genius" && "AI answers in 0.8–2.2 s with near-perfect accuracy"}
                </div>
              </button>
            ))}
          </div>
          <div className="muted" style={{ fontSize: 13, marginBottom: 12 }}>
            {TOTAL_ROUNDS} questions · subjects: Math, Science, History, Tech, Wordplay, Art
          </div>
          <button onClick={startGame}
            style={{ background: "#7c3aed", color: "#fff", padding: "12px 28px", fontSize: 17, borderRadius: 10, border: 0, cursor: "pointer" }}>
            ⚔️ Start duel
          </button>
        </div>
      )}

      {/* Countdown */}
      {duelState === "countdown" && (
        <div className="card" style={{ textAlign: "center", padding: 40 }}>
          <div style={{ fontSize: 14, color: "#94a3b8", marginBottom: 8 }}>Get ready!</div>
          <div style={{ fontSize: 72, fontWeight: 900 }}>{countdown === 0 ? "GO!" : countdown}</div>
        </div>
      )}

      {/* Question */}
      {duelState === "question" && currentQ && (
        <>
          {/* Scoreboard */}
          <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
            <div className="card" style={{ flex: 1, textAlign: "center", padding: "10px", margin: 0 }}>
              <div style={{ fontSize: 12, color: "#94a3b8" }}>You</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: "#22c55e" }}>{playerScore}</div>
            </div>
            <div className="card" style={{ flex: 1, textAlign: "center", padding: "10px", margin: 0 }}>
              <div style={{ fontSize: 12, color: "#94a3b8" }}>Round {roundIdx + 1}/{TOTAL_ROUNDS}</div>
              <div style={{ fontSize: 14, fontWeight: 700 }}>{(timeMs / 1000).toFixed(1)}s</div>
            </div>
            <div className="card" style={{ flex: 1, textAlign: "center", padding: "10px", margin: 0 }}>
              <div style={{ fontSize: 12, color: "#94a3b8" }}>AI {DIFFICULTY_LABELS[difficulty].split(" ")[0]}</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: "#a78bfa" }}>{aiScore}</div>
            </div>
          </div>

          {/* Time bar */}
          <div style={{ height: 8, background: "#1e293b", borderRadius: 4, marginBottom: 12, overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${timeBarPct}%`, background: timeColor, borderRadius: 4, transition: "width 0.1s linear, background 0.3s" }} />
          </div>

          {/* Question card */}
          <div className="card" style={{ border: "2px solid #7c3aed" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <span style={{ fontSize: 12, background: "#1e293b", borderRadius: 6, padding: "2px 8px" }}>
                {SUBJECT_ICON[currentQ.subject] ?? "📘"} {currentQ.subject}
              </span>
              <span style={{ fontSize: 12, color: aiThinking ? "#fbbf24" : "#22c55e" }}>
                {aiThinking ? "🤖 AI thinking…" : "🤖 AI answered!"}
              </span>
            </div>
            <div style={{ fontWeight: 700, fontSize: 18, marginBottom: 14, lineHeight: 1.35 }}>{currentQ.prompt}</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {currentQ.options.map((opt, i) => (
                <button key={i} onClick={() => handleAnswer(i)}
                  style={{
                    padding: "12px 16px", borderRadius: 10, textAlign: "left",
                    border: "1px solid var(--border)", background: "transparent",
                    color: "var(--text)", cursor: "pointer", fontSize: 15, fontWeight: 500,
                    transition: "transform 0.1s",
                  }}
                  onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.transform = "scale(1.02)"; }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.transform = "scale(1)"; }}>
                  <span style={{ display: "inline-block", minWidth: 26, fontWeight: 700, color: "#7c3aed" }}>
                    {["A","B","C","D"][i]}.
                  </span> {opt}
                </button>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Reveal */}
      {duelState === "reveal" && lastResult && (
        <>
          <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
            <div className="card" style={{ flex: 1, textAlign: "center", padding: "10px", margin: 0 }}>
              <div style={{ fontSize: 12, color: "#94a3b8" }}>You</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: "#22c55e" }}>{playerScore}</div>
            </div>
            <div className="card" style={{ flex: 1, textAlign: "center", padding: "10px", margin: 0 }}>
              <div style={{ fontSize: 12, color: "#94a3b8" }}>Round {roundIdx + 1}/{TOTAL_ROUNDS}</div>
            </div>
            <div className="card" style={{ flex: 1, textAlign: "center", padding: "10px", margin: 0 }}>
              <div style={{ fontSize: 12, color: "#94a3b8" }}>AI</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: "#a78bfa" }}>{aiScore}</div>
            </div>
          </div>

          <div className="card" style={{ border: `2px solid ${lastResult.playerCorrect ? "#16a34a" : "#dc2626"}` }}>
            <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
              <span style={{ fontWeight: 700, fontSize: 16 }}>
                {lastResult.playerCorrect ? "✅ Correct!" : lastResult.playerAnswerIdx === null ? "⏱ Timed out" : "❌ Wrong"}
              </span>
              <span style={{ fontWeight: 700, fontSize: 16, color: "#a78bfa" }}>
                {lastResult.aiCorrect ? "🤖 AI correct" : "🤖 AI wrong"}
              </span>
            </div>

            {/* Question recap */}
            <div style={{ fontWeight: 600, marginBottom: 10 }}>{lastResult.question.prompt}</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 10 }}>
              {lastResult.question.options.map((opt, i) => {
                const isCorrect = i === lastResult.question.answerIdx;
                const isPlayerPick = i === lastResult.playerAnswerIdx;
                const isAiPick = i === lastResult.aiAnswerIdx;
                let bg = "transparent";
                if (isCorrect) bg = "rgba(34,197,94,0.15)";
                else if (isPlayerPick || isAiPick) bg = "rgba(239,68,68,0.12)";
                return (
                  <div key={i} style={{ padding: "8px 12px", borderRadius: 8, background: bg, border: isCorrect ? "1px solid #16a34a" : "1px solid transparent", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span><span style={{ fontWeight: 700, color: "#7c3aed", marginRight: 6 }}>{["A","B","C","D"][i]}.</span>{opt}</span>
                    <span style={{ fontSize: 12, display: "flex", gap: 6 }}>
                      {isPlayerPick && <span style={{ color: lastResult.playerCorrect ? "#22c55e" : "#ef4444" }}>You</span>}
                      {isAiPick && <span style={{ color: lastResult.aiCorrect ? "#a78bfa" : "#f87171" }}>AI</span>}
                    </span>
                  </div>
                );
              })}
            </div>

            <div className="muted" style={{ fontSize: 13, fontStyle: "italic", marginBottom: 10 }}>
              💡 {lastResult.question.explain}
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 12 }}>
              <span style={{ color: "#22c55e" }}>
                You: +{lastResult.playerPoints} pts
                {lastResult.playerMs !== null ? ` (${(lastResult.playerMs / 1000).toFixed(2)}s)` : " (timeout)"}
              </span>
              <span style={{ color: "#a78bfa" }}>
                AI: +{lastResult.aiPoints} pts ({(lastResult.aiMs / 1000).toFixed(2)}s)
              </span>
            </div>

            <button onClick={roundIdx + 1 >= TOTAL_ROUNDS ? () => setDuelState("gameover") : nextRound}
              style={{ width: "100%", padding: "12px 0", background: "#7c3aed", color: "#fff", borderRadius: 10, border: 0, cursor: "pointer", fontSize: 15, fontWeight: 600 }}>
              {roundIdx + 1 >= TOTAL_ROUNDS ? "See final results" : `Next question (${roundIdx + 2}/${TOTAL_ROUNDS})`}
            </button>
          </div>
        </>
      )}

      {/* Game over */}
      {duelState === "gameover" && (
        <div className="card" style={{ border: `2px solid ${won ? "#fbbf24" : tied ? "#94a3b8" : "#7c3aed"}` }}>
          <div style={{ textAlign: "center", marginBottom: 16 }}>
            <div style={{ fontSize: 48 }}>{won ? "🏆" : tied ? "🤝" : "🤖"}</div>
            <div style={{ fontSize: 24, fontWeight: 800, marginTop: 8 }}>
              {won ? "You beat the AI!" : tied ? "It's a tie!" : "AI wins this round!"}
            </div>
            <div style={{ fontSize: 15, marginTop: 6, color: "#94a3b8" }}>
              You: {playerScore} pts · AI: {aiScore} pts
            </div>
          </div>

          {/* Round-by-round summary */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>Round breakdown</div>
            {results.map((r, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 0", borderBottom: "1px solid var(--border)", fontSize: 13 }}>
                <span style={{ opacity: 0.7 }}>{i + 1}. {r.question.subject}</span>
                <span style={{ color: r.playerCorrect ? "#22c55e" : "#ef4444" }}>
                  {r.playerCorrect ? "✓" : "✗"} +{r.playerPoints}
                </span>
                <span style={{ color: r.aiCorrect ? "#a78bfa" : "#f87171" }}>
                  AI {r.aiCorrect ? "✓" : "✗"} +{r.aiPoints}
                </span>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", gap: 10 }}>
            <button onClick={startGame} style={{ flex: 1, padding: "12px 0", background: "#7c3aed", color: "#fff", borderRadius: 10, border: 0, cursor: "pointer", fontSize: 15, fontWeight: 600 }}>
              ⚔️ Play again
            </button>
            <button onClick={() => setDuelState("idle")}
              style={{ flex: 1, padding: "12px 0", background: "transparent", color: "var(--text)", borderRadius: 10, border: "1px solid var(--border)", cursor: "pointer", fontSize: 15 }}>
              Change difficulty
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
