"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  gradeReviewDecide,
  gradeReviews,
  hilDecide,
  hilQueue,
  type ReviewItem,
} from "../lib/api";
import { useFlags, useFlag } from "../lib/flags";

export default function ConsolePage() {
  const { ready: flagsReady } = useFlags();
  const consoleOn = useFlag<boolean>("access.educator_console", true);
  const [autonomy, setAutonomy] = useState("");
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [grades, setGrades] = useState<ReviewItem[]>([]);
  const [error, setError] = useState("");

  async function refresh() {
    try {
      const r = await hilQueue();
      setAutonomy(r.autonomy);
      setItems(r.items);
    } catch (e) {
      setError(String(e));
    }
    try {
      const g = await gradeReviews();
      setGrades(g.items);
    } catch {
      /* curriculum service may be down; ignore */
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

  async function decideGrade(id: string, action: string) {
    try {
      if (action === "edit") {
        const corrected = window.prompt("Corrected grade feedback (back-propagated to training):");
        if (corrected === null) return;
        await gradeReviewDecide(id, "edit", { corrected });
      } else {
        await gradeReviewDecide(id, action);
      }
      await refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  if (flagsReady && !consoleOn) {
    return (
      <main className="container" style={{ maxWidth: 520 }}>
        <h1>Teacher console</h1>
        <div className="card">
          <p className="muted">
            The educator console is currently disabled. An administrator can re-enable it from the{" "}
            <Link href="/admin">Admin</Link> console (access.educator_console).
          </p>
        </div>
      </main>
    );
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

      <h2>Grading lane</h2>
      {grades.length === 0 && (
        <div className="card">
          <div className="muted">No grades awaiting review.</div>
        </div>
      )}
      {grades.map((it) => (
        <div className="card" key={it.id}>
          <div className="muted">
            grade · score {String(it.payload.score)}/{String(it.payload.max_score)} · risk {it.risk} · status {it.status}
          </div>
          {Array.isArray(it.payload.validity_flags) && (it.payload.validity_flags as string[]).length > 0 && (
            <div className="muted">flags: {(it.payload.validity_flags as string[]).join(", ")}</div>
          )}
          {it.status === "pending" ? (
            <div className="row">
              <button onClick={() => decideGrade(it.id, "approve")}>Approve</button>
              <button onClick={() => decideGrade(it.id, "edit")}>Override</button>
              <button onClick={() => decideGrade(it.id, "reject")}>Reject</button>
            </div>
          ) : (
            <div className="muted">Decided: {it.status}</div>
          )}
        </div>
      ))}
    </main>
  );
}
