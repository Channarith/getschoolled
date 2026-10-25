"use client";

import { useEffect } from "react";

export type ConsentChoice = "mic" | "mic-camera" | "none";

type Props = {
  labels: { title: string; body: string; headphones: string; mic: string; micCamera: string; notNow: string };
  onChoose: (choice: ConsentChoice) => void;
};

/** Asked once, before the first microphone prompt: what is listened to, where it goes, and that the camera is optional and local. */
export default function OnTheGoConsent({ labels, onChoose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onChoose("none"); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onChoose]);
  const btn = { padding: "10px 14px", borderRadius: 12, fontWeight: 800, cursor: "pointer", fontSize: 15 } as const;
  return (
    <div role="dialog" aria-modal="true" aria-labelledby="otg-consent-title" data-testid="on-the-go-consent"
      style={{ position: "fixed", inset: 0, zIndex: 70, background: "rgba(5,8,20,.82)", display: "grid", placeItems: "center", padding: 16 }}>
      <div style={{ maxWidth: 440, width: "100%", background: "#0b1020", color: "#e8ecf6", borderRadius: 18, padding: 22, border: "2px solid #d4af37", display: "grid", gap: 12 }}>
        <h2 id="otg-consent-title" style={{ margin: 0, fontSize: 20 }}>{labels.title}</h2>
        <p style={{ margin: 0, fontSize: 15, lineHeight: 1.45 }}>{labels.body}</p>
        <p style={{ margin: 0, fontSize: 13, color: "#9fbac2" }}>{labels.headphones}</p>
        <div style={{ display: "grid", gap: 8 }}>
          <button type="button" autoFocus data-testid="otg-consent-mic-camera" onClick={() => onChoose("mic-camera")}
            style={{ ...btn, border: 0, background: "#d4af37", color: "#0b1020" }}>{labels.micCamera}</button>
          <button type="button" data-testid="otg-consent-mic" onClick={() => onChoose("mic")}
            style={{ ...btn, border: "1.5px solid #d4af37", background: "transparent", color: "#fde047" }}>{labels.mic}</button>
          <button type="button" data-testid="otg-consent-none" onClick={() => onChoose("none")}
            style={{ ...btn, border: "1.5px solid #475569", background: "transparent", color: "#cbd5e1", fontWeight: 600 }}>{labels.notNow}</button>
        </div>
      </div>
    </div>
  );
}
