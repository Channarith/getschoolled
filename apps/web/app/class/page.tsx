"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import ClassRoom from "../components/ClassRoom";

export default function ClassPage() {
  return (
    <Suspense fallback={<main className="container"><p className="muted">Loading class…</p></main>}>
      <ClassPageInner />
    </Suspense>
  );
}

function ClassPageInner() {
  const searchParams = useSearchParams();
  const initialLessonId = searchParams.get("lesson") ?? undefined;
  return (
    <ClassRoom
      title="Live Class"
      initialLessonId={initialLessonId}
      hideCorporate
      startLabel="Start class"
    />
  );
}
