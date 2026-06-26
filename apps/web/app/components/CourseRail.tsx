"use client";

import { useRouter } from "next/navigation";
import { bumpCourseView, type CatalogCourse, type HomeRail } from "../lib/api";
import { CoursePosterImg } from "./CoursePosterImg";

export function Tile({ course, kids = false }: { course: CatalogCourse; kids?: boolean }) {
  const router = useRouter();
  const open = () => {
    void bumpCourseView(course.course_id);
    if (course.deep_link) {
      router.push(course.deep_link);
      return;
    }
    if (course.media_format === "audio" || course.format === "audio") {
      router.push(`/drive?course=${encodeURIComponent(course.course_id)}`);
      return;
    }
    if (course.format === "live_class" || course.source === "lesson") {
      router.push(`/class?lesson=${encodeURIComponent(course.course_id)}`);
      return;
    }
    router.push(`/watch?course=${encodeURIComponent(course.course_id)}`);
  };
  const typeLabel = course.format || course.source || course.media_format;
  const tierLabel = course.access_tier && course.access_tier !== "free" ? course.access_tier : "free";
  const posterInput = {
    title: course.title,
    category: course.category,
    subject: course.subject,
    tags: course.tags,
    format: course.format,
    media_format: course.media_format,
    thumbnail: course.thumbnail,
  };
  return (
    <div className="tile" onClick={open} role="button" tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && open()}>
      <div className="tile-art">
        <CoursePosterImg input={posterInput} className="tile-poster" />
        <div className="tile-art-scrim" aria-hidden />
        {kids && <span className="tile-art-badge">🎈</span>}
      </div>
      <div className="tile-body">
        <strong style={{ fontSize: kids ? 15 : 14 }}>{course.title}</strong>
        <div className="meta">
          {(course.category || course.subject)} · {course.level}
          {course.duration_min ? ` · ${course.duration_min} min` : ""}
        </div>
        <div style={{ marginTop: 6 }}>
          <span className="pill" style={{ color: tierLabel === "free" ? "#16a34a" : "#b45309" }}>
            {tierLabel}
          </span>
          {typeLabel && (
            <span className="pill" style={{ color: "#0ea5e9" }}>{typeLabel}</span>
          )}
          {course.maturity_rating && course.maturity_rating !== "all" && (
            <span className="pill" style={{ color: "#6b7280" }}>{course.maturity_rating}</span>
          )}
          {course.hands_on && <span className="pill" style={{ color: "#7c3aed" }}>hands-on</span>}
        </div>
      </div>
    </div>
  );
}

export function Rail({ rail, kids = false }: { rail: HomeRail; kids?: boolean }) {
  if (!rail.courses?.length) return null;
  return (
    <section className="rail">
      <h2>{rail.title}</h2>
      <div className="rail-track">
        {rail.courses.map((c) => <Tile key={c.course_id} course={c} kids={kids} />)}
      </div>
    </section>
  );
}
