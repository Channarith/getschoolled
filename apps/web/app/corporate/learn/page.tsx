"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import ClassRoom from "../../components/ClassRoom";

export default function CorporateLearnPage() {
  return (
    <Suspense fallback={<main className="container"><p className="muted">Loading course…</p></main>}>
      <CorporateLearnInner />
    </Suspense>
  );
}

function CorporateLearnInner() {
  const searchParams = useSearchParams();
  const lessonId = searchParams.get("lesson") ?? "";
  if (!lessonId) {
    return (
      <main className="container">
        <h1>Corporate training</h1>
        <p className="muted">No course selected. Pick one from the corporate programs page.</p>
      </main>
    );
  }
  return (
    <ClassRoom
      title="Corporate training"
      lockedLessonId={lessonId}
      backHref="/corporate"
      backLabel="← Back to Corporate training"
      startLabel="Start course"
    />
  );
}
