import Link from "next/link";

import { PUBLIC_COURSES } from "../lib/courseStudio";

/** Paid courses. Shown on Live Class and Group Class, not on the public home page. */
export function FullCourseLinks() {
  return (
    <section className="card" aria-label="Full courses">
      <h2 style={{ marginTop: 0 }}>Full courses</h2>
      <p className="muted" style={{ marginTop: 0 }}>
        Admins take the full course. Everyone else pays.
      </p>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        {PUBLIC_COURSES.map((course) => (
          <Link key={course.id} href={course.href}>
            <button type="button">{course.title}</button>
          </Link>
        ))}
      </div>
    </section>
  );
}
