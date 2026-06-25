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

export default function CorporatePage() {
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
    // AI-led corporate courses come from the orchestrator (lessons tagged
    // AUDIENCE: corporate). These are taught live by the AI teacher.
    listLessons()
      .then((ls) => setCorpLessons(ls.filter((l) => (l.audience ?? "general") === "corporate")))
      .catch(() => setCorpLessons([]));
  }, []);

  return (
    <main className="container">
      <h1>Corporate training programs</h1>
      <p className="muted">
        Curated, multi-course tracks for enterprise teams — onboarding, compliance,
        and upskilling. Adaptive sequencing advances each learner by mastery.
      </p>

      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}

      {corpLessons.length > 0 && (
        <div style={{ marginBottom: 18 }}>
          <h2 style={{ marginBottom: 4 }}>AI-led courses</h2>
          <p className="muted" style={{ marginTop: 0 }}>
            Taught live by the AI teacher — start anytime, ask questions, learn at your pace.
          </p>
          {corpLessons.map((l) => (
            <div className="card" key={l.lesson_id}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <h3 style={{ margin: 0 }}>{l.title}</h3>
                <span className="pill" style={{ color: "#0369a1" }}>corporate</span>
              </div>
              <p className="muted" style={{ fontSize: 13, marginBottom: 8 }}>
                {l.slides.length} slide{l.slides.length === 1 ? "" : "s"} · AI teacher · Q&amp;A
              </p>
              <Link href={`/corporate/learn?lesson=${encodeURIComponent(l.lesson_id)}`}>
                <button>Start course</button>
              </Link>
            </div>
          ))}
        </div>
      )}
      {programs === null && !error && <p className="muted">Loading programs…</p>}
      {programs && programs.length === 0 && (
        <div className="card">
          <p className="muted">No corporate programs yet. An admin can create them via the
            curriculum <code>POST /programs</code> API (audience &ldquo;corporate&rdquo;).</p>
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
            <strong>{p.course_ids.length}</strong> course{p.course_ids.length === 1 ? "" : "s"}:
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
            <Link href="/class"><button>Start program</button></Link>
            <Link href="/account"><button style={{ background: "transparent", border: "1px solid var(--border)" }}>Assign to team</button></Link>
          </div>
        </div>
      ))}
    </main>
  );
}
