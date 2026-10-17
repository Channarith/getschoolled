"use client";

import { useEffect, useState } from "react";
import { ORCHESTRATOR_URL } from "../lib/api";

export default function TrainingPage() {
  const [body, setBody] = useState<string>("Loading training catalog…");

  useEffect(() => {
    let cancel = false;
    void fetch(`${ORCHESTRATOR_URL}/api/training/capabilities`, { credentials: "include" })
      .then(async (res) => {
        const text = await res.text();
        if (!res.ok) throw new Error(text || "training catalog unavailable");
        return text;
      })
      .then((text) => {
        if (!cancel) setBody(text);
      })
      .catch((err: unknown) => {
        if (!cancel) setBody(err instanceof Error ? err.message : "training catalog unavailable");
      });
    return () => {
      cancel = true;
    };
  }, []);

  return (
    <main className="container">
      <h1>Training</h1>
      <p className="muted">Procedural scenarios, tracks, and the coaching catalog.</p>
      <pre style={{ whiteSpace: "pre-wrap" }}>{body}</pre>
    </main>
  );
}
