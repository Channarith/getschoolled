"use client";

// Challenge the AI — hub for arcade games where you compete against an AI opponent.
// Each game scales AI difficulty by age group; beat the AI to earn bragging rights.

import Link from "next/link";
import { useState } from "react";

type Age = "kids" | "tween" | "teen" | "adult";

const CHALLENGES = [
  {
    href: "/arcade/challenge-ai/quiz-duel",
    icon: "⚔️",
    title: "Quiz Duel",
    desc: "Race the AI to answer questions correctly. First to 5 wins — can you outsmart it?",
    color: "#7c3aed",
  },
  {
    href: "/arcade/challenge-ai/grid-master",
    icon: "🎯",
    title: "Grid Master",
    desc: "Tic-tac-toe vs AI. Answer a quick question before each move — wrong answers let the AI strike.",
    color: "#0ea5e9",
  },
  {
    href: "/arcade/shape-stack",
    icon: "📐",
    title: "Shape Stack",
    desc: "Tetris-style geometry quiz. Drop shapes into the correct answer column before they land.",
    color: "#6366f1",
  },
  {
    href: "/arcade/market-moves?vs=ai",
    icon: "📈",
    title: "Market Moves vs AI",
    desc: "Stock-trading scenarios — grow your portfolio faster than the AI trader.",
    color: "#059669",
  },
  {
    href: "/arcade/cosmic-catch",
    icon: "🪐",
    title: "Cosmic Catch",
    desc: "Catch falling math answers. Beat your high score — the AI watches and learns your patterns.",
    color: "#9333ea",
    tag: "Solo challenge",
  },
];

export default function ChallengeAiHub() {
  const [age, setAge] = useState<Age>("teen");

  return (
    <main className="container" style={{ maxWidth: 900 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>🤖 Challenge the AI</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
      </div>
      <p className="muted">
        Think you can beat our AI instructor? Pick a challenge below. Difficulty scales with age group —
        the AI gets smarter as you level up. Win to climb the leaderboard and earn bragging rights.
      </p>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="muted" style={{ fontSize: 13, marginBottom: 8 }}>Your age group (sets AI difficulty)</div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {(["kids", "tween", "teen", "adult"] as Age[]).map((a) => (
            <button key={a} onClick={() => setAge(a)}
              style={{
                opacity: age === a ? 1 : 0.55,
                background: age === a ? "#7c3aed" : undefined,
                color: age === a ? "#fff" : undefined,
              }}>
              {a}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
        {CHALLENGES.map((c) => {
          const sep = c.href.includes("?") ? "&" : "?";
          const href = `${c.href}${sep}age=${age}`;
          return (
            <Link key={c.href} href={href} style={{ textDecoration: "none", color: "inherit" }}>
              <div className="card" style={{
                height: "100%", borderLeft: `4px solid ${c.color}`,
                transition: "transform 0.15s", cursor: "pointer",
              }}>
                <div style={{ fontSize: 32, marginBottom: 8 }}>{c.icon}</div>
                <h3 style={{ margin: "0 0 8px" }}>{c.title}</h3>
                {c.tag && <span style={{ fontSize: 11, background: "#334155", padding: "2px 8px", borderRadius: 6 }}>{c.tag}</span>}
                <p className="muted" style={{ marginTop: 8, fontSize: 14 }}>{c.desc}</p>
                <div style={{ marginTop: 12, color: c.color, fontWeight: 600 }}>Play →</div>
              </div>
            </Link>
          );
        })}
      </div>

      <div className="card" style={{ marginTop: 24, background: "linear-gradient(135deg, rgba(124,58,237,0.12), rgba(14,165,233,0.08))" }}>
        <h3 style={{ marginTop: 0 }}>How AI opponents work</h3>
        <ul className="muted" style={{ margin: 0, paddingLeft: 20, lineHeight: 1.7 }}>
          <li><strong>Quiz Duel</strong> — AI answers with human-like delay; accuracy scales 55% (kids) → 88% (adult).</li>
          <li><strong>Grid Master</strong> — Minimax tic-tac-toe AI; you must pass a question gate before each move.</li>
          <li><strong>Market Moves</strong> — AI makes parallel buy/hold/sell decisions; highest portfolio wins.</li>
          <li>All challenges store your best scores locally and sync to the rewards leaderboard when signed in.</li>
        </ul>
      </div>
    </main>
  );
}
