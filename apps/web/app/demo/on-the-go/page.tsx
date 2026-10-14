import Link from "next/link";

import { CourseStudioFrame } from "../../components/CourseStudioFrame";
import { courseStudioFrameSrc } from "../../lib/courseStudio";

export default function OnTheGoDemoPage() {
  return (
    <main className="course-stage">
      <p className="course-stage-links">
        <Link href="/">← Back to Salareen</Link>
        <Link href="/demo/drivers-ed">Driver&apos;s ed on screen</Link>
      </p>
      <CourseStudioFrame
        fill
        title="On the Go 10-minute audio demo"
        src={courseStudioFrameSrc({ access: "sample", course: "drivers-ed", presentation: "audio" })}
      />
    </main>
  );
}
