"use client";

import { useEffect, useState } from "react";
import { hilDecide, hilQueue, type ReviewItem } from "../lib/api";

export default function ConsolePage() {
  const [autonomy, setAutonomy] = useState("");
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [error, setError] = useState("");

  async function refresh() {
    try {
      const r = await hilQueue();
      setAutonomy(r.autonomy);
      setItems(r.items);
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, []);

  async function decide(id: string, action: string) {
    try {
      if (action === "edit") {
        const text = window.prompt("Edited answer to send to the student:");
        if (text === null) return;
        await hilDecide(id, "edit", { text });
      } else {
        await hilDecide(id, action);
      }
      await refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <main className="container">
      <h1>Teacher console (human-in-the-loop)</h1>
      <p className="muted">
        AI-drafted answers/grades that need a human. Autonomy: <strong>{autonomy || "…"}</strong>.
        Approve, edit, reject, or take over.
      </p>
      {error && (
        <div className="card" style={{ borderColor: "#ff6b6b" }}>
          <div className="muted">{error}</div>
        </div>
      )}
      {items.length === 0 && (
        <div className="card">
          <div className="muted">Review queue is empty.</div>
        </div>
      )}
      {items.map((it) => (
        <div className="card" key={it.id}>
          <div className="muted">
            {it.kind} · risk {it.risk} · confidence {it.ai_confidence} · status {it.status}
          </div>
          {"question" in it.payload && (
            <div className="muted">Q: {String(it.payload.question)}</div>
          )}
          <p>{String(it.payload.text ?? "")}</p>
          {it.status === "pending" ? (
            <div className="row">
              <button onClick={() => decide(it.id, "approve")}>Approve</button>
              <button onClick={() => decide(it.id, "edit")}>Edit</button>
              <button onClick={() => decide(it.id, "reject")}>Reject</button>
              <button onClick={() => decide(it.id, "takeover")}>Take over</button>
            </div>
          ) : (
            <div className="muted">
              Decided: {it.status}
              {it.final_payload?.text ? ` -> "${String(it.final_payload.text)}"` : ""}
            </div>
          )}
        </div>
      ))}
    </main>
  );
}
