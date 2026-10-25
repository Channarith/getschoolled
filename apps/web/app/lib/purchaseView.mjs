// Pure view helpers for purchases and policy pages (the server owns every number and every decision).

export function moneyLabel(cents, currency = "usd") {
  const n = Number(cents);
  if (!Number.isFinite(n)) return "";
  const sign = n < 0 ? "-" : "";
  const abs = Math.abs(Math.trunc(n));
  const body = `${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
  return String(currency).toLowerCase() === "usd" ? `${sign}$${body}` : `${sign}${body} ${String(currency).toUpperCase()}`;
}

export function statusLabel(status) {
  if (status === "paid") return "Paid";
  if (status === "refunded") return "Refunded";
  if (status === "revoked") return "Access ended";
  return "";
}

/** What the refund control for one purchase should say and do. The server decides eligibility; this only words it. */
export function refundControl(purchase) {
  if (!purchase || purchase.status !== "paid") return { show: false, label: "", note: "" };
  if (purchase.refund_requested) return { show: false, label: "", note: "Refund request sent. Support will contact you." };
  const refund = purchase.refund || {};
  if (refund.reason === "store_purchase") return { show: false, label: "", note: refund.message || "Refunds for store purchases come from the store." };
  return { show: true, label: "Request a refund", note: refund.eligible ? `Eligible for an automatic refund (${refund.days_left} days left).` : refund.message || "" };
}

export function policyFacts(policy, kind) {
  const refund = (policy && policy.refund) || {};
  const seller = (policy && policy.seller) || {};
  const facts = [];
  if (kind === "refund" || kind === "sale") {
    facts.push({ label: "Refund window", value: `${refund.window_days} days from purchase` });
    facts.push({ label: "Course used", value: `up to ${refund.max_progress_pct}% for an automatic refund` });
    facts.push({ label: "After a certificate", value: refund.block_after_certificate ? "not refunded automatically" : "may still be refunded" });
    facts.push({ label: "Who decides", value: refund.auto_approve ? "automatic when the rules are met, otherwise a person" : "a person reviews every request" });
  }
  if (kind === "receipts" || kind === "sale") {
    facts.push({ label: "Sales tax", value: policy && policy.tax_mode === "none" ? "none charged at the moment" : "calculated at checkout when it applies" });
  }
  facts.push({ label: "Seller", value: seller.legal_name || "" });
  facts.push({ label: "Support", value: seller.support_email || "" });
  return facts.filter((fact) => fact.value && fact.value !== "undefined days from purchase");
}

export const US_STATES = [
  "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
  "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD",
  "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
];

/** The pay buttons stay disabled until a state is chosen, but only when the server says it needs one to calculate tax. */
export function canStartCheckout(quote, state) {
  if (!quote) return false;
  if (quote.requires_state && !US_STATES.includes(String(state || "").toUpperCase())) return false;
  return true;
}
