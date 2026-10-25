import test from "node:test";
import assert from "node:assert/strict";

import { US_STATES, canStartCheckout, moneyLabel, policyFacts, refundControl, statusLabel } from "../../app/lib/purchaseView.mjs";

test("money is formatted in cents without floating point surprises", () => {
  assert.equal(moneyLabel(1999), "$19.99");
  assert.equal(moneyLabel(2144, "USD"), "$21.44");
  assert.equal(moneyLabel(5), "$0.05");
  assert.equal(moneyLabel(-1999), "-$19.99");
  assert.equal(moneyLabel(1999, "eur"), "19.99 EUR");
  assert.equal(moneyLabel("x"), "");
});

test("status wording", () => {
  assert.equal(statusLabel("paid"), "Paid");
  assert.equal(statusLabel("refunded"), "Refunded");
  assert.equal(statusLabel("revoked"), "Access ended");
  assert.equal(statusLabel("weird"), "");
});

test("a paid web purchase shows the refund button with the server's words", () => {
  const control = refundControl({ status: "paid", refund: { eligible: true, reason: "eligible", days_left: 9, message: "" } });
  assert.equal(control.show, true);
  assert.equal(control.label, "Request a refund");
  assert.match(control.note, /9 days left/);
});

test("an ineligible purchase still lets the learner ask, with the reason: a person reviews it", () => {
  const control = refundControl({ status: "paid", refund: { eligible: false, reason: "window_passed", message: "Refunds are available for 14 days." } });
  assert.equal(control.show, true);
  assert.match(control.note, /14 days/);
});

test("store purchases never show a refund button: the store refunds", () => {
  const control = refundControl({ status: "paid", refund: { reason: "store_purchase", message: "Ask the App Store." } });
  assert.equal(control.show, false);
  assert.match(control.note, /App Store/);
});

test("a refunded, revoked or already-requested purchase has no button", () => {
  assert.equal(refundControl({ status: "refunded" }).show, false);
  assert.equal(refundControl({ status: "revoked" }).show, false);
  const asked = refundControl({ status: "paid", refund_requested: true, refund: { eligible: true } });
  assert.equal(asked.show, false);
  assert.match(asked.note, /Support will contact you/);
  assert.equal(refundControl(null).show, false);
});

test("checkout waits for a state only when the server needs one for tax", () => {
  assert.equal(canStartCheckout(null, ""), false);
  assert.equal(canStartCheckout({ requires_state: false }, ""), true);
  assert.equal(canStartCheckout({ requires_state: true }, ""), false);
  assert.equal(canStartCheckout({ requires_state: true }, "zz"), false);
  assert.equal(canStartCheckout({ requires_state: true }, "ca"), true);
  assert.equal(US_STATES.length, 51);
});

test("policy facts mirror what the server reports", () => {
  const policy = {
    refund: { window_days: 14, max_progress_pct: 20, block_after_certificate: true, auto_approve: true },
    tax_mode: "none",
    seller: { legal_name: "[to be set by the seller]", support_email: "help@example.com" },
  };
  const refund = policyFacts(policy, "refund");
  assert.deepEqual(refund.find((f) => f.label === "Refund window"), { label: "Refund window", value: "14 days from purchase" });
  assert.equal(refund.find((f) => f.label === "Course used").value, "up to 20% for an automatic refund");
  assert.equal(refund.find((f) => f.label === "After a certificate").value, "not refunded automatically");
  const receipts = policyFacts(policy, "receipts");
  assert.equal(receipts.find((f) => f.label === "Sales tax").value, "none charged at the moment");
  assert.equal(receipts.find((f) => f.label === "Refund window"), undefined);
  assert.equal(policyFacts({ ...policy, tax_mode: "manual" }, "receipts").find((f) => f.label === "Sales tax").value, "calculated at checkout when it applies");
});
