"use client";

import { useEffect, useState } from "react";
import { getModelCards, type ModelCard } from "../lib/api";

export default function ModelCardsPage() {
  const [cards, setCards] = useState<ModelCard[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    getModelCards()
      .then(setCards)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <main className="container">
      <h1>Model cards</h1>
      <p className="muted">
        Transparency about the models we serve: what they are for, how they score
        (including per-category accuracy and a fairness gap), and their known limits.
      </p>

      {error && (
        <div className="card" style={{ borderColor: "#ff6b6b" }}>
          <div className="muted">Could not load model cards: {error}</div>
        </div>
      )}

      {cards.length === 0 && !error && (
        <div className="card">
          <div className="muted">No model cards published yet.</div>
        </div>
      )}

      {cards.map((c, i) => (
        <div className="card" key={i}>
          <h3>{c.name}</h3>
          {c.base_model && <div className="muted">Base model: {c.base_model}</div>}
          <ul>
            <li>Accuracy: {c.metrics.accuracy ?? "n/a"}</li>
            <li>Fairness gap: {c.metrics.fairness_gap ?? "n/a"}</li>
            <li>Intended use: {c.intended_use}</li>
            <li>Training data: {c.training_data}</li>
            <li>Fairness: {c.fairness}</li>
          </ul>
          {c.limitations?.length > 0 && (
            <div className="muted">
              <strong>Limitations:</strong>
              <ul>
                {c.limitations.map((l, j) => (
                  <li key={j}>{l}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ))}
    </main>
  );
}
