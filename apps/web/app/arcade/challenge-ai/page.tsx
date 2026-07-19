"use client";

// Challenge the AI — duel Salareen AI on the same quiz round. Race the clock,
// beat the bot's score, earn a versus bonus when you win.

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getGamesCatalog,
  getToken,
  newGame,
  submitGame,
  type GamesCatalog,
  type GameRound,
  type GameSubmit,
} from "../../lib/api";
import { useT } from "../../lib/i18n";

const SUBJECT_ICON: Record<string, string> = {
  biology: "🧬", chemistry: "⚗️", physics: "🪐", math: "➗", science: "🔬",
  history: "🏛️", art: "🎨", technology: "💻", programming: "👾",
  life_growth: "🌱", etiquette: "🤝", wordplay: "🔤", geometry: "📐",
  creation: "🛠️", farming: "🌾", finance: "📈",
};

type AiState = { answered: number; correct: number; thinking: boolean };

export default function ChallengeAiPage() {
  const { t, locale } = useT();
  const [cat, setCat] = useState<GamesCatalog | null>(null);
  const [subject, setSubject] = useState("math");
  const [ageGroup, setAgeGroup] = useState("teen");
  const [round, setRound] = useState<GameRound | null>(null);
  const [idx, setIdx] = useState(0);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [ai, setAi] = useState<AiState>({ answered: 0, correct: 0, thinking: false });
  const [timeLeft, setTimeLeft] = useState(0);
  const [result, setResult] = useState<GameSubmit | null>(null);
  const [error, setError] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);
  const [startedAt, setStartedAt] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => { setLoggedIn(Boolean(getToken())); }, []);
  useEffect(() => {
    getGamesCatalog(locale).then(setCat).catch((e) => setError(String(e)));
  }, [locale]);

  const items = round?.items ?? [];
  const current = items[idx];
  const aiSkill = typeof round?.ai_skill === "number" ? round.ai_skill : 0.65;
  const progressYou = items.length ? Math.round((Object.keys(answers).length / items.length) * 100) : 0;
  const progressAi = items.length ? Math.round((ai.answered / items.length) * 100) : 0;

  const subjectLabel = useMemo(() => {
    const loc = cat?.subjects_localized?.find((s) => s.id === subject);
    return loc?.name ?? subject.replace(/_/g, " ");
  }, [cat, subject]);

  const finish = useCallback(async (finalAnswers: Record<string, number>) => {
    if (!round || busy) return;
    setBusy(true);
    try {
      if (!loggedIn) {
        setError(t("arcade.signInSubmit"));
        setBusy(false);
        return;
      }
      const elapsed = (Date.now() - startedAt) / 1000;
      const r = await submitGame(round.game_id, finalAnswers, elapsed);
      setResult(r);
      setRound(null);
    } catch (e) {
      const msg = String(e);
      if (msg.includes("404") || msg.includes("unknown or expired")) {
        setError(t("arcade.sessionExpired"));
        setRound(null);
      } else setError(msg);
    } finally {
      setBusy(false);
    }
  }, [round, busy, loggedIn, startedAt, t]);

  // Countdown
  useEffect(() => {
    if (!round || round.game_type !== "challenge" || timeLeft <= 0) return;
    if (timeLeft <= 0) return;
    const timer = setTimeout(() => setTimeLeft((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [round, timeLeft]);

  useEffect(() => {
    if (round && timeLeft === 0 && round.time_limit_s > 0 && !result) {
      void finish(answers);
    }
  }, [timeLeft, round, answers, finish, result]);

  // AI answers in parallel with delay based on skill (faster when skilled).
  useEffect(() => {
    if (!round?.items?.length || result) return;
    let cancelled = false;
    const itemsLocal = round.items;
    const skill = typeof round.ai_skill === "number" ? round.ai_skill : 0.65;
    const delayMs = Math.max(700, 2200 - skill * 1400);

    async function runAi() {
      setAi({ answered: 0, correct: 0, thinking: true });
      let correct = 0;
      for (let i = 0; i < itemsLocal.length; i++) {
        if (cancelled) return;
        await new Promise((r) => setTimeout(r, delayMs + Math.random() * 400));
        if (cancelled) return;
        // Visual only — real AI score is computed server-side on submit.
        if (Math.random() < skill) correct += 1;
        setAi({ answered: i + 1, correct, thinking: i + 1 < itemsLocal.length });
      }
      setAi((a) => ({ ...a, thinking: false }));
    }
    void runAi();
    return () => { cancelled = true; };
  }, [round, result]);

  async function play() {
    setError(""); setResult(null); setAnswers({});
    setAi({ answered: 0, correct: 0, thinking: false }); setIdx(0);
    try {
      const r = await newGame(subject, "challenge", ageGroup, 8);
      setStartedAt(Date.now());
      setTimeLeft(r.time_limit_s || 60);
      setRound(r);
    } catch (e) {
      setError(String(e));
    }
  }

  function pick(optionIdx: number) {
    if (!current || answers[current.id] !== undefined) return;
    const next = { ...answers, [current.id]: optionIdx };
    setAnswers(next);
    if (idx + 1 < items.length) {
      setIdx(idx + 1);
    } else {
      void finish(next);
    }
  }

  const outcome = result?.result?.versus_outcome;
  const outcomeLabel =
    outcome === "win" ? "You beat the AI!" :
    outcome === "tie" ? "Dead heat — tie with the AI." :
    outcome === "lose" ? "AI wins this round — rematch?" : "";

  return (
    <main className="container" style={{ maxWidth: 900 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>🤖 Challenge the AI</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
      </div>
      <p className="muted">
        Same questions. Same clock. Can you outscore Salareen AI?
        Win the duel for a versus bonus that feeds your rewards.
      </p>

      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}

      {!round && !result && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Pick your arena</h3>
          <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
            {(cat?.subjects ?? Object.keys(SUBJECT_ICON)).map((s) => (
              <button key={s} onClick={() => setSubject(s)}
                style={{ opacity: subject === s ? 1 : 0.55 }}>
                {SUBJECT_ICON[s] ?? "📘"} {s === subject ? subjectLabel : s.replace(/_/g, " ")}
              </button>
            ))}
          </div>
          <div className="muted" style={{ marginTop: 14, fontSize: 13 }}>{t("arcade.ageGroup")}</div>
          <div className="row" style={{ marginTop: 4, gap: 8, flexWrap: "wrap" }}>
            {(cat?.age_groups ?? [
              { id: "kids", name: "Kids", range: "5-8" },
              { id: "tween", name: "Tweens", range: "9-12" },
              { id: "teen", name: "Teens", range: "13-17" },
              { id: "adult", name: "Adults", range: "18+" },
            ]).map((a) => (
              <button key={a.id} onClick={() => setAgeGroup(a.id)}
                style={{
                  opacity: ageGroup === a.id ? 1 : 0.55,
                  background: ageGroup === a.id ? "#dc2626" : undefined,
                  color: ageGroup === a.id ? "#fff" : undefined,
                }}>
                {a.name}
              </button>
            ))}
          </div>
          <div style={{ marginTop: 16 }}>
            <button onClick={play} style={{ background: "#dc2626", color: "#fff", padding: "12px 24px", fontSize: 16 }}>
              ⚔ Challenge the AI · {subjectLabel}
            </button>
          </div>
          {!loggedIn && (
            <p className="muted" style={{ marginTop: 12 }}>
              <Link href="/login">{t("profile.signIn")}</Link> {t("arcade.signInSave")}
            </p>
          )}
        </div>
      )}

      {round && current && (
        <>
          <div className="row" style={{ gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
            <div className="card" style={{ flex: "1 1 240px", background: "linear-gradient(135deg, rgba(14,165,233,0.15), transparent)" }}>
              <div style={{ fontWeight: 700 }}>You</div>
              <div className="muted" style={{ fontSize: 13 }}>Answered {Object.keys(answers).length}/{items.length}</div>
              <div style={{ height: 8, background: "#1e293b", borderRadius: 4, marginTop: 8 }}>
                <div style={{ width: `${progressYou}%`, height: "100%", background: "#0ea5e9", borderRadius: 4 }} />
              </div>
            </div>
            <div className="card" style={{ flex: "0 0 auto", textAlign: "center", minWidth: 100 }}>
              <div style={{ fontSize: 28, fontWeight: 800 }}>{timeLeft}s</div>
              <div className="muted">VS</div>
            </div>
            <div className="card" style={{ flex: "1 1 240px", background: "linear-gradient(135deg, rgba(220,38,38,0.18), transparent)" }}>
              <div style={{ fontWeight: 700 }}>{round.ai_name ?? "Salareen AI"}</div>
              <div className="muted" style={{ fontSize: 13 }}>
                {ai.thinking ? "Thinking…" : "Done"} · skill {Math.round(aiSkill * 100)}%
              </div>
              <div className="muted" style={{ fontSize: 12 }}>Sim progress {ai.answered}/{items.length}</div>
              <div style={{ height: 8, background: "#1e293b", borderRadius: 4, marginTop: 8 }}>
                <div style={{ width: `${progressAi}%`, height: "100%", background: "#dc2626", borderRadius: 4 }} />
              </div>
            </div>
          </div>

          <div className="card">
            <div className="muted" style={{ marginBottom: 6 }}>Question {idx + 1} of {items.length}</div>
            <h3 style={{ marginTop: 0 }}>{current.prompt}</h3>
            <div className="row" style={{ flexDirection: "column", gap: 8, alignItems: "stretch" }}>
              {current.options.map((opt, i) => (
                <button key={opt} onClick={() => pick(i)}
                  disabled={answers[current.id] !== undefined}
                  style={{
                    textAlign: "left", padding: "12px 14px",
                    opacity: answers[current.id] !== undefined ? 0.6 : 1,
                    borderColor: answers[current.id] === i ? "#0ea5e9" : undefined,
                  }}>
                  {String.fromCharCode(65 + i)}. {opt}
                </button>
              ))}
            </div>
          </div>
        </>
      )}

      {result && (
        <div className="card" style={{
          background: outcome === "win"
            ? "linear-gradient(135deg, rgba(5,150,105,0.25), transparent)"
            : outcome === "lose"
              ? "linear-gradient(135deg, rgba(220,38,38,0.2), transparent)"
              : "linear-gradient(135deg, rgba(234,179,8,0.2), transparent)",
        }}>
          <h2 style={{ marginTop: 0 }}>{outcomeLabel || "Duel complete"}</h2>
          <p>
            You {result.result.correct}/{result.result.total}
            {" · "}
            AI {result.result.ai_correct}/{result.result.ai_total}
            {" · "}
            +{result.points_earned} pts
            {result.result.versus_bonus ? ` (includes +${result.result.versus_bonus} versus bonus)` : ""}
          </p>
          <div className="row" style={{ gap: 8 }}>
            <button onClick={play} style={{ background: "#dc2626", color: "#fff" }}>Rematch</button>
            <Link href="/arcade">{t("arcade.playAgain")}</Link>
            <Link href="/rewards">{t("arcade.rewardsLink")}</Link>
          </div>
        </div>
      )}
    </main>
  );
}
