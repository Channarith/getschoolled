"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { CourseStudioFrame } from "../../components/CourseStudioFrame";
import { getMe, getPortfolio, getToken, purchaseCourse } from "../../lib/api";
import {
  COURSE_STUDIO_LIBRARY_ID,
  courseStudioFrameSrc,
  fullClassAllowed,
} from "../../lib/courseStudio";

type Gate = "loading" | "signedout" | "sample" | "full";

export default function CourseStudioLibraryPage() {
  const [gate, setGate] = useState<Gate>("loading");
  const [accountId, setAccountId] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      setGate("signedout");
      return;
    }
    Promise.all([getMe(), getPortfolio()])
      .then(([me, portfolio]) => {
        setAccountId(me.id);
        const row = portfolio.enrollments.find(
          (enrollment) => enrollment.course_id === COURSE_STUDIO_LIBRARY_ID,
        );
        setGate(fullClassAllowed(true, row?.status || "") ? "full" : "sample");
      })
      .catch(() => setGate("signedout"));
  }, []);

  async function payForClass() {
    setBusy(true);
    setError("");
    try {
      const enrollment = await purchaseCourse(COURSE_STUDIO_LIBRARY_ID, "Course Studio");
      if (fullClassAllowed(true, enrollment.status)) setGate("full");
      else setError("Payment was not recorded for this class.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (gate === "loading") {
    return (
      <main className="container">
        <p className="muted">Loading Course Studio…</p>
      </main>
    );
  }

  if (gate === "signedout") {
    return (
      <main className="container">
        <h1>Course Studio</h1>
        <div className="card">
          <p>
            Register an account to take this class. The sales demo plays a 10-minute sample.
            The full class opens after you are registered and have paid for it.
          </p>
          <p>
            <Link href="/login">Sign in or create an account</Link>
          </p>
        </div>
      </main>
    );
  }

  const access = gate === "full" ? "full" : "sample";

  return (
    <main className="container">
      <h1>Course Studio</h1>
      {gate === "full" ? (
        <p className="muted">Your account is registered and this class is paid. This is the full course.</p>
      ) : (
        <div className="card" style={{ marginBottom: 16 }}>
          <p>
            This is a 10-minute sample. Registering alone does not open the rest of the class.
            Pay for the class on this account to take the full course.
          </p>
          <button type="button" onClick={() => { void payForClass(); }} disabled={busy}>
            {busy ? "Recording payment…" : "Pay for the full class"}
          </button>
          {error ? <p className="muted">{error}</p> : null}
        </div>
      )}
      <p className="muted">
        <Link href="/browse">Back to the library</Link>
      </p>
      <CourseStudioFrame
        title={gate === "full" ? "Course Studio full class" : "Course Studio 10-minute sample"}
        src={courseStudioFrameSrc({ access, accountId })}
      />
    </main>
  );
}
