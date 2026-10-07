import Link from "next/link";

import { PUBLIC_COURSES } from "../lib/courseStudio";

/** Driver's ed demo and the two paid courses, for the public Salareen page. */
export function PublicCourses() {
  const drivers = PUBLIC_COURSES[0];
  const food = PUBLIC_COURSES[1];
  return (
    <section aria-label="Courses" style={{ width: "100%", maxWidth: 720, margin: "28px auto 0", textAlign: "left" }}>
      <h2 style={{ fontSize: 22, margin: "0 0 8px" }}>Demo</h2>
      <p style={{ margin: "0 0 12px" }}>
        Driver&apos;s Education is free for 10 minutes. Anyone can start it, with or without an account.
      </p>
      <p style={{ margin: "0 0 18px" }}>
        <Link href={drivers.demoHref}><button type="button">Start the free driver&apos;s ed demo</button></Link>
      </p>
      <h2 style={{ fontSize: 22, margin: "0 0 8px" }}>Full courses</h2>
      <p style={{ margin: "0 0 12px" }}>
        Admins take the full course. Everyone else pays.
      </p>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <Link href={drivers.href}><button type="button">{drivers.title}</button></Link>
        <Link href={food.href}><button type="button">{food.title}</button></Link>
      </div>
    </section>
  );
}
