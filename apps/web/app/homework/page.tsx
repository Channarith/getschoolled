"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getFlag, gradeHomework, type HomeworkGrade } from "../lib/api";

export default function HomeworkPage() {
  const [flagReady, setFlagReady] = useState(false);
  const [homeworkOn, setHomeworkOn] = useState(false);

  const [subject, setSubject] = useState("biology");
  const [submission, setSubmission] = useState(
    "1. Plants convert light, water, and carbon dioxide into glucose and oxygen.\n2. The mitochondria releases energy from glucose."
  );
  const [handwritten, setHandwritten] = useState(false);
  const [grade, setGrade] = useState<HomeworkGrade | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getFlag("access.homework_grader")
      .then((v) => setHomeworkOn(Boolean(v)))
      .catch(() => setHomeworkOn(false))
      .finally(() => setFlagReady(true));
  }, []);

  async function onGrade() {
    setError("");
    setBusy(true);
    try {
      const assignment = {
        title: "Homework",
        subject,
        questions: [
          { type: "short", prompt: "Explain photosynthesis", answer_key: "" },
          { type: "short", prompt: "What does the mitochondria do?", answer_key: "" },
        ],
      };
      const g = await gradeHomework({ assignment, submission_text: submission, subject, handwritten });
      setGrade(g);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (flagReady && !homeworkOn) {
    return (
      <main className="container" style={{ maxWidth: 520 }}>
        <h1>Homework grader</h1>
        <div className="card">
          <p className="muted">
            This operator tool is disabled. An administrator can enable the{" "}
            <strong>access.homework_grader</strong> feature flag on the{" "}
            <Link href="/admin">Admin</Link> page.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="container">
      <h1>Homework grader</h1>
      <p className="muted">
        Paste a learner submission; the grader scores it against the assignment rubric.
      </p>

      <div className="card">
        <label style={{ display: "block", marginBottom: 8 }}>
          Subject
          <input value={subject} onChange={(e) => setSubject(e.target.value)}
            style={{ width: "100%", padding: 8 }} />
        </label>
        <label style={{ display: "block", marginBottom: 8 }}>
          Submission
          <textarea value={submission} onChange={(e) => setSubmission(e.target.value)}
            rows={8} style={{ width: "100%", padding: 8 }} />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <input type="checkbox" checked={handwritten} onChange={(e) => setHandwritten(e.target.checked)} />
          Handwritten / OCR submission
        </label>
        <button onClick={onGrade} disabled={busy}>
          {busy ? "Grading…" : "Grade homework"}
        </button>
      </div>

      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}

      {grade && (
        <div className="card">
          <h3>Result</h3>
          <p>Score: {Math.round(grade.percentage * 100) / 100}% ({grade.score}/{grade.max_score})</p>
          {grade.items.length > 0 && (
            <ul>
              {grade.items.map((it, i) => (
                <li key={i} className="muted">{it.rationale}</li>
              ))}
            </ul>
          )}
          {grade.validity_flags.length > 0 && (
            <p className="muted">flags: {grade.validity_flags.join(", ")}</p>
          )}
        </div>
      )}
    </main>
  );
}
