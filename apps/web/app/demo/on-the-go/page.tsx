import Link from "next/link";

import { CourseStudioFrame } from "../../components/CourseStudioFrame";
import { courseStudioFrameSrc } from "../../lib/courseStudio";

export default function OnTheGoDemoPage() {
  return (
    <main className="container" style={{ maxWidth: 1180, margin: "0 auto", padding: "28px 22px 70px" }}>
      <p className="theme-badge">DEMO</p>
      <h1>On the Go — 10 minutes, audio only</h1>
      <p className="muted" style={{ maxWidth: 720 }}>
        The same classes as the driver&apos;s education demo, heard instead of watched.
        Driver&apos;s Education and Food Health &amp; Safety are both here. There is no camera.
        The trial stops at 10 minutes.
      </p>
      <p style={{ margin: "12px 0 18px" }}>
        <Link href="/">← Back to Salareen</Link>
        {" · "}
        <Link href="/demo/drivers-ed">Driver&apos;s ed on screen</Link>
      </p>
      <CourseStudioFrame
        title="On the Go 10-minute audio demo"
        src={courseStudioFrameSrc({ access: "sample", course: "drivers-ed", presentation: "audio" })}
      />
    </main>
  );
}
