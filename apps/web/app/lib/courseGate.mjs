// Pure decisions for the signed-in full-course page. The SERVER decides what an account may do
// (GET /api/studio/entitlement); this only maps its answer to a screen and reads the processor's return URL.

export const PAYMENT_RETURN_KEYS = ["paid", "session_id", "token", "PayerID"];

/** "signedout" | "pay" | "enter". Only must_pay ever reaches the payment screen; anything unknown fails closed. */
export function gateForEntitlement(state) {
  if (state === "free" || state === "paid") return "enter";
  if (state === "must_pay") return "pay";
  return "signedout";
}

/** A price is shown only to a signed-in account that must pay: never to anonymous, admin, VIP/premium or paid accounts. */
export function showsPrice(state) {
  return state === "must_pay";
}

/** The processor sent the buyer back with ?paid=1 and a session (Stripe) or token (PayPal). */
export function paymentReturn(search) {
  const params = new URLSearchParams(search || "");
  const sessionId = params.get("session_id") || params.get("token") || "";
  if (params.get("paid") !== "1" || !sessionId) return null;
  return { sessionId, method: params.get("token") ? "paypal" : "card" };
}

/** The query string without the processor's return parameters, so a reload does not confirm twice. */
export function cleanReturnSearch(search) {
  const params = new URLSearchParams(search || "");
  PAYMENT_RETURN_KEYS.forEach((key) => params.delete(key));
  return params.toString();
}
