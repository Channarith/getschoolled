"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  checkAuthorship, generateHomework, getFlag, gradeHomework, scanHomework,
  type AuthorshipResult, type GeneratedAssignment, type HomeworkGrade,
} from "../lib/api";
import { useT } from "../lib/i18n";

export default function HomeworkPage() {
  const { t } = useT();
  const [flagReady, setFlagReady] = useState(false);
  const [homeworkOn, setHomeworkOn] = useState(false);

  const [subject, setSubject] = useState("biology");
  const [numQuestions, setNumQuestions] = useState(4);
  const [courseId, setCourseId] = useState("");
  const [sourceContent, setSourceContent] = useState(
    "Photosynthesis: the process by which plants convert light energy into glucose and oxygen.\n" +
    "Chlorophyll: the green pigment in leaves that captures light energy.\n" +
    "Glucose: the sugar that plants use and store for energy.\n" +
    "Stomata: tiny pores on a leaf that let carbon dioxide in and oxygen out."
  );
  const [assignment, setAssignment] = useState<GeneratedAssignment | null>(null);
  const [generating, setGenerating] = useState(false);

  const [submission, setSubmission] = useState(
    "1. Plants convert light, water, and carbon dioxide into glucose and oxygen.\n2. The mitochondria releases energy from glucose."
  );
  const [handwritten, setHandwritten] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [grade, setGrade] = useState<HomeworkGrade | null>(null);
  const [authorship, setAuthorship] = useState<AuthorshipResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getFlag("access.homework_grader")
      .then((v) => setHomeworkOn(Boolean(v)))
      .catch(() => setHomeworkOn(false))
      .finally(() => setFlagReady(true));
  }, []);

  async function onGenerate() {
    setError(""); setGenerating(true); setGrade(null);
    try {
      const a = await generateHomework({
        subject,
        num_questions: numQuestions,
        course_id: courseId.trim() || undefined,
        content: courseId.trim() ? undefined : sourceContent,
        title: `${subject} homework`,
      });
      setAssignment(a);
    } catch (e) {
      setError(String(e));
    } finally {
      setGenerating(false);
    }
  }

  async function onScan(file: File) {
    setError(""); setScanning(true);
    try {
      const r = await scanHomework(file, { hint: handwritten ? "handwritten" : undefined });
      setSubmission(r.raw_text || r.segments.join("\n"));
      if (r.handwritten) setHandwritten(true);
    } catch (e) {
      setError(String(e));
    } finally {
      setScanning(false);
    }
  }

  async function onGrade() {
    setError(""); setBusy(true); setAuthorship(null);
    try {
      // Grade against the GENERATED assignment when present; otherwise a small
      // built-in fallback so the tool still works before generating.
      const asg = assignment ?? {
        title: "Homework", subject,
        questions: [
          { type: "short", prompt: "Explain photosynthesis", answer_key: "" },
          { type: "short", prompt: "What does the mitochondria do?", answer_key: "" },
        ],
      };
      const [g, a] = await Promise.all([
        gradeHomework({
          assignment: asg, submission_text: submission, subject, handwritten,
          course_id: courseId.trim() || undefined,
        }),
        checkAuthorship(submission, handwritten).catch(() => null),
      ]);
      setGrade(g);
      setAuthorship(a);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (flagReady && !homeworkOn) {
    return (
      <main className="container" style={{ maxWidth: 520 }}>
        <h1>{t("homework.title")}</h1>
        <div className="card">
          <p className="muted">
            {t("homework.disabledBefore")}{" "}
            <Link href="/admin">{t("account.admin")}</Link>{" "}
            {t("homework.disabledAfter")}
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="container">
      <h1>{t("homework.title")}</h1>
      <p className="muted">{t("homework.intro")}</p>

      {/* 1) Generate an assignment from a subject (optionally grounded in a course). */}
      <div className="card">
        <h3 style={{ marginTop: 0 }}>1 · Generate homework</h3>
        <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
          <label style={{ flex: "1 1 160px" }}>
            {t("homework.subject")}
            <input value={subject} onChange={(e) => setSubject(e.target.value)} style={{ width: "100%", padding: 8 }} />
          </label>
          <label style={{ width: 120 }}>
            Questions
            <input type="number" min={1} max={12} value={numQuestions}
              onChange={(e) => setNumQuestions(Math.max(1, Math.min(12, Number(e.target.value) || 4)))}
              style={{ width: "100%", padding: 8 }} />
          </label>
          <label style={{ flex: "1 1 180px" }}>
            Course id <span className="muted">(optional)</span>
            <input value={courseId} onChange={(e) => setCourseId(e.target.value)}
              placeholder="e.g. intro-to-photosynthesis" style={{ width: "100%", padding: 8 }} />
          </label>
          <button onClick={onGenerate} disabled={generating}>
            {generating ? "Generating…" : "Generate"}
          </button>
        </div>
        <label style={{ display: "block", marginTop: 10 }}>
          Source material <span className="muted">(used when no course id is given)</span>
          <textarea value={sourceContent} onChange={(e) => setSourceContent(e.target.value)}
            rows={4} style={{ width: "100%", padding: 8 }}
            placeholder="Paste lesson notes / topic text; questions are generated from this." />
        </label>
        {assignment && (
          <div style={{ marginTop: 12 }}>
            <strong>{assignment.title}</strong> <span className="muted">· {assignment.questions.length} questions</span>
            <ol style={{ marginTop: 6 }}>
              {assignment.questions.map((q) => (
                <li key={q.question_id} style={{ marginBottom: 4 }}>
                  <span>{q.prompt}</span> <span className="muted">[{q.type}]</span>
                  {q.type === "mcq" && q.options.length > 0 && (
                    <div className="muted" style={{ fontSize: 13 }}>{q.options.join(" · ")}</div>
                  )}
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>

      {/* 2) Provide the student's submission (typed, pasted, or scanned) and grade it. */}
      <div className="card">
        <h3 style={{ marginTop: 0 }}>2 · Grade a submission</h3>
        <label style={{ display: "block", marginBottom: 8 }}>
          {t("homework.submission")}
          <textarea value={submission} onChange={(e) => setSubmission(e.target.value)}
            rows={8} style={{ width: "100%", padding: 8 }} />
        </label>
        <div className="row" style={{ gap: 12, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input type="checkbox" checked={handwritten} onChange={(e) => setHandwritten(e.target.checked)} />
            {t("homework.handwritten")}
          </label>
          <label className="muted" style={{ fontSize: 13 }}>
            📷 Scan file (OCR):{" "}
            <input type="file" accept="image/*,.txt,.pdf"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) void onScan(f); }} />
          </label>
          {scanning && <span className="muted">Scanning…</span>}
        </div>
        <button onClick={onGrade} disabled={busy}>
          {busy ? t("homework.grading") : (assignment ? "Grade against generated homework" : t("homework.gradeBtn"))}
        </button>
      </div>

      {error && <div className="card" style={{ borderColor: "#ff6b6b" }}><div className="muted">{error}</div></div>}

      {grade && (
        <div className="card">
          <h3>{t("homework.result")}</h3>
          <p>{t("homework.score", {
            pct: Math.round(grade.percentage * 100) / 100,
            score: grade.score,
            max: grade.max_score,
          })}</p>
          {grade.items.length > 0 && (
            <ul>
              {grade.items.map((it, i) => (
                <li key={i} className="muted">{it.rationale}</li>
              ))}
            </ul>
          )}
          {grade.validity_flags.length > 0 && (
            <p className="muted">{t("homework.flags")} {grade.validity_flags.join(", ")}</p>
          )}
          {authorship && (
            <p style={{ marginTop: 8 }}>
              <strong>Authorship:</strong>{" "}
              <span style={{ color: authorship.label === "ai" ? "#dc2626" : authorship.label === "human" ? "#16a34a" : "#d97706" }}>
                {authorship.label}
              </span>{" "}
              <span className="muted">({Math.round(authorship.ai_probability * 100)}% AI-likelihood — {authorship.note})</span>
            </p>
          )}
        </div>
      )}
    </main>
  );
}
