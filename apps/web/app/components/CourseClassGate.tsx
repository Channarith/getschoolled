"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getMe, getPortfolio, getToken, purchaseCourse } from "../lib/api";
import {
  courseStudioFrameSrc,
  fullClassAllowed,
  type PublicCourseId,
} from "../lib/courseStudio";
import { CourseStudioFrame } from "./CourseStudioFrame";

type Gate = "loading" | "signedout" | "pay" | "full";

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
  const [accountId, setAccountId] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
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
        const admin = Boolean(me.is_admin);
        setIsAdmin(admin);
        const row = portfolio.enrollments.find((enrollment) => enrollment.course_id === courseId);
        setGate(fullClassAllowed(true, row?.status || "", admin) ? "full" : "pay");
      })
      .catch(() => setGate("signedout"));
  }, [courseId]);

  async function payForClass() {
    setBusy(true);
    setError("");
    try {
      const enrollment = await purchaseCourse(courseId, title);
      if (fullClassAllowed(true, enrollment.status, isAdmin)) setGate("full");
      else setError("Payment was not recorded for this course.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (gate === "loading") {
    return (
      <main className="container">
        <p className="muted">Loading {title}…</p>
      </main>
    );
  }

  if (gate === "signedout") {
    return (
      <main className="container">
        <h1>{title}</h1>
        <div className="card">
          <p>Sign in to take this course. Admins open the full course. Everyone else pays.</p>
          {demoHref ? (
            <p>
              The 10-minute demo is free for anyone. <Link href={demoHref}>Start the demo</Link>
            </p>
          ) : null}
          <p>
            <Link href="/login">Sign in or create an account</Link>
          </p>
        </div>
      </main>
    );
  }

  if (gate === "pay") {
    return (
      <main className="container">
        <h1>{title}</h1>
        <div className="card">
          <p>This course is paid. An admin account takes it without paying.</p>
          {demoHref ? (
            <p>
              Anyone can try the free 10-minute demo. <Link href={demoHref}>Start the demo</Link>
            </p>
          ) : null}
          <button type="button" onClick={() => { void payForClass(); }} disabled={busy}>
            {busy ? "Recording payment…" : "Pay for this course"}
          </button>
          {error ? <p className="muted">{error}</p> : null}
        </div>
      </main>
    );
  }

  return (
    <main className="container">
      <h1>{title}</h1>
      <p className="muted">
        {isAdmin
          ? "Your account is an admin, so this is the full course."
          : "This account has paid for the course. This is the full course."}
      </p>
      <p className="muted">
        <Link href="/">Back to Salareen</Link>
      </p>
      <CourseStudioFrame
        title={`${title} full course`}
        src={courseStudioFrameSrc({ access: "full", course: courseId, accountId, isAdmin })}
      />
    </main>
  );
}
