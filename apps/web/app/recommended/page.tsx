"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getHomeFeed,
  getToken,
  listStudents,
  recommendForProfile,
  type ForesightRec,
  type ForesightResult,
  type StudentProfile,
} from "../lib/api";
import { useT } from "../lib/i18n";

function homeFeedToResult(students: StudentProfile[], selected: string): ForesightResult {
  return {
    student_id: selected,
    difficulty: "beginner",
    gaps: [],
    cold_start: true,
    fallback: true,
    recommendations: [],
    relational_map: { nodes: [], edges: [] },
  };
}

export default function RecommendedPage() {
  const { t, locale } = useT();
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
    setError("");
    recommendForProfile({
      student_id: prof.id, mastery: prof.mastery,
      completed_course_ids: prof.completed_course_ids, interests: prof.interests,
    })
      .then((r) => {
        if (r.recommendations.length === 0) {
          return applyHomeFallback(r, prof.id);
        }
        setResult(r);
      })
      .catch(() => applyHomeFallback(homeFeedToResult(students, prof.id), prof.id));
  }, [selected, students, locale]);

  async function applyHomeFallback(base: ForesightResult, studentId: string) {
    try {
      const rails = await getHomeFeed(false, locale);
      const popular = rails.find((r) => r.key === "popular")?.courses
        ?? rails.find((r) => r.courses.length)?.courses
        ?? [];
      const recs: ForesightRec[] = popular.slice(0, 8).map((c) => ({
        course_id: c.course_id,
        title: c.title,
        score: 1,
        covers_gaps: [],
        reason: "Popular starter pick — great for your first classes",
      }));
      setResult({
        ...base,
        student_id: studentId,
        cold_start: true,
        fallback: true,
        recommendations: recs,
      });
      setError("");
    } catch (e) {
      setError(String(e));
      setResult(base);
    }
  }

  if (!loggedIn) {
    return (
      <main className="container">
        <h1>{t("recommended.title")}</h1>
        <div className="card">
          <p>
            {t("recommended.signInBefore")}{" "}
            <Link href="/login">{t("profile.signIn")}</Link>{" "}
            {t("recommended.signInMid")}{" "}
            <Link href="/account">{t("account.title")}</Link>{" "}
            {t("recommended.signInAfter")}
          </p>
        </div>
      </main>
    );
  }

  const prof = students.find((s) => s.id === selected);

  return (
    <main className="container">
      <h1>{t("recommended.title")}</h1>
      <p className="muted">{t("recommended.intro")}</p>

      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}

      {students.length === 0 ? (
        <div className="card">
          <p>
            {t("recommended.noProfilesBefore")}{" "}
            <Link href="/account">{t("account.title")}</Link>{" "}
            {t("recommended.noProfilesAfter")}
          </p>
        </div>
      ) : (
        <div className="card">
          <label>{t("recommended.studentProfile")}&nbsp;
            <select value={selected} onChange={(e) => setSelected(e.target.value)}>
              {students.map((s) => <option key={s.id} value={s.id}>{s.display_name}</option>)}
            </select>
          </label>
          {prof && (
            <div className="muted" style={{ marginTop: 6 }}>
              {t("recommended.knownSkills")}{" "}
              {Object.keys(prof.mastery).length
                ? Object.entries(prof.mastery).map(([k, v]) => `${k} ${Math.round(v * 100)}%`).join(", ")
                : t("recommended.noSkills")}
            </div>
          )}
        </div>
      )}

      {result && (
        <>
          {result.cold_start && (
            <div className="card" style={{ borderColor: "#16a34a", marginTop: 12 }}>
              <strong>{t("recommended.starterTitle")}</strong>
              <p className="muted" style={{ margin: "6px 0 0", fontSize: 14 }}>
                {t("recommended.starterBody")}
              </p>
            </div>
          )}
          <div className="card" style={{ borderColor: "#6ea8fe", marginTop: 12 }}>
            <strong>{t("recommended.adapted", { level: result.difficulty })}</strong>
            {result.gaps.length > 0 && (
              <div className="muted">{t("recommended.gaps")} {result.gaps.join(", ")}</div>
            )}
          </div>

          <h3>{t("recommended.topPicks")}</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 12 }}>
            {result.recommendations.length === 0 && (
              <div className="muted">{t("recommended.noRecs")}</div>
            )}
            {result.recommendations.map((r) => (
              <div className="card" key={r.course_id}>
                <strong>{r.title}</strong>
                <div className="muted" style={{ fontSize: 12 }}>
                  {t("recommended.matchScore", { score: r.score })}
                </div>
                <p className="muted" style={{ marginTop: 6 }}>{r.reason}</p>
                {r.covers_gaps.length > 0 && (
                  <div style={{ fontSize: 11 }}>{t("recommended.covers")} {r.covers_gaps.join(", ")}</div>
                )}
                <Link href={`/browse?q=${encodeURIComponent(r.title)}`} style={{ fontSize: 13 }}>
                  {t("recommended.openCourse")}
                </Link>
              </div>
            ))}
          </div>
        </>
      )}
    </main>
  );
}
