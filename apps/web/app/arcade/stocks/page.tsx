"use client";

// Stock Market Lab — learn investing with a live simulated chart + quiz
// decisions (buy / hold / sell and concept MCQs). Age scales volatility and
// question depth. Portfolio return + quiz accuracy drive the score.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  GameLoop, Particles, Surface, clamp, rand, roundRect,
} from "../../lib/gameEngine2d";

type Age = "kids" | "tween" | "teen" | "adult";

type Quiz = { prompt: string; options: string[]; answer: number; explain: string };

const QUIZ_BANK: Record<Age, Quiz[]> = {
  kids: [
    { prompt: "If a toy stock goes UP, that means…", options: ["It's worth more", "It's broken", "You owe money", "School is out"], answer: 0, explain: "Rising price = worth more." },
    { prompt: "Saving some money in different jars is like…", options: ["Diversifying", "Gambling only", "Throwing away", "Ignoring math"], answer: 0, explain: "Don't put all eggs in one basket." },
    { prompt: "A 'bull' market means prices are…", options: ["Going up", "Going down", "Invisible", "Always free"], answer: 0, explain: "Bulls charge upward." },
  ],
  tween: [
    { prompt: "Buy at $10, sell at $12. Profit per share?", options: ["$2", "$10", "$12", "$22"], answer: 0, explain: "12 − 10 = 2." },
    { prompt: "A bear market means prices are…", options: ["Falling", "Rising", "Only for gold", "Illegal"], answer: 0, explain: "Bears swipe down." },
    { prompt: "Best beginner habit?", options: ["Diversify", "One stock only", "Ignore research", "Sell your bike tip-only"], answer: 0, explain: "Spread risk." },
  ],
  teen: [
    { prompt: "A dividend is usually…", options: ["Cash paid to shareholders", "A loan", "A trading fee", "A stock split"], answer: 0, explain: "Share of profits." },
    { prompt: "Higher expected return usually means…", options: ["Higher risk", "Zero risk", "Guaranteed profit", "No homework"], answer: 0, explain: "Risk and return travel together." },
    { prompt: "An index fund typically…", options: ["Tracks a market basket", "Picks one company", "Guarantees 50%", "Is illegal"], answer: 0, explain: "Broad market slice." },
    { prompt: "Money needed next month belongs in…", options: ["Safer cash-like places", "The riskiest meme stock", "Only crypto", "Nowhere"], answer: 0, explain: "Short-term needs ≠ volatile bets." },
  ],
  adult: [
    { prompt: "Portfolio $60 stocks + $40 bonds. Stock %?", options: ["60%", "40%", "100%", "24%"], answer: 0, explain: "60/100 = 60%." },
    { prompt: "Friend tips a hot stock. First move?", options: ["Research before buying", "All-in immediately", "Sell your house", "Never invest"], answer: 0, explain: "Do your own homework." },
    { prompt: "Diversification mainly reduces…", options: ["Single-asset blow-up risk", "All taxes forever", "Need for patience", "Gravity"], answer: 0, explain: "One failure hurts less." },
    { prompt: "In a sharp drop, panic-selling locked losses is often…", options: ["Emotional, not a plan", "Always optimal", "Required by brokers", "Tax-free magic"], answer: 0, explain: "Have a plan before the storm." },
  ],
};

type EventCard = { kind: "news" | "quiz"; text: string; drift: number; quiz?: Quiz };

function newsFor(age: Age): EventCard[] {
  const base: EventCard[] = [
    { kind: "news", text: "Strong earnings beat — buyers pile in.", drift: 0.04 },
    { kind: "news", text: "Rate hike fears — market wobbles.", drift: -0.03 },
    { kind: "news", text: "New product launch buzz.", drift: 0.025 },
    { kind: "news", text: "Supply-chain snag reported.", drift: -0.02 },
    { kind: "news", text: "Quiet week — sideways drift.", drift: 0.002 },
  ];
  if (age === "adult" || age === "teen") {
    base.push(
      { kind: "news", text: "Inflation cools — risk appetite returns.", drift: 0.035 },
      { kind: "news", text: "Credit scare in a peer sector.", drift: -0.045 },
    );
  }
  return base;
}

export default function StocksLabPage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [age, setAge] = useState<Age>("tween");
  const [running, setRunning] = useState(false);
  const [over, setOver] = useState(false);
  const [score, setScore] = useState(0);
  const [best, setBest] = useState(0);
  const [cash, setCash] = useState(1000);
  const [shares, setShares] = useState(0);
  const [price, setPrice] = useState(100);
  const [eventText, setEventText] = useState("");
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [feedback, setFeedback] = useState("");
  const stateRef = useRef({
    cash: 1000, shares: 0, price: 100, history: [] as number[],
    t: 0, eventT: 0, score: 0, quizCorrect: 0, quizTotal: 0,
    over: false, vol: 0.02, event: null as EventCard | null,
  });

  useEffect(() => {
    try { setBest(Number(localStorage.getItem("aoep_stocks_best") || 0)); } catch { /* */ }
    const q = new URLSearchParams(window.location.search).get("age");
    if (q === "kids" || q === "tween" || q === "teen" || q === "adult") setAge(q);
  }, []);

  const syncHud = () => {
    const s = stateRef.current;
    setCash(Math.round(s.cash));
    setShares(s.shares);
    setPrice(Math.round(s.price * 100) / 100);
    setScore(s.score);
  };

  const buy = useCallback(() => {
    const s = stateRef.current;
    if (s.over || s.cash < s.price) return;
    s.cash -= s.price;
    s.shares += 1;
    s.score += 2;
    syncHud();
  }, []);

  const sell = useCallback(() => {
    const s = stateRef.current;
    if (s.over || s.shares <= 0) return;
    s.cash += s.price;
    s.shares -= 1;
    s.score += 2;
    syncHud();
  }, []);

  const answerQuiz = useCallback((idx: number) => {
    const s = stateRef.current;
    if (!quiz || s.over) return;
    s.quizTotal += 1;
    const ok = idx === quiz.answer;
    if (ok) {
      s.quizCorrect += 1;
      s.score += 30;
      s.cash += 25;
      setFeedback(`✓ ${quiz.explain}`);
    } else {
      setFeedback(`✗ ${quiz.explain}`);
    }
    setQuiz(null);
    syncHud();
  }, [quiz]);

  const finish = useCallback(() => {
    const s = stateRef.current;
    if (s.over) return;
    s.over = true;
    const equity = s.cash + s.shares * s.price;
    const ret = equity - 1000;
    s.score += Math.max(0, Math.round(ret)) + s.quizCorrect * 5;
    setScore(s.score);
    setOver(true);
    setRunning(false);
    setEventText(`Session end · equity $${Math.round(equity)} (${ret >= 0 ? "+" : ""}${Math.round(ret)})`);
    try {
      const b = Math.max(s.score, Number(localStorage.getItem("aoep_stocks_best") || 0));
      localStorage.setItem("aoep_stocks_best", String(b));
      setBest(b);
    } catch { /* */ }
  }, []);

  const start = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const s = stateRef.current;
    s.cash = 1000; s.shares = 0; s.price = 100;
    s.history = [100]; s.t = 0; s.eventT = 0; s.score = 0;
    s.quizCorrect = 0; s.quizTotal = 0; s.over = false;
    s.vol = age === "kids" ? 0.012 : age === "tween" ? 0.018 : age === "teen" ? 0.028 : 0.038;
    s.event = null;
    setOver(false); setRunning(true); setQuiz(null); setFeedback(""); setEventText("Markets open — trade wisely.");
    syncHud();

    const surface = new Surface(canvas);
    const particles = new Particles();
    const news = newsFor(age);
    const bank = QUIZ_BANK[age];
    const sessionLen = age === "kids" ? 45 : 60;

    const loop = new GameLoop((dt) => {
      if (s.over) return;
      const { ctx } = surface;
      const W = surface.width, H = surface.height;
      s.t += dt;
      s.eventT += dt;

      // Price random walk + event drift.
      const drift = s.event?.kind === "news" ? s.event.drift * dt * 0.35 : 0;
      const shock = (Math.random() - 0.5) * s.vol * s.price;
      s.price = clamp(s.price + shock + s.price * drift, 20, 400);
      if (s.history.length > 120) s.history.shift();
      s.history.push(s.price);

      if (s.eventT > (age === "kids" ? 7 : 5.5)) {
        s.eventT = 0;
        if (Math.random() < 0.45) {
          const q = bank[Math.floor(rand(0, bank.length))];
          s.event = { kind: "quiz", text: q.prompt, drift: 0, quiz: q };
          setQuiz(q);
          setEventText("Quiz time — earn cash for correct answers.");
        } else {
          const n = news[Math.floor(rand(0, news.length))];
          s.event = n;
          setEventText(n.text);
          if (n.drift > 0) particles.burst(W * 0.8, H * 0.3, "#4ade80", 14, { speed: 120 });
          if (n.drift < 0) particles.burst(W * 0.8, H * 0.3, "#f87171", 14, { speed: 120 });
        }
      }

      if (s.t >= sessionLen) finish();

      ctx.clearRect(0, 0, W, H);
      const bg = ctx.createLinearGradient(0, 0, 0, H);
      bg.addColorStop(0, "#052e1a"); bg.addColorStop(1, "#0f172a");
      ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);

      // Chart panel
      const cx = 16, cy = 36, cw = W - 32, ch = H - 70;
      ctx.fillStyle = "rgba(15,23,42,0.7)";
      roundRect(ctx, cx, cy, cw, ch, 12); ctx.fill();
      ctx.strokeStyle = "#14532d"; ctx.stroke();

      const hist = s.history;
      const minP = Math.min(...hist) * 0.96;
      const maxP = Math.max(...hist) * 1.04;
      ctx.beginPath();
      hist.forEach((p, i) => {
        const x = cx + 8 + (i / Math.max(1, hist.length - 1)) * (cw - 16);
        const y = cy + ch - 12 - ((p - minP) / (maxP - minP + 0.01)) * (ch - 24);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.strokeStyle = s.price >= 100 ? "#4ade80" : "#fbbf24";
      ctx.lineWidth = 2.5; ctx.stroke();

      // Fill under curve
      const lastX = cx + 8 + ((hist.length - 1) / Math.max(1, hist.length - 1)) * (cw - 16);
      ctx.lineTo(lastX, cy + ch - 8);
      ctx.lineTo(cx + 8, cy + ch - 8);
      ctx.closePath();
      ctx.fillStyle = "rgba(74,222,128,0.12)";
      ctx.fill();

      particles.update(dt); particles.draw(ctx);

      const equity = s.cash + s.shares * s.price;
      ctx.fillStyle = "#bbf7d0"; ctx.font = "bold 14px system-ui, sans-serif";
      ctx.textAlign = "left";
      ctx.fillText(`$${s.price.toFixed(2)}`, 20, 22);
      ctx.textAlign = "center";
      ctx.fillText(`Equity $${equity.toFixed(0)} · Score ${s.score}`, W / 2, 22);
      ctx.textAlign = "right";
      ctx.fillText(`${Math.max(0, Math.ceil(sessionLen - s.t))}s`, W - 16, 22);
    });

    const cleanup = () => {
      loop.stop();
      surface.dispose();
    };
    (canvas as unknown as { __cleanup?: () => void }).__cleanup = cleanup;
    loop.start();
  }, [age, finish]);

  useEffect(() => () => {
    const c = canvasRef.current as unknown as { __cleanup?: () => void } | null;
    c?.__cleanup?.();
  }, []);

  return (
    <main style={{ maxWidth: 760, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>📈 Stock Market Lab</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
      </div>
      <p className="muted">
        Learn investing on a live chart: buy, hold, or sell through news shocks,
        and answer quizzes to grow cash. Score = portfolio skill + quiz accuracy.
      </p>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
        <span className="muted">Age:</span>
        {(["kids", "tween", "teen", "adult"] as Age[]).map((a) => (
          <button key={a} onClick={() => setAge(a)} disabled={running}
            style={{ opacity: age === a ? 1 : 0.55, fontWeight: age === a ? 700 : 400 }}>
            {a}
          </button>
        ))}
        <span className="muted" style={{ marginLeft: "auto" }}>Best: {best}</span>
      </div>

      <div style={{ position: "relative", width: "100%", aspectRatio: "16 / 10", borderRadius: 14, overflow: "hidden", border: "1px solid #14532d" }}>
        <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block" }} />
        {!running && (
          <div style={{
            position: "absolute", inset: 0, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", gap: 12,
            background: "rgba(6,40,24,0.78)", color: "#fff",
          }}>
            {over && <div style={{ fontSize: 22, fontWeight: 700 }}>Session over · Score {score}</div>}
            <button onClick={start} style={{ background: "#059669", color: "#fff", padding: "12px 28px", fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer" }}>
              {over ? "Trade again" : "▶ Open market"}
            </button>
          </div>
        )}
      </div>

      <div className="card" style={{ marginTop: 12 }}>
        <div className="muted" style={{ marginBottom: 6 }}>{eventText}</div>
        {feedback && <div style={{ marginBottom: 8, color: feedback.startsWith("✓") ? "#4ade80" : "#f87171" }}>{feedback}</div>}
        <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <span>Cash ${cash}</span>
          <span>Shares {shares}</span>
          <span>Price ${price}</span>
          <button onClick={buy} disabled={!running} style={{ background: "#059669", color: "#fff" }}>Buy</button>
          <button onClick={sell} disabled={!running} style={{ background: "#b45309", color: "#fff" }}>Sell</button>
          <button onClick={finish} disabled={!running}>End session</button>
        </div>
        {quiz && (
          <div style={{ marginTop: 12 }}>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>{quiz.prompt}</div>
            <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
              {quiz.options.map((opt, i) => (
                <button key={opt} onClick={() => answerQuiz(i)}
                  style={{ padding: "8px 12px", borderRadius: 8 }}>
                  {opt}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
