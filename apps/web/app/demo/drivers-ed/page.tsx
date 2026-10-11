import Link from "next/link";

import { CourseStudioFrame } from "../../components/CourseStudioFrame";
import { courseStudioFrameSrc } from "../../lib/courseStudio";

export default function DriversEdDemoPage() {
  return (
    <main className="container" style={{ maxWidth: 1180, margin: "0 auto", padding: "16px 16px 40px" }}>
      <p style={{ margin: "0 0 12px", display: "flex", flexWrap: "wrap", gap: "6px 14px" }}>
        <Link href="/">← Back to Salareen</Link>
        <Link href="/learn/drivers-ed">Full course</Link>
        <Link href="/demo/on-the-go">Audio only</Link>
      </p>
      <p className="muted" style={{ margin: "0 0 12px" }}>
        Serenity (holographic AI teacher) presents this demo. Voice uses xAI Grok when
        the speech service has <code>XAI_API_KEY</code>.
      </p>
      <CourseStudioFrame
        title="Driver's Education 10-minute demo"
        src={courseStudioFrameSrc({ access: "sample", course: "drivers-ed" })}
      />
    </main>
  );
}
