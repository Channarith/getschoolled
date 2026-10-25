"use client";

import { Suspense, useEffect, useState } from "react";
import { safeReturnPath } from "../../lib/safeRedirect";
import { useRouter, useSearchParams } from "next/navigation";
import BiometricSetupAssistant from "../../components/BiometricSetupAssistant";
import { completeOnboarding, getToken, listStudents, type StudentProfile } from "../../lib/api";
import { isRetryableIdentityWrite, queueOnboardingSync } from "../../lib/onboardingSync";

export default function CameraCheckPage() {
  return (
    <Suspense fallback={<main style={{ minHeight: "100svh", background: "#080b1d" }} />}>
      <CameraCheckContent />
    </Suspense>
  );
}

function CameraCheckContent() {
  const router = useRouter();
  const search = useSearchParams();
  const [student, setStudent] = useState<StudentProfile | null>(null);
  const onboarding = search.get("onboarding") === "1";
  const required = search.get("required") === "1";
  const returnTo = search.get("returnTo");

  useEffect(() => {
    // Only a missing or rejected sign-in goes to /login. A slow identity
    // service used to sign people out of this page.
    let cancelled = false;
    let timer: number | undefined;
    const load = (attempt: number) => {
      listStudents().then((result) => {
        if (!cancelled) setStudent(result.students[0] ?? null);
      }).catch((reason) => {
        if (cancelled) return;
        if (!getToken() || /\b401\b|not signed in/i.test(String(reason)) || attempt >= 4) {
          router.replace("/login");
          return;
        }
        timer = window.setTimeout(() => load(attempt + 1), 5_000 * 2 ** attempt);
      });
    };
    load(0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [router]);

  async function done() {
    if (onboarding) {
      const finish = {
        learner_name: localStorage.getItem("onboarding_learner_name") || student?.display_name || "",
        age_band: localStorage.getItem("onboarding_age_band") || student?.age_band || "adult",
      };
      try {
        await completeOnboarding(finish);
      } catch (reason) {
        if (!isRetryableIdentityWrite(reason)) throw reason;
        queueOnboardingSync(finish);
      }
      localStorage.removeItem("onboarding_step");
      localStorage.removeItem("onboarding_plan");
      localStorage.removeItem("onboarding_learner_name");
      localStorage.removeItem("onboarding_age_band");
    }
    router.push(safeReturnPath(returnTo, required ? "/courses" : onboarding ? "/" : "/account"));
  }

  if (!student) {
    return <main style={{ minHeight: "100svh", background: "#080b1d" }} aria-label="Loading identity setup" />;
  }
  const effectiveAgeBand = onboarding && typeof window !== "undefined"
    ? (localStorage.getItem("onboarding_age_band") || student.age_band)
    : student.age_band;

  return (
    <BiometricSetupAssistant
      studentId={student.id}
      ageBand={effectiveAgeBand}
      requireGovernmentId={required}
      allowSkip={!required}
      onComplete={() => void done()}
      onSkip={() => void done()}
    />
  );
}
