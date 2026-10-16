"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import BiometricSetupAssistant from "../../components/BiometricSetupAssistant";
import { completeOnboarding, listStudents, type StudentProfile } from "../../lib/api";

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
    listStudents().then((result) => setStudent(result.students[0] ?? null)).catch(() => {
      router.replace("/login");
    });
  }, [router]);

  async function done() {
    if (onboarding) {
      await completeOnboarding({
        learner_name: localStorage.getItem("onboarding_learner_name") || student?.display_name || "",
        age_band: localStorage.getItem("onboarding_age_band") || student?.age_band || "adult",
      });
      localStorage.removeItem("onboarding_step");
      localStorage.removeItem("onboarding_plan");
      localStorage.removeItem("onboarding_learner_name");
      localStorage.removeItem("onboarding_age_band");
    }
    router.push(returnTo || (required ? "/courses" : onboarding ? "/" : "/account"));
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
