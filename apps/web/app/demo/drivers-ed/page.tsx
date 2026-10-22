import Link from "next/link";

import { CourseStudioFrame } from "../../components/CourseStudioFrame";
import { courseStudioFrameSrc } from "../../lib/courseStudio";

export default function DriversEdDemoPage() {
  return (
    <main className="course-stage">
      <p className="course-stage-links">
        <Link href="/">← Back to Salareen</Link>
        <Link href="/learn/drivers-ed">Full course</Link>
        <Link href="/demo/on-the-go">Audio only</Link>
      </p>
      <CourseStudioFrame
        fill
        title="Driver's Education 10-minute demo"
        src={courseStudioFrameSrc({ access: "sample", course: "drivers-ed", demo: true })}
      />
    </main>
  );
}
