"use client";

import { useEffect, useState } from "react";
import {
  createStudent,
  getMe,
  getOnboardingSurvey,
  listStudents,
  skipLearningProfile,
  submitLearningProfile,
  submitOnboardingSurveyAnalytics,
  type SurveyQuestion,
  type SurveyTemplate,
} from "../lib/api";

type Answers = Record<string, string | number | boolean>;

type Props = {
  learnerName: string;
  onBack: () => void;
  onDone: () => void;
};

const ANSWERS_KEY = "onboarding_learning_answers";

function savedAnswers(): Answers {
  try {
    return JSON.parse(localStorage.getItem(ANSWERS_KEY) || "{}") as Answers;
  } catch {
    return {};
  }
}

/** Learning-profile questions asked one per screen inside the setup assistant. */
export default function LearningPreferencesStep({ learnerName, onBack, onDone }: Props) {
  const [template, setTemplate] = useState<SurveyTemplate | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [index, setIndex] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setAnswers(savedAnswers());
    getMe()
      .then((me) => getOnboardingSurvey(me.id, me.tier))
      .then((survey) => setTemplate(survey.enabled ? survey.template : null))
      .catch(() => setTemplate(null))
      .finally(() => setLoaded(true));
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(ANSWERS_KEY, JSON.stringify(answers));
    } catch {
      /* private mode */
    }
  }, [answers]);

  if (!loaded) return <p className="muted">Loading your learning preferences…</p>;

  if (!template || template.questions.length === 0) {
    return (
      <>
        <h2 style={{ marginTop: 0 }}>Your learning</h2>
        <p className="muted">You can personalize pace and style later in Account → Learning profile.</p>
        <button type="button" className="btn primary" onClick={onDone}>Continue</button>
      </>
    );
  }

  const questions = template.questions;
  const question: SurveyQuestion = questions[index];
  const value = answers[question.id];
  const answered = !question.required || (value != null && value !== "");
  const last = index === questions.length - 1;

  function set(next: string | number | boolean) {
    setAnswers((current) => ({ ...current, [question.id]: next }));
  }

  async function studentId(): Promise<string> {
    const students = (await listStudents()).students;
    const primary = students.find((s) => !s.onboarding_completed_at) ?? students[0];
    if (primary) return primary.id;
    return (await createStudent(learnerName || "Learner")).id;
  }

  async function save() {
    setBusy(true);
    setError("");
    try {
      const me = await getMe();
      const id = await studentId();
      await submitLearningProfile(id, answers);
      await submitOnboardingSurveyAnalytics({
        account_id: me.id, student_id: id, answers,
      }).catch(() => undefined);
      localStorage.removeItem(ANSWERS_KEY);
      window.dispatchEvent(new CustomEvent("aoep-learning-profile-saved"));
      onDone();
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function skip() {
    setBusy(true);
    setError("");
    try {
      await skipLearningProfile(await studentId());
      localStorage.removeItem(ANSWERS_KEY);
      onDone();
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  const option = (label: string, selected: boolean, onClick: () => void) => (
    <button
      key={label}
      type="button"
      aria-pressed={selected}
      disabled={busy}
      onClick={onClick}
      style={{
        textAlign: "left", padding: "14px 16px", borderRadius: 14, cursor: "pointer",
        border: selected ? "2px solid #72d8ff" : "1px solid #3b4568",
        background: selected ? "#14364b" : "#111831", color: "#eef4ff", fontSize: 16,
      }}
    >
      {label}
    </button>
  );

  return (
    <>
      <p className="muted" style={{ marginTop: 0 }}>
        Your learning · {index + 1} of {questions.length}
      </p>
      <h2 style={{ marginTop: 0, fontSize: 30, lineHeight: 1.15 }}>
        {question.prompt}{question.required ? "" : " (optional)"}
      </h2>
      <div style={{ display: "grid", gap: 10, margin: "18px 0" }}>
        {question.type === "choice" && question.options.map((opt) => (
          option(opt, value === opt, () => set(opt))
        ))}
        {question.type === "bool" && (
          <>
            {option("Yes", value === true, () => set(true))}
            {option("No", value === false, () => set(false))}
          </>
        )}
        {question.type === "rating" && [1, 2, 3, 4, 5].map((n) => (
          option("★".repeat(n), Number(value ?? 0) === n, () => set(n))
        ))}
        {question.type === "text" && (
          <textarea
            rows={4}
            disabled={busy}
            value={String(value ?? "")}
            onChange={(event) => set(event.target.value)}
            style={{ width: "100%", padding: 12 }}
          />
        )}
      </div>
      {error && <p style={{ color: "#f87171" }}>{error}</p>}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <button
          type="button"
          disabled={busy}
          onClick={() => (index === 0 ? onBack() : setIndex(index - 1))}
          style={{ padding: "8px 18px", borderRadius: 8, border: "1px solid #e2e8f0", background: "#fff", cursor: "pointer", fontWeight: 600 }}
        >
          ← Back
        </button>
        <button
          type="button"
          className="btn primary"
          disabled={busy || !answered}
          onClick={() => (last ? void save() : setIndex(index + 1))}
        >
          {busy ? "Saving…" : last ? "Save and continue" : "Next"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void skip()}
          style={{ background: "transparent", border: "1px solid #3b4568", color: "#cbd5ea", borderRadius: 8, padding: "8px 14px" }}
        >
          Set up later
        </button>
      </div>
    </>
  );
}
