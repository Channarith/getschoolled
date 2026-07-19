"use client";

// Stock Trader — a stocks-learning arcade game. Trade three simulated companies
// over a set number of days, each with its own volatility and trend. Buy low,
// sell high, react to news headlines, and try to beat a passive "buy & hold"
// index. A live animated price chart (canvas game loop) plus a running lesson
// panel teaches real concepts: volatility, diversification, trend, and why
// timing the market is hard. No real money, no backend — pure learning sandbox.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { GameLoop, Surface, clamp } from "../../lib/gameEngine2d";

type Age = "kids" | "tween" | "teen" | "adult";

type Stock = {
  symbol: string;
  name: string;
  color: string;
  price: number;
  drift: number; // per-day expected return
  vol: number;   // per-day volatility
  history: number[];
  shock: number; // pending one-day news impact
};

type News = { text: string; symbol: string; impact: number };

const START_CASH = 1000;

function makeStocks(): Stock[] {
  return [
    { symbol: "NOVA", name: "Nova Tech", color: "#22d3ee", price: 50, drift: 0.006, vol: 0.06, history: [50], shock: 0 },
    { symbol: "GRUB", name: "Green Grub Foods", color: "#34d399", price: 40, drift: 0.003, vol: 0.025, history: [40], shock: 0 },
    { symbol: "ORB", name: "Orbit Energy", color: "#f59e0b", price: 65, drift: 0.004, vol: 0.09, history: [65], shock: 0 },
  ];
}

const HEADLINES: { text: (n: string) => string; impact: number }[] = [
  { text: (n) => `📈 ${n} lands a huge new contract!`, impact: 0.14 },
  { text: (n) => `🚀 ${n} beats earnings expectations.`, impact: 0.1 },
  { text: (n) => `🤝 ${n} announces a popular partnership.`, impact: 0.08 },
  { text: (n) => `📉 ${n} recalls a faulty product.`, impact: -0.13 },
  { text: (n) => `⚠️ ${n} misses earnings; investors worry.`, impact: -0.1 },
  { text: (n) => `🔻 ${n} faces a new competitor.`, impact: -0.07 },
];

const TIPS = [
  "Volatility = how much a price swings. ORB swings the most; GRUB is calmest.",
  "Diversifying (spreading money across stocks) lowers your overall risk.",
  "Buy low, sell high — but nobody knows the future price for sure.",
  "A rising trend can reverse. Past gains don't guarantee future gains.",
  "News moves prices fast. Reacting after the crowd is often too late.",
  "Holding a good company long-term often beats frantic trading.",
];

function gaussian(): number {
  // Sum of uniforms → approx normal, mean 0.
  return (Math.random() + Math.random() + Math.random() + Math.random() - 2) / 1.0;
}

function ageDays(age: Age): number {
  return age === "kids" ? 15 : age === "tween" ? 20 : age === "teen" ? 30 : 40;
}

export default function StockTrader() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [age, setAge] = useState<Age>("teen");
  const [running, setRunning] = useState(false);
  const [over, setOver] = useState(false);
  const [, forceTick] = useState(0);
  const [best, setBest] = useState(0);

  const stateRef = useRef({
    stocks: makeStocks(),
    cash: START_CASH,
    shares: {} as Record<string, number>,
    day: 0,
    maxDays: 30,
    selected: "NOVA",
    news: null as News | null,
    baselineShares: {} as Record<string, number>, // buy & hold at day 0
    tip: TIPS[0],
    over: false,
  });

  const rerender = useCallback(() => forceTick((n) => n + 1), []);

  useEffect(() => {
    try { setBest(Number(localStorage.getItem("aoep_stocktrader_best") || 0)); } catch { /* */ }
    const q = new URLSearchParams(window.location.search).get("age");
    if (q === "kids" || q === "tween" || q === "teen" || q === "adult") setAge(q);
  }, []);

  const netWorth = (): number => {
    const s = stateRef.current;
    let v = s.cash;
    for (const st of s.stocks) v += (s.shares[st.symbol] || 0) * st.price;
    return v;
  };

  const baselineWorth = (): number => {
    const s = stateRef.current;
    let v = 0;
    for (const st of s.stocks) v += (s.baselineShares[st.symbol] || 0) * st.price;
    return v;
  };

  const start = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const s = stateRef.current;
    const stocks = makeStocks();
    s.stocks = stocks;
    s.cash = START_CASH;
    s.shares = {};
    s.day = 0;
    s.maxDays = ageDays(age);
    s.selected = "NOVA";
    s.news = null;
    s.over = false;
    s.tip = TIPS[Math.floor(Math.random() * TIPS.length)];
    // Buy & hold baseline: split starting cash equally across the 3 stocks at day 0.
    const per = START_CASH / stocks.length;
    s.baselineShares = {};
    for (const st of stocks) s.baselineShares[st.symbol] = per / st.price;

    setOver(false); setRunning(true);
    rerender();

    const surface = new Surface(canvas);

    const loop = new GameLoop(() => {
      const { ctx } = surface;
      const W = surface.width, H = surface.height;
      const st = s.stocks.find((x) => x.symbol === s.selected) || s.stocks[0];
      const hist = st.history;

      const grad = ctx.createLinearGradient(0, 0, 0, H);
      grad.addColorStop(0, "#0b1020"); grad.addColorStop(1, "#0a1526");
      ctx.fillStyle = grad; ctx.fillRect(0, 0, W, H);

      const padL = 48, padR = 12, padT = 30, padB = 24;
      const plotW = W - padL - padR;
      const plotH = H - padT - padB;

      const lo = Math.min(...hist) * 0.96;
      const hi = Math.max(...hist) * 1.04;
      const yFor = (p: number) => padT + plotH - ((p - lo) / Math.max(0.001, hi - lo)) * plotH;
      const xFor = (i: number) => padL + (hist.length <= 1 ? 0 : (i / (s.maxDays)) * plotW);

      // Gridlines + price labels.
      ctx.strokeStyle = "rgba(255,255,255,0.06)";
      ctx.fillStyle = "#7f8db3";
      ctx.font = "11px system-ui, sans-serif";
      ctx.textAlign = "right"; ctx.textBaseline = "middle";
      for (let g = 0; g <= 4; g++) {
        const p = lo + ((hi - lo) * g) / 4;
        const y = yFor(p);
        ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(W - padR, y); ctx.stroke();
        ctx.fillText(`$${p.toFixed(0)}`, padL - 6, y);
      }

      // Price line.
      const up = st.price >= (hist[0] ?? st.price);
      const lineColor = up ? "#34d399" : "#f87171";
      ctx.strokeStyle = lineColor;
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      hist.forEach((p, i) => {
        const x = xFor(i), y = yFor(p);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.stroke();

      // Fill under line.
      ctx.lineTo(xFor(hist.length - 1), padT + plotH);
      ctx.lineTo(xFor(0), padT + plotH);
      ctx.closePath();
      ctx.fillStyle = up ? "rgba(52,211,153,0.12)" : "rgba(248,113,113,0.12)";
      ctx.fill();

      // Current price pulsing dot.
      const cx = xFor(hist.length - 1), cy = yFor(st.price);
      const t = performance.now() / 1000;
      const pr = 4 + Math.sin(t * 4) * 1.5;
      ctx.fillStyle = lineColor;
      ctx.beginPath(); ctx.arc(cx, cy, pr, 0, Math.PI * 2); ctx.fill();
      ctx.globalAlpha = 0.25;
      ctx.beginPath(); ctx.arc(cx, cy, pr + 6, 0, Math.PI * 2); ctx.fill();
      ctx.globalAlpha = 1;

      // Header.
      ctx.fillStyle = "#e2e8f0";
      ctx.font = "bold 16px system-ui, sans-serif";
      ctx.textAlign = "left"; ctx.textBaseline = "top";
      ctx.fillText(`${st.symbol}  $${st.price.toFixed(2)}`, padL, 8);
      ctx.textAlign = "right"; ctx.fillStyle = "#7f8db3";
      ctx.fillText(`Day ${s.day}/${s.maxDays}`, W - padR, 8);
    });

    (canvas as unknown as { __cleanup?: () => void }).__cleanup = () => { loop.stop(); surface.dispose(); };
    loop.start();
  }, [age, rerender]);

  useEffect(() => () => {
    const c = canvasRef.current as unknown as { __cleanup?: () => void } | null;
    c?.__cleanup?.();
  }, []);

  function nextDay() {
    const s = stateRef.current;
    if (s.over) return;
    // Apply any pending news shock, then evolve each stock.
    for (const st of s.stocks) {
      const move = st.drift + st.vol * gaussian() + st.shock;
      st.shock = 0;
      st.price = Math.max(1, +(st.price * (1 + move)).toFixed(2));
      st.history.push(st.price);
    }
    s.day += 1;

    // Maybe generate a news headline that hits a random stock next day.
    if (Math.random() < 0.5 && s.day < s.maxDays) {
      const st = s.stocks[Math.floor(Math.random() * s.stocks.length)];
      const h = HEADLINES[Math.floor(Math.random() * HEADLINES.length)];
      st.shock = h.impact;
      s.news = { text: h.text(st.name), symbol: st.symbol, impact: h.impact };
    } else {
      s.news = null;
    }
    s.tip = TIPS[Math.floor(Math.random() * TIPS.length)];

    if (s.day >= s.maxDays) {
      s.over = true;
      const worth = Math.round(netWorth());
      try {
        const b = Math.max(worth, Number(localStorage.getItem("aoep_stocktrader_best") || 0));
        localStorage.setItem("aoep_stocktrader_best", String(b));
        setBest(b);
      } catch { /* */ }
      setOver(true); setRunning(false);
    }
    rerender();
  }

  function buy(qty: number) {
    const s = stateRef.current;
    const st = s.stocks.find((x) => x.symbol === s.selected);
    if (!st || s.over) return;
    const affordable = Math.min(qty, Math.floor(s.cash / st.price));
    if (affordable <= 0) return;
    s.cash -= affordable * st.price;
    s.shares[st.symbol] = (s.shares[st.symbol] || 0) + affordable;
    rerender();
  }

  function sell(qty: number) {
    const s = stateRef.current;
    const st = s.stocks.find((x) => x.symbol === s.selected);
    if (!st || s.over) return;
    const held = s.shares[st.symbol] || 0;
    const q = Math.min(qty, held);
    if (q <= 0) return;
    s.cash += q * st.price;
    s.shares[st.symbol] = held - q;
    rerender();
  }

  function buyMax() {
    const s = stateRef.current;
    const st = s.stocks.find((x) => x.symbol === s.selected);
    if (!st) return;
    buy(Math.floor(s.cash / st.price));
  }

  const s = stateRef.current;
  const selStock = s.stocks.find((x) => x.symbol === s.selected) || s.stocks[0];
  const worth = netWorth();
  const startWorth = START_CASH;
  const pnl = worth - startWorth;
  const base = baselineWorth();

  return (
    <main style={{ maxWidth: 900, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>📊 Stock Trader</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
        <Link href="/rewards">Rewards</Link>
      </div>
      <p className="muted">
        Learn investing risk-free. Trade three companies over {ageDays(age)} days, react to news,
        and try to beat a passive buy &amp; hold portfolio. Start with ${START_CASH}.
      </p>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
        <span className="muted">Age:</span>
        {(["kids", "tween", "teen", "adult"] as Age[]).map((a) => (
          <button key={a} onClick={() => setAge(a)} disabled={running}
            style={{ opacity: age === a ? 1 : 0.55, fontWeight: age === a ? 700 : 400 }}>
            {a}
          </button>
        ))}
        <span className="muted" style={{ marginLeft: "auto" }}>Best net worth: ${best}</span>
      </div>

      <div style={{ position: "relative", width: "100%", aspectRatio: "16 / 8", borderRadius: 14, overflow: "hidden", border: "1px solid #1e293b" }}>
        <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block" }} />
        {!running && (
          <div style={{
            position: "absolute", inset: 0, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", gap: 12,
            background: "rgba(10,16,32,0.8)", color: "#fff", textAlign: "center", padding: 16,
          }}>
            {over && (
              <div>
                <div style={{ fontSize: 22, fontWeight: 700 }}>
                  Final net worth: ${Math.round(worth)}
                </div>
                <div style={{ marginTop: 6, color: pnl >= 0 ? "#34d399" : "#f87171" }}>
                  {pnl >= 0 ? "▲" : "▼"} {pnl >= 0 ? "+" : ""}{Math.round(pnl)} ({((pnl / startWorth) * 100).toFixed(1)}%) vs your $1000 start
                </div>
                <div style={{ marginTop: 4, color: worth >= base ? "#34d399" : "#fbbf24", fontSize: 14 }}>
                  {worth >= base
                    ? `🏆 You beat buy & hold ($${Math.round(base)})!`
                    : `📚 Buy & hold made $${Math.round(base)} — hard to beat the market!`}
                </div>
              </div>
            )}
            <button onClick={start} style={{ background: "#0ea5e9", color: "#fff", padding: "12px 28px", fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer" }}>
              {over ? "Trade again" : "▶ Start trading"}
            </button>
          </div>
        )}
      </div>

      {running && (
        <>
          {/* Ticker row */}
          <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
            {s.stocks.map((st) => {
              const prev = st.history[st.history.length - 2] ?? st.price;
              const chg = ((st.price - prev) / prev) * 100;
              const held = s.shares[st.symbol] || 0;
              return (
                <button key={st.symbol} onClick={() => { s.selected = st.symbol; rerender(); }}
                  style={{
                    flex: "1 1 140px", textAlign: "left", padding: 10, borderRadius: 10,
                    border: s.selected === st.symbol ? `2px solid ${st.color}` : "1px solid var(--border)",
                    background: s.selected === st.symbol ? "rgba(255,255,255,0.04)" : "transparent",
                  }}>
                  <div style={{ fontWeight: 700 }}>{st.symbol} <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>{st.name}</span></div>
                  <div>${st.price.toFixed(2)} <span style={{ color: chg >= 0 ? "#16a34a" : "#dc2626", fontSize: 12 }}>{chg >= 0 ? "▲" : "▼"}{Math.abs(chg).toFixed(1)}%</span></div>
                  <div className="muted" style={{ fontSize: 12 }}>You hold: {held}</div>
                </button>
              );
            })}
          </div>

          {/* Portfolio + actions */}
          <div className="card" style={{ marginTop: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
              <div><span className="muted">Cash:</span> <strong>${s.cash.toFixed(2)}</strong></div>
              <div><span className="muted">Net worth:</span> <strong>${worth.toFixed(2)}</strong></div>
              <div style={{ color: pnl >= 0 ? "#16a34a" : "#dc2626" }}>
                {pnl >= 0 ? "▲ +" : "▼ "}{pnl.toFixed(2)} ({((pnl / startWorth) * 100).toFixed(1)}%)
              </div>
            </div>
            <div className="row" style={{ gap: 8, marginTop: 12, flexWrap: "wrap" }}>
              <button onClick={() => buy(1)} style={{ background: "#16a34a", color: "#fff" }}>Buy 1 {selStock.symbol}</button>
              <button onClick={() => buy(10)} style={{ background: "#16a34a", color: "#fff" }}>Buy 10</button>
              <button onClick={buyMax} style={{ background: "#15803d", color: "#fff" }}>Buy max</button>
              <button onClick={() => sell(1)} style={{ background: "#dc2626", color: "#fff" }}>Sell 1</button>
              <button onClick={() => sell(10)} style={{ background: "#dc2626", color: "#fff" }}>Sell 10</button>
              <button onClick={() => sell((s.shares[selStock.symbol] || 0))} style={{ background: "#b91c1c", color: "#fff" }}>Sell all</button>
              <button onClick={nextDay} style={{ marginLeft: "auto", background: "#0ea5e9", color: "#fff", fontWeight: 700, padding: "8px 20px" }}>
                Next day ▶
              </button>
            </div>
          </div>

          {/* News + lesson */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 10 }}>
            <div className="card" style={{ margin: 0, minHeight: 64 }}>
              <div className="muted" style={{ fontSize: 12 }}>📰 Market news</div>
              <div style={{ marginTop: 4 }}>{s.news ? s.news.text : "Quiet day — no major headlines."}</div>
            </div>
            <div className="card" style={{ margin: 0, minHeight: 64, background: "rgba(14,165,233,0.06)" }}>
              <div className="muted" style={{ fontSize: 12 }}>💡 Investing tip</div>
              <div style={{ marginTop: 4 }}>{s.tip}</div>
            </div>
          </div>
        </>
      )}
    </main>
  );
}
