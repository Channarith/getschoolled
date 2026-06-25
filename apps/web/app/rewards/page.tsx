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
import { useT } from "../lib/i18n";

export default function RewardsPage() {
  const { t } = useT();
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
        setMsg(t("rewards.redeemedVoucher", {
          name: p.name, code: r.redemption.voucher_code, balance: r.balance,
        }));
      } else {
        setMsg(t("rewards.raffleEntered", {
          prize: String(r.redemption.detail.prize),
          entry: r.redemption.raffle_entry_id,
          balance: r.balance,
        }));
      }
      await refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  const balance = summary?.balance ?? 0;

  return (
    <main className="container">
      <h1>{t("rewards.title")}</h1>
      <p className="muted">
        {t("rewards.intro")}{" "}
        <Link href="/legal">{t("rewards.rulesLink")}</Link> {t("rewards.noPurchase")}
      </p>

      {!loggedIn && (
        <div className="card">
          <p>
            {t("rewards.signInBefore")}{" "}
            <Link href="/login">{t("profile.signIn")}</Link>{" "}
            {t("rewards.signInAfter")}
          </p>
        </div>
      )}

      {loggedIn && (
        <div className="card" style={{ borderColor: "#34d399" }}>
          <h2 style={{ margin: 0 }}>{t("rewards.points", { balance })}</h2>
          <div className="muted">{t("rewards.balanceDesc")}</div>
        </div>
      )}

      {msg && <div className="card" style={{ borderColor: "#34d399" }}><div className="muted">{msg}</div></div>}
      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}

      <h3>{t("rewards.redeemSection")}</h3>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 12 }}>
        {catalog.map((p) => {
          const affordable = loggedIn && balance >= p.cost_points;
          return (
            <div className="card" key={p.id}>
              <strong>{p.name}</strong>
              <div className="muted" style={{ fontSize: 12, textTransform: "capitalize" }}>{p.kind}</div>
              <p style={{ margin: "6px 0" }}>
                {p.cost_points} pts{p.kind === "raffle" ? t("rewards.perEntry") : ""}
              </p>
              <button onClick={() => onRedeem(p)} disabled={!affordable}>
                {p.kind === "raffle" ? t("rewards.enterRaffle") : t("rewards.redeemBtn")}
              </button>
              {!affordable && loggedIn && (
                <div className="muted" style={{ fontSize: 11 }}>
                  {t("rewards.needMore", { n: p.cost_points - balance })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {loggedIn && summary && summary.ledger.length > 0 && (
        <div className="card">
          <h3>{t("rewards.recentActivity")}</h3>
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
