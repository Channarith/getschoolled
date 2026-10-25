import Link from "next/link";

import { DriversEdDemoFrame } from "../../components/DriversEdDemoFrame";
import { DriversEdIntro } from "../../components/DriversEdIntro";

export default function DriversEdDemoPage() {
  return (
    <main className="course-stage">
      <DriversEdIntro />
      <p className="course-stage-links">
        <Link href="/">← Back to Salareen</Link>
        <Link href="/learn/drivers-ed">Full course</Link>
      </p>
      <DriversEdDemoFrame />
    </main>
  );
}
