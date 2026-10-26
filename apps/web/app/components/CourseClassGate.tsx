"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  confirmCoursePayment,
  friendlyApiError,
  getCourseEntitlement,
  getCoursePolicy,
  getCourseQuote,
  getIdentityAssurance,
  getLessonAccreditation,
  getMe,
  getToken,
  listStudents,
  startCourseCheckout,
  type CoursePolicy,
  type CourseOffer,
  type CourseQuote,
} from "../lib/api";
import { cleanReturnSearch, gateForEntitlement, paymentReturn } from "../lib/courseGate.mjs";
import { US_STATES, canStartCheckout } from "../lib/purchaseView.mjs";
import { courseStudioFrameSrc, type PublicCourseId } from "../lib/courseStudio";
import { CourseStudioFrame } from "./CourseStudioFrame";

type Gate = "loading" | "signedout" | "pay" | "confirming" | "identity" | "full";

/**
 * The full course page for a SIGNED-IN visitor. The server decides (GET /api/studio/entitlement):
 *   free         admin, VIP or premium: straight into the class, no price anywhere
 *   paid         this account bought it (on the web or in an app): into the class
 *   must_pay     the one-time offer with Credit card and PayPal (the server owns the price)
 *   login_required  no account: nothing to buy yet, send them to create or log in
 * Payment is only ever offered here, after login. The anonymous demo never shows a price.
 */
export function CourseClassGate({
  courseId,
  title,
  demoHref,
}: {
  courseId: PublicCourseId;
  title: string;
  demoHref?: string;
}) {
  const [gate, setGate] = useState<Gate>("loading");
  const [studentId, setStudentId] = useState("");
  const [offer, setOffer] = useState<CourseOffer | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<"" | "card" | "paypal">("");
  const [quote, setQuote] = useState<CourseQuote | null>(null);
  const [policy, setPolicy] = useState<CoursePolicy | null>(null);
  const [billingState, setBillingState] = useState("");

  useEffect(() => {
    if (gate !== "pay") return;
    getCoursePolicy().then(setPolicy).catch(() => setPolicy(null));
  }, [gate]);

  useEffect(() => {
    if (gate !== "pay") return;
    getCourseQuote(courseId, billingState).then(setQuote).catch(() => setQuote(null));
  }, [gate, courseId, billingState]);

  const enter = useCallback(async () => {
    if (!getToken()) {
      setGate("signedout");
      return;
    }
    try {
      const [, students, accreditation, entitlement] = await Promise.all([
        getMe(),
        listStudents(),
        getLessonAccreditation(courseId),
        getCourseEntitlement(courseId),
      ]);
      const learnerId = students.students[0]?.id || "";
      setStudentId(learnerId);
      const next = gateForEntitlement(entitlement.entitlement);
      if (next === "signedout") {
        setGate("signedout");
        return;
      }
      if (next === "pay") {
        setOffer(entitlement.offer || null);
        setGate("pay");
        return;
      }
      if (accreditation.requires_identity_assurance && learnerId) {
        const assurance = await getIdentityAssurance(learnerId, true);
        setGate(assurance.allowed ? "full" : "identity");
        return;
      }
      setGate("full");
    } catch {
      setGate("signedout");
    }
  }, [courseId]);

  useEffect(() => {
    // Coming back from the processor: confirm with the server, then re-check what this account may do.
    const back = paymentReturn(window.location.search);
    if (back && getToken()) {
      setGate("confirming");
      confirmCoursePayment(back.sessionId, back.method as "card" | "paypal")
        .catch((err) => setError(friendlyApiError(err, "We could not confirm your payment yet.")))
        .finally(() => {
          const clean = cleanReturnSearch(window.location.search);
          window.history.replaceState(null, "", window.location.pathname + (clean ? `?${clean}` : ""));
          void enter();
        });
      return;
    }
    void enter();
  }, [enter]);

  async function pay(method: "card" | "paypal") {
    setBusy(method);
    setError("");
    try {
      const session = await startCourseCheckout(courseId, method, billingState);
      if (session.already_entitled) {
        await enter();
        return;
      }
      if (!session.url) throw new Error("The payment page did not open.");
      window.location.assign(session.url);
    } catch (err) {
      setError(friendlyApiError(err, "Payments are not available right now. Please try again later."));
      setBusy("");
    }
  }

  if (gate === "loading" || gate === "confirming") {
    return (
      <main className="container">
        <p className="muted">{gate === "confirming" ? "Confirming your payment…" : `Loading ${title}…`}</p>
        {error ? <p className="muted">{error}</p> : null}
      </main>
    );
  }

  if (gate === "signedout") {
    return (
      <main className="container">
        <h1>{title}</h1>
        <div className="card">
          <p>Create or log in to your account to take this course.</p>
          {demoHref ? (
            <p>
              The 4-minute demo is free for anyone. <Link href={demoHref}>Start the demo</Link>
            </p>
          ) : null}
          <p>
            <Link href="/login">Create or log in to your account</Link>
          </p>
        </div>
      </main>
    );
  }

  if (gate === "pay") {
    const ready = canStartCheckout(quote, billingState);
    return (
      <main className="container">
        <h1>{title}</h1>
        <div className="card">
          <p>
            Full course: one payment{offer ? ` of ${offer.label}` : ""} unlocks the whole class, on the web and in the
            app.
          </p>
          {quote && quote.requires_state ? (
            <p>
              <label>
                Your state (to calculate tax){" "}
                <select value={billingState} onChange={(event) => setBillingState(event.target.value)}>
                  <option value="">Choose…</option>
                  {US_STATES.map((code) => (
                    <option key={code} value={code}>{code}</option>
                  ))}
                </select>
              </label>
            </p>
          ) : null}
          {quote && quote.tax_cents > 0 ? (
            <p className="muted">
              {offer ? offer.label : ""} + {quote.tax_label} = <strong>{quote.total_label}</strong>
            </p>
          ) : null}
          {demoHref ? (
            <p>
              Want to try it first? <Link href={demoHref}>Start the free 4-minute demo</Link>
            </p>
          ) : null}
          <p>
            <button type="button" onClick={() => { void pay("card"); }} disabled={Boolean(busy) || !ready}>
              {busy === "card" ? "Opening secure checkout…" : "Credit card"}
            </button>{" "}
            <button type="button" onClick={() => { void pay("paypal"); }} disabled={Boolean(busy) || !ready}>
              {busy === "paypal" ? "Opening PayPal…" : "PayPal"}
            </button>
          </p>
          {error ? <p role="alert" className="muted">{error}</p> : null}
          {policy ? <p className="muted" style={{ fontSize: 12 }}>{policy.disclaimer}</p> : null}
          <p className="muted" style={{ fontSize: 12 }}>
            <Link href="/legal/terms-of-sale">Terms of Sale</Link> · <Link href="/legal/refund-policy">Refund Policy</Link> ·{" "}
            <Link href="/legal/receipts-and-taxes">Receipts &amp; Taxes</Link>
          </p>
        </div>
      </main>
    );
  }

  if (gate === "identity") {
    return (
      <main className="container">
        <h1>{title}</h1>
        <div className="card">
          <p>Complete Face, Audio, and government-ID setup before starting this credited course.</p>
          <Link href={`/account/camera-check?required=1&returnTo=${encodeURIComponent("/")}`}>
            Open identity setup
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="course-stage">
      <CourseStudioFrame
        fill
        clean
        title={`${title} full course`}
        src={courseStudioFrameSrc({ access: "full", course: courseId, learnerId: studentId })}
      />
    </main>
  );
}
