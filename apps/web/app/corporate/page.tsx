"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  getPrograms,
  listLessons,
  searchCourses,
  type CatalogCourse,
  type Lesson,
  type Program,
} from "../lib/api";
import { useT } from "../lib/i18n";

const TRACK_ORDER = [
  "Compliance", "Safety", "Privacy", "Trade", "Automotive",
  "AI", "Data", "Engineering",
];
const TRACK_LABELS: Record<string, string> = {
  Compliance: "Workplace Compliance",
  Safety: "Workplace Safety",
  Privacy: "Privacy & Security",
  Trade: "Trade & Export Control",
  Automotive: "Automotive",
  AI: "Artificial Intelligence",
  Data: "Data",
  Engineering: "Engineering",
};

function trackLabel(track: string): string {
  if (!track || track === "Other") return "AI-led";
  return TRACK_LABELS[track] ?? track;
}

// Group lessons by their `track` metadata, ordered AI → Data → Engineering →
// anything else. Lessons without a track fall into "Other".
function groupByTrack(lessons: Lesson[]): [string, Lesson[]][] {
  const groups: Record<string, Lesson[]> = {};
  for (const l of lessons) {
    const key = (l.track || "Other").trim() || "Other";
    (groups[key] ??= []).push(l);
  }
  const ordered = Object.keys(groups).sort((a, b) => {
    const ia = TRACK_ORDER.indexOf(a);
    const ib = TRACK_ORDER.indexOf(b);
    if (ia === -1 && ib === -1) return a.localeCompare(b);
    if (ia === -1) return 1;
    if (ib === -1) return -1;
    return ia - ib;
  });
  return ordered.map((k) => [k, groups[k]]);
}

function ProgrammeCard({ lesson }: { lesson: Lesson }) {
  const { t } = useT();
  const { lesson_id, title, summary, delivery, fit, level, role, slides } = lesson;
  const slidesLabel =
    slides.length === 1
      ? t("corporate.slides", { n: slides.length })
      : t("corporate.slidesPlural", { n: slides.length });
  return (
    <div className="card" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {delivery && (
        <span className="muted" style={{ fontSize: 12 }}>{delivery}</span>
      )}
      <h3 style={{ margin: 0 }}>{title}</h3>
      <p className="muted" style={{ margin: 0 }}>
        {summary || `${slidesLabel} · ${t("corporate.aiTeacher")}`}
      </p>
      {fit && (
        <div style={{ fontSize: 13 }}>
          <strong>Who&apos;s it for</strong>
          <div className="muted">{fit}</div>
        </div>
      )}
      <div style={{ flex: 1 }} />
      {(level || role) && (
        <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
          {level && <span className="pill" style={{ color: "#0369a1" }}>{level}</span>}
          {role && <span className="pill">{role}</span>}
        </div>
      )}
      <Link href={`/corporate/learn?lesson=${encodeURIComponent(lesson_id)}`}>
        <button style={{ width: "100%" }}>{t("corporate.startCourse")}</button>
      </Link>
    </div>
  );
}

export default function CorporatePage() {
  const { t } = useT();
  const [programs, setPrograms] = useState<Program[] | null>(null);
  const [courses, setCourses] = useState<Record<string, CatalogCourse>>({});
  const [corpLessons, setCorpLessons] = useState<Lesson[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getPrograms("corporate"), searchCourses({})])
      .then(([progs, all]) => {
        setPrograms(progs);
        const byId: Record<string, CatalogCourse> = {};
        for (const c of all) byId[c.course_id] = c;
        setCourses(byId);
      })
      .catch((e) => setError(String(e)));
    listLessons()
      .then((ls) => setCorpLessons(ls.filter((l) => (l.audience ?? "general") === "corporate")))
      .catch(() => setCorpLessons([]));
  }, []);

  return (
    <main className="container">
      <h1>{t("corporate.title")}</h1>
      <p className="muted">{t("corporate.intro")}</p>

      {/* Custom / bespoke Agentic courses for a specific company. */}
      <div
        className="card"
        style={{
          borderColor: "#6366f1",
          background: "linear-gradient(135deg, rgba(99,102,241,0.10), rgba(56,189,248,0.08))",
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
          <h2 style={{ margin: 0 }}>Need a custom course for your business?</h2>
          <span className="pill" style={{ color: "#4338ca" }}>Bespoke &amp; private</span>
        </div>
        <p className="muted" style={{ margin: 0 }}>
          We build custom Agentic courses tailored to your company&apos;s tools, workflows, and topics —
          complete with classes and materials made for your teams. Have them{" "}
          <strong>hosted privately</strong> for your employees or{" "}
          <strong>download</strong> them to run on your own systems.
        </p>
        <div className="row" style={{ marginTop: 6, gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <a href="mailto:courses@salareen.com?subject=Custom%20Agentic%20course%20for%20our%20business&body=Hi%20Salareen%20team%2C%0A%0AWe%27d%20like%20a%20custom%20Agentic%20course%20for%20our%20company.%0A%0ACompany%3A%20%0ATopics%2Fgoals%3A%20%0AApprox.%20number%20of%20employees%3A%20%0APrivate%20hosting%20or%20download%3A%20%0A%0AThanks%21">
            <button style={{ background: "#4f46e5", color: "#fff" }}>✉️ Consult us: courses@salareen.com</button>
          </a>
          <span className="muted" style={{ fontSize: 13 }}>
            Tell us your topics and team size — we&apos;ll design classes and materials for your organization.
          </span>
        </div>
      </div>

      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}

      {corpLessons.length > 0 && (
        <div style={{ marginBottom: 18 }}>
          <h2 style={{ marginBottom: 4 }}>{t("corporate.aiLed")}</h2>
          <p className="muted" style={{ marginTop: 0 }}>{t("corporate.aiLedDesc")}</p>
          {groupByTrack(corpLessons).map(([track, lessons]) => (
            <section key={track} style={{ marginTop: 18 }}>
              <h3 style={{ marginBottom: 8 }}>
                {trackLabel(track)} programmes{" "}
                <span className="muted" style={{ fontWeight: 400 }}>({lessons.length})</span>
              </h3>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
                  gap: 12,
                }}
              >
                {lessons.map((l) => (
                  <ProgrammeCard key={l.lesson_id} lesson={l} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
      {programs === null && !error && <p className="muted">{t("corporate.loading")}</p>}
      {programs && programs.length === 0 && (
        <div className="card">
          <p className="muted">{t("corporate.noPrograms")}</p>
        </div>
      )}

      {programs?.map((p) => {
        const lessonById: Record<string, Lesson> = {};
        for (const l of corpLessons) lessonById[l.lesson_id] = l;
        const firstLesson = p.course_ids.map((cid) => lessonById[cid]).find(Boolean);
        return (
        <div className="card" key={p.program_id}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h3 style={{ margin: 0 }}>{p.title}</h3>
            <span className="pill" style={{ color: "#0369a1" }}>{p.audience || "enterprise"}</span>
          </div>
          <p className="muted">{p.description}</p>
          <div style={{ fontSize: 13, marginTop: 6 }}>
            <strong>{p.course_ids.length}</strong>{" "}
            {p.course_ids.length === 1
              ? t("corporate.courses", { n: p.course_ids.length })
              : t("corporate.coursesPlural", { n: p.course_ids.length })}:
          </div>
          <ul style={{ marginTop: 6 }}>
            {p.course_ids.map((cid) => (
              <li key={cid}>
                {lessonById[cid]
                  ? <Link href={`/corporate/learn?lesson=${encodeURIComponent(cid)}`}>{lessonById[cid].title}</Link>
                  : courses[cid]
                    ? <Link href={`/watch?course=${cid}`}>{courses[cid].title}</Link>
                    : <span className="muted">{cid}</span>}
                {!lessonById[cid] && courses[cid] && (
                  <span className="muted" style={{ fontSize: 12 }}>
                    {" "}· {courses[cid].level} · {courses[cid].duration_min} min
                  </span>
                )}
              </li>
            ))}
          </ul>
          <div className="row" style={{ marginTop: 8 }}>
            <Link href={firstLesson ? `/corporate/learn?lesson=${encodeURIComponent(firstLesson.lesson_id)}` : "/class"}>
              <button>{t("corporate.startProgram")}</button>
            </Link>
            <a href="mailto:sales@salareen.com?subject=Team%20seats%20for%20corporate%20training">
              <button style={{ background: "transparent", border: "1px solid var(--border)" }}>
                {t("corporate.assignTeam")}
              </button>
            </a>
          </div>
        </div>
        );
      })}
    </main>
  );
}
