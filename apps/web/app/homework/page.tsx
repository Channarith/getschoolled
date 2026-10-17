"use client";

import { useState } from "react";
import { gradeHomework } from "../lib/api";

export default function HomeworkPage() {
  const [text, setText] = useState("");
  const [result, setResult] = useState("");
  const [busy, setBusy] = useState(false);

  return (
    <main className="container">
      <h1>Homework</h1>
      <p className="muted">Paste an answer. The grader scores it and keeps the rationale.</p>
      <label>
        Answer
        <textarea
          aria-label="Homework answer"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={8}
          style={{ display: "block", width: "100%", marginTop: 8 }}
        />
      </label>
      <button
        type="button"
        disabled={busy || !text.trim()}
        onClick={() => {
          setBusy(true);
          setResult("");
          void gradeHomework({
            assignment: { title: "Practice", questions: [{ id: "q1", prompt: "Your answer" }] },
            submission_text: text,
          })
            .then((grade) => setResult(JSON.stringify(grade, null, 2)))
            .catch((err: unknown) => setResult(err instanceof Error ? err.message : "grade failed"))
            .finally(() => setBusy(false));
        }}
        style={{ marginTop: 12 }}
      >
        {busy ? "Grading…" : "Grade"}
      </button>
      {result ? <pre style={{ whiteSpace: "pre-wrap" }}>{result}</pre> : null}
    </main>
  );
}
