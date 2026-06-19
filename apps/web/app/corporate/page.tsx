"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  getPrograms,
  searchCourses,
  type CatalogCourse,
  type Program,
} from "../lib/api";

export default function CorporatePage() {
  const [programs, setPrograms] = useState<Program[] | null>(null);
  const [courses, setCourses] = useState<Record<string, CatalogCourse>>({});
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
  }, []);

  return (
    <main className="container">
      <h1>Corporate training programs</h1>
      <p className="muted">
        Curated, multi-course tracks for enterprise teams — onboarding, compliance,
        and upskilling. Adaptive sequencing advances each learner by mastery.
      </p>

      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}
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
