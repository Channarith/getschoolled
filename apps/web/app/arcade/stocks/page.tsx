"use client";

// Market Mogul — a stocks learning game. Watch live-ticking share prices on a
// real canvas chart, buy low and sell high, and grow your net worth before the
// trading period ends. Contextual coaching teaches core investing ideas
// (volatility, diversification, buying above/below the trend, holding vs. panic
// selling). Difficulty (number of stocks, volatility, trading days, starting
// cash) scales with age group (?age=kids|tween|teen|adult). Fully client-side.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

type Age = "kids" | "tween" | "teen" | "adult";

type StockDef = { symbol: string; name: string; color: string; start: number; drift: number; vol: number };
const BASE_STOCKS: StockDef[] = [
  { symbol: "GRN", name: "GreenLeaf Farms", color: "#34d399", start: 20, drift: 0.006, vol: 0.03 },
  { symbol: "TCH", name: "TechNova", color: "#60a5fa", start: 40, drift: 0.012, vol: 0.07 },
  { symbol: "BNK", name: "SafeBank", color: "#facc15", start: 30, drift: 0.003, vol: 0.02 },
  { symbol: "ZAP", name: "ZapCoin", color: "#f472b6", start: 15, drift: 0.0, vol: 0.14 },
];

type Profile = { count: number; days: number; cash: number; volMul: number; tickMs: number };
const PROFILES: Record<Age, Profile> = {
  kids: { count: 1, days: 12, cash: 500, volMul: 0.5, tickMs: 2000 },
  tween: { count: 2, days: 16, cash: 800, volMul: 0.8, tickMs: 1800 },
  teen: { count: 3, days: 20, cash: 1000, volMul: 1.0, tickMs: 1500 },
  adult: { count: 4, days: 24, cash: 1000, volMul: 1.3, tickMs: 1300 },
};

const TIPS = [
  "Diversify: spreading money across stocks softens any single crash.",
  "Buy low, sell high — easy to say, hard to do when emotions run high.",
  "Volatile stocks swing hard: bigger gains, but bigger losses too.",
  "Time in the market usually beats trying to time the market.",
  "Don't panic-sell a dip — check whether the trend is still up.",
  "Your average cost is your break-even line; sell above it for profit.",
];

// Standard-normal via Box–Muller.
function randn(): number {
  let u = 0, v = 0;
  while (u === 0) u = Math.random();
  while (v === 0) v = Math.random();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

type Stock = StockDef & { history: number[] };

export default function MarketMogul() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [age, setAge] = useState<Age>("teen");
  const [running, setRunning] = useState(false);
  const [over, setOver] = useState(false);
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [holdings, setHoldings] = useState<number[]>([]);
  const [avgCost, setAvgCost] = useState<number[]>([]);
  const [cash, setCash] = useState(0);
  const [day, setDay] = useState(0);
  const [sel, setSel] = useState(0);
  const [tip, setTip] = useState(TIPS[0]);
  const [coach, setCoach] = useState("");
  const [best, setBest] = useState(0);
  const [finalWorth, setFinalWorth] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const startCash = useRef(0);

  useEffect(() => {
    try { setBest(Number(localStorage.getItem("aoep_stocks_best") || 0)); } catch { /* */ }
    const q = new URLSearchParams(window.location.search).get("age");
    if (q === "kids" || q === "tween" || q === "teen" || q === "adult") setAge(q);
  }, []);

  const totalDays = PROFILES[age].days;

  const price = (i: number, st = stocks) => st[i]?.history[st[i].history.length - 1] ?? 0;
  const netWorth = useCallback((st: Stock[], hold: number[], c: number) =>
    c + st.reduce((sum, s, i) => sum + (s.history[s.history.length - 1] ?? 0) * (hold[i] ?? 0), 0),
  []);

  const stopTimer = () => { if (timer.current) { clearInterval(timer.current); timer.current = null; } };

  const start = useCallback(() => {
    const prof = PROFILES[age];
    const chosen = BASE_STOCKS.slice(0, prof.count).map((d) => ({
      ...d, vol: d.vol * prof.volMul, history: [d.start],
    }));
    setStocks(chosen);
    setHoldings(Array(chosen.length).fill(0));
    setAvgCost(Array(chosen.length).fill(0));
    setCash(prof.cash);
    startCash.current = prof.cash;
    setDay(0); setSel(0); setOver(false); setFinalWorth(0);
    setCoach(""); setTip(TIPS[Math.floor(Math.random() * TIPS.length)]);
    setRunning(true);

    stopTimer();
    timer.current = setInterval(() => {
      setStocks((prev) => {
        const nxt = prev.map((s) => {
          const last = s.history[s.history.length - 1];
          const change = s.drift + s.vol * randn();
          const np = Math.max(1, +(last * (1 + change)).toFixed(2));
          return { ...s, history: [...s.history, np] };
        });
        return nxt;
      });
      setDay((d) => {
        const nd = d + 1;
        if (nd % 4 === 0) setTip(TIPS[Math.floor(Math.random() * TIPS.length)]);
        if (nd >= prof.days) {
          stopTimer();
          setRunning(false); setOver(true);
        }
        return nd;
      });
    }, prof.tickMs);
  }, [age]);

  // Finalize net worth + best score when the game ends.
  useEffect(() => {
    if (!over || stocks.length === 0) return;
    const w = Math.round(netWorth(stocks, holdings, cash));
    setFinalWorth(w);
    try {
      const b = Math.max(w, Number(localStorage.getItem("aoep_stocks_best") || 0));
      localStorage.setItem("aoep_stocks_best", String(b)); setBest(b);
    } catch { /* */ }
  }, [over, stocks, holdings, cash, netWorth]);

  useEffect(() => () => stopTimer(), []);

  const buy = (qty: number) => {
    if (!running) return;
    const p = price(sel);
    const cost = p * qty;
    if (cash < cost) { setCoach("Not enough cash for that buy."); return; }
    setCash((c) => c - cost);
    setHoldings((h) => { const n = [...h]; n[sel] += qty; return n; });
    setAvgCost((a) => {
      const n = [...a]; const prevSh = holdings[sel];
      n[sel] = prevSh + qty > 0 ? (a[sel] * prevSh + cost) / (prevSh + qty) : 0;
      return n;
    });
    const hist = stocks[sel].history;
    const recent = hist.slice(-5);
    const avg = recent.reduce((s, x) => s + x, 0) / recent.length;
    setCoach(p > avg * 1.05
      ? "⚠️ You bought above the recent trend — that's buying high."
      : "👍 Nice — you bought near or below the recent average.");
  };

  const sell = (qty: number) => {
    if (!running) return;
    if (holdings[sel] < qty) { setCoach("You don't own that many shares."); return; }
    const p = price(sel);
    setCash((c) => c + p * qty);
    setHoldings((h) => { const n = [...h]; n[sel] -= qty; return n; });
    const ac = avgCost[sel];
    setCoach(p >= ac
      ? `✅ Sold for a profit (${((p / ac - 1) * 100).toFixed(0)}% above your cost).`
      : `📉 Sold below your average cost — a realized loss.`);
  };

  // Draw the selected stock's price chart whenever prices change.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || stocks.length === 0) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const rect = canvas.getBoundingClientRect();
    const W = Math.max(1, Math.round(rect.width)), H = Math.max(1, Math.round(rect.height));
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const s = stocks[sel];
    const hist = s.history;
    const pad = 34;
    ctx.fillStyle = "#0b1220"; ctx.fillRect(0, 0, W, H);

    const lo = Math.min(...hist) * 0.98, hi = Math.max(...hist) * 1.02;
    const span = Math.max(0.01, hi - lo);
    const N = Math.max(2, totalDays);
    const xAt = (i: number) => pad + (i / (N - 1)) * (W - pad * 2);
    const yAt = (v: number) => H - pad - ((v - lo) / span) * (H - pad * 2);

    // grid
    ctx.strokeStyle = "rgba(148,163,184,0.15)"; ctx.lineWidth = 1;
    ctx.fillStyle = "#64748b"; ctx.font = "11px system-ui, sans-serif"; ctx.textAlign = "right";
    for (let g = 0; g <= 4; g++) {
      const v = lo + (span * g) / 4; const y = yAt(v);
      ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(W - pad, y); ctx.stroke();
      ctx.fillText(`$${v.toFixed(0)}`, pad - 4, y + 3);
    }

    // avg-cost line
    if ((holdings[sel] ?? 0) > 0 && avgCost[sel] > 0 && avgCost[sel] >= lo && avgCost[sel] <= hi) {
      ctx.strokeStyle = "rgba(250,204,21,0.7)"; ctx.setLineDash([6, 4]);
      const y = yAt(avgCost[sel]);
      ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(W - pad, y); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "#facc15"; ctx.textAlign = "left";
      ctx.fillText(`avg $${avgCost[sel].toFixed(2)}`, pad + 4, y - 4);
    }

    // price line
    const up = hist[hist.length - 1] >= (hist[hist.length - 2] ?? hist[0]);
    ctx.strokeStyle = up ? "#34d399" : "#f87171"; ctx.lineWidth = 2.5;
    ctx.beginPath();
    hist.forEach((v, i) => { const x = xAt(i), y = yAt(v); i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y); });
    ctx.stroke();

    // current dot + label
    const cx = xAt(hist.length - 1), cy = yAt(hist[hist.length - 1]);
    ctx.fillStyle = s.color; ctx.beginPath(); ctx.arc(cx, cy, 5, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#e2e8f0"; ctx.font = "bold 16px system-ui, sans-serif"; ctx.textAlign = "left";
    ctx.fillText(`${s.symbol}  $${hist[hist.length - 1].toFixed(2)}`, pad, 20);
  }, [stocks, sel, holdings, avgCost, totalDays]);

  const worth = stocks.length ? Math.round(netWorth(stocks, holdings, cash)) : 0;
  const displayWorth = over ? finalWorth : worth;
  const profit = displayWorth - startCash.current;

  return (
    <main style={{ maxWidth: 820, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0 }}>📈 Market Mogul</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
        <Link href="/rewards">Rewards</Link>
      </div>
      <p className="muted">
        Learn investing by trading a simulated market. Buy low, sell high, diversify,
        and grow your net worth before the trading period ends.
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

      <div style={{ position: "relative", width: "100%", aspectRatio: "16 / 9", borderRadius: 14, overflow: "hidden", border: "1px solid #1e293b" }}>
        <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block" }} />
        {!running && (
          <div style={{
            position: "absolute", inset: 0, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", gap: 12,
            background: "rgba(11,18,32,0.8)", color: "#fff", textAlign: "center", padding: 16,
          }}>
            {over && (
              <div>
                <div style={{ fontSize: 22, fontWeight: 700 }}>Market closed!</div>
                <div style={{ fontSize: 18, marginTop: 6, color: profit >= 0 ? "#34d399" : "#f87171" }}>
                  Net worth ${finalWorth} · {profit >= 0 ? "+" : ""}{profit} ({((profit / (startCash.current || 1)) * 100).toFixed(1)}%)
                </div>
              </div>
            )}
            <button onClick={start} style={{ background: "#059669", color: "#fff", padding: "12px 28px", fontSize: 18, borderRadius: 10, border: 0, cursor: "pointer" }}>
              {over ? "Trade again" : "▶ Open the market"}
            </button>
          </div>
        )}
      </div>

      {running && (
        <>
          <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
            <span><b>Day</b> {day}/{totalDays}</span>
            <span><b>Cash</b> ${cash.toFixed(2)}</span>
            <span><b>Net worth</b> ${worth} <span style={{ color: profit >= 0 ? "#16a34a" : "#dc2626" }}>({profit >= 0 ? "+" : ""}{profit})</span></span>
          </div>

          <div className="row" style={{ gap: 8, flexWrap: "wrap", marginTop: 10 }}>
            {stocks.map((s, i) => {
              const p = s.history[s.history.length - 1];
              const prev = s.history[s.history.length - 2] ?? p;
              const chg = ((p / prev - 1) * 100);
              return (
                <button key={s.symbol} onClick={() => setSel(i)}
                  style={{ opacity: sel === i ? 1 : 0.6, border: sel === i ? `2px solid ${s.color}` : "1px solid var(--border)", textAlign: "left", minWidth: 150 }}>
                  <div style={{ fontWeight: 700 }}>{s.symbol} · ${p.toFixed(2)}</div>
                  <div style={{ fontSize: 12, color: chg >= 0 ? "#16a34a" : "#dc2626" }}>{chg >= 0 ? "▲" : "▼"} {Math.abs(chg).toFixed(1)}% · own {holdings[i]}</div>
                </button>
              );
            })}
          </div>

          <div className="row" style={{ gap: 8, flexWrap: "wrap", marginTop: 10 }}>
            <button onClick={() => buy(1)} style={{ background: "#16a34a", color: "#fff" }}>Buy 1</button>
            <button onClick={() => buy(10)} style={{ background: "#16a34a", color: "#fff" }}>Buy 10</button>
            <button onClick={() => sell(1)} style={{ background: "#dc2626", color: "#fff" }}>Sell 1</button>
            <button onClick={() => sell(10)} style={{ background: "#dc2626", color: "#fff" }}>Sell 10</button>
          </div>

          {coach && <div className="card" style={{ marginTop: 10, padding: 10 }}><div style={{ fontSize: 14 }}>{coach}</div></div>}
          <div className="muted" style={{ marginTop: 8, fontSize: 13 }}>💡 {tip}</div>
        </>
      )}
    </main>
  );
}
