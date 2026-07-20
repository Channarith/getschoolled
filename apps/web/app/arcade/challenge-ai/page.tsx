"use client";

// Challenge the AI — hub consolidating every head-to-head arcade duel from the
// parallel agent branches (quiz, board games, math race, trading, geometry).

import Link from "next/link";
import { useState } from "react";

type Age = "kids" | "tween" | "teen" | "adult";

const CHALLENGES = [
  {
    href: "/arcade/challenge-ai/quiz-duel",
    icon: "⚔️",
    title: "Quiz Duel",
    desc: "Race the AI to answer questions correctly. First to 5 wins.",
    color: "#7c3aed",
  },
  {
    href: "/arcade/ai-duel",
    icon: "🧠",
    title: "AI Duel",
    desc: "Alternate head-to-head quiz race — same questions, faster answers win.",
    color: "#a855f7",
  },
  {
    href: "/arcade/challenge-ai/grid-master",
    icon: "🎯",
    title: "Grid Master",
    desc: "Tic-tac-toe vs AI with a question gate before each move.",
    color: "#0ea5e9",
  },
  {
    href: "/arcade/challenge-ai/tic-tac-toe",
    icon: "⭕",
    title: "Tic-Tac-Toe Duel",
    desc: "Classic X vs O. Hard mode uses full minimax — can you force a draw?",
    color: "#0284c7",
  },
  {
    href: "/arcade/challenge-ai/connect-four",
    icon: "🔴",
    title: "Connect Four",
    desc: "Drop discs against a depth-limited AI. Line up four to win.",
    color: "#dc2626",
  },
  {
    href: "/arcade/challenge-ai/number-duel",
    icon: "🔢",
    title: "Number Duel",
    desc: "Mental-math race — solve equations faster than the AI.",
    color: "#ea580c",
  },
  {
    href: "/arcade/market-moves?vs=ai",
    icon: "📈",
    title: "Market Moves vs AI",
    desc: "Grow your portfolio faster than the AI trader.",
    color: "#059669",
  },
  {
    href: "/arcade/stock-rush",
    icon: "💹",
    title: "Stock Rush",
    desc: "Trade a simulated stock against an AI investor under a timer.",
    color: "#10b981",
  },
  {
    href: "/arcade/shape-stack",
    icon: "📐",
    title: "Shape Stack",
    desc: "Tetris-style geometry — drop shapes into the correct answer column.",
    color: "#6366f1",
  },
  {
    href: "/arcade/cosmic-catch",
    icon: "🪐",
    title: "Cosmic Catch",
    desc: "Catch falling math answers. Beat your best — solo challenge mode.",
    color: "#9333ea",
    tag: "Solo challenge",
  },
];

export default function ChallengeAiHub() {
  const [age, setAge] = useState<Age>("teen");

  return (
    <main className="container" style={{ maxWidth: 960 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>🤖 Challenge the AI</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
      </div>
      <p className="muted">
        Think you can beat our AI instructor? Pick a duel below. Difficulty scales with age group —
        the AI gets sharper as you level up.
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

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 16 }}>
        {CHALLENGES.map((c) => {
          const sep = c.href.includes("?") ? "&" : "?";
          const href = `${c.href}${sep}age=${age}`;
          return (
            <Link key={c.href} href={href} style={{ textDecoration: "none", color: "inherit" }}>
              <div className="card" style={{
                height: "100%", borderLeft: `4px solid ${c.color}`,
                cursor: "pointer",
              }}>
                <div style={{ fontSize: 32, marginBottom: 8 }}>{c.icon}</div>
                <h3 style={{ margin: "0 0 8px" }}>{c.title}</h3>
                {c.tag && (
                  <span style={{ fontSize: 11, background: "#334155", padding: "2px 8px", borderRadius: 6 }}>
                    {c.tag}
                  </span>
                )}
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
          <li><strong>Quiz / AI Duel</strong> — age-scaled accuracy and human-like answer delay.</li>
          <li><strong>Grid / Tic-Tac-Toe</strong> — minimax (or depth-limited) board AI.</li>
          <li><strong>Connect Four</strong> — heuristic search that deepens with age group.</li>
          <li><strong>Number Duel</strong> — timed mental math against a paced AI solver.</li>
          <li><strong>Market / Stock Rush</strong> — parallel portfolio decisions vs the bot.</li>
        </ul>
      </div>
    </main>
  );
}
