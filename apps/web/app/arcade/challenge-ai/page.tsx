"use client";

// Challenge the AI — hub for head-to-head arcade games. Pick a mode and see
// if you can beat the bot. Difficulty scales with age group.

import Link from "next/link";
import { useState } from "react";

import { aiProfile } from "../../lib/arcadeAi";
import type { ArcadeAge } from "../../lib/arcadeQuestions";

const GAMES = [
  {
    id: "quiz-duel",
    href: (age: string) => `/arcade/challenge-ai/quiz-duel?age=${age}`,
    icon: "⚔️",
    title: "Quiz Duel",
    desc: "8 rounds of rapid-fire MCQ. Answer faster than the AI for bonus points.",
    color: "#7c3aed",
  },
  {
    id: "geometry-blocks",
    href: (age: string) => `/arcade/geometry-blocks?age=${age}&ai=1`,
    icon: "📐",
    title: "Geometry Blocks vs AI",
    desc: "Tetris-style geometry quiz — race the AI to clear answer rows.",
    color: "#6366f1",
  },
  {
    id: "market-catch",
    href: (age: string) => `/arcade/market-catch?age=${age}&ai=1`,
    icon: "📈",
    title: "Market Catch vs AI",
    desc: "Catch investing answers before the AI portfolio does.",
    color: "#16a34a",
  },
  {
    id: "cosmic-catch",
    href: (age: string) => `/arcade/cosmic-catch?age=${age}`,
    icon: "🪐",
    title: "Cosmic Catch",
    desc: "Solo math arcade — practice speed for your next AI duel.",
    color: "#0ea5e9",
  },
];

export default function ChallengeAiHub() {
  const [age, setAge] = useState<ArcadeAge>("teen");
  const profile = aiProfile(age);

  return (
    <main className="container" style={{ maxWidth: 900 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>🤖 Challenge the AI</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
      </div>
      <p className="muted">
        Think you can beat the bot? Pick your age group, choose a game, and go head-to-head.
        The AI gets smarter as you level up — can you outscore it?
      </p>

      <div className="card" style={{ background: "linear-gradient(135deg, rgba(99,102,241,0.15), rgba(124,58,237,0.12))" }}>
        <h3 style={{ marginTop: 0 }}>Your opponent</h3>
        <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
          <div style={{
            width: 64, height: 64, borderRadius: "50%", background: "#4f46e5",
            display: "flex", alignItems: "center", justifyContent: "center", fontSize: 28,
          }}>🤖</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 18 }}>{profile.name}</div>
            <div className="muted" style={{ fontSize: 14 }}>
              Accuracy ~{Math.round(profile.accuracy * 100)}% · reacts in ~{(profile.thinkMs / 1000).toFixed(1)}s
            </div>
          </div>
          <div style={{ marginLeft: "auto" }}>
            <span className="muted" style={{ marginRight: 8 }}>Age:</span>
            {(["kids", "tween", "teen", "adult"] as ArcadeAge[]).map((a) => (
              <button key={a} onClick={() => setAge(a)}
                style={{
                  opacity: age === a ? 1 : 0.55, marginRight: 4,
                  background: age === a ? "#4f46e5" : undefined,
                  color: age === a ? "#fff" : undefined,
                }}>{a}</button>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 14, marginTop: 16 }}>
        {GAMES.map((g) => (
          <Link key={g.id} href={g.href(age)} className="card" style={{
            textDecoration: "none", color: "inherit", borderLeft: `4px solid ${g.color}`,
            transition: "transform 0.15s",
          }}>
            <div style={{ fontSize: 28 }}>{g.icon}</div>
            <h3 style={{ margin: "8px 0 4px" }}>{g.title}</h3>
            <p className="muted" style={{ margin: 0, fontSize: 14 }}>{g.desc}</p>
            <div style={{ marginTop: 12, color: g.color, fontWeight: 600, fontSize: 14 }}>
              Play vs {profile.name} →
            </div>
          </Link>
        ))}
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>How scoring works</h3>
        <ul className="muted" style={{ margin: 0, paddingLeft: 20, fontSize: 14 }}>
          <li>Correct answer: +10 points (Quiz Duel: +15 if you beat the AI to it)</li>
          <li>Beat the AI on a round: +5 bonus</li>
          <li>AI scores when it answers correctly — outscore it to win</li>
          <li>Higher age groups face tougher opponents with better accuracy</li>
        </ul>
      </div>
    </main>
  );
}
