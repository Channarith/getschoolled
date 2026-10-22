"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MODES, savedModalityRatings } from "../lib/learningModes";
import {
  createStudent,
  getMe,
  getToken,
  identitySupportsLearningProfile,
  listStudents,
  submitLearningProfile,
  submitOnboardingSurveyAnalytics,
} from "../lib/api";

export const OPEN_LEARNING_PROFILE_EVENT = "aoep-open-learning-profile";

/** When identity lacks learning-profile API, remember the failed save until deploy. */
const SURVEY_LOCAL_DISMISS_KEY = "aoep_learning_profile_local_dismiss_v1";
const TAB_PROMPT_LOCK_KEY = "aoep_learning_profile_tab_prompt";

function dismissSurveyLocally(reason: string): void {
  try {
    localStorage.setItem(SURVEY_LOCAL_DISMISS_KEY, JSON.stringify({ at: Date.now(), reason }));
  } catch {
    /* private mode */
  }
}

function clearSurveyLocalDismiss(): void {
  try {
    localStorage.removeItem(SURVEY_LOCAL_DISMISS_KEY);
  } catch {
    /* */
  }
}

function releaseTabPromptLock(accountId: string): void {
  try {
    const raw = localStorage.getItem(TAB_PROMPT_LOCK_KEY);
    if (!raw) return;
    const { id } = JSON.parse(raw) as { id: string; at: number };
    if (id === accountId) localStorage.removeItem(TAB_PROMPT_LOCK_KEY);
  } catch {
    /* */
  }
}

function isIdentityApiMissingError(err: unknown): boolean {
  const msg = String(err);
  return msg.includes("404") && (msg.includes("Not Found") || msg.toLowerCase().includes("not found"));
}

/**
 * Account → Learning profile. The same six "how do you learn best" ratings as
 * the setup assistant, without the face or voice check. Saved ratings are
 * prefilled so a change is a few taps.
 */
export default function LearningProfileSurvey() {
  const [open, setOpen] = useState(false);
  const openRef = useRef(false);
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [studentId, setStudentId] = useState<string | null>(null);
  const [accountId, setAccountId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [doneCategory, setDoneCategory] = useState("");

  useEffect(() => {
    openRef.current = open;
  }, [open]);

  const openForStudent = useCallback(async () => {
    if (!getToken()) return;

    const apiReady = await identitySupportsLearningProfile();
    if (!apiReady) {
      setError(
        "Learning profile API is not available on this server (identity deploy update required). "
        + "Ask an admin to run Deploy VKE (identity + web), then try again from Account → Learning profile.",
      );
      setStudentId(null);
      setOpen(true);
      return;
    }

    const me = await getMe();
    let students = (await listStudents()).students;
    if (!students.length) {
      const created = await createStudent(me.display_name || me.email.split("@")[0]);
      students = [created];
    }
    const primary = students.find((s) => s.onboarding_completed_at) ?? students[0];

    setAccountId(me.id);
    setStudentId(primary.id);
    setRatings(savedModalityRatings(primary.onboarding_answers));
    setDoneCategory("");
    setError("");
    setOpen(true);
  }, []);

  useEffect(() => {
    function onOpen() {
      if (openRef.current) return;
      openForStudent().catch(() => undefined);
    }
    window.addEventListener(OPEN_LEARNING_PROFILE_EVENT, onOpen);
    return () => window.removeEventListener(OPEN_LEARNING_PROFILE_EVENT, onOpen);
  }, [openForStudent]);

  const unrated = MODES.filter((mode) => ratings[mode.id] == null).length;

  async function onSubmit() {
    if (!studentId || !accountId) return;
    if (unrated) {
      setError("Please rate all six.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const answers = { modality_ratings: ratings };
      const res = await submitLearningProfile(studentId, answers);
      void submitOnboardingSurveyAnalytics({ account_id: accountId, student_id: studentId, answers })
        .catch(() => undefined);
      clearSurveyLocalDismiss();
      setDoneCategory(res.learner_category);
      window.dispatchEvent(new CustomEvent("aoep-learning-profile-saved"));
      setTimeout(() => setOpen(false), 1200);
    } catch (e) {
      if (isIdentityApiMissingError(e)) {
        dismissSurveyLocally("identity_learning_profile_missing");
        releaseTabPromptLock(accountId);
        setError(
          "Could not save to the cloud — identity service needs an update (404). "
          + "Your answers were not lost if you reopen from Account → Learning profile.",
        );
        setTimeout(() => setOpen(false), 4000);
      } else {
        setError(String(e).replace(/^Error:\s*/, ""));
      }
    } finally {
      setBusy(false);
    }
  }

  if (!open) return null;

  const backdrop = {
    position: "fixed" as const, inset: 0, zIndex: 1001, display: "flex",
    alignItems: "center", justifyContent: "center",
    background: "rgba(0,0,0,0.65)", padding: 16,
  };

  if (!studentId) {
    return (
      <div role="dialog" aria-modal="true" aria-label="Learning profile" style={backdrop}>
        <div className="card" style={{ maxWidth: 520, width: "100%" }}>
          <h2 style={{ marginTop: 0 }}>Learning profile unavailable</h2>
          {error && <p className="muted" style={{ color: "#ff6b6b" }}>{error}</p>}
          <button onClick={() => setOpen(false)} style={{ marginTop: 12 }}>Close</button>
        </div>
      </div>
    );
  }

  return (
    <div role="dialog" aria-modal="true" aria-label="Learning profile" style={backdrop}>
      <div className="card" style={{ maxWidth: 640, maxHeight: "90vh", overflowY: "auto", width: "100%" }}>
        <h2 style={{ marginTop: 0 }}>How do you learn best?</h2>
        {doneCategory ? (
          <p>
            Thanks! We&apos;ll adapt courses for a <strong>{doneCategory.replace(/_/g, " ")}</strong> learner profile.
          </p>
        ) : (
          <>
            <p className="muted" style={{ marginTop: 0 }}>
              Rate from 1 (not for me) to 10 (I love it). Changes sync to your account.
            </p>
            {MODES.map((mode) => (
              <fieldset key={mode.id} style={{ border: 0, padding: 0, margin: "0 0 14px" }}>
                <legend style={{ fontWeight: 700, marginBottom: 6 }}>
                  {mode.label} <span className="muted" style={{ fontWeight: 400 }}>· {mode.blurb}</span>
                </legend>
                <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
                  {Array.from({ length: 10 }, (_, i) => i + 1).map((value) => {
                    const on = ratings[mode.id] === value;
                    return (
                      <button
                        key={value}
                        type="button"
                        disabled={busy}
                        aria-pressed={on}
                        aria-label={`${mode.label}: ${value} of 10`}
                        onClick={() => setRatings((r) => ({ ...r, [mode.id]: value }))}
                        style={{
                          minWidth: 40,
                          background: on ? undefined : "transparent",
                          border: on ? undefined : "1px solid var(--border)",
                        }}
                      >
                        {value}
                      </button>
                    );
                  })}
                </div>
              </fieldset>
            ))}
            {error && <p className="muted" style={{ color: "#ff6b6b" }}>{error}</p>}
            <div className="row" style={{ marginTop: 16, gap: 8, flexWrap: "wrap" }}>
              <button onClick={onSubmit} disabled={busy || unrated > 0}>
                {busy ? "Saving…" : unrated ? `Rate ${unrated} more` : "Save changes"}
              </button>
              <button
                onClick={() => {
                  if (accountId) releaseTabPromptLock(accountId);
                  setOpen(false);
                }}
                disabled={busy}
                style={{ background: "transparent", border: "1px solid var(--border)" }}
              >
                Cancel
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
