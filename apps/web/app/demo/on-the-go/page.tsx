import Link from "next/link";

import OnTheGo from "../../components/OnTheGo";

/** Public demo of the same On the Go player, limited to a 10-minute sample. */
export default function OnTheGoDemoPage() {
  return (
    <main className="course-stage">
      <p className="course-stage-links">
        <Link href="/">← Back to Salareen</Link>
        <Link href="/demo/drivers-ed">Driver&apos;s ed on screen</Link>
      </p>
      <OnTheGo mode="demo" />
    </main>
  );
}
