"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  completeOnboarding,
  getMe,
  getOnboardingStatus,
  getToken,
  selectOnboardingPlan,
  submitOnboardingBilling,
  submitOnboardingProfile,
} from "../lib/api";

const PLANS = [
  { id: "free", label: "Free", price: "$0", class: "standard", blurb: "English classes with ads" },
  { id: "basic", label: "Basic", price: "$9/mo", class: "standard", blurb: "5 languages, with ads" },
  { id: "pro", label: "Pro", price: "$19/mo", class: "vip", blurb: "All languages, ad-free, solo classes" },
  { id: "premium", label: "Premium", price: "$29/mo", class: "vip", blurb: "Everything + analytics" },
] as const;

const STEPS = ["Your info", "Choose plan", "Payment", "Who's learning"];

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [phone, setPhone] = useState("");
  const [plan, setPlan] = useState("free");
  const [learnerName, setLearnerName] = useState("");
  const [ageBand, setAgeBand] = useState("adult");
  const [billing, setBilling] = useState({
    line1: "", line2: "", city: "", state: "", postal_code: "", country: "US",
    card_number: "", exp_month: 12, exp_year: new Date().getFullYear() + 2, cvv: "",
  });

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login?mode=signup");
      return;
    }
    getOnboardingStatus().then((s) => {
      if (s.completed) router.replace("/");
    }).catch(() => {});
    getMe().then((m) => {
      setDisplayName(m.display_name || "");
      setLearnerName(m.display_name || "");
    }).catch(() => {});
  }, [router]);

  const needsPayment = plan !== "free";

  async function nextFromInfo() {
    setBusy(true); setError("");
    try {
      await submitOnboardingProfile({ display_name: displayName, phone });
      setStep(1);
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  async function nextFromPlan() {
    if (!needsPayment) {
      setBusy(true); setError("");
      try {
        await selectOnboardingPlan(plan);
        setStep(3);
      } catch (e) { setError(String(e)); }
      finally { setBusy(false); }
      return;
    }
    setStep(2);
  }

  async function nextFromBilling() {
    setBusy(true); setError("");
    try {
      await submitOnboardingBilling({ ...billing, phone });
      await selectOnboardingPlan(plan);
      setStep(3);
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  async function finish() {
    setBusy(true); setError("");
    try {
      await completeOnboarding({ learner_name: learnerName, age_band: ageBand });
      router.push("/");
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  return (
    <main className="container" style={{ maxWidth: 640 }}>
      <h1 style={{ marginBottom: 4 }}>Welcome to Salareen</h1>
      <p className="muted">Set up your account in a few steps — just like Netflix.</p>
      <div style={{ display: "flex", gap: 8, margin: "16px 0 24px", flexWrap: "wrap" }}>
        {STEPS.map((label, i) => (
          <span
            key={label}
            style={{
              padding: "4px 10px", borderRadius: 999, fontSize: 12, fontWeight: 700,
              background: i === step ? "#0ea5e9" : i < step ? "#164e63" : "#1e293b",
              color: i === step ? "#001022" : "#94a3b8",
            }}
          >
            {i + 1}. {label}
          </span>
        ))}
      </div>

      <div className="card">
        {step === 0 && (
          <>
            <h2 style={{ marginTop: 0 }}>Tell us about you</h2>
            <label style={{ display: "block", marginBottom: 10 }}>
              Name
              <input value={displayName} onChange={(e) => setDisplayName(e.target.value)}
                style={{ width: "100%", padding: 8, marginTop: 4 }} />
            </label>
            <label style={{ display: "block", marginBottom: 10 }}>
              Phone (optional)
              <input value={phone} onChange={(e) => setPhone(e.target.value)}
                style={{ width: "100%", padding: 8, marginTop: 4 }} />
            </label>
            <button type="button" className="btn primary" disabled={busy} onClick={() => void nextFromInfo()}>
              Continue
            </button>
          </>
        )}

        {step === 1 && (
          <>
            <h2 style={{ marginTop: 0 }}>Choose your plan</h2>
            <p className="muted" style={{ fontSize: 14 }}>
              <strong>Standard</strong> plans include ads. <strong>VIP</strong> (Pro/Premium) is ad-free with more features.
            </p>
            <div style={{ display: "grid", gap: 10 }}>
              {PLANS.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => setPlan(p.id)}
                  style={{
                    textAlign: "left", padding: 14, borderRadius: 12, cursor: "pointer",
                    border: plan === p.id ? "2px solid #0ea5e9" : "1px solid #334155",
                    background: plan === p.id ? "#0c4a6e" : "#151c34",
                    color: "#e2e8f0",
                  }}
                >
                  <strong>{p.label}</strong> · {p.price}
                  <span style={{
                    marginLeft: 8, fontSize: 10, fontWeight: 800, textTransform: "uppercase",
                    color: p.class === "vip" ? "#fbbf24" : "#94a3b8",
                  }}>
                    {p.class}
                  </span>
                  <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>{p.blurb}</div>
                </button>
              ))}
            </div>
            <button type="button" className="btn primary" style={{ marginTop: 16 }} disabled={busy}
              onClick={() => void nextFromPlan()}>
              {needsPayment ? "Continue to payment" : "Continue"}
            </button>
          </>
        )}

        {step === 2 && (
          <>
            <h2 style={{ marginTop: 0 }}>Payment details</h2>
            <p className="muted" style={{ fontSize: 13 }}>
              Card is validated (Luhn + expiry). In production, payment runs through Stripe — we never store full card numbers.
            </p>
            <div style={{ display: "grid", gap: 8 }}>
              <input placeholder="Card number" value={billing.card_number}
                onChange={(e) => setBilling({ ...billing, card_number: e.target.value })}
                style={{ padding: 8 }} />
              <div style={{ display: "flex", gap: 8 }}>
                <input type="number" placeholder="MM" value={billing.exp_month}
                  onChange={(e) => setBilling({ ...billing, exp_month: Number(e.target.value) })}
                  style={{ padding: 8, width: 80 }} />
                <input type="number" placeholder="YYYY" value={billing.exp_year}
                  onChange={(e) => setBilling({ ...billing, exp_year: Number(e.target.value) })}
                  style={{ padding: 8, width: 100 }} />
                <input placeholder="CVV" value={billing.cvv}
                  onChange={(e) => setBilling({ ...billing, cvv: e.target.value })}
                  style={{ padding: 8, width: 80 }} />
              </div>
              <input placeholder="Street address" value={billing.line1}
                onChange={(e) => setBilling({ ...billing, line1: e.target.value })}
                style={{ padding: 8 }} />
              <div style={{ display: "flex", gap: 8 }}>
                <input placeholder="City" value={billing.city}
                  onChange={(e) => setBilling({ ...billing, city: e.target.value })}
                  style={{ padding: 8, flex: 1 }} />
                <input placeholder="State" value={billing.state}
                  onChange={(e) => setBilling({ ...billing, state: e.target.value })}
                  style={{ padding: 8, width: 80 }} />
                <input placeholder="ZIP" value={billing.postal_code}
                  onChange={(e) => setBilling({ ...billing, postal_code: e.target.value })}
                  style={{ padding: 8, width: 100 }} />
              </div>
            </div>
            <button type="button" className="btn primary" style={{ marginTop: 16 }} disabled={busy}
              onClick={() => void nextFromBilling()}>
              Validate &amp; continue
            </button>
          </>
        )}

        {step === 3 && (
          <>
            <h2 style={{ marginTop: 0 }}>Who&apos;s learning?</h2>
            <label style={{ display: "block", marginBottom: 10 }}>
              Profile name
              <input value={learnerName} onChange={(e) => setLearnerName(e.target.value)}
                style={{ width: "100%", padding: 8, marginTop: 4 }} />
            </label>
            <label style={{ display: "block", marginBottom: 10 }}>
              Age group
              <select value={ageBand} onChange={(e) => setAgeBand(e.target.value)}
                style={{ width: "100%", padding: 8, marginTop: 4 }}>
                <option value="child">Child</option>
                <option value="teen">Teen</option>
                <option value="adult">Adult</option>
              </select>
            </label>
            <button type="button" className="btn primary" disabled={busy} onClick={() => void finish()}>
              Start watching
            </button>
          </>
        )}

        {error && <p style={{ color: "#f87171", marginTop: 12 }}>{error}</p>}
      </div>
    </main>
  );
}
