"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getBillingPlans,
  getLoginHistory,
  getMe,
  getOnboardingStatus,
  getToken,
  type Account,
  type LoginEvent,
} from "../lib/api";

export default function BillingPage() {
  const [me, setMe] = useState<Account | null>(null);
  const [status, setStatus] = useState<Awaited<ReturnType<typeof getOnboardingStatus>> | null>(null);
  const [plans, setPlans] = useState<Record<string, unknown> | null>(null);
  const [events, setEvents] = useState<LoginEvent[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getToken()) return;
    Promise.all([
      getMe(),
      getOnboardingStatus(),
      getBillingPlans(),
      getLoginHistory(),
    ]).then(([account, st, pl, hist]) => {
      setMe(account);
      setStatus(st);
      setPlans(pl);
      setEvents(hist.events);
    }).catch((e) => setError(String(e)));
  }, []);

  if (!getToken()) {
    return (
      <main className="container">
        <p>Please <Link href="/login">sign in</Link> to manage billing.</p>
      </main>
    );
  }

  return (
    <main className="container" style={{ maxWidth: 720 }}>
      <h1>Membership &amp; billing</h1>
      {error && <p style={{ color: "#f87171" }}>{error}</p>}
      {me && (
        <section className="card">
          <h2 style={{ marginTop: 0 }}>Your plan</h2>
          <p>
            <strong>{me.tier}</strong>
            {" · "}
            <span style={{ color: me.membership_class === "vip" ? "#fbbf24" : "#94a3b8" }}>
              {me.membership_class === "vip" ? "VIP member" : "Standard member"}
            </span>
          </p>
          {me.card_last4 && (
            <p className="muted">Card on file: •••• {me.card_last4}</p>
          )}
          {status && !status.billing_validated && status.billing_required && (
            <p>
              <Link href="/onboarding" className="btn primary">Complete payment setup</Link>
            </p>
          )}
        </section>
      )}

      {plans && (
        <section className="card" style={{ marginTop: "1rem" }}>
          <h2 style={{ marginTop: 0 }}>Available plans</h2>
          <pre style={{ fontSize: 12, overflow: "auto" }}>{JSON.stringify(plans, null, 2)}</pre>
        </section>
      )}

      <section className="card" style={{ marginTop: "1rem" }}>
        <h2 style={{ marginTop: 0 }}>Sign-in security</h2>
        <p className="muted" style={{ fontSize: 14 }}>
          Recent sign-ins for your account (IP and device). Report anything unfamiliar to support.
        </p>
        {events.length === 0 ? (
          <p className="muted">No sign-in history yet.</p>
        ) : (
          <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left", color: "#94a3b8" }}>
                <th>When</th><th>OK</th><th>IP</th><th>Device</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev, i) => (
                <tr key={i} style={{ borderTop: "1px solid #334155" }}>
                  <td>{new Date(ev.ts * 1000).toLocaleString()}</td>
                  <td>{ev.success ? "✓" : "✗"}</td>
                  <td>{ev.ip || "—"}</td>
                  <td style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis" }}>
                    {ev.user_agent?.slice(0, 60) || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="card" style={{ marginTop: "1rem" }}>
        <h2 style={{ marginTop: 0 }}>Ad partners</h2>
        <p className="muted" style={{ fontSize: 14 }}>
          Standard members see ads from our configured network (house promos locally;
          Google AdSense, Google Ad Manager, or Meta Audience Network in production).
          Set <code>AD_NETWORK</code> and publisher credentials in cloud config. VIP members are ad-free.
        </p>
      </section>
    </main>
  );
}
