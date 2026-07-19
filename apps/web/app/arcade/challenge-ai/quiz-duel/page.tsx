"use client";

// Quiz Duel — turn-based MCQ race against the AI. Eight rounds; fastest correct
// answer earns bonus points. Mix of geometry and investing questions.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  aiProfile, aiPickAnswer, aiThinkDelay, duelWinner, initDuel, scoreDuelRound, type DuelState,
} from "../../../lib/arcadeAi";
import { type ArcadeAge, financeQuestions, geometryQuestions, randomQuestion, type QuizQ } from "../../../lib/arcadeQuestions";

type SubjectMix = "mixed" | "geometry" | "investing";

export default function QuizDuel() {
  const [age, setAge] = useState<ArcadeAge>("teen");
  const [mix, setMix] = useState<SubjectMix>("mixed");
  const [duel, setDuel] = useState<DuelState | null>(null);
  const [question, setQuestion] = useState<QuizQ | null>(null);
  const [picked, setPicked] = useState<number | null>(null);
  const [aiPick, setAiPick] = useState<number | null>(null);
  const [aiThinking, setAiThinking] = useState(false);
  const [roundStart, setRoundStart] = useState(0);
  const [feedback, setFeedback] = useState("");
  const usedRef = useRef(new Set<string>());
  const scoredRoundRef = useRef(-1);
  const profile = aiProfile(age);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const a = q.get("age");
    if (a === "kids" || a === "tween" || a === "teen" || a === "adult") setAge(a);
    const s = q.get("subject");
    if (s === "geometry" || s === "investing" || s === "mixed") setMix(s);
  }, []);

  const nextQuestion = useCallback(() => {
    const geo = geometryQuestions(age);
    const fin = financeQuestions(age);
    let bank: QuizQ[];
    if (mix === "geometry") bank = geo;
    else if (mix === "investing") bank = fin;
    else bank = Math.random() < 0.5 ? geo : fin;
    const q = randomQuestion(bank, usedRef.current);
    setQuestion(q);
    setPicked(null);
    setAiPick(null);
    setAiThinking(true);
    setFeedback("");
    setRoundStart(Date.now());

    const delay = aiThinkDelay(profile);
    setTimeout(() => {
      const pick = aiPickAnswer(q.answerIndex, q.options.length, profile.accuracy);
      setAiPick(pick);
      setAiThinking(false);
    }, delay);
  }, [age, mix, profile]);

  const startDuel = useCallback(() => {
    usedRef.current = new Set();
    scoredRoundRef.current = -1;
    setDuel(initDuel(8));
    nextQuestion();
  }, [nextQuestion]);

  const pickAnswer = (idx: number) => {
    if (!duel || !question || picked !== null || duel.round >= duel.maxRounds) return;
    setPicked(idx);
  };

  // Score the round once both player and AI have answered.
  useEffect(() => {
    if (!duel || !question || picked === null || aiPick === null) return;
    if (duel.round >= duel.maxRounds) return;
    if (scoredRoundRef.current === duel.round) return;
    scoredRoundRef.current = duel.round;

    const playerCorrect = picked === question.answerIndex;
    const aiCorrect = aiPick === question.answerIndex;
    const elapsed = Date.now() - roundStart;
    const playerFast = playerCorrect && elapsed < 2500;
    const next = scoreDuelRound(duel, playerCorrect, aiCorrect, playerFast);
    setDuel(next);

    const parts: string[] = [];
    if (playerCorrect) parts.push(playerFast ? "Fast +15!" : "+10");
    else parts.push("Missed");
    if (aiCorrect) parts.push(`${profile.name} +10`);
    if (playerCorrect && !aiCorrect) parts.push("Beat AI +5");
    setFeedback(parts.join(" · "));

    const timer = setTimeout(() => {
      if (next.round >= next.maxRounds) return;
      nextQuestion();
    }, 1400);
    return () => clearTimeout(timer);
  }, [picked, aiPick, duel, question, roundStart, profile.name, nextQuestion]);

  const winner = duel ? duelWinner(duel) : null;
  const finished = duel !== null && duel.round >= duel.maxRounds;

  return (
    <main className="container" style={{ maxWidth: 640 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>⚔️ Quiz Duel</h1>
        <Link href="/arcade/challenge-ai" style={{ marginLeft: "auto" }}>← Challenge AI</Link>
      </div>
      <p className="muted">8-round head-to-head quiz. Answer correctly — faster than {profile.name} for bonus points.</p>

      {!duel && (
        <div className="card">
          <div className="muted" style={{ marginBottom: 8 }}>Age group</div>
          <div className="row" style={{ gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
            {(["kids", "tween", "teen", "adult"] as ArcadeAge[]).map((a) => (
              <button key={a} onClick={() => setAge(a)}
                style={{ opacity: age === a ? 1 : 0.55, background: age === a ? "#7c3aed" : undefined, color: age === a ? "#fff" : undefined }}>
                {a}
              </button>
            ))}
          </div>
          <div className="muted" style={{ marginBottom: 8 }}>Subject mix</div>
          <div className="row" style={{ gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
            {(["mixed", "geometry", "investing"] as SubjectMix[]).map((s) => (
              <button key={s} onClick={() => setMix(s)} style={{ opacity: mix === s ? 1 : 0.55 }}>{s}</button>
            ))}
          </div>
          <p className="muted" style={{ fontSize: 14 }}>Opponent: <strong>{profile.name}</strong> (~{Math.round(profile.accuracy * 100)}% accuracy)</p>
          <button onClick={startDuel} style={{ background: "#7c3aed", color: "#fff", padding: "12px 24px", marginTop: 8 }}>
            ▶ Start duel
          </button>
        </div>
      )}

      {duel && !finished && question && (
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between", marginBottom: 12 }}>
            <span>Round {duel.round + 1} / {duel.maxRounds}</span>
            <span style={{ fontWeight: 700 }}>You {duel.playerScore} — {profile.name} {duel.aiScore}</span>
          </div>
          <div style={{ fontWeight: 600, fontSize: 18, marginBottom: 16 }}>{question.prompt}</div>
          <div style={{ display: "grid", gap: 8 }}>
            {question.options.map((opt: string, idx: number) => {
              const playerChose = picked === idx;
              const aiChose = aiPick === idx;
              const isCorrect = idx === question.answerIndex;
              let border = "1px solid var(--border)";
              let bg = "transparent";
              if (picked !== null) {
                if (isCorrect) { border = "2px solid #16a34a"; bg = "#dcfce7"; }
                else if (playerChose) { border = "2px solid #dc2626"; bg = "#fee2e2"; }
              }
              return (
                <button key={idx} onClick={() => pickAnswer(idx)} disabled={picked !== null}
                  style={{ textAlign: "left", padding: "12px 16px", border, background: bg, borderRadius: 8 }}>
                  {opt}
                  {aiChose && <span style={{ marginLeft: 8, fontSize: 12, color: "#6366f1" }}>🤖 AI</span>}
                  {playerChose && <span style={{ marginLeft: 8, fontSize: 12, color: "#7c3aed" }}>You</span>}
                </button>
              );
            })}
          </div>
          {aiThinking && picked === null && (
            <p className="muted" style={{ marginTop: 12, fontSize: 14 }}>🤖 {profile.name} is thinking…</p>
          )}
          {feedback && <p style={{ marginTop: 12, fontWeight: 600, color: "#7c3aed" }}>{feedback}</p>}
        </div>
      )}

      {finished && duel && (
        <div className="card" style={{ borderColor: "#7c3aed", textAlign: "center" }}>
          <h2 style={{ marginTop: 0 }}>
            {winner === "player" && "🎉 You beat the AI!"}
            {winner === "ai" && `🤖 ${profile.name} wins!`}
            {winner === "tie" && "🤝 It's a tie!"}
          </h2>
          <div style={{ fontSize: 28, fontWeight: 700, margin: "16px 0" }}>
            {duel.playerScore} — {duel.aiScore}
          </div>
          <p className="muted">You {winner === "player" ? "outscored" : winner === "ai" ? "were outscored by" : "tied with"} {profile.name} over {duel.maxRounds} rounds.</p>
          <button onClick={startDuel} style={{ background: "#7c3aed", color: "#fff", padding: "10px 22px", marginTop: 8 }}>
            Rematch
          </button>
          <Link href="/arcade/challenge-ai" style={{ display: "block", marginTop: 12 }}>← More AI challenges</Link>
        </div>
      )}
    </main>
  );
}
