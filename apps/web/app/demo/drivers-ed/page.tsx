import Link from "next/link";

import { CourseStudioFrame } from "../../components/CourseStudioFrame";
import { DriversEdIntro } from "../../components/DriversEdIntro";
import { courseStudioFrameSrc } from "../../lib/courseStudio";

export default function DriversEdDemoPage() {
  return (
    <main className="course-stage">
      <DriversEdIntro />
      <p className="course-stage-links">
        <Link href="/">← Back to Salareen</Link>
        <Link href="/learn/drivers-ed">Full course</Link>
      </p>
      <CourseStudioFrame
        fill
        title="Driver's Education 10-minute demo"
        src={courseStudioFrameSrc({ access: "sample", course: "drivers-ed", demo: true, intro: true })}
      />
    </main>
  );
}
