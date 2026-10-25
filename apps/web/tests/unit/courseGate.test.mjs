import test from "node:test";
import assert from "node:assert/strict";

import { cleanReturnSearch, gateForEntitlement, paymentReturn, showsPrice } from "../../app/lib/courseGate.mjs";

test("only a signed-in account that must pay reaches the payment screen", () => {
  assert.equal(gateForEntitlement("must_pay"), "pay");
  assert.equal(gateForEntitlement("free"), "enter");
  assert.equal(gateForEntitlement("paid"), "enter");
  assert.equal(gateForEntitlement("login_required"), "signedout");
});

test("anything unknown fails closed: no payment screen, no class", () => {
  for (const bad of ["", undefined, null, "FULL", "admin", "true", 1]) assert.equal(gateForEntitlement(bad), "signedout");
});

test("the price is shown to must_pay only", () => {
  assert.equal(showsPrice("must_pay"), true);
  for (const state of ["free", "paid", "login_required", "", undefined]) assert.equal(showsPrice(state), false);
});

test("a Stripe return carries a session id and PayPal carries a token", () => {
  assert.deepEqual(paymentReturn("?paid=1&session_id=cs_test_1"), { sessionId: "cs_test_1", method: "card" });
  assert.deepEqual(paymentReturn("?paid=1&token=ORDER1&PayerID=P1"), { sessionId: "ORDER1", method: "paypal" });
});

test("a cancel or a bare visit is not a return", () => {
  assert.equal(paymentReturn(""), null);
  assert.equal(paymentReturn("?paid=1"), null);
  assert.equal(paymentReturn("?session_id=cs_1"), null);
  assert.equal(paymentReturn(undefined), null);
});

test("the return parameters are removed so a reload does not confirm twice", () => {
  assert.equal(cleanReturnSearch("?paid=1&session_id=cs_1&lang=km"), "lang=km");
  assert.equal(cleanReturnSearch("?paid=1&token=O&PayerID=P"), "");
});
