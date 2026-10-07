import Link from "next/link";

import { CourseStudioFrame } from "../../components/CourseStudioFrame";
import { courseStudioFrameSrc } from "../../lib/courseStudio";

export default function DriversEdDemoPage() {
  return (
    <main className="container" style={{ maxWidth: 1180, margin: "0 auto", padding: "28px 22px 70px" }}>
      <p className="theme-badge">DEMO</p>
      <h1>Driver&apos;s Education — 10 minutes, free</h1>
      <p className="muted" style={{ maxWidth: 720 }}>
        Anyone can take this demo. It stops at 10 minutes. The full course is paid unless you are an admin.
      </p>
      <p style={{ margin: "12px 0 18px" }}>
        <Link href="/">← Back to Salareen</Link>
        {" · "}
        <Link href="/learn/drivers-ed">Full course</Link>
      </p>
      <CourseStudioFrame
        title="Driver's Education 10-minute demo"
        src={courseStudioFrameSrc({ access: "sample", course: "drivers-ed" })}
      />
    </main>
  );
}
