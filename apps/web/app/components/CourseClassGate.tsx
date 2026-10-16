"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  getIdentityAssurance,
  getLessonAccreditation,
  getMe,
  getPortfolio,
  getToken,
  listStudents,
  purchaseCourse,
} from "../lib/api";
import {
  courseStudioFrameSrc,
  fullClassAllowed,
  type PublicCourseId,
} from "../lib/courseStudio";
import { CourseStudioFrame } from "./CourseStudioFrame";

type Gate = "loading" | "signedout" | "pay" | "identity" | "full";

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
  const [studentId, setStudentId] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      setGate("signedout");
      return;
    }
    Promise.all([getMe(), getPortfolio(), listStudents(), getLessonAccreditation(courseId)])
      .then(async ([me, portfolio, students, accreditation]) => {
        setAccountId(me.id);
        const learnerId = students.students[0]?.id || "";
        setStudentId(learnerId);
        const admin = Boolean(me.is_admin);
        setIsAdmin(admin);
        const row = portfolio.enrollments.find((enrollment) => enrollment.course_id === courseId);
        if (!fullClassAllowed(true, row?.status || "", admin)) {
          setGate("pay");
          return;
        }
        if (accreditation.requires_identity_assurance && learnerId) {
          const assurance = await getIdentityAssurance(learnerId, true);
          setGate(assurance.allowed ? "full" : "identity");
          return;
        }
        setGate("full");
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
      const msg = err instanceof Error ? err.message : String(err);
      // jsonOrThrow raises Error("<status> <detail>"); surface a friendly
      // message when payments aren't enabled in this environment instead of
      // the raw "402 This class stays a 10-minute sample..." which looks like
      // a client crash.
      if (msg.startsWith("402")) {
        setError(
          "Paid checkout isn't enabled on this environment yet. The free 10-minute demo is open to everyone.",
        );
      } else {
        setError(msg);
      }
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
      <p className="course-stage-links">
        <Link href="/">← Back to Salareen</Link>
        <span className="muted">
          {isAdmin ? "Full course (admin)." : "Full course."}
        </span>
      </p>
      <CourseStudioFrame
        fill
        title={`${title} full course`}
        src={courseStudioFrameSrc({
          access: "full",
          course: courseId,
          accountId,
          learnerId: studentId,
          isAdmin,
        })}
      />
    </main>
  );
}
