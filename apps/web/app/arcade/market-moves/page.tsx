"use client";

// Market Moves — stocks learning arcade. Watch a simulated ticker, answer
// finance questions, and make buy/hold/sell calls. Portfolio value tracks your
// decisions; wrong calls cost cash. Teaches diversification, compound growth,
// and risk management through play.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { GameLoop, Particles, clamp, rand } from "../../lib/gameEngine2d";

type Age = "kids" | "tween" | "teen" | "adult";
type Action = "buy" | "hold" | "sell";

type Scenario = {
  prompt: string;
  context: string;
  correct: Action;
  explain: string;
  priceDelta: number; // % change after decision
};

const SCENARIOS: Record<Age, Scenario[]> = {
  kids: [
    { prompt: "You saved $10. Candy costs $2. How many can you buy?", context: "Price: $2 each", correct: "hold", explain: "Saving teaches patience — you can buy 5 later!", priceDelta: 0 },
    { prompt: "Lemonade stand earns $5/day. Reinvest or spend all?", context: "Stand value: $20", correct: "buy", explain: "Reinvesting grows your business!", priceDelta: 8 },
    { prompt: "Toy price drops from $10 to $8. Good time to buy?", context: "Toy Co. $8", correct: "buy", explain: "Buy low — same toy, lower price.", priceDelta: 5 },
    { prompt: "You need lunch money tomorrow. Sell your toy collection?", context: "Collection: $15", correct: "sell", explain: "Sell when you need cash for essentials.", priceDelta: -2 },
  ],
  tween: [
    { prompt: "Stock rose 10% after good earnings. Already own shares — action?", context: "TechCo $55 (+10%)", correct: "hold", explain: "Hold if fundamentals still strong.", priceDelta: 3 },
    { prompt: "Company news is bad; stock down 15%. Panic sell?", context: "GameInc $34 (-15%)", correct: "hold", explain: "Don't panic — research first.", priceDelta: -5 },
    { prompt: "You have cash; index fund steady for 5 years. Buy?", context: "Index ETF $120", correct: "buy", explain: "Diversified index funds reduce single-stock risk.", priceDelta: 6 },
    { prompt: "One stock is 80% of your portfolio. Rebalance?", context: "Portfolio heavy", correct: "sell", explain: "Diversify — don't put all eggs in one basket.", priceDelta: 2 },
  ],
  teen: [
    { prompt: "P/E ratio very high vs peers. Bubble risk?", context: "GrowthCo P/E 85", correct: "sell", explain: "Extreme P/E may mean overvaluation.", priceDelta: -8 },
    { prompt: "Dollar-cost average $50/month into index fund?", context: "S&P 500 ETF", correct: "buy", explain: "Regular investing reduces timing risk.", priceDelta: 4 },
    { prompt: "Emergency fund empty; market dips 20%. Borrow to buy?", context: "Market -20%", correct: "hold", explain: "Never invest emergency money.", priceDelta: -3 },
    { prompt: "Dividend stock yields 6% with stable earnings. Add?", context: "DivPay $42, 6% yield", correct: "buy", explain: "Dividends provide income + reinvestment.", priceDelta: 5 },
  ],
  adult: [
    { prompt: "Portfolio up 40%; rebalancing target is 60/40 stocks/bonds.", context: "Now 75/25", correct: "sell", explain: "Rebalance by selling overweight stocks.", priceDelta: -2 },
    { prompt: "Fed raises rates; growth stocks fall. Shift to value?", context: "Rates +0.5%", correct: "buy", explain: "Value/dividend stocks often hold better in rate hikes.", priceDelta: 3 },
    { prompt: "Options offer 10× leverage on meme stock. Safe?", context: "MemeCo volatile", correct: "hold", explain: "Leverage amplifies losses — avoid speculation.", priceDelta: -12 },
    { prompt: "Tax-loss harvest losing position, buy similar ETF?", context: "Loss: -$2,000", correct: "buy", explain: "Harvest losses for taxes; stay invested via similar asset.", priceDelta: 4 },
  ],
};

function aiAccuracy(age: Age): number {
  return { kids: 0.55, tween: 0.65, teen: 0.78, adult: 0.88 }[age];
}

export default function MarketMoves() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [age, setAge] = useState<Age>("teen");
  const [vsAi, setVsAi] = useState(false);
  const [running, setRunning] = useState(false);
  const [over, setOver] = useState(false);
  const [portfolio, setPortfolio] = useState(1000);
  const [aiPortfolio, setAiPortfolio] = useState(1000);
  const [best, setBest] = useState(0);
  const [round, setRound] = useState(0);
  const [feedback, setFeedback] = useState("");
  const stateRef = useRef({
    cash: 1000, aiCash: 1000, round: 0, scenarios: [] as Scenario[],
    price: 100, priceHistory: [] as number[], t: 0, over: false,
    waiting: true, lastResult: "",
  });

  useEffect(() => {
    try { setBest(Number(localStorage.getItem("aoep_market_best") || 0)); } catch { /* */ }
    const q = new URLSearchParams(window.location.search);
    const a = q.get("age");
    if (a === "kids" || a === "tween" || a === "teen" || a === "adult") setAge(a);
    if (q.get("vs") === "ai") setVsAi(true);
  }, []);

  const currentScenario = () => stateRef.current.scenarios[stateRef.current.round % stateRef.current.scenarios.length];

  const applyAction = useCallback((action: Action, isAi: boolean) => {
    const s = stateRef.current;
    const sc = currentScenario();
    if (!sc) return;
    const correct = action === sc.correct;
    const mult = correct ? 1 + sc.priceDelta / 100 : 1 - Math.abs(sc.priceDelta) / 200;
    if (isAi) {
      s.aiCash = Math.round(s.aiCash * mult);
      setAiPortfolio(s.aiCash);
    } else {
      s.cash = Math.round(s.cash * mult);
      setPortfolio(s.cash);
      setFeedback(correct ? `✓ ${sc.explain}` : `✗ ${sc.explain}`);
    }
  }, []);

  const nextRound = useCallback(() => {
    const s = stateRef.current;
    s.round += 1;
    setRound(s.round);
    s.waiting = true;
    if (vsAi) {
      const sc = currentScenario();
      const aiPick = Math.random() < aiAccuracy(age)
        ? sc.correct
        : (["buy", "hold", "sell"] as Action[]).filter((a) => a !== sc.correct)[Math.floor(rand(0, 2))];
      setTimeout(() => applyAction(aiPick, true), 800);
    }
    if (s.round >= 8) {
      s.over = true;
      setOver(true); setRunning(false);
      try {
        const b = Math.max(s.cash, Number(localStorage.getItem("aoep_market_best") || 0));
        localStorage.setItem("aoep_market_best", String(b));
        setBest(b);
      } catch { /* */ }
    }
  }, [age, vsAi, applyAction]);

  const choose = useCallback((action: Action) => {
    if (!stateRef.current.waiting || stateRef.current.over) return;
    stateRef.current.waiting = false;
    applyAction(action, false);
    const sc = currentScenario();
    stateRef.current.price = clamp(stateRef.current.price * (1 + sc.priceDelta / 100), 50, 200);
    stateRef.current.priceHistory.push(stateRef.current.price);
    if (stateRef.current.priceHistory.length > 40) stateRef.current.priceHistory.shift();
    setTimeout(nextRound, 1200);
  }, [applyAction, nextRound]);

  const start = useCallback(() => {
    const s = stateRef.current;
    s.cash = 1000; s.aiCash = 1000; s.round = 0; s.over = false; s.waiting = true;
    s.scenarios = [...SCENARIOS[age]].sort(() => Math.random() - 0.5);
    s.price = 100; s.priceHistory = [100]; s.t = 0;
    setPortfolio(1000); setAiPortfolio(1000); setRound(0); setFeedback("");
    setOver(false); setRunning(true);
  }, [age]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !running) return;
    const particles = new Particles();
    const loop = new GameLoop((dt) => {
      const s = stateRef.current;
      if (s.over) return;
      s.t += dt;
      s.price += Math.sin(s.t * 2) * 0.15 + (rand(-0.5, 0.5));
      s.price = clamp(s.price, 60, 180);

      const W = canvas.clientWidth, H = canvas.clientHeight;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      ctx.fillStyle = "#0f172a"; ctx.fillRect(0, 0, W, H);

      // Ticker chart
      const hist = s.priceHistory.length ? s.priceHistory : [s.price];
      const minP = Math.min(...hist) - 5, maxP = Math.max(...hist) + 5;
      ctx.strokeStyle = hist.length > 1 && hist[hist.length - 1] >= hist[0] ? "#34d399" : "#f87171";
      ctx.lineWidth = 2; ctx.beginPath();
      hist.forEach((p, i) => {
        const x = 20 + (i / Math.max(hist.length - 1, 1)) * (W - 40);
        const y = H * 0.35 - ((p - minP) / (maxP - minP || 1)) * H * 0.25;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.stroke();

      ctx.fillStyle = "#94a3b8"; ctx.font = "bold 14px system-ui, sans-serif";
      ctx.textAlign = "left"; ctx.fillText(`$${s.price.toFixed(2)}`, 20, H * 0.12);

      particles.update(dt); particles.draw(ctx);
    });
    loop.start();
    return () => loop.stop();
  }, [running]);

  const sc = running && !over ? currentScenario() : null;

  return (
    <main style={{ maxWidth: 760, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>📈 Market Moves</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
        <Link href="/arcade/challenge-ai">🤖 Challenge AI</Link>
      </div>
      <p className="muted">Learn stocks and investing — read the scenario, then buy, hold, or sell. {vsAi && "You're competing against the AI trader!"}</p>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
        <span className="muted">Age:</span>
        {(["kids", "tween", "teen", "adult"] as Age[]).map((a) => (
          <button key={a} onClick={() => setAge(a)} disabled={running}
            style={{ opacity: age === a ? 1 : 0.55 }}>{a}</button>
        ))}
        <label style={{ marginLeft: 12, display: "flex", alignItems: "center", gap: 6 }}>
          <input type="checkbox" checked={vsAi} onChange={(e) => setVsAi(e.target.checked)} disabled={running} />
          vs AI
        </label>
        <span className="muted" style={{ marginLeft: "auto" }}>Best: ${best}</span>
      </div>

      <div style={{ position: "relative", width: "100%", height: 120, borderRadius: 14, overflow: "hidden", border: "1px solid #1e293b", marginBottom: 12 }}>
        <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block" }} />
      </div>

      {!running && (
        <div style={{ textAlign: "center", padding: 24 }}>
          {over && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 22, fontWeight: 700 }}>Round complete!</div>
              <div>Your portfolio: <strong>${portfolio}</strong></div>
              {vsAi && <div>AI portfolio: <strong>${aiPortfolio}</strong> — {portfolio > aiPortfolio ? "You win! 🎉" : portfolio < aiPortfolio ? "AI wins 🤖" : "Tie!"}</div>}
            </div>
          )}
          <button onClick={start} style={{ background: "#059669", color: "#fff", padding: "12px 28px", fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer" }}>
            {over ? "Play again" : "▶ Start trading"}
          </button>
        </div>
      )}

      {running && sc && (
        <div className="card">
          <div className="muted" style={{ fontSize: 13 }}>Round {round + 1} / 8 · {sc.context}</div>
          <h3 style={{ marginTop: 8 }}>{sc.prompt}</h3>
          <div style={{ display: "flex", gap: 10, marginTop: 16, flexWrap: "wrap" }}>
            {(["buy", "hold", "sell"] as Action[]).map((a) => (
              <button key={a} onClick={() => choose(a)} disabled={!stateRef.current.waiting}
                style={{
                  flex: 1, minWidth: 90, padding: "14px 20px", fontSize: 16, fontWeight: 700,
                  background: a === "buy" ? "#059669" : a === "sell" ? "#dc2626" : "#475569",
                  color: "#fff", border: 0, borderRadius: 10, cursor: "pointer",
                  opacity: stateRef.current.waiting ? 1 : 0.5,
                }}>
                {a === "buy" ? "📈 Buy" : a === "sell" ? "📉 Sell" : "⏸ Hold"}
              </button>
            ))}
          </div>
          {feedback && <p style={{ marginTop: 12, color: feedback.startsWith("✓") ? "#34d399" : "#f87171" }}>{feedback}</p>}
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 12, fontSize: 14 }}>
            <span>Portfolio: <strong>${portfolio}</strong></span>
            {vsAi && <span>AI: <strong>${aiPortfolio}</strong></span>}
          </div>
        </div>
      )}
    </main>
  );
}
