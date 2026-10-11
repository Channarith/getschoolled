import Link from "next/link";

import { CourseStudioFrame } from "../../components/CourseStudioFrame";
import { courseStudioFrameSrc } from "../../lib/courseStudio";

export default function OnTheGoDemoPage() {
  return (
    <main className="container" style={{ maxWidth: 1180, margin: "0 auto", padding: "16px 16px 40px" }}>
      <p style={{ margin: "0 0 12px", display: "flex", flexWrap: "wrap", gap: "6px 14px" }}>
        <Link href="/">← Back to Salareen</Link>
        <Link href="/demo/drivers-ed">Driver&apos;s ed on screen</Link>
      </p>
      <p className="muted" style={{ margin: "0 0 12px" }}>
        Audio demo with Serenity + xAI Grok voice when configured.
      </p>
      <CourseStudioFrame
        title="On the Go 10-minute audio demo"
        src={courseStudioFrameSrc({ access: "sample", course: "drivers-ed", presentation: "audio" })}
      />
    </main>
  );
}
