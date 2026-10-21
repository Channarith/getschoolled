"use client";

import type { ModalityMix } from "../lib/api";

const LABELS: Record<string, string> = {
  tutoring: "Tutoring",
  gaming: "Gaming",
  reading: "Reading",
  presentation: "Presentation",
  video: "Video",
  live_teacher: "Live teacher",
};

export function modalityLabel(id?: string): string {
  if (!id) return "";
  return LABELS[id] || id;
}

export default function ModalityMixScore({
  mix,
  slideFormat,
}: {
  mix?: ModalityMix | null;
  slideFormat?: string;
}) {
  const lines = mix?.lines || [];
  if (!lines.length) return null;
  const current = modalityLabel(slideFormat);
  return (
    <aside
      data-testid="modality-mix"
      style={{
        margin: "8px 0 12px",
        padding: "10px 12px",
        borderRadius: 10,
        background: "#f8fafc",
        color: "#0f172a",
        border: "1px solid #cbd5e1",
        fontSize: 13,
        lineHeight: 1.45,
      }}
    >
      <div style={{ fontWeight: 700, marginBottom: 4 }}>Course mix</div>
      {lines.map((line) => (
        <div key={line}>{line}</div>
      ))}
      {current ? (
        <div style={{ marginTop: 6, fontWeight: 700 }}>This page: {current}</div>
      ) : null}
    </aside>
  );
}
