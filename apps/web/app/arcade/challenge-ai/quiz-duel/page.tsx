"use client";

// Quiz Duel — Challenge the AI. Race to answer MCQs; first to WIN_TARGET correct wins.
// AI opponent answers with realistic delay and age-scaled accuracy.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

type Age = "kids" | "tween" | "teen" | "adult";

type Q = { prompt: string; options: string[]; answer: number };

const BANK: Record<Age, Q[]> = {
  kids: [
    { prompt: "2 + 2 = ?", options: ["3", "4", "5", "6"], answer: 1 },
    { prompt: "Color of the sky?", options: ["Green", "Blue", "Red", "Yellow"], answer: 1 },
    { prompt: "How many legs does a dog have?", options: ["2", "4", "6", "8"], answer: 1 },
    { prompt: "First letter of the alphabet?", options: ["B", "C", "A", "D"], answer: 2 },
    { prompt: "5 − 2 = ?", options: ["2", "3", "4", "1"], answer: 1 },
    { prompt: "Sun rises in the…", options: ["West", "North", "East", "South"], answer: 2 },
  ],
  tween: [
    { prompt: "7 × 8 = ?", options: ["54", "56", "58", "64"], answer: 1 },
    { prompt: "Capital of France?", options: ["London", "Berlin", "Paris", "Rome"], answer: 2 },
    { prompt: "Largest planet?", options: ["Earth", "Mars", "Jupiter", "Venus"], answer: 2 },
    { prompt: "144 ÷ 12 = ?", options: ["10", "11", "12", "14"], answer: 2 },
    { prompt: "H₂O is…", options: ["Salt", "Water", "Air", "Sugar"], answer: 1 },
    { prompt: "Past tense of 'run'?", options: ["Running", "Ran", "Runs", "Runned"], answer: 1 },
  ],
  teen: [
    { prompt: "Speed of light ≈ ?", options: ["300 km/s", "3×10⁸ m/s", "3×10⁶ m/s", "3000 m/s"], answer: 1 },
    { prompt: "Mitochondria function?", options: ["Protein synthesis", "Energy (ATP)", "Photosynthesis", "Digestion"], answer: 1 },
    { prompt: "x² = 49 → x = ?", options: ["±5", "±6", "±7", "±8"], answer: 2 },
    { prompt: "WWII ended in…", options: ["1943", "1944", "1945", "1946"], answer: 2 },
    { prompt: "DNA stands for…", options: ["Deoxyribonucleic acid", "Dynamic nuclear acid", "Dual nucleotide array", "Dense nucleic atom"], answer: 0 },
    { prompt: "Derivative of x²?", options: ["x", "2x", "x²", "2"], answer: 1 },
  ],
  adult: [
    { prompt: "GDP measures…", options: ["Inflation", "Total economic output", "Unemployment", "Trade balance"], answer: 1 },
    { prompt: "Schrödinger equation describes…", options: ["Gravity", "Quantum states", "Thermodynamics", "Electromagnetism"], answer: 1 },
    { prompt: "Bayes' theorem updates…", options: ["Frequencies", "Probabilities", "Variances", "Correlations"], answer: 1 },
    { prompt: "Opportunity cost is…", options: ["Sunk cost", "Value of next best alternative", "Fixed cost", "Marginal cost"], answer: 1 },
    { prompt: "Big-O of binary search?", options: ["O(n)", "O(log n)", "O(n²)", "O(1)"], answer: 1 },
    { prompt: "Heisenberg uncertainty relates…", options: ["Energy-time", "Position-momentum", "Mass-charge", "Spin-color"], answer: 1 },
  ],
};

const WIN_TARGET = 5;

function aiAccuracy(age: Age): number {
  return { kids: 0.55, tween: 0.65, teen: 0.78, adult: 0.88 }[age];
}

function aiDelay(age: Age): number {
  return { kids: 3500, tween: 2800, teen: 2200, adult: 1600 }[age];
}

export default function QuizDuel() {
  const [age, setAge] = useState<Age>("teen");
  const [phase, setPhase] = useState<"idle" | "playing" | "done">("idle");
  const [questions, setQuestions] = useState<Q[]>([]);
  const [qIdx, setQIdx] = useState(0);
  const [playerScore, setPlayerScore] = useState(0);
  const [aiScore, setAiScore] = useState(0);
  const [aiThinking, setAiThinking] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [winner, setWinner] = useState<"player" | "ai" | "tie" | null>(null);
  const aiTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const answered = useRef(false);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("age");
    if (q === "kids" || q === "tween" || q === "teen" || q === "adult") setAge(q);
  }, []);

  const checkWin = useCallback((p: number, a: number) => {
    if (p >= WIN_TARGET) { setWinner("player"); setPhase("done"); return true; }
    if (a >= WIN_TARGET) { setWinner("ai"); setPhase("done"); return true; }
    return false;
  }, []);

  const nextQuestion = useCallback((p: number, a: number) => {
    if (checkWin(p, a)) return;
    setQIdx((i) => i + 1);
    setFeedback("");
    answered.current = false;
    setAiThinking(true);

    aiTimer.current = setTimeout(() => {
      setAiThinking(false);
      const qs = questions;
      const q = qs[(qIdx + 1) % qs.length];
      if (!q) return;
      const correct = Math.random() < aiAccuracy(age);
      const pick = correct ? q.answer : [0, 1, 2, 3].filter((i) => i !== q.answer)[Math.floor(Math.random() * 3)];
      if (correct) {
        setAiScore((s) => {
          const ns = s + 1;
          checkWin(p, ns);
          return ns;
        });
        setFeedback((f) => f + " · AI got it right 🤖");
      } else {
        setFeedback((f) => f + " · AI missed!");
      }
    }, aiDelay(age) + Math.random() * 1000);
  }, [age, checkWin, qIdx, questions]);

  const start = () => {
    if (aiTimer.current) clearTimeout(aiTimer.current);
    const qs = [...BANK[age]].sort(() => Math.random() - 0.5);
    setQuestions(qs);
    setQIdx(0); setPlayerScore(0); setAiScore(0);
    setWinner(null); setFeedback(""); answered.current = false;
    setPhase("playing"); setAiThinking(true);
    aiTimer.current = setTimeout(() => {
      setAiThinking(false);
      const q = qs[0];
      if (Math.random() < aiAccuracy(age)) {
        setAiScore(1);
        setFeedback("AI got the first one! 🤖");
      }
    }, aiDelay(age));
  };

  const pick = (idx: number) => {
    if (phase !== "playing" || answered.current) return;
    answered.current = true;
    const q = questions[qIdx % questions.length];
    if (!q) return;
    const correct = idx === q.answer;
    const p = correct ? playerScore + 1 : playerScore;
    if (correct) {
      setPlayerScore(p);
      setFeedback("You got it! ✓");
    } else {
      setFeedback(`Wrong — answer was "${q.options[q.answer]}"`);
    }
    setTimeout(() => nextQuestion(p, aiScore), 800);
  };

  useEffect(() => () => { if (aiTimer.current) clearTimeout(aiTimer.current); }, []);

  const q = questions[qIdx % questions.length];

  return (
    <main className="container" style={{ maxWidth: 680 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>⚔️ Quiz Duel</h1>
        <Link href="/arcade/challenge-ai" style={{ marginLeft: "auto" }}>← Challenge AI</Link>
      </div>
      <p className="muted">First to {WIN_TARGET} correct answers wins. The AI is thinking alongside you — beat it!</p>

      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        {(["kids", "tween", "teen", "adult"] as Age[]).map((a) => (
          <button key={a} onClick={() => setAge(a)} disabled={phase === "playing"}
            style={{ opacity: age === a ? 1 : 0.55 }}>{a}</button>
        ))}
      </div>

      {phase === "idle" && (
        <div style={{ textAlign: "center", padding: 32 }}>
          <button onClick={start} style={{ background: "#7c3aed", color: "#fff", padding: "14px 32px", fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer" }}>
            ▶ Challenge the AI
          </button>
        </div>
      )}

      {phase === "playing" && q && (
        <>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16, fontSize: 18, fontWeight: 700 }}>
            <span style={{ color: "#34d399" }}>You: {playerScore} / {WIN_TARGET}</span>
            <span style={{ color: aiThinking ? "#fbbf24" : "#f87171" }}>
              AI: {aiScore} / {WIN_TARGET} {aiThinking && "…thinking"}
            </span>
          </div>
          <div className="card">
            <h3>{q.prompt}</h3>
            <div style={{ display: "grid", gap: 10, marginTop: 16 }}>
              {q.options.map((opt, i) => (
                <button key={i} onClick={() => pick(i)} disabled={answered.current}
                  style={{ textAlign: "left", padding: "12px 16px", fontSize: 16, opacity: answered.current ? 0.6 : 1 }}>
                  {opt}
                </button>
              ))}
            </div>
            {feedback && <p style={{ marginTop: 12, color: "#94a3b8" }}>{feedback}</p>}
          </div>
        </>
      )}

      {phase === "done" && (
        <div className="card" style={{ textAlign: "center", padding: 32 }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>
            {winner === "player" ? "🎉" : winner === "ai" ? "🤖" : "🤝"}
          </div>
          <h2>{winner === "player" ? "You beat the AI!" : winner === "ai" ? "AI wins this round" : "It's a tie!"}</h2>
          <p className="muted">Final score — You: {playerScore} · AI: {aiScore}</p>
          <button onClick={start} style={{ marginTop: 16, background: "#7c3aed", color: "#fff", padding: "12px 28px", fontSize: 16, borderRadius: 10, border: 0, cursor: "pointer" }}>
            Rematch
          </button>
        </div>
      )}
    </main>
  );
}
