"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import SurveyForm from "./SurveyForm";
import {
  createStudent,
  getMe,
  getOnboardingSurvey,
  getToken,
  listStudents,
  submitLearningProfile,
  submitOnboardingSurveyAnalytics,
  type SurveyTemplate,
} from "../lib/api";

const DISCLAIMER_KEY = "aoep_disclaimer_accepted_v1";
const STORAGE_KEY = "aoep_onboarding_survey_v1";

function requiredMissing(template: SurveyTemplate, answers: Record<string, unknown>): string[] {
  return template.questions
    .filter((q) => q.required && (answers[q.id] == null || answers[q.id] === ""))
    .map((q) => q.id);
}

/** One-time learning-behavior survey after signup (after legal disclaimer). */
export default function OnboardingSurveyGate() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [template, setTemplate] = useState<SurveyTemplate | null>(null);
  const [answers, setAnswers] = useState<Record<string, string | number | boolean>>({});
  const [studentId, setStudentId] = useState<string | null>(null);
  const [accountId, setAccountId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [doneCategory, setDoneCategory] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        if (!getToken()) return;
        if (!localStorage.getItem(DISCLAIMER_KEY)) return;
        if (localStorage.getItem(STORAGE_KEY)) return;

        const me = await getMe();
        const survey = await getOnboardingSurvey(me.id, me.tier);
        if (!survey.enabled || !survey.template) return;

        let students = (await listStudents()).students;
        if (!students.length) {
          const created = await createStudent(me.display_name || me.email.split("@")[0]);
          students = [created];
        }
        const primary = students.find((s) => !s.onboarding_completed_at) ?? students[0];
        if (primary.onboarding_completed_at) {
          localStorage.setItem(STORAGE_KEY, String(primary.onboarding_completed_at));
          return;
        }
        if (cancelled) return;
        setAccountId(me.id);
        setStudentId(primary.id);
        setTemplate(survey.template);
        setAnswers({});
        setOpen(true);
      } catch {
        /* offline / service down — don't block the app */
      }
    }
    load();
    return () => { cancelled = true; };
  }, [pathname]);

  async function onSubmit() {
    if (!template || !studentId || !accountId) return;
    const missing = requiredMissing(template, answers);
    if (missing.length) {
      setError("Please answer all required questions.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const res = await submitLearningProfile(studentId, answers);
      await submitOnboardingSurveyAnalytics({
        account_id: accountId,
        student_id: studentId,
        answers,
      }).catch(() => undefined);
      localStorage.setItem(STORAGE_KEY, String(Date.now()));
      setDoneCategory(res.learner_category);
      setTimeout(() => setOpen(false), 1800);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  function onSkip() {
    try {
      localStorage.setItem(STORAGE_KEY, "skipped");
    } catch { /* ignore */ }
    setOpen(false);
  }

  if (!open || !template) return null;

  return (
    <div role="dialog" aria-modal="true" aria-label="Learning profile survey"
      style={{
        position: "fixed", inset: 0, zIndex: 1001, display: "flex",
        alignItems: "center", justifyContent: "center",
        background: "rgba(0,0,0,0.65)", padding: 16,
      }}>
      <div className="card" style={{ maxWidth: 640, maxHeight: "90vh", overflowY: "auto", width: "100%" }}>
        <h2 style={{ marginTop: 0 }}>{template.title}</h2>
        {doneCategory ? (
          <p>
            Thanks! We&apos;ll adapt courses for a <strong>{doneCategory.replace(/_/g, " ")}</strong> learner profile.
          </p>
        ) : (
          <>
            <SurveyForm template={template} answers={answers} onChange={setAnswers} disabled={busy} />
            {error && <p className="muted" style={{ color: "#ff6b6b" }}>{error}</p>}
            <div className="row" style={{ marginTop: 16, gap: 8, flexWrap: "wrap" }}>
              <button onClick={onSubmit} disabled={busy}>{busy ? "Saving…" : "Save my learning profile"}</button>
              <button onClick={onSkip} disabled={busy} style={{ background: "transparent", border: "1px solid var(--border)" }}>
                Skip for now
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
