"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { CourseStudioFrame } from "../../components/CourseStudioFrame";
import { getToken } from "../../lib/api";
import { courseStudioFrameSrc } from "../../lib/courseStudio";
import { useFlags } from "../../lib/flags";
import { SALES_DEMO_FLAGS } from "../../lib/salesDemo";

export default function CourseStudioSamplePage() {
  const router = useRouter();
  const { flags, ready } = useFlags();
  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  const demoEnabled = !ready || flags[SALES_DEMO_FLAGS.enabled] !== false;

  useEffect(() => {
    const authenticated = Boolean(getToken());
    setSignedIn(authenticated);
    if (!authenticated) router.replace("/login");
  }, [router]);

  useEffect(() => {
    if (signedIn && ready && !demoEnabled) router.replace("/");
  }, [demoEnabled, ready, router, signedIn]);

  if (signedIn !== true || (ready && !demoEnabled)) {
    return <main style={{ padding: 40, textAlign: "center" }}>Loading the sample…</main>;
  }

  return (
    <main style={{ maxWidth: 1180, margin: "0 auto", padding: "28px 22px 70px" }}>
      <p className="theme-badge">SALES DEMO</p>
      <h1 className="theme-title" style={{ fontSize: 36, marginBottom: 8 }}>
        Course Studio — 10-minute sample
      </h1>
      <p className="muted" style={{ maxWidth: 720 }}>
        This frame is the live class for a sales presentation. It stops at 10 minutes.
        A registered learner who has paid for the class takes the full course from the library.
      </p>
      <p className="muted">
        Course Studio needs to be running on this computer at port 8040. An empty frame means it is not started yet.
      </p>
      <div style={{ margin: "12px 0 18px" }}>
        <Link href="/demo"><button type="button">← Back to the sales demo</button></Link>
      </div>
      <CourseStudioFrame
        title="Course Studio 10-minute sample"
        src={courseStudioFrameSrc({ access: "sample" })}
      />
    </main>
  );
}
