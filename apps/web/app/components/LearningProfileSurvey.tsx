"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import SurveyForm from "./SurveyForm";
import {
  createStudent,
  getMe,
  getOnboardingSurvey,
  getToken,
  listStudents,
  skipLearningProfile,
  submitLearningProfile,
  submitOnboardingSurveyAnalytics,
  type StudentProfile,
  type SurveyTemplate,
} from "../lib/api";

export const OPEN_LEARNING_PROFILE_EVENT = "aoep-open-learning-profile";

const DISCLAIMER_KEY = "aoep_disclaimer_accepted_v1";

function requiredMissing(template: SurveyTemplate, answers: Record<string, unknown>): string[] {
  return template.questions
    .filter((q) => q.required && (answers[q.id] == null || answers[q.id] === ""))
    .map((q) => q.id);
}

function answersFromProfile(student: StudentProfile): Record<string, string | number | boolean> {
  const stored = student.onboarding_answers;
  if (stored && Object.keys(stored).length) {
    return stored as Record<string, string | number | boolean>;
  }
  const styleLabels: Record<string, string> = {
    visual: "Visual — diagrams, video, demonstrations",
    auditory: "Auditory — listening, discussion, narration",
    reading_writing: "Reading & writing — notes, text, written steps",
    hands_on: "Hands-on — practice, labs, doing it yourself",
    mixed: "Mixed — no single style stands out",
  };
  const paceLabels: Record<string, string> = {
    slow: "Slower with more review",
    moderate: "Moderate and steady",
    fast: "Faster with less repetition",
  };
  const structureLabels: Record<string, string> = {
    step_by_step: "Step-by-step in order",
    examples_first: "Examples first, then rules",
    big_picture: "Big picture first, then details",
    practice_heavy: "Short bursts with frequent practice",
  };
  const sessionLabels: Record<string, string> = {
    short: "About 10 minutes",
    medium: "About 20–30 minutes",
    long: "45 minutes or longer",
  };
  const groupLabels: Record<string, string> = {
    solo: "Mostly on my own",
    group: "Small group or class",
    either: "Either works for me",
  };
  const readingLabels: Record<string, string> = {
    beginner: "Beginner — keep language simple",
    intermediate: "Intermediate",
    advanced: "Advanced — dense text is fine",
  };
  const motivationLabels: Record<string, string> = {
    career: "Career / job skills",
    school: "School or certification",
    personal: "Personal curiosity",
    other: "Other",
  };
  const acc = student.accessibility || {};
  return {
    primary_style: styleLabels[student.primary_style || ""] || "",
    pace: paceLabels[student.learning_pace || ""] || "",
    structure: structureLabels[student.learning_structure || ""] || "",
    session_length: sessionLabels[student.session_length || ""] || "",
    group_preference: groupLabels[student.group_preference || ""] || "",
    reading_level: readingLabels[student.reading_level || ""] || "",
    motivation: motivationLabels[student.motivation || ""] || "",
    needs_captions: Boolean(acc.needs_captions),
    needs_large_text: Boolean(acc.needs_large_text),
    needs_extra_time: Boolean(acc.needs_extra_time),
    uses_assistive_tech: Boolean(acc.uses_assistive_tech),
    accommodations_notes: student.accommodations_notes || "",
  };
}

/** One-time learning survey (auto after signup) + manual relaunch from Account settings. */
export default function LearningProfileSurvey() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [manual, setManual] = useState(false);
  const [template, setTemplate] = useState<SurveyTemplate | null>(null);
  const [answers, setAnswers] = useState<Record<string, string | number | boolean>>({});
  const [studentId, setStudentId] = useState<string | null>(null);
  const [accountId, setAccountId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [doneCategory, setDoneCategory] = useState("");

  const openForStudent = useCallback(async (force = false) => {
    if (!getToken()) return;
    const me = await getMe();
    const survey = await getOnboardingSurvey(me.id, me.tier);
    if (!survey.enabled || !survey.template) return;

    let students = (await listStudents()).students;
    if (!students.length) {
      const created = await createStudent(me.display_name || me.email.split("@")[0]);
      students = [created];
    }
    const primary = students.find((s) => !s.onboarding_completed_at) ?? students[0];
    if (!force && primary.onboarding_completed_at) return;

    setAccountId(me.id);
    setStudentId(primary.id);
    setTemplate(survey.template);
    setAnswers(primary.onboarding_completed_at ? answersFromProfile(primary) : {});
    setDoneCategory("");
    setError("");
    setManual(force);
    setOpen(true);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function autoPrompt() {
      try {
        if (!getToken()) return;
        if (!localStorage.getItem(DISCLAIMER_KEY)) return;
        await openForStudent(false);
      } catch {
        /* offline / service down — don't block the app */
      }
    }
    if (!cancelled) autoPrompt();
    return () => { cancelled = true; };
  }, [pathname, openForStudent]);

  useEffect(() => {
    function onOpen() {
      openForStudent(true).catch(() => undefined);
    }
    window.addEventListener(OPEN_LEARNING_PROFILE_EVENT, onOpen);
    return () => window.removeEventListener(OPEN_LEARNING_PROFILE_EVENT, onOpen);
  }, [openForStudent]);

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
      setDoneCategory(res.learner_category);
      window.dispatchEvent(new CustomEvent("aoep-learning-profile-saved"));
      setTimeout(() => setOpen(false), manual ? 1200 : 1800);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onSkip() {
    if (!studentId) {
      setOpen(false);
      return;
    }
    setBusy(true);
    setError("");
    try {
      await skipLearningProfile(studentId);
      window.dispatchEvent(new CustomEvent("aoep-learning-profile-saved"));
      setOpen(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
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
            {manual && (
              <p className="muted" style={{ marginTop: 0 }}>
                Update your saved learning profile. Changes sync to your account in the cloud.
              </p>
            )}
            <SurveyForm template={template} answers={answers} onChange={setAnswers} disabled={busy} />
            {error && <p className="muted" style={{ color: "#ff6b6b" }}>{error}</p>}
            <div className="row" style={{ marginTop: 16, gap: 8, flexWrap: "wrap" }}>
              <button onClick={onSubmit} disabled={busy}>
                {busy ? "Saving…" : manual ? "Save changes" : "Save my learning profile"}
              </button>
              {!manual && (
                <button onClick={onSkip} disabled={busy}
                  style={{ background: "transparent", border: "1px solid var(--border)" }}>
                  Skip for now
                </button>
              )}
              {manual && (
                <button onClick={() => setOpen(false)} disabled={busy}
                  style={{ background: "transparent", border: "1px solid var(--border)" }}>
                  Cancel
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
