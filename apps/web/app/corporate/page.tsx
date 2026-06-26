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

const TRACK_ORDER = ["AI", "Data", "Engineering"];
const TRACK_LABELS: Record<string, string> = {
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

      {programs?.map((p) => (
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
                {courses[cid]
                  ? <Link href={`/watch?course=${cid}`}>{courses[cid].title}</Link>
                  : <span className="muted">{cid}</span>}
                {courses[cid] && (
                  <span className="muted" style={{ fontSize: 12 }}>
                    {" "}· {courses[cid].level} · {courses[cid].duration_min} min
                  </span>
                )}
              </li>
            ))}
          </ul>
          <div className="row" style={{ marginTop: 8 }}>
            <Link href="/class"><button>{t("corporate.startProgram")}</button></Link>
            <Link href="/account">
              <button style={{ background: "transparent", border: "1px solid var(--border)" }}>
                {t("corporate.assignTeam")}
              </button>
            </Link>
          </div>
        </div>
      ))}
    </main>
  );
}
