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
  const { lesson_id, title, summary, delivery, fit, level, role, slides } = lesson;
  return (
    <div className="card" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {delivery && (
        <span className="muted" style={{ fontSize: 12 }}>{delivery}</span>
      )}
      <h3 style={{ margin: 0 }}>{title}</h3>
      <p className="muted" style={{ margin: 0 }}>
        {summary || `${slides.length} slide${slides.length === 1 ? "" : "s"} · AI teacher · Q&A`}
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
        <button style={{ width: "100%" }}>Start course</button>
      </Link>
    </div>
  );
}

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
          <h2 style={{ marginBottom: 4 }}>AI-led programmes</h2>
          <p className="muted" style={{ marginTop: 0 }}>
            Taught live by the AI teacher — start anytime, ask questions, learn at your pace.
          </p>
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
