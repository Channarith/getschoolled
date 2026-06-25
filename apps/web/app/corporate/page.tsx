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
          {corpLessons.map((l) => (
            <div className="card" key={l.lesson_id}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <h3 style={{ margin: 0 }}>{l.title}</h3>
                <span className="pill" style={{ color: "#0369a1" }}>{t("corporate.corporateTag")}</span>
              </div>
              <p className="muted" style={{ fontSize: 13, marginBottom: 8 }}>
                {l.slides.length === 1
                  ? t("corporate.slides", { n: l.slides.length })
                  : t("corporate.slidesPlural", { n: l.slides.length })}{" "}
                · {t("corporate.aiTeacher")}
              </p>
              <Link href={`/corporate/learn?lesson=${encodeURIComponent(l.lesson_id)}`}>
                <button>{t("corporate.startCourse")}</button>
              </Link>
            </div>
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
