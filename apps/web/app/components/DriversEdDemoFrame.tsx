"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { getMe, getPortfolio } from "../lib/api";
import { courseStudioFrameSrc, fullClassAllowed } from "../lib/courseStudio";
import { useSignedIn } from "../lib/flags";
import { CourseStudioFrame } from "./CourseStudioFrame";

/**
 * The free 10-minute demo, with its countdown, is for visitors who are not signed in or who have not unlocked the course.
 * An admin or a learner who paid for Driver's Ed goes straight to the full course, which has no timer.
 */
export function DriversEdDemoFrame() {
  const signedIn = useSignedIn();
  const router = useRouter();
  const [demo, setDemo] = useState(false);

  useEffect(() => {
    if (signedIn === null) return;
    if (!signedIn) { setDemo(true); return; }
    let live = true;
    Promise.all([getMe(), getPortfolio()])
      .then(([me, portfolio]) => {
        const row = portfolio.enrollments.find((e) => e.course_id === "drivers-ed");
        if (!live) return;
        if (fullClassAllowed(true, row?.status || "", Boolean(me.is_admin))) router.replace("/learn/drivers-ed");
        else setDemo(true);
      })
      .catch(() => { if (live) setDemo(true); });
    return () => { live = false; };
  }, [signedIn, router]);

  if (!demo) return <p className="muted" role="status">Loading…</p>;
  return (
    <CourseStudioFrame
      fill
      title="Driver's Education 10-minute demo"
      src={courseStudioFrameSrc({ access: "sample", course: "drivers-ed", demo: true, intro: true })}
    />
  );
}
