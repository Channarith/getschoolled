"use client";

import { useEffect, useState } from "react";

import { getCoursePolicy, type CoursePolicy } from "../lib/api";
import { policyFacts } from "../lib/purchaseView.mjs";

/** The numbers the server really enforces right now, so the page can never disagree with the checkout. */
export default function PolicyFacts({ kind }: { kind: "sale" | "refund" | "receipts" }) {
  const [policy, setPolicy] = useState<CoursePolicy | null>(null);
  useEffect(() => {
    getCoursePolicy().then(setPolicy).catch(() => setPolicy(null));
  }, []);
  if (!policy) return null;
  const facts = policyFacts(policy, kind) as { label: string; value: string }[];
  return (
    <main className="container" style={{ maxWidth: 820, paddingTop: 0 }}>
      <div className="card" aria-label="Current settings">
        <h2 style={{ marginTop: 0, fontSize: 16 }}>Current settings</h2>
        <dl style={{ margin: 0 }}>
          {facts.map((fact) => (
            <div key={fact.label} style={{ display: "flex", gap: 12, padding: "4px 0" }}>
              <dt style={{ minWidth: 180, opacity: 0.75 }}>{fact.label}</dt>
              <dd style={{ margin: 0 }}>{fact.value}</dd>
            </div>
          ))}
        </dl>
        <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>
          Draft policy: these values may change after legal review.
        </p>
      </div>
    </main>
  );
}
