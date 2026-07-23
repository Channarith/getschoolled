"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
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
import { useT } from "../lib/i18n";

const SUBJECT_ICON: Record<string, string> = {
  biology: "🧬", chemistry: "⚗️", physics: "🪐", math: "➗", science: "🔬",
  history: "🏛️", art: "🎨", technology: "💻", programming: "👾",
  life_growth: "🌱", etiquette: "🤝", wordplay: "🔤", geometry: "📐",
  creation: "🛠️", farming: "🌾", finance: "📈", workplace: "💼",
};

const KIND_BADGE: Record<string, string> = {
  tiles: "🍌", resource: "⚖️", dependency: "🔗", rpg: "🎭", cartoon: "📺",
  idiom: "💬", create: "✨", doing: "🙌", farm: "🚜", spelling: "✏️", geometry: "📐",
  shape_drop: "🧱", stocks: "📈", challenge: "🤖", scenario: "💼",
};

const DEFAULT_AGE_GROUPS = [
  { id: "kids",  name: "Kids",   range: "5–8"  },
  { id: "tween", name: "Tweens", range: "9–12" },
  { id: "teen",  name: "Teens",  range: "13–17"},
  { id: "adult", name: "Adults", range: "18+"  },
];

function subjectLabel(cat: GamesCatalog | null, id: string): string {
  const loc = cat?.subjects_localized?.find((s) => s.id === id);
  return loc?.name ?? id.replace(/_/g, " ");
}

export default function ArcadePage() {
  const { t, locale } = useT();
  const router = useRouter();
  const [cat, setCat] = useState<GamesCatalog | null>(null);
  const [subject, setSubject] = useState("biology");
  const [gameType, setGameType] = useState("quiz");
  const [ageGroup, setAgeGroup] = useState("teen");
  const [round, setRound] = useState<GameRound | null>(null);
  const [answers, setAnswers] = useState<Record<string, number | string>>({});
  const [selTerm, setSelTerm] = useState<string>("");
  const [result, setResult] = useState<GameSubmit | null>(null);
  const [error, setError] = useState("");
  const [timeLeft, setTimeLeft] = useState(0);
  const [leaders, setLeaders] = useState<Leader[]>([]);
  const [lbSubject, setLbSubject] = useState<string>("");
  const [loggedIn, setLoggedIn] = useState(false);
  const startedAt = useRef(0);

  // Read auth on the client only (avoids SSR/client hydration mismatch).
  useEffect(() => { setLoggedIn(Boolean(getToken())); }, []);
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const s = q.get("subject");
    const g = q.get("game");
    const a = q.get("age");
    if (s) setSubject(s);
    if (g) setGameType(g);
    if (a === "kids" || a === "tween" || a === "teen" || a === "adult") setAgeGroup(a);
  }, []);
  useEffect(() => {
    getGamesCatalog(locale).then(setCat).catch((e) => setError(String(e)));
  }, [locale]);

  const [lbAge, setLbAge] = useState<string>("");
  const loadLeaders = useCallback(() => {
    getLeaderboard(lbSubject || undefined, lbAge || undefined)
      .then((r) => setLeaders(r.leaders)).catch(() => setLeaders([]));
  }, [lbSubject, lbAge]);
  useEffect(() => { loadLeaders(); }, [loadLeaders]);

  // Sync the leaderboard age filter with the picker age group so the
  // leaderboard visibly responds when the user switches age group.
  useEffect(() => { setLbAge(ageGroup); }, [ageGroup]);

  const finish = useCallback(async () => {
    if (!round) return;
    if (!loggedIn) { setError(t("arcade.signInSubmit")); return; }
    const elapsed = (Date.now() - startedAt.current) / 1000;
    try {
      const r = await submitGame(round.game_id, answers, elapsed);
      setResult(r);
      setRound(null);
      loadLeaders();
    } catch (e) {
      const msg = String(e);
      if (msg.includes("404") || msg.includes("unknown or expired")) {
        setError(t("arcade.sessionExpired"));
        setRound(null);
      } else {
        setError(msg);
      }
    }
  }, [round, answers, loggedIn, loadLeaders, t]);

  // Timed modes: speed + marathon + challenge countdown -> auto-submit at zero.
  useEffect(() => {
    const timed = round && (round.game_type === "speed" || round.game_type === "marathon" || round.game_type === "challenge");
    if (!timed || round!.time_limit_s <= 0) return;
    if (timeLeft <= 0) { void finish(); return; }
    const timer = setTimeout(() => setTimeLeft((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [round, timeLeft, finish]);

  async function play() {
    // Potion Lab is a real-time arcade game (its own page); launch it with the
    // chosen age group so difficulty scales (kids = slow/simple, adults = fast/complex).
    if (subject === "chemistry" && gameType === "potion") {
      router.push(`/arcade/chemistry?age=${ageGroup}`);
      return;
    }
    if (gameType === "shape_drop") {
      router.push(`/arcade/shape-drop?age=${ageGroup}`);
      return;
    }
    if (gameType === "stocks") {
      router.push(`/arcade/stocks?age=${ageGroup}`);
      return;
    }
    if (gameType === "challenge") {
      router.push(`/arcade/challenge-ai?age=${ageGroup}`);
      return;
    }
    setError(""); setResult(null); setAnswers({}); setSelTerm("");
    try {
      const n = gameType === "marathon" ? 20 : gameType === "match" ? 8 : gameType === "challenge" ? 8 : 12;
      const r = await newGame(subject, gameType, ageGroup, n);
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
      <h1>{t("arcade.title")}</h1>
      <p className="muted">
        {t("arcade.intro")}{" "}
        <Link href="/rewards">{t("arcade.rewardsLink")}</Link>.
        {!loggedIn && <> <Link href="/login">{t("profile.signIn")}</Link> {t("arcade.signInSave")}</>}
      </p>

      {/* ── Salareen Worlds hero banner ─────────────────────────────────────── */}
      {!round && (
        <div style={{
          position: "relative",
          borderRadius: 20,
          overflow: "hidden",
          marginBottom: 28,
          minHeight: 260,
          background: "linear-gradient(135deg, #0f0c29 0%, #302b63 45%, #24243e 100%)",
          boxShadow: "0 12px 48px rgba(0,0,0,0.45)",
        }}>
          {/* Starfield overlay */}
          <div style={{
            position: "absolute", inset: 0,
            backgroundImage: "radial-gradient(circle at 20% 30%, rgba(124,58,237,0.35) 0%, transparent 55%), radial-gradient(circle at 80% 70%, rgba(34,211,238,0.25) 0%, transparent 55%), radial-gradient(white 1px, transparent 1px)",
            backgroundSize: "100% 100%, 100% 100%, 40px 40px",
            opacity: 0.8,
          }} aria-hidden />
          {/* Glowing planet */}
          <div style={{
            position: "absolute", right: 40, top: "50%", transform: "translateY(-50%)",
            width: 180, height: 180, borderRadius: "50%",
            background: "radial-gradient(circle at 38% 38%, #4ade80 0%, #16a34a 40%, #14532d 80%, #052e16 100%)",
            boxShadow: "0 0 60px 20px rgba(74,222,128,0.35), 0 0 120px 40px rgba(22,163,74,0.2)",
            opacity: 0.9,
          }} aria-hidden />
          {/* Ring */}
          <div style={{
            position: "absolute", right: -10, top: "50%", transform: "translateY(-50%) rotate(-20deg)",
            width: 260, height: 60, borderRadius: "50%",
            border: "12px solid rgba(167,243,208,0.3)",
            boxShadow: "0 0 20px rgba(167,243,208,0.2)",
            pointerEvents: "none",
          }} aria-hidden />
          {/* Text content */}
          <div style={{ position: "relative", padding: "36px 40px", maxWidth: 560, zIndex: 1 }}>
            <div style={{ display: "inline-block", background: "rgba(124,58,237,0.7)", color: "#e9d5ff", borderRadius: 20, padding: "3px 12px", fontSize: 12, fontWeight: 700, letterSpacing: 1, marginBottom: 12 }}>
              ✨ FEATURED · 3D OPEN WORLD
            </div>
            <h2 style={{ margin: "0 0 10px", color: "#fff", fontSize: 34, fontWeight: 900, lineHeight: 1.1, textShadow: "0 2px 12px rgba(0,0,0,0.6)" }}>
              🌍 Salareen Worlds
            </h2>
            <p style={{ margin: "0 0 20px", color: "rgba(255,255,255,0.8)", fontSize: 15, lineHeight: 1.6 }}>
              A 3D open-world educational RPG. Explore two planets, battle enemies, ride mounts, craft items, and answer trivia to earn XP — with an AI opponent to race against. Math, science, geography, history, biology, and more.
            </p>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <Link href="/worlds" style={{
                display: "inline-block", padding: "13px 28px", borderRadius: 12,
                background: "linear-gradient(135deg, #7c3aed, #4f46e5)",
                color: "#fff", fontWeight: 800, fontSize: 16, textDecoration: "none",
                boxShadow: "0 4px 16px rgba(124,58,237,0.5)",
              }}>
                ▶ Play Now
              </Link>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 8, color: "rgba(255,255,255,0.6)", fontSize: 13 }}>
                🎮 WASD to move · E to interact · Space to jump · B to build
              </span>
            </div>
          </div>
        </div>
      )}

      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}

      {/* ── Salareen Worlds hero banner ─────────────────────────────── */}
      {!round && (
        <div style={{
          position: 'relative', borderRadius: 20, overflow: 'hidden',
          marginBottom: 28, minHeight: 240,
          background: 'linear-gradient(135deg, #0f0c29 0%, #302b63 45%, #24243e 100%)',
          boxShadow: '0 8px 40px rgba(0,0,0,0.4)',
        }}>
          <div style={{ position: 'absolute', inset: 0,
            backgroundImage: 'radial-gradient(circle at 20% 30%, rgba(124,58,237,0.35) 0%, transparent 55%), radial-gradient(white 1px, transparent 1px)',
            backgroundSize: '100% 100%, 40px 40px', opacity: 0.6 }} aria-hidden />
          <div style={{ position: 'absolute', right: 40, top: '50%', transform: 'translateY(-50%)',
            width: 160, height: 160, borderRadius: '50%',
            background: 'radial-gradient(circle at 38% 38%, #4ade80 0%, #16a34a 40%, #14532d 80%, #052e16 100%)',
            boxShadow: '0 0 60px 20px rgba(74,222,128,0.3)', opacity: 0.85 }} aria-hidden />
          <div style={{ position: 'relative', padding: '32px 36px', maxWidth: 560, zIndex: 1 }}>
            <div style={{ display: 'inline-block', background: 'rgba(124,58,237,0.7)', color: '#e9d5ff',
              borderRadius: 20, padding: '3px 12px', fontSize: 12, fontWeight: 700, letterSpacing: 1, marginBottom: 10 }}>
              ✨ FEATURED · 3D OPEN WORLD
            </div>
            <h2 style={{ margin: '0 0 8px', color: '#fff', fontSize: 30, fontWeight: 900, lineHeight: 1.15 }}>
              🌍 Salareen Worlds
            </h2>
            <p style={{ margin: '0 0 18px', color: 'rgba(255,255,255,0.8)', fontSize: 14, lineHeight: 1.6 }}>
              3D open-world RPG — explore planets, answer trivia, race an AI opponent. Math, science, geography, history &amp; more.
            </p>
            <Link href="/worlds" style={{ display: 'inline-block', padding: '12px 26px', borderRadius: 12,
              background: 'linear-gradient(135deg, #7c3aed, #4f46e5)', color: '#fff',
              fontWeight: 800, fontSize: 15, textDecoration: 'none',
              boxShadow: '0 4px 16px rgba(124,58,237,0.5)' }}>
              ▶ Play Now
            </Link>
          </div>
        </div>
      )}


      {/* Professional scenario drills */}
      {!round && (
        <div className="card" style={{ background: "linear-gradient(135deg, rgba(67,56,202,0.18), rgba(99,102,241,0.1))" }}>
          <h3 style={{ marginTop: 0 }}>💼 Professional scenarios</h3>
          <p className="muted" style={{ marginTop: 0 }}>
            &quot;What would you do?&quot; drills for corporate courses — compliance, safety, privacy, ethics, and more.
          </p>
          <div className="row" style={{ flexWrap: "wrap", gap: 10 }}>
            <Link href="/arcade/pro-scenarios"
              style={{ padding: "10px 16px", borderRadius: 10, background: "#4338ca", color: "#fff", fontWeight: 700 }}>
              🎯 What Would You Do?
            </Link>
            <Link href={`/arcade?subject=workplace&game=scenario&age=${ageGroup}`}
              style={{ padding: "10px 16px", borderRadius: 10, background: "#6366f1", color: "#fff", fontWeight: 600 }}>
              💼 Scenario quiz (arcade)
            </Link>
            <Link href="/corporate"
              style={{ padding: "10px 16px", borderRadius: 10, background: "#312e81", color: "#fff", fontWeight: 600 }}>
              📚 Corporate courses
            </Link>
          </div>
        </div>
      )}

      {/* Kids' Games — fun, colorful learning adventures. */}
      {!round && (
        <div className="card" style={{ background: "linear-gradient(135deg, rgba(249,168,37,0.18), rgba(236,72,153,0.12))" }}>
          <h3 style={{ marginTop: 0 }}>🎮 Kids&apos; Games</h3>
          <p className="muted" style={{ marginTop: 0 }}>Jeopardy, kart racing, creature catching, card matching, and Uno — education wrapped in fun.</p>
          <div className="row" style={{ flexWrap: "wrap", gap: 10 }}>
            <Link href={`/arcade/jeopardy?age=${ageGroup}`}
              style={{ padding: "10px 16px", borderRadius: 10, background: "#1e3a8a", color: "#fbbf24", fontWeight: 700 }}>
              📺 Jeopardy!
            </Link>
            <Link href={`/arcade/kart-race?age=${ageGroup}`}
              style={{ padding: "10px 16px", borderRadius: 10, background: "#dc2626", color: "#fff", fontWeight: 700 }}>
              🏎️ Kart Race
            </Link>
            <Link href={`/arcade/creature-catch?age=${ageGroup}`}
              style={{ padding: "10px 16px", borderRadius: 10, background: "#7c3aed", color: "#fff", fontWeight: 700 }}>
              🦊 Creature Catch
            </Link>
            <Link href={`/arcade/card-match?age=${ageGroup}`}
              style={{ padding: "10px 16px", borderRadius: 10, background: "#0f766e", color: "#fff", fontWeight: 700 }}>
              🃏 Card Match
            </Link>
            <Link href={`/arcade/uno-quiz?age=${ageGroup}`}
              style={{ padding: "10px 16px", borderRadius: 10, background: "#b91c1c", color: "#fff", fontWeight: 700 }}>
              🎴 Uno Quiz
            </Link>
          </div>
        </div>
      )}

      {/* Discovery Games */}
      {!round && (
        <div className="card" style={{ background: "linear-gradient(135deg, rgba(16,185,129,0.18), rgba(139,92,246,0.12))" }}>
          <h3 style={{ marginTop: 0 }}>🔍 Discovery Games</h3>
          <p className="muted" style={{ marginTop: 0 }}>Spot differences, find hidden items, and reveal stunning artwork by answering questions.</p>
          <div className="row" style={{ flexWrap: "wrap", gap: 10 }}>
            <Link href={`/arcade/spot-difference?age=${ageGroup}`} style={{ padding: "10px 16px", borderRadius: 10, background: "#0891b2", color: "#fff", fontWeight: 700 }}>
              🔍 Spot the Difference
            </Link>
            <Link href={`/arcade/hidden-items?age=${ageGroup}`} style={{ padding: "10px 16px", borderRadius: 10, background: "#7c3aed", color: "#fff", fontWeight: 700 }}>
              🕵️ Find the Hidden Items
            </Link>
            <Link href={`/arcade/photo-reveal?age=${ageGroup}`} style={{ padding: "10px 16px", borderRadius: 10, background: "#059669", color: "#fff", fontWeight: 700 }}>
              🖼️ Photo Reveal
            </Link>
          </div>
        </div>
      )}

      {/* Zoo & Reef — memorize animal and fish species. */}
      {!round && (
        <div className="card" style={{ background: "linear-gradient(135deg, rgba(180,83,9,0.18), rgba(8,145,178,0.14))" }}>
          <h3 style={{ marginTop: 0 }}>🦁 Zoo & Reef</h3>
          <p className="muted" style={{ marginTop: 0 }}>Memorize animal and fish species — build your field guide and reef journal.</p>
          <div className="row" style={{ flexWrap: "wrap", gap: 10 }}>
            <Link href={`/arcade/zoo-safari?age=${ageGroup}`}
              style={{ padding: "10px 16px", borderRadius: 10, background: "#b45309", color: "#fff", fontWeight: 700 }}>
              🦁 Zoo Safari
            </Link>
            <Link href={`/arcade/reef-quest?age=${ageGroup}`}
              style={{ padding: "10px 16px", borderRadius: 10, background: "#0891b2", color: "#fff", fontWeight: 700 }}>
              🐠 Reef Quest
            </Link>
            <Link href={`/arcade/species-match?age=${ageGroup}`}
              style={{ padding: "10px 16px", borderRadius: 10, background: "#059669", color: "#fff", fontWeight: 700 }}>
              🃏 Species Match
            </Link>
          </div>
        </div>
      )}

      {/* Featured graphics-engine games (2D canvas + 3D WebGL). */}
      {!round && (
        <>
          <div className="card" style={{ background: "linear-gradient(135deg, rgba(124,58,237,0.22), rgba(239,68,68,0.1))" }}>
            <h3 style={{ marginTop: 0 }}>🤖 Challenge the AI</h3>
            <p className="muted" style={{ marginTop: 0 }}>Quiz duels, board games, number races, and trading showdowns vs the bot.</p>
            <div className="row" style={{ flexWrap: "wrap", gap: 10 }}>
              <Link href={`/arcade/challenge-ai?age=${ageGroup}`}
                style={{ padding: "10px 16px", borderRadius: 10, background: "#dc2626", color: "#fff", fontWeight: 600 }}>
                🤖 Challenge the AI hub
              </Link>
              <Link href={`/arcade/challenge-ai/quiz-duel?age=${ageGroup}`}
                style={{ padding: "10px 16px", borderRadius: 10, background: "#7c3aed", color: "#fff", fontWeight: 600 }}>
                ⚔️ Quiz Duel
              </Link>
              <Link href={`/arcade/challenge-ai/tic-tac-toe?age=${ageGroup}`}
                style={{ padding: "10px 16px", borderRadius: 10, background: "#0284c7", color: "#fff", fontWeight: 600 }}>
                ⭕ Tic-Tac-Toe
              </Link>
              <Link href={`/arcade/challenge-ai/connect-four?age=${ageGroup}`}
                style={{ padding: "10px 16px", borderRadius: 10, background: "#b91c1c", color: "#fff", fontWeight: 600 }}>
                🔴 Connect Four
              </Link>
              <Link href={`/arcade/challenge-ai/number-duel?age=${ageGroup}`}
                style={{ padding: "10px 16px", borderRadius: 10, background: "#ea580c", color: "#fff", fontWeight: 600 }}>
                🔢 Number Duel
              </Link>
              <Link href={`/arcade/ai-duel?age=${ageGroup}`}
                style={{ padding: "10px 16px", borderRadius: 10, background: "#a855f7", color: "#fff", fontWeight: 600 }}>
                🧠 AI Duel
              </Link>
            </div>
          </div>
          <div className="card" style={{ background: "linear-gradient(135deg, rgba(124,58,237,0.18), rgba(34,211,238,0.12))" }}>
            <h3 style={{ marginTop: 0 }}>🎮 Featured arcade games</h3>
            <p className="muted" style={{ marginTop: 0 }}>Geometry, stocks, and classic learning engines — consolidated from all arcade branches.</p>
            <div className="row" style={{ flexWrap: "wrap", gap: 10 }}>
              <Link href={`/arcade/shape-stack?age=${ageGroup}`}
                style={{ padding: "10px 16px", borderRadius: 10, background: "#6366f1", color: "#fff", fontWeight: 600 }}>
                📐 Shape Stack
              </Link>
              <Link href={`/arcade/shape-drop?age=${ageGroup}`}
                style={{ padding: "10px 16px", borderRadius: 10, background: "#4f46e5", color: "#fff", fontWeight: 600 }}>
                🧱 Shape Drop
              </Link>
              <Link href={`/arcade/geo-blocks?age=${ageGroup}`}
                style={{ padding: "10px 16px", borderRadius: 10, background: "#4338ca", color: "#fff", fontWeight: 600 }}>
                🧊 Geo Blocks
              </Link>
              <Link href={`/arcade/geometry-blocks?age=${ageGroup}`}
                style={{ padding: "10px 16px", borderRadius: 10, background: "#3730a3", color: "#fff", fontWeight: 600 }}>
                🧩 Geometry Blocks
              </Link>
              <Link href={`/arcade/geometry-tetris?age=${ageGroup}`}
                style={{ padding: "10px 16px", borderRadius: 10, background: "#312e81", color: "#fff", fontWeight: 600 }}>
                🟦 Geometry Tetris
              </Link>
              <Link href={`/arcade/market-moves?age=${ageGroup}`}
                style={{ padding: "10px 16px", borderRadius: 10, background: "#059669", color: "#fff", fontWeight: 600 }}>
                📈 Market Moves
              </Link>
              <Link href={`/arcade/stocks?age=${ageGroup}`}
                style={{ padding: "10px 16px", borderRadius: 10, background: "#047857", color: "#fff", fontWeight: 600 }}>
                💰 Market Mogul
              </Link>
              <Link href={`/arcade/stock-trader?age=${ageGroup}`}
                style={{ padding: "10px 16px", borderRadius: 10, background: "#0f766e", color: "#fff", fontWeight: 600 }}>
                📊 Stock Trader
              </Link>
              <Link href={`/arcade/stock-rush?age=${ageGroup}`}
                style={{ padding: "10px 16px", borderRadius: 10, background: "#115e59", color: "#fff", fontWeight: 600 }}>
                💹 Stock Rush
              </Link>
              <Link href={`/arcade/market-catch?age=${ageGroup}`}
                style={{ padding: "10px 16px", borderRadius: 10, background: "#134e4a", color: "#fff", fontWeight: 600 }}>
                📉 Market Catch
              </Link>
              <Link href={`/arcade/cosmic-catch?age=${ageGroup}`}
                style={{ padding: "10px 16px", borderRadius: 10, background: "#7c3aed", color: "#fff", fontWeight: 600 }}>
                🪐 Cosmic Catch
              </Link>
              <Link href={`/arcade/solar-3d`}
                style={{ padding: "10px 16px", borderRadius: 10, background: "#0ea5e9", color: "#fff", fontWeight: 600 }}>
                🌌 Solar Quiz · 3D
              </Link>
              {SUBJECT_ICON.chemistry && (
                <Link href={`/arcade/chemistry?age=${ageGroup}`}
                  style={{ padding: "10px 16px", borderRadius: 10, background: "#047857", color: "#fff", fontWeight: 600 }}>
                  ⚗️ Potion Lab
                </Link>
              )}
              <Link href="/arcade/stem-research"
                style={{ padding: "10px 16px", borderRadius: 10, background: "linear-gradient(135deg, #00d4aa, #0097a7)", color: "#fff", fontWeight: 700 }}>
                🔬 Stem Cell Lab
              </Link>
            </div>
          </div>
        </>
      )}

      {/* Picker */}
      {!round && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>{t("arcade.chooseGame")}</h3>
          <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
            {cat?.subjects.map((s) => (
              <button key={s}
                onClick={() => { setSubject(s); if (s !== "chemistry" && gameType === "potion") setGameType("quiz"); }}
                style={{ opacity: subject === s ? 1 : 0.55, fontSize: 14 }}>
                {SUBJECT_ICON[s] ?? "📘"} {subjectLabel(cat, s)}
              </button>
            ))}
          </div>
          <div className="muted" style={{ marginTop: 14, fontSize: 13 }}>{t("arcade.ageGroup")}</div>
          <div className="row" style={{ marginTop: 4, gap: 8, flexWrap: "wrap" }}>
            {(cat?.age_groups?.length ? cat.age_groups : DEFAULT_AGE_GROUPS).map((a) => (
              <button key={a.id} onClick={() => setAgeGroup(a.id)} title={a.range}
                style={{
                  background: ageGroup === a.id ? "#0ea5e9" : "transparent",
                  color: ageGroup === a.id ? "#fff" : "var(--text)",
                  border: ageGroup === a.id ? "2px solid #0ea5e9" : "2px solid var(--border)",
                  opacity: 1,
                  cursor: "pointer",
                }}>
                {a.name} <span style={{ fontSize: 11, opacity: 0.75 }}>({a.range})</span>
              </button>
            ))}
          </div>
          <div className="muted" style={{ marginTop: 14, fontSize: 13 }}>{t("arcade.gameMode")}</div>
          <div className="row" style={{ marginTop: 4, gap: 8, flexWrap: "wrap" }}>
            {cat?.game_types.map((g) => (
              <button key={g.id} onClick={() => setGameType(g.id)} title={g.desc}
                style={{ opacity: gameType === g.id ? 1 : 0.55 }}>
                {g.name}
              </button>
            ))}
            {subject === "chemistry" && (
              <button onClick={() => setGameType("potion")}
                title={t("arcade.potionTip")}
                style={{ opacity: gameType === "potion" ? 1 : 0.55, background: gameType === "potion" ? "#7c3aed" : undefined, color: gameType === "potion" ? "#fff" : undefined }}>
                {t("arcade.potionLab")}
              </button>
            )}
          </div>
          <div style={{ marginTop: 16 }}>
            <button onClick={play} style={{ background: "#7c3aed", color: "#fff", padding: "10px 22px" }}>
              {t("arcade.play", { subject, game: gameType, age: ageGroup })}
            </button>
          </div>
        </div>
      )}

      {/* Quiz / Speed */}
      {round && round.items && (
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h3 style={{ margin: 0 }}>
              {SUBJECT_ICON[round.subject] ?? "📘"} {subjectLabel(cat, round.subject)} · {round.game_type}
            </h3>
            {(round.game_type === "speed" || round.game_type === "marathon") && round.time_limit_s > 0 && (
              <span style={{ fontWeight: 700, color: timeLeft <= 10 ? "#e11d48" : "#16a34a" }}>⏱ {timeLeft}s</span>
            )}
          </div>
          {round.items.map((it, qi) => {
            const kind = it.kind ?? "mcq";
            const meta = it.meta ?? {};
            return (
            <div key={it.id} style={{ margin: "12px 0", padding: kind !== "mcq" ? 10 : 0,
              border: kind !== "mcq" ? "1px solid var(--border)" : undefined, borderRadius: 8 }}>
              {kind !== "mcq" && (
                <span style={{ fontSize: 12, opacity: 0.75 }}>{KIND_BADGE[kind] ?? "🎮"} {kind}</span>
              )}
              {kind === "tiles" && !!(meta as Record<string, unknown>).letters && (
                <div style={{ fontFamily: "monospace", fontSize: 20, letterSpacing: 6, margin: "6px 0" }}>
                  {(String((meta as Record<string, unknown>).letters)).split("").join(" ")}
                </div>
              )}
              {kind === "cartoon" && (
                <div className="muted" style={{ fontSize: 13, marginBottom: 6 }}>
                  📺 {t("arcade.cartoonScene")} {(meta as Record<string, unknown>).focus ? `· ${(meta as Record<string, unknown>).focus}` : ""}
                </div>
              )}
              {kind === "farm" && !!(meta as Record<string, unknown>).crop && (
                <div className="muted" style={{ fontSize: 13 }}>🌾 {String((meta as Record<string, unknown>).crop)}</div>
              )}
              {kind === "rpg" && !!(meta as Record<string, unknown>).scene && (
                <div className="muted" style={{ fontSize: 13 }}>🎭 {String((meta as Record<string, unknown>).scene)}</div>
              )}
              {kind === "scenario" && (
                <div className="muted" style={{ fontSize: 13, marginBottom: 6 }}>
                  💼 {(meta as Record<string, unknown>).track ? String((meta as Record<string, unknown>).track) : "workplace"}
                  {(meta as Record<string, unknown>).policy ? ` · ${String((meta as Record<string, unknown>).policy)}` : ""}
                </div>
              )}
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
          );})}
          <button onClick={finish} style={{ marginTop: 8, background: "#16a34a", color: "#fff" }}>{t("arcade.submit")}</button>
        </div>
      )}

      {/* Match */}
      {round && round.terms && round.options && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>{SUBJECT_ICON[round.subject]} {round.subject} · match</h3>
          <p className="muted">{t("arcade.matchHint")}</p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div>
              {round.terms.map((t) => (
                <button key={t.id} onClick={() => setSelTerm(t.id)}
                  style={{ display: "block", width: "100%", marginBottom: 8, textAlign: "left",
                    border: selTerm === t.id ? "2px solid #7c3aed" : "1px solid var(--border)",
                    background: answers[t.id] ? "#dcfce7" : "transparent",
                    color: answers[t.id] ? "#166534" : "var(--text)" }}>
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
                      opacity: taken ? 0.5 : 1, border: "1px solid var(--border)",
                      background: "transparent", color: "var(--text)" }}>
                    {o.text}
                  </button>
                );
              })}
            </div>
          </div>
          <button onClick={finish} style={{ marginTop: 12, background: "#16a34a", color: "#fff" }}>{t("arcade.submit")}</button>
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
          <button onClick={() => setResult(null)} style={{ background: "#7c3aed", color: "#fff" }}>{t("arcade.playAgain")}</button>
        </div>
      )}

      {/* Leaderboard */}
      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h3 style={{ margin: 0 }}>{t("arcade.leaderboard")}</h3>
          <select value={lbAge} onChange={(e) => { setLbAge(e.target.value); if (e.target.value) setLbSubject(""); }}>
            <option value="">{t("arcade.allAges")}</option>
            {cat?.age_groups.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          <select value={lbSubject} onChange={(e) => { setLbSubject(e.target.value); if (e.target.value) setLbAge(""); }}>
            <option value="">{t("arcade.overall")}</option>
            {cat?.subjects.map((s) => <option key={s} value={s}>{subjectLabel(cat, s)}</option>)}
          </select>
        </div>
        {leaders.length === 0 ? (
          <p className="muted">{t("arcade.noScores")}</p>
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
