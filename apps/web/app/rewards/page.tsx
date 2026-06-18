"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getRewards,
  getRewardsCatalog,
  getToken,
  redeemReward,
  type RewardPrize,
  type RewardsSummary,
} from "../lib/api";

export default function RewardsPage() {
  const [summary, setSummary] = useState<RewardsSummary | null>(null);
  const [catalog, setCatalog] = useState<RewardPrize[]>([]);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);

  async function refresh() {
    try {
      setSummary(await getRewards());
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    setLoggedIn(Boolean(getToken()));
    getRewardsCatalog().then((c) => setCatalog(c.prizes)).catch(() => setCatalog([]));
    if (getToken()) refresh();
  }, []);

  async function onRedeem(p: RewardPrize) {
    setMsg(""); setError("");
    try {
      const r = await redeemReward(p.id);
      if (r.redemption.voucher_code) {
        setMsg(`Redeemed "${p.name}" — voucher ${r.redemption.voucher_code}. Balance: ${r.balance} pts.`);
      } else {
        setMsg(`Entered the ${String(r.redemption.detail.prize)} raffle (entry ${r.redemption.raffle_entry_id}). Balance: ${r.balance} pts.`);
      }
      await refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  const balance = summary?.balance ?? 0;

  return (
    <main className="container">
      <h1>Rewards</h1>
      <p className="muted">
        Earn points every time you pass a course (more for harder levels, higher
        scores, and hands-on labs). Redeem them for class discounts or enter
        raffles for prizes. See the <Link href="/legal">Rewards &amp; Sweepstakes rules</Link> (no purchase necessary).
      </p>

      {!loggedIn && (
        <div className="card"><p>Please <Link href="/login">sign in</Link> to earn and redeem points.</p></div>
      )}

      {loggedIn && (
        <div className="card" style={{ borderColor: "#34d399" }}>
          <h2 style={{ margin: 0 }}>{balance} points</h2>
          <div className="muted">Your current balance.</div>
        </div>
      )}

      {msg && <div className="card" style={{ borderColor: "#34d399" }}><div className="muted">{msg}</div></div>}
      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}

      <h3>Redeem</h3>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 12 }}>
        {catalog.map((p) => {
          const affordable = loggedIn && balance >= p.cost_points;
          return (
            <div className="card" key={p.id}>
              <strong>{p.name}</strong>
              <div className="muted" style={{ fontSize: 12, textTransform: "capitalize" }}>{p.kind}</div>
              <p style={{ margin: "6px 0" }}>{p.cost_points} pts{p.kind === "raffle" ? " / entry" : ""}</p>
              <button onClick={() => onRedeem(p)} disabled={!affordable}>
                {p.kind === "raffle" ? "Enter raffle" : "Redeem"}
              </button>
              {!affordable && loggedIn && (
                <div className="muted" style={{ fontSize: 11 }}>Need {p.cost_points - balance} more pts</div>
              )}
            </div>
          );
        })}
      </div>

      {loggedIn && summary && summary.ledger.length > 0 && (
        <div className="card">
          <h3>Recent activity</h3>
          <ul>
            {summary.ledger.slice().reverse().map((e, i) => (
              <li key={i}>
                <span style={{ color: e.delta >= 0 ? "#16a34a" : "#d97706" }}>
                  {e.delta >= 0 ? "+" : ""}{e.delta}
                </span>{" "}
                — {e.reason}{e.ref ? ` (${e.ref})` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}
    </main>
  );
}
