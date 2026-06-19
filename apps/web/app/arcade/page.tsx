"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  getGamesCatalog,
  getLeaderboard,
  getToken,
  newGame,
  submitGame,
  type GamesCatalog,
  type GameRound,
  type GameSubmit,
  type Leader,
} from "../lib/api";

const SUBJECT_ICON: Record<string, string> = {
  biology: "🧬", chemistry: "⚗️", physics: "🪐", math: "➗", science: "🔬",
  history: "🏛️", art: "🎨", technology: "💻", programming: "👾",
};

export default function ArcadePage() {
  const [cat, setCat] = useState<GamesCatalog | null>(null);
  const [subject, setSubject] = useState("biology");
  const [gameType, setGameType] = useState("quiz");
  const [round, setRound] = useState<GameRound | null>(null);
  const [answers, setAnswers] = useState<Record<string, number | string>>({});
  const [selTerm, setSelTerm] = useState<string>("");
  const [result, setResult] = useState<GameSubmit | null>(null);
  const [error, setError] = useState("");
  const [timeLeft, setTimeLeft] = useState(0);
  const [leaders, setLeaders] = useState<Leader[]>([]);
  const [lbSubject, setLbSubject] = useState<string>("");
  const startedAt = useRef(0);
  const loggedIn = typeof window !== "undefined" && Boolean(getToken());

  useEffect(() => { getGamesCatalog().then(setCat).catch((e) => setError(String(e))); }, []);

  const loadLeaders = useCallback(() => {
    getLeaderboard(lbSubject || undefined).then((r) => setLeaders(r.leaders)).catch(() => setLeaders([]));
  }, [lbSubject]);
  useEffect(() => { loadLeaders(); }, [loadLeaders]);

  const finish = useCallback(async () => {
    if (!round) return;
    if (!loggedIn) { setError("Sign in to submit your score and earn points."); return; }
    const elapsed = (Date.now() - startedAt.current) / 1000;
    try {
      const r = await submitGame(round.game_id, answers, elapsed);
      setResult(r);
      setRound(null);
      loadLeaders();
    } catch (e) { setError(String(e)); }
  }, [round, answers, loggedIn, loadLeaders]);

  // Speed-round countdown -> auto-submit at zero.
  useEffect(() => {
    if (!round || round.game_type !== "speed" || round.time_limit_s <= 0) return;
    if (timeLeft <= 0) { void finish(); return; }
    const t = setTimeout(() => setTimeLeft((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [round, timeLeft, finish]);

  async function play() {
    setError(""); setResult(null); setAnswers({}); setSelTerm("");
    try {
      const r = await newGame(subject, gameType, gameType === "match" ? 4 : 5);
      startedAt.current = Date.now();
      setTimeLeft(r.time_limit_s || 0);
      setRound(r);
    } catch (e) { setError(String(e)); }
  }

  function pickOption(itemId: string, idx: number) {
    setAnswers((a) => ({ ...a, [itemId]: idx }));
  }
  function pickMatch(optionId: string) {
    if (!selTerm) return;
    setAnswers((a) => ({ ...a, [selTerm]: optionId }));
    setSelTerm("");
  }

  return (
    <main className="container" style={{ maxWidth: 1000 }}>
      <h1>🎮 Learning Arcade</h1>
      <p className="muted">
        Learn by playing! Pick a subject and a game, earn points, and climb the
        leaderboard. Points feed your <Link href="/rewards">rewards</Link>.
        {!loggedIn && <> <Link href="/login">Sign in</Link> to save scores.</>}
      </p>

      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}

      {/* Picker */}
      {!round && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Choose your game</h3>
          <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
            {cat?.subjects.map((s) => (
              <button key={s} onClick={() => setSubject(s)}
                style={{ opacity: subject === s ? 1 : 0.55, fontSize: 14 }}>
                {SUBJECT_ICON[s] ?? "📘"} {s}
              </button>
            ))}
          </div>
          <div className="row" style={{ marginTop: 12, gap: 8, flexWrap: "wrap" }}>
            {cat?.game_types.map((g) => (
              <button key={g.id} onClick={() => setGameType(g.id)} title={g.desc}
                style={{ opacity: gameType === g.id ? 1 : 0.55 }}>
                {g.name}
              </button>
            ))}
          </div>
          <div style={{ marginTop: 14 }}>
            <button onClick={play} style={{ background: "#7c3aed", color: "#fff", padding: "10px 22px" }}>
              ▶ Play {subject} · {gameType}
            </button>
          </div>
        </div>
      )}

      {/* Quiz / Speed */}
      {round && round.items && (
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h3 style={{ margin: 0 }}>{SUBJECT_ICON[round.subject]} {round.subject} · {round.game_type}</h3>
            {round.game_type === "speed" && (
              <span style={{ fontWeight: 700, color: timeLeft <= 10 ? "#e11d48" : "#16a34a" }}>⏱ {timeLeft}s</span>
            )}
          </div>
          {round.items.map((it, qi) => (
            <div key={it.id} style={{ margin: "12px 0" }}>
              <div style={{ fontWeight: 600 }}>{qi + 1}. {it.prompt}</div>
              <div className="row" style={{ flexWrap: "wrap", gap: 8, marginTop: 6 }}>
                {it.options.map((opt, idx) => (
                  <button key={idx} onClick={() => pickOption(it.id, idx)}
                    style={{
                      border: answers[it.id] === idx ? "2px solid #7c3aed" : "1px solid var(--border)",
                      background: answers[it.id] === idx ? "#ede9fe" : "transparent",
                      color: answers[it.id] === idx ? "#4c1d95" : "var(--text)",
                    }}>
                    {opt}
                  </button>
                ))}
              </div>
            </div>
          ))}
          <button onClick={finish} style={{ marginTop: 8, background: "#16a34a", color: "#fff" }}>Submit</button>
        </div>
      )}

      {/* Match */}
      {round && round.terms && round.options && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>{SUBJECT_ICON[round.subject]} {round.subject} · match</h3>
          <p className="muted">Click a term, then its matching definition.</p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div>
              {round.terms.map((t) => (
                <button key={t.id} onClick={() => setSelTerm(t.id)}
                  style={{ display: "block", width: "100%", marginBottom: 8, textAlign: "left",
                    border: selTerm === t.id ? "2px solid #7c3aed" : "1px solid var(--border)",
                    background: answers[t.id] ? "#dcfce7" : "transparent" }}>
                  {t.term} {answers[t.id] ? "✓" : ""}
                </button>
              ))}
            </div>
            <div>
              {round.options.map((o) => {
                const taken = Object.values(answers).includes(o.id);
                return (
                  <button key={o.id} onClick={() => pickMatch(o.id)} disabled={!selTerm}
                    style={{ display: "block", width: "100%", marginBottom: 8, textAlign: "left",
                      opacity: taken ? 0.5 : 1, border: "1px solid var(--border)", background: "transparent" }}>
                    {o.text}
                  </button>
                );
              })}
            </div>
          </div>
          <button onClick={finish} style={{ marginTop: 12, background: "#16a34a", color: "#fff" }}>Submit</button>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="card" style={{ borderColor: "#7c3aed" }}>
          <h3 style={{ marginTop: 0 }}>Score: {result.result.correct}/{result.result.total} · +{result.points_earned} pts 🎉</h3>
          <div className="muted">
            accuracy {Math.round(result.result.accuracy * 100)}%
            {result.result.speed_bonus > 0 && ` · speed bonus +${result.result.speed_bonus}`}
            {result.result.accuracy_bonus > 0 && ` · perfect +${result.result.accuracy_bonus}`}
            {" · "}balance {result.balance} pts
            {result.rank && ` · global rank #${result.rank}`}
          </div>
          <ul style={{ marginTop: 8 }}>
            {result.result.results.map((r) => (
              <li key={r.id} style={{ color: r.correct ? "#16a34a" : "#b00", fontSize: 13 }}>
                {r.correct ? "✓" : "✗"} {r.explain}
              </li>
            ))}
          </ul>
          <button onClick={() => setResult(null)} style={{ background: "#7c3aed", color: "#fff" }}>Play again</button>
        </div>
      )}

      {/* Leaderboard */}
      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h3 style={{ margin: 0 }}>🏆 Top players</h3>
          <select value={lbSubject} onChange={(e) => setLbSubject(e.target.value)}>
            <option value="">Overall</option>
            {cat?.subjects.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        {leaders.length === 0 ? (
          <p className="muted">No scores yet — be the first to play!</p>
        ) : (
          <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 14, marginTop: 8 }}>
            <thead><tr style={{ textAlign: "left", background: "#f7f7f7" }}>
              <th style={{ padding: 6 }}>#</th><th style={{ padding: 6 }}>Player</th>
              <th style={{ padding: 6 }}>{lbSubject ? "Best" : "Points"}</th><th style={{ padding: 6 }}>Games</th>
            </tr></thead>
            <tbody>
              {leaders.map((l) => (
                <tr key={l.rank} style={{ borderTop: "1px solid #eee" }}>
                  <td style={{ padding: 6 }}>{l.rank === 1 ? "🥇" : l.rank === 2 ? "🥈" : l.rank === 3 ? "🥉" : l.rank}</td>
                  <td style={{ padding: 6 }}>{l.name}</td>
                  <td style={{ padding: 6 }}>{l.score}</td>
                  <td style={{ padding: 6 }}>{l.games_played}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </main>
  );
}
