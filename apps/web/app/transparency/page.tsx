"use client";

import { useEffect, useState } from "react";
import { getDisclosure, type Disclosure } from "../lib/api";

export default function TransparencyPage() {
  const [disclosure, setDisclosure] = useState<Disclosure | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    getDisclosure()
      .then(setDisclosure)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <main className="container">
      <h1>Transparency</h1>
      <p className="muted">
        We disclose the AI rather than disguise it. Here is how this platform
        uses AI, what stays human, and how you can verify or dispute anything.
      </p>

      {disclosure && (
        <div className="card" style={{ borderColor: "#6ea8fe" }}>
          <strong>Current disclosure</strong>
          <div className="muted">{disclosure.line}</div>
          <ul>
            <li>Instructor: {disclosure.instructor} (AI: {String(disclosure.is_ai)})</li>
            <li>Model: {disclosure.model_name}</li>
            <li>Persona: {disclosure.persona}</li>
            <li>
              Human of record: {disclosure.human_of_record ?? "assigned per course"}
            </li>
          </ul>
        </div>
      )}
      {error && (
        <div className="card" style={{ borderColor: "#ff6b6b" }}>
          <div className="muted">Could not load live disclosure: {error}</div>
        </div>
      )}

      <div className="card">
        <h3>What the AI does</h3>
        <ul>
          <li>Presents lessons and answers questions, grounded in the course material with citations.</li>
          <li>Refuses/abstains when an answer is not supported by the material (hallucination guard).</li>
          <li>Adapts pacing and difficulty to each learner.</li>
        </ul>
      </div>

      <div className="card">
        <h3>What stays human</h3>
        <ul>
          <li>A human of record reviews course content.</li>
          <li>You can dispute any answer or grade; a human reviews it.</li>
          <li>Optional human-led and hybrid class tracks are available.</li>
        </ul>
      </div>

      <div className="card">
        <h3>Your data and choices</h3>
        <ul>
          <li>Biometric/face features are opt-in and consent-gated, with a name-only fallback.</li>
          <li>Content authenticity can be verified (content credentials / provenance).</li>
        </ul>
      </div>
    </main>
  );
}
