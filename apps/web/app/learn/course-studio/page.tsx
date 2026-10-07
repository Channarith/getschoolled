import Link from "next/link";

import { PUBLIC_COURSES } from "../../lib/courseStudio";

export default function CourseStudioDirectoryPage() {
  return (
    <main className="container">
      <h1>Courses</h1>
      <div className="card">
        <p>Driver&apos;s Education has a free 10-minute demo. Both full courses are paid unless you are an admin.</p>
        <ul>
          {PUBLIC_COURSES.map((course) => (
            <li key={course.id}>
              <Link href={course.href}>{course.title}</Link>
              {course.demoHref ? (
                <>
                  {" — "}
                  <Link href={course.demoHref}>10-minute demo</Link>
                </>
              ) : null}
              <div className="muted">{course.blurb}</div>
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}
