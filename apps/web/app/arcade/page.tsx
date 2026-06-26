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
  creation: "🛠️", farming: "🌾",
};

const KIND_BADGE: Record<string, string> = {
  tiles: "🍌", resource: "⚖️", dependency: "🔗", rpg: "🎭", cartoon: "📺",
  idiom: "💬", create: "✨", doing: "🙌", farm: "🚜", spelling: "✏️", geometry: "📐",
};

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
    getGamesCatalog(locale).then(setCat).catch((e) => setError(String(e)));
  }, [locale]);

  const [lbAge, setLbAge] = useState<string>("");
  const loadLeaders = useCallback(() => {
    getLeaderboard(lbSubject || undefined, lbAge || undefined)
      .then((r) => setLeaders(r.leaders)).catch(() => setLeaders([]));
  }, [lbSubject, lbAge]);
  useEffect(() => { loadLeaders(); }, [loadLeaders]);

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

  // Timed modes: speed + marathon countdown -> auto-submit at zero.
  useEffect(() => {
    const timed = round && (round.game_type === "speed" || round.game_type === "marathon");
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
    setError(""); setResult(null); setAnswers({}); setSelTerm("");
    try {
      const n = gameType === "marathon" ? 20 : gameType === "match" ? 8 : 12;
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

      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}

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
            {cat?.age_groups.map((a) => (
              <button key={a.id} onClick={() => setAgeGroup(a.id)} title={a.range}
                style={{ opacity: ageGroup === a.id ? 1 : 0.55,
                  background: ageGroup === a.id ? "#0ea5e9" : undefined,
                  color: ageGroup === a.id ? "#fff" : undefined }}>
                {a.name} <span style={{ fontSize: 11, opacity: 0.8 }}>({a.range})</span>
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
