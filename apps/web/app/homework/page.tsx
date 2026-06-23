"use client";

import { useEffect, useState } from "react";
import { gradeHomework, isAdminUnlocked, unlockAdmin, type HomeworkGrade } from "../lib/api";

export default function HomeworkPage() {
  const [admin, setAdmin] = useState(false);
  const [adminReady, setAdminReady] = useState(false);
  const [pw, setPw] = useState("");
  const [pwError, setPwError] = useState("");
  useEffect(() => {
    setAdmin(isAdminUnlocked());
    setAdminReady(true);
  }, []);

  const [subject, setSubject] = useState("biology");
  const [submission, setSubmission] = useState(
    "1. Plants convert light, water, and carbon dioxide into glucose and oxygen.\n2. The mitochondria releases energy from glucose."
  );
  const [handwritten, setHandwritten] = useState(false);
  const [grade, setGrade] = useState<HomeworkGrade | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onGrade() {
    setError("");
    setBusy(true);
    try {
      // Minimal demo assignment (two short-answer questions).
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

  function onUnlock(e: React.FormEvent) {
    e.preventDefault();
    if (unlockAdmin(pw)) {
      setAdmin(true);
      setPwError("");
    } else {
      setPwError("Incorrect admin password.");
    }
    setPw("");
  }

  // Operator-only tool: gate behind the admin password (default 88888888,
  // configurable via NEXT_PUBLIC_ADMIN_UNLOCK). Server endpoints are already
  // internal-only; this hides the UI from learners/preview/paying customers.
  if (adminReady && !admin) {
    return (
      <main className="container" style={{ maxWidth: 480 }}>
        <h1>🔒 Admin only</h1>
        <p className="muted">
          The Homework grader is an operator tool, not a learner feature. Enter the
          admin password to access it.
        </p>
        <form onSubmit={onUnlock} className="card">
          <label style={{ display: "block", marginBottom: 8 }}>Admin password</label>
          <input
            type="password"
            value={pw}
            onChange={(e) => setPw(e.target.value)}
            placeholder="••••••••"
            autoFocus
            style={{ width: "100%", padding: 10 }}
          />
          {pwError && <div className="muted" style={{ color: "#ff6b6b", marginTop: 8 }}>{pwError}</div>}
          <div className="row" style={{ marginTop: 12 }}>
            <button type="submit" disabled={!pw}>Unlock</button>
          </div>
        </form>
      </main>
    );
  }

  return (
    <main className="container">
      <h1>Homework grader</h1>
      <p className="muted">
        Paste (or scan) a submission. We check correctness against our catalog and
        trusted sources, flag possible AI authorship, and route disputes to a human.
      </p>

      <div className="card">
        <label>Subject&nbsp;
          <input value={subject} onChange={(e) => setSubject(e.target.value)} />
        </label>
        <label style={{ marginLeft: 12 }}>
          <input type="checkbox" checked={handwritten} onChange={(e) => setHandwritten(e.target.checked)} />
          &nbsp;handwritten
        </label>
        <textarea
          value={submission}
          onChange={(e) => setSubmission(e.target.value)}
          rows={6}
          style={{ width: "100%", marginTop: 8 }}
        />
        <div className="row" style={{ marginTop: 8 }}>
          <button onClick={onGrade} disabled={busy || !submission.trim()}>
            {busy ? "Grading…" : "Grade homework"}
          </button>
        </div>
      </div>

      {error && (
        <div className="card" style={{ borderColor: "#ff6b6b" }}>
          <div className="muted">{error}</div>
        </div>
      )}

      {grade && (
        <div className="card">
          <h3>
            Score: {grade.score} / {grade.max_score} ({grade.percentage}%)
          </h3>
          <div className="muted">
            Authorship: {grade.authorship_label ?? "n/a"}
            {grade.validity_flags.length > 0 && (
              <> · flags: {grade.validity_flags.join(", ")}</>
            )}
          </div>
          <ul>
            {grade.items.map((it, i) => (
              <li key={i}>
                <strong>{it.type}</strong>: score {it.score}{" "}
                {it.correct === true ? "✓" : it.correct === false ? "✗" : "(needs review)"}
                {it.citations.length > 0 && (
                  <div className="muted">
                    sources:{" "}
                    {it.citations
                      .map((c) => c.url || c.source || "")
                      .filter(Boolean)
                      .join(", ")}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </main>
  );
}
