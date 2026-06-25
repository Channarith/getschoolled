"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import ClassRoom from "../components/ClassRoom";
import { useT } from "../lib/i18n";

export default function ClassPage() {
  const { t } = useT();
  return (
    <Suspense fallback={
      <main className="container"><p className="muted">{t("class.loading")}</p></main>
    }>
      <ClassPageInner />
    </Suspense>
  );
}

function ClassPageInner() {
  const { t } = useT();
  const searchParams = useSearchParams();
  const initialLessonId = searchParams.get("lesson") ?? undefined;
  return (
    <ClassRoom
      title={t("class.title")}
      initialLessonId={initialLessonId}
      hideCorporate
      startLabel={t("class.startLabel")}
    />
  );
}
