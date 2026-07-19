"use client";

// Challenge the AI — a hub of head-to-head games where you try to beat a computer
// opponent whose skill scales with the chosen difficulty. Each game is a real,
// self-contained match (no backend). "Can you beat the AI?"

import Link from "next/link";

const GAMES = [
  {
    href: "/arcade/challenge-ai/tic-tac-toe",
    icon: "❌⭕",
    name: "Tic-Tac-Toe Duel",
    desc: "Classic 3×3. On Hard the AI plays a perfect game — the best you can do is force a draw.",
    color: "#7c3aed",
  },
  {
    href: "/arcade/challenge-ai/connect-four",
    icon: "🔴🟡",
    name: "Connect Four Duel",
    desc: "Drop discs to line up four. The AI looks moves ahead with alpha-beta search.",
    color: "#0ea5e9",
  },
  {
    href: "/arcade/challenge-ai/number-duel",
    icon: "⚡➗",
    name: "Number Duel",
    desc: "A mental-math race. Answer before the AI buzzes in. Faster, sharper AI at higher levels.",
    color: "#f59e0b",
  },
];

export default function ChallengeAIHub() {
  return (
    <main style={{ maxWidth: 820, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>🤖 Challenge the AI</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
        <Link href="/rewards">Rewards</Link>
      </div>
      <p className="muted">
        Go head-to-head with a computer opponent. Pick a game and a difficulty, then
        see if you can beat the AI.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 14, marginTop: 12 }}>
        {GAMES.map((g) => (
          <Link key={g.href} href={g.href} style={{ textDecoration: "none" }}>
            <div className="card" style={{ height: "100%", borderTop: `4px solid ${g.color}` }}>
              <div style={{ fontSize: 30 }}>{g.icon}</div>
              <h3 style={{ margin: "8px 0 4px" }}>{g.name}</h3>
              <p className="muted" style={{ margin: 0, fontSize: 14 }}>{g.desc}</p>
              <div style={{ marginTop: 12, color: g.color, fontWeight: 700 }}>Play →</div>
            </div>
          </Link>
        ))}
      </div>
    </main>
  );
}
