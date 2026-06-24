"use client";

import type { SurveyQuestion, SurveyTemplate } from "../lib/api";

type Props = {
  template: SurveyTemplate;
  answers: Record<string, string | number | boolean>;
  onChange: (answers: Record<string, string | number | boolean>) => void;
  disabled?: boolean;
};

/** Shared dynamic survey renderer (rating / choice / bool / text). */
export default function SurveyForm({ template, answers, onChange, disabled }: Props) {
  function set(id: string, value: string | number | boolean) {
    onChange({ ...answers, [id]: value });
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {template.subtitle && (
        <p className="muted" style={{ margin: 0 }}>{template.subtitle}</p>
      )}
      {template.questions.map((q: SurveyQuestion) => (
        <label key={q.id} style={{ display: "block" }}>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>
            {q.prompt}{q.required ? " *" : ""}
          </div>
          {q.type === "rating" && (
            <div className="row" style={{ gap: 6 }}>
              {[1, 2, 3, 4, 5].map((n) => (
                <button key={n} type="button" disabled={disabled}
                  onClick={() => set(q.id, n)}
                  style={{
                    filter: Number(answers[q.id] ?? 0) >= n ? "none" : "grayscale(1) opacity(0.4)",
                  }}>
                  {"★".repeat(n)}
                </button>
              ))}
            </div>
          )}
          {q.type === "choice" && (
            <select value={(answers[q.id] as string) ?? ""} disabled={disabled}
              onChange={(e) => set(q.id, e.target.value)}
              style={{ width: "100%", padding: 8 }}>
              <option value="">Select…</option>
              {q.options.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          )}
          {q.type === "bool" && (
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 400 }}>
              <input type="checkbox" disabled={disabled}
                checked={Boolean(answers[q.id])}
                onChange={(e) => set(q.id, e.target.checked)} />
              Yes
            </label>
          )}
          {q.type === "text" && (
            <textarea rows={3} disabled={disabled}
              value={(answers[q.id] as string) ?? ""}
              onChange={(e) => set(q.id, e.target.value)}
              style={{ width: "100%", padding: 8 }} />
          )}
        </label>
      ))}
    </div>
  );
}
