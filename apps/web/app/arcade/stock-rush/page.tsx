"use client";

// Stock Rush — Learn investing by trading a simulated stock against an AI
// opponent. Candlestick chart scrolls right. You and the AI each start with
// $1000. Buy/sell to beat the AI's portfolio over 60 seconds. Educational
// tooltips explain each market concept as it appears. Canvas-based.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { GameLoop, Particles, Surface, clamp, rand, roundRect } from "../../lib/gameEngine2d";

// ─── Types ────────────────────────────────────────────────────────────────────

type Candle = {
  open: number; close: number; high: number; low: number;
};

type Trade = { type: "buy" | "sell"; price: number; time: number };

type TipEntry = { text: string; time: number };

type StockState = {
  price: number;
  candles: Candle[];
  currentCandle: Candle;
  candleTimer: number;
  playerCash: number;
  playerShares: number;
  aiCash: number;
  aiShares: number;
  trades: Trade[];
  aiTrades: Trade[];
  tips: TipEntry[];
  timeLeft: number;
  t: number;
  over: boolean;
  // AI decision cooldown
  aiCooldown: number;
  // Trend mode
  trend: number; // -1..+1 persistent drift
  trendTimer: number;
  volatility: number;
};

// ─── Market simulation ────────────────────────────────────────────────────────

function initState(): StockState {
  const startPrice = 100 + Math.random() * 50;
  const startCandle: Candle = { open: startPrice, close: startPrice, high: startPrice, low: startPrice };
  return {
    price: startPrice,
    candles: Array.from({ length: 20 }, () => startCandle),
    currentCandle: { ...startCandle },
    candleTimer: 0,
    playerCash: 1000, playerShares: 0,
    aiCash: 1000, aiShares: 0,
    trades: [], aiTrades: [], tips: [],
    timeLeft: 60, t: 0,
    over: false,
    aiCooldown: 3 + Math.random() * 2,
    trend: (Math.random() - 0.5) * 0.4,
    trendTimer: 5 + Math.random() * 10,
    volatility: 0.8 + Math.random() * 0.8,
  };
}

function stepMarket(s: StockState, dt: number): void {
  s.t += dt;
  s.timeLeft = Math.max(0, s.timeLeft - dt);
  s.trendTimer -= dt;
  if (s.trendTimer <= 0) {
    s.trend = clamp(s.trend + (Math.random() - 0.5) * 0.5, -0.9, 0.9);
    s.volatility = clamp(s.volatility + (Math.random() - 0.5) * 0.3, 0.4, 2.0);
    s.trendTimer = 4 + Math.random() * 10;
  }
  // Price random walk with trend
  const drift = s.trend * 0.6 * dt;
  const noise = (Math.random() - 0.5) * s.volatility * 2.5 * dt;
  const change = (drift + noise) * s.price;
  s.price = clamp(s.price + change, 5, 500);

  // Update current candle
  s.currentCandle.close = s.price;
  s.currentCandle.high = Math.max(s.currentCandle.high, s.price);
  s.currentCandle.low = Math.min(s.currentCandle.low, s.price);

  // Advance candle every 2.5s
  s.candleTimer += dt;
  if (s.candleTimer >= 2.5) {
    s.candles.push({ ...s.currentCandle });
    if (s.candles.length > 30) s.candles.shift();
    s.currentCandle = { open: s.price, close: s.price, high: s.price, low: s.price };
    s.candleTimer = 0;
  }
}

// ─── Education tips ───────────────────────────────────────────────────────────

const TIPS = [
  "Candles: green = price rose, red = price fell.",
  "Buy low, sell high — the core trading idea.",
  "Volatility: big candles = risky but potentially rewarding.",
  "Trend: sustained direction (up or down) helps predict short-term moves.",
  "Portfolio value = cash + (shares × current price).",
  "AI uses a simple momentum strategy: it buys on rises, sells on drops.",
  "Diversification: don't put all cash in at once.",
  "Timing the market is hard — even pros get it wrong often!",
  "A green candle: close > open. A red candle: close < open.",
  "The wicks (thin lines) show the high and low for that period.",
  "Volume and price trends together signal stronger moves.",
  "Selling all shares locks in your profit (or loss).",
];

// ─── AI strategy (simple momentum) ───────────────────────────────────────────

function runAI(s: StockState, dt: number): void {
  s.aiCooldown -= dt;
  if (s.aiCooldown > 0) return;
  s.aiCooldown = 2 + Math.random() * 4;

  // Momentum: look at last 3 candles
  const n = s.candles.length;
  if (n < 3) return;
  const recent = s.candles.slice(n - 3);
  const bullish = recent.filter((c) => c.close > c.open).length >= 2;
  const bearish = recent.filter((c) => c.close < c.open).length >= 2;

  if (bullish && s.aiCash >= s.price) {
    // Buy up to half cash
    const shares = Math.floor((s.aiCash * 0.45) / s.price);
    if (shares > 0) {
      s.aiCash -= shares * s.price;
      s.aiShares += shares;
      s.aiTrades.push({ type: "buy", price: s.price, time: s.t });
    }
  } else if (bearish && s.aiShares > 0) {
    const sell = Math.ceil(s.aiShares * 0.6);
    s.aiCash += sell * s.price;
    s.aiShares -= sell;
    s.aiTrades.push({ type: "sell", price: s.price, time: s.t });
  }
}

// ─── Candle drawing ───────────────────────────────────────────────────────────

function drawCandle(
  ctx: CanvasRenderingContext2D,
  c: Candle,
  x: number,
  chartTop: number,
  chartH: number,
  minP: number,
  maxP: number,
  w: number,
): void {
  const yFor = (p: number) => chartTop + chartH - ((p - minP) / (maxP - minP + 0.01)) * chartH;
  const bull = c.close >= c.open;
  const color = bull ? "#22c55e" : "#ef4444";
  const bodyTop = Math.min(yFor(c.open), yFor(c.close));
  const bodyH = Math.max(2, Math.abs(yFor(c.open) - yFor(c.close)));
  ctx.fillStyle = color;
  ctx.fillRect(x - w / 2, bodyTop, w, bodyH);
  ctx.strokeStyle = color; ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(x, yFor(c.high)); ctx.lineTo(x, bodyTop);
  ctx.moveTo(x, bodyTop + bodyH); ctx.lineTo(x, yFor(c.low));
  ctx.stroke();
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function StockRush() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [running, setRunning] = useState(false);
  const [over, setOver] = useState(false);
  const [playerVal, setPlayerVal] = useState(1000);
  const [aiVal, setAiVal] = useState(1000);
  const [timeLeft, setTimeLeft] = useState(60);
  const [tip, setTip] = useState(TIPS[0]);
  const [shares, setShares] = useState(0);
  const [cash, setCash] = useState(1000);
  const [price, setPrice] = useState(100);
  const [lastAction, setLastAction] = useState("");
  const [won, setWon] = useState(false);

  const stateRef = useRef<StockState | null>(null);
  const actionRef = useRef<"buy" | "sell" | null>(null);
  const tipTimerRef = useRef(0);
  const tipIdxRef = useRef(0);

  const start = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const surface = new Surface(canvas);
    const particles = new Particles();
    const s = initState();
    stateRef.current = s;
    actionRef.current = null;
    tipTimerRef.current = 0; tipIdxRef.current = 0;
    setRunning(true); setOver(false);
    setPlayerVal(1000); setAiVal(1000);
    setTimeLeft(60); setShares(0); setCash(1000); setPrice(Math.round(s.price));
    setLastAction(""); setTip(TIPS[0]);

    const loop = new GameLoop((dt) => {
      if (!stateRef.current) return;
      const st = stateRef.current;
      if (st.over) return;

      stepMarket(st, dt);
      runAI(st, dt);

      // Process player action
      if (actionRef.current === "buy" && st.playerCash >= st.price) {
        const maxShares = Math.floor(st.playerCash / st.price);
        const buyN = Math.max(1, Math.floor(maxShares * 0.25));
        st.playerCash -= buyN * st.price;
        st.playerShares += buyN;
        st.trades.push({ type: "buy", price: st.price, time: st.t });
        particles.burst(surface.width * 0.3, surface.height * 0.55, "#22c55e", 12, { speed: 100 });
        setLastAction(`Bought ${buyN} @ $${st.price.toFixed(1)}`);
      } else if (actionRef.current === "sell" && st.playerShares > 0) {
        const sellN = Math.max(1, Math.floor(st.playerShares * 0.5));
        st.playerCash += sellN * st.price;
        st.playerShares -= sellN;
        st.trades.push({ type: "sell", price: st.price, time: st.t });
        particles.burst(surface.width * 0.3, surface.height * 0.55, "#f59e0b", 12, { speed: 100 });
        setLastAction(`Sold ${sellN} @ $${st.price.toFixed(1)}`);
      }
      actionRef.current = null;

      // Update React UI state
      const pv = st.playerCash + st.playerShares * st.price;
      const av = st.aiCash + st.aiShares * st.price;
      setPlayerVal(Math.round(pv));
      setAiVal(Math.round(av));
      setTimeLeft(Math.ceil(st.timeLeft));
      setShares(st.playerShares);
      setCash(Math.round(st.playerCash));
      setPrice(Math.round(st.price * 10) / 10);

      // Tip rotation every 10s
      tipTimerRef.current += dt;
      if (tipTimerRef.current > 10) {
        tipTimerRef.current = 0;
        tipIdxRef.current = (tipIdxRef.current + 1) % TIPS.length;
        setTip(TIPS[tipIdxRef.current]);
      }

      if (st.timeLeft <= 0) {
        st.over = true;
        loop.stop();
        cleanup();
        setOver(true); setRunning(false);
        setWon(pv >= av);
        return;
      }

      // ── render ──────────────────────────────────────────────────────────────
      const { ctx } = surface;
      const W = surface.width, H = surface.height;

      // Background
      const bg = ctx.createLinearGradient(0, 0, 0, H);
      bg.addColorStop(0, "#0a0e1a"); bg.addColorStop(1, "#0d1b2a");
      ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);

      // Chart area
      const chartTop = 50, chartH = H * 0.52;
      const candles = [...st.candles, st.currentCandle];
      const prices = candles.flatMap((c) => [c.high, c.low]);
      const minP = Math.min(...prices) * 0.995;
      const maxP = Math.max(...prices) * 1.005;
      const candleW = Math.max(5, W / candles.length - 2);
      const spacing = W / candles.length;

      // Price axis
      ctx.fillStyle = "#475569"; ctx.font = "10px monospace";
      ctx.textAlign = "right";
      const yFor = (p: number) => chartTop + chartH - ((p - minP) / (maxP - minP + 0.01)) * chartH;
      for (let i = 0; i <= 4; i++) {
        const p = minP + (maxP - minP) * (i / 4);
        const y = yFor(p);
        ctx.fillText(`$${p.toFixed(0)}`, W - 4, y + 4);
        ctx.strokeStyle = "rgba(71,85,105,0.3)"; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W - 44, y); ctx.stroke();
      }

      // Candles
      candles.forEach((c, i) => {
        const x = spacing * i + spacing / 2;
        drawCandle(ctx, c, x, chartTop, chartH, minP, maxP, candleW);
      });

      // Current price line
      const curY = yFor(st.price);
      ctx.strokeStyle = "#38bdf8"; ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath(); ctx.moveTo(0, curY); ctx.lineTo(W - 44, curY); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "#38bdf8"; ctx.font = "bold 11px monospace";
      ctx.textAlign = "left";
      ctx.fillText(`$${st.price.toFixed(1)}`, 4, curY - 4);

      // Portfolio bars
      const barY = chartTop + chartH + 16;
      const barH = 14;
      const maxVal = Math.max(1000, pv, av) * 1.05;
      const barW = (W - 60) * 0.48;
      // Player bar
      roundRect(ctx, 8, barY, (pv / maxVal) * barW, barH, 4);
      ctx.fillStyle = pv >= 1000 ? "#22c55e" : "#ef4444"; ctx.fill();
      ctx.fillStyle = "#fff"; ctx.font = "bold 10px system-ui"; ctx.textAlign = "left";
      ctx.fillText(`You $${Math.round(pv)}`, 8, barY + barH + 12);
      // AI bar
      const aiBarX = W / 2 + 4;
      roundRect(ctx, aiBarX, barY, (av / maxVal) * barW, barH, 4);
      ctx.fillStyle = "#7c3aed"; ctx.fill();
      ctx.fillText(`AI $${Math.round(av)}`, aiBarX, barY + barH + 12);

      // Mark AI trades
      st.aiTrades.slice(-3).forEach((tr) => {
        const trX = clamp((tr.time / (60 - st.timeLeft + tr.time)) * W * 0.9, 10, W - 50);
        const trY = yFor(tr.price);
        ctx.fillStyle = tr.type === "buy" ? "#7c3aed" : "#e879f9";
        ctx.beginPath(); ctx.arc(trX, trY, 5, 0, Math.PI * 2); ctx.fill();
      });

      // Player trades
      st.trades.slice(-5).forEach((tr) => {
        const trX = clamp((tr.time / (60 - st.timeLeft + tr.time)) * W * 0.9, 10, W - 50);
        const trY = yFor(tr.price);
        ctx.fillStyle = tr.type === "buy" ? "#22c55e" : "#f59e0b";
        ctx.beginPath();
        ctx.moveTo(trX, trY - 7); ctx.lineTo(trX + 5, trY + 4); ctx.lineTo(trX - 5, trY + 4);
        ctx.closePath(); ctx.fill();
      });

      particles.update(dt); particles.draw(ctx);

      // Timer
      const tl = Math.ceil(st.timeLeft);
      ctx.fillStyle = tl <= 10 ? "#ef4444" : "#94a3b8";
      ctx.font = `bold 20px system-ui`;
      ctx.textAlign = "center"; ctx.textBaseline = "top";
      ctx.fillText(`${tl}s`, W / 2, 8);
      ctx.textBaseline = "alphabetic";
    });

    const cleanup = () => { loop.stop(); surface.dispose(); };
    (canvas as unknown as { __cleanup?: () => void }).__cleanup = cleanup;
    loop.start();
  }, []);

  useEffect(() => () => {
    const c = canvasRef.current as unknown as { __cleanup?: () => void } | null;
    c?.__cleanup?.();
  }, []);

  const buy = useCallback(() => { actionRef.current = "buy"; }, []);
  const sell = useCallback(() => { actionRef.current = "sell"; }, []);

  const playerPct = playerVal >= 1000 ? `+${playerVal - 1000}` : `${playerVal - 1000}`;
  const aiPct = aiVal >= 1000 ? `+${aiVal - 1000}` : `${aiVal - 1000}`;

  return (
    <main style={{ maxWidth: 600, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 8 }}>
        <h1 style={{ margin: 0 }}>📈 Stock Rush</h1>
        <Link href="/arcade" style={{ marginLeft: "auto" }}>← Arcade</Link>
      </div>
      <p className="muted" style={{ marginTop: 0 }}>
        Trade a simulated stock against the AI. Start with $1,000 each. 60 seconds. Highest portfolio wins!
      </p>

      <div style={{ position: "relative", width: "100%", aspectRatio: "16/10", borderRadius: 14, overflow: "hidden", border: "2px solid #1e3a5f" }}>
        <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block" }} />
        {!running && (
          <div style={{
            position: "absolute", inset: 0, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", gap: 14,
            background: "rgba(10,14,26,0.82)", color: "#fff",
          }}>
            {over ? (
              <>
                <div style={{ fontSize: 28 }}>{won ? "🏆" : "🤖"}</div>
                <div style={{ fontSize: 20, fontWeight: 700 }}>{won ? "You beat the AI!" : "AI wins this round!"}</div>
                <div className="muted">You: ${playerVal} ({playerPct}) · AI: ${aiVal} ({aiPct})</div>
              </>
            ) : (
              <>
                <div style={{ fontSize: 36 }}>📈</div>
                <div style={{ fontWeight: 700, fontSize: 18 }}>Stock Rush</div>
                <div className="muted" style={{ fontSize: 13, textAlign: "center", maxWidth: 320 }}>
                  Buy when prices look low, sell when high. Beat the AI portfolio in 60 seconds!
                </div>
              </>
            )}
            <button onClick={start} style={{ background: "#0ea5e9", color: "#fff", padding: "12px 28px", fontSize: 17, borderRadius: 10, border: 0, cursor: "pointer" }}>
              {over ? "Play again" : "▶ Play"}
            </button>
          </div>
        )}
      </div>

      {/* Trading controls */}
      {running && (
        <div style={{ marginTop: 10 }}>
          <div style={{ display: "flex", gap: 10, alignItems: "stretch", flexWrap: "wrap" }}>
            {/* Stats */}
            <div className="card" style={{ flex: 1, minWidth: 140, padding: "10px 14px", margin: 0 }}>
              <div style={{ fontSize: 12, color: "#94a3b8" }}>Your portfolio</div>
              <div style={{ fontWeight: 700, fontSize: 18 }}>${playerVal}</div>
              <div style={{ fontSize: 12, color: "#94a3b8" }}>Cash ${cash} · {shares} shares</div>
              <div style={{ fontSize: 12, color: "#94a3b8" }}>Price: ${price}</div>
            </div>
            <div className="card" style={{ flex: 1, minWidth: 140, padding: "10px 14px", margin: 0 }}>
              <div style={{ fontSize: 12, color: "#94a3b8" }}>AI portfolio</div>
              <div style={{ fontWeight: 700, fontSize: 18, color: "#a78bfa" }}>${aiVal}</div>
              <div style={{ fontSize: 12, color: "#7c3aed" }}>⏱ {timeLeft}s left</div>
              {lastAction && <div style={{ fontSize: 11, color: "#6ee7b7", marginTop: 4 }}>{lastAction}</div>}
            </div>
          </div>
          <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
            <button onClick={buy} disabled={cash < price}
              style={{ flex: 1, padding: "14px 0", fontSize: 16, fontWeight: 700, background: "#16a34a", color: "#fff", borderRadius: 10, border: 0, cursor: cash >= price ? "pointer" : "not-allowed", opacity: cash >= price ? 1 : 0.5 }}>
              📥 Buy 25%
            </button>
            <button onClick={sell} disabled={shares === 0}
              style={{ flex: 1, padding: "14px 0", fontSize: 16, fontWeight: 700, background: "#dc2626", color: "#fff", borderRadius: 10, border: 0, cursor: shares > 0 ? "pointer" : "not-allowed", opacity: shares > 0 ? 1 : 0.5 }}>
              📤 Sell 50%
            </button>
          </div>
          {/* Tip */}
          <div style={{ marginTop: 8, padding: "8px 12px", background: "rgba(14,165,233,0.1)", borderRadius: 8, borderLeft: "3px solid #0ea5e9", fontSize: 12, color: "#7dd3fc" }}>
            💡 {tip}
          </div>
        </div>
      )}

      {!running && !over && (
        <div className="card" style={{ marginTop: 8 }}>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>How to play</div>
          <ul className="muted" style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
            <li>Candlestick chart shows price history (green = up, red = down)</li>
            <li>Press <strong>Buy 25%</strong> to spend 25% of your cash on shares</li>
            <li>Press <strong>Sell 50%</strong> to sell half your shares for cash</li>
            <li>The AI uses a momentum strategy — try to out-trade it!</li>
            <li>Your portfolio = cash + shares × current price</li>
          </ul>
        </div>
      )}
    </main>
  );
}
