"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getToken,
  listStudents,
  recommendForProfile,
  type ForesightResult,
  type StudentProfile,
} from "../lib/api";

export default function RecommendedPage() {
  const [students, setStudents] = useState<StudentProfile[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [result, setResult] = useState<ForesightResult | null>(null);
  const [error, setError] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    setLoggedIn(Boolean(getToken()));
    if (getToken()) {
      listStudents().then((r) => {
        setStudents(r.students);
        if (r.students.length) setSelected(r.students[0].id);
      }).catch((e) => setError(String(e)));
    }
  }, []);

  useEffect(() => {
    const prof = students.find((s) => s.id === selected);
    if (!prof) return;
    recommendForProfile({
      student_id: prof.id, mastery: prof.mastery,
      completed_course_ids: prof.completed_course_ids, interests: prof.interests,
    }).then(setResult).catch((e) => setError(String(e)));
  }, [selected, students]);

  if (!loggedIn) {
    return (
      <main className="container">
        <h1>Recommended for you</h1>
        <div className="card"><p>Please <Link href="/login">sign in</Link> and add a student profile (on <Link href="/account">Account</Link>) to get personalized recommendations.</p></div>
      </main>
    );
  }

  const prof = students.find((s) => s.id === selected);

  return (
    <main className="container">
      <h1>Recommended for you</h1>
      <p className="muted">
        Powered by <strong>Foresight</strong> — recommendations adapt to each
        student profile&apos;s mastery and history, targeting the skills they&apos;re lacking.
      </p>

      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}

      {students.length === 0 ? (
        <div className="card"><p>No student profiles yet. Add one on the <Link href="/account">Account</Link> page.</p></div>
      ) : (
        <div className="card">
          <label>Student profile&nbsp;
            <select value={selected} onChange={(e) => setSelected(e.target.value)}>
              {students.map((s) => <option key={s.id} value={s.id}>{s.display_name}</option>)}
            </select>
          </label>
          {prof && (
            <div className="muted" style={{ marginTop: 6 }}>
              Known skills: {Object.keys(prof.mastery).length
                ? Object.entries(prof.mastery).map(([k, v]) => `${k} ${Math.round(v * 100)}%`).join(", ")
                : "none yet — add mastery on Account"}
            </div>
          )}
        </div>
      )}

      {result && (
        <>
          <div className="card" style={{ borderColor: "#6ea8fe" }}>
            <strong>Adapted difficulty: {result.difficulty}</strong>
            {result.gaps.length > 0 && (
              <div className="muted">Skill gaps to focus on: {result.gaps.join(", ")}</div>
            )}
          </div>

          <h3>Top picks</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 12 }}>
            {result.recommendations.length === 0 && <div className="muted">No recommendations — try adding mastery gaps.</div>}
            {result.recommendations.map((r) => (
              <div className="card" key={r.course_id}>
                <strong>{r.title}</strong>
                <div className="muted" style={{ fontSize: 12 }}>match score {r.score}</div>
                <p className="muted" style={{ marginTop: 6 }}>{r.reason}</p>
                {r.covers_gaps.length > 0 && (
                  <div style={{ fontSize: 11 }}>covers: {r.covers_gaps.join(", ")}</div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </main>
  );
}
