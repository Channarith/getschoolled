"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getConsumerPlans,
  getMe,
  getSubscription,
  getToken,
  subscribeToPlan,
  type Account,
  type ConsumerPlan,
  type Subscription,
} from "../lib/api";

function formatUsd(amount: number): string {
  return amount === 0 ? "$0" : `$${amount.toFixed(2)}`;
}

function formatBillingDate(ts: number | null): string {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleDateString(undefined, {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

export default function BillingPage() {
  const [me, setMe] = useState<Account | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [plans, setPlans] = useState<Record<string, ConsumerPlan> | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  async function refresh() {
    const [account, sub, pl] = await Promise.all([
      getMe(),
      getSubscription(),
      getConsumerPlans(),
    ]);
    setMe(account);
    setSubscription(sub);
    setPlans(pl);
  }

  useEffect(() => {
    if (!getToken()) return;
    refresh().catch((e) => setError(String(e)));
  }, []);

  async function pickPlan(tier: string) {
    setBusy(tier);
    setError("");
    try {
      await subscribeToPlan(tier);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy("");
    }
  }

  if (!getToken()) {
    return (
      <main className="container">
        <p>Please <Link href="/login">sign in</Link> to manage billing.</p>
      </main>
    );
  }

  const paidPlans = plans
    ? ["basic", "premium"].map((id) => plans[id]).filter(Boolean)
    : [];

  return (
    <main className="container" style={{ maxWidth: 720 }}>
      <h1>Membership &amp; billing</h1>
      <p className="muted">
        Netflix-style plans — Standard with ads, VIP ad-free. Billed monthly on the
        calendar day you signed up.
      </p>
      {error && <p style={{ color: "#f87171" }}>{error}</p>}

      {me && subscription && (
        <section className="card">
          <h2 style={{ marginTop: 0 }}>Your plan</h2>
          <p>
            <strong>{subscription.display_name}</strong>
            {" · "}
            <span style={{ color: me.membership_class === "vip" ? "#fbbf24" : "#94a3b8" }}>
              {me.membership_class === "vip" ? "VIP member" : "Standard member"}
            </span>
          </p>
          <p className="muted">
            {subscription.price_usd > 0
              ? `${formatUsd(subscription.price_usd)}/month`
              : "Free"}
            {subscription.ads ? " · includes ads" : " · no ads"}
          </p>
          {subscription.billing_anchor_day && (
            <p className="muted">
              Billing day: the {subscription.billing_anchor_day}
              {subscription.billing_anchor_day === 1 ? "st" :
                subscription.billing_anchor_day === 2 ? "nd" :
                subscription.billing_anchor_day === 3 ? "rd" : "th"} of each month
            </p>
          )}
          {subscription.next_billing_at && (
            <p>Next billing date: <strong>{formatBillingDate(subscription.next_billing_at)}</strong></p>
          )}
        </section>
      )}

      {paidPlans.length > 0 && (
        <section className="card" style={{ marginTop: "1rem" }}>
          <h2 style={{ marginTop: 0 }}>Choose your plan</h2>
          <div style={{ display: "grid", gap: 12 }}>
            {paidPlans.map((plan) => (
              <div
                key={plan.tier}
                style={{
                  border: "1px solid #334155",
                  borderRadius: 8,
                  padding: 16,
                  outline: subscription?.tier === plan.tier ? "2px solid #6ea8fe" : "none",
                }}
              >
                <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <strong style={{ fontSize: 18 }}>{plan.display_name}</strong>
                    <div style={{ fontSize: 22, fontWeight: 700, margin: "4px 0" }}>
                      {formatUsd(plan.price_usd)}<span className="muted" style={{ fontSize: 14 }}>/month</span>
                    </div>
                    <p className="muted" style={{ margin: 0 }}>{plan.blurb}</p>
                    <p className="muted" style={{ margin: "6px 0 0", fontSize: 13 }}>
                      {plan.ads ? "With ads" : "No ads"}
                    </p>
                  </div>
                  <button
                    disabled={busy === plan.tier || subscription?.tier === plan.tier}
                    onClick={() => pickPlan(plan.tier)}
                  >
                    {subscription?.tier === plan.tier ? "Current plan" : busy === plan.tier ? "…" : "Select"}
                  </button>
                </div>
              </div>
            ))}
          </div>
          <p className="muted" style={{ marginTop: 12, fontSize: 13 }}>
            <Link href="/account">Back to account</Link>
            {" · "}
            <button type="button" style={{ fontSize: 13 }} disabled={!!busy}
              onClick={() => pickPlan("free")}>Switch to free</button>
          </p>
        </section>
      )}
    </main>
  );
}
