"use client";

import { useEffect, useRef, useState } from "react";

export type DemoTutorialProps = {
  storageKey: string;
  title: string;
  steps: string[];
};

/** First-visit tutorial for a demo page, with a ? button to bring it back. */
export default function DemoTutorial({ storageKey, title, steps }: DemoTutorialProps) {
  const [open, setOpen] = useState(false);
  const key = `salareen.demo.tutorial.v1.${storageKey}`;
  const doneRef = useRef<HTMLButtonElement>(null);
  const helpRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    try { if (!localStorage.getItem(key)) setOpen(true); } catch { /* private mode */ }
  }, [key]);

  function close() {
    setOpen(false);
    try { localStorage.setItem(key, "1"); } catch { /* private mode */ }
    helpRef.current?.focus({ preventScroll: true });
  }

  useEffect(() => {
    if (!open) return;
    doneRef.current?.focus({ preventScroll: true });
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") close(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  return (
    <>
      <button
        ref={helpRef}
        type="button"
        data-testid={`demo-tutorial-help-${storageKey}`}
        aria-label="How this demo works"
        title="How this demo works"
        onClick={() => setOpen(true)}
        style={{ position: "fixed", left: 18, bottom: 18, zIndex: 1000, width: 40, height: 40, borderRadius: "50%", border: "2px solid #d4af37", background: "#0b1020", color: "#fde047", fontWeight: 800, cursor: "pointer" }}
      >?</button>
      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={title}
          data-testid={`demo-tutorial-${storageKey}`}
          onClick={close}
          style={{ position: "fixed", inset: 0, zIndex: 1100, background: "rgba(5,8,20,.82)", display: "grid", placeItems: "center", padding: 16 }}
        >
          <div onClick={(e) => e.stopPropagation()} style={{ maxWidth: 420, width: "100%", background: "#0b1020", color: "#e8ecf6", borderRadius: 18, padding: 22, border: "2px solid #d4af37" }}>
            <h2 style={{ margin: "0 0 12px", fontSize: 20 }}>{title}</h2>
            <ol style={{ margin: 0, paddingLeft: 20, display: "grid", gap: 8, fontSize: 15 }}>
              {steps.map((step) => <li key={step}>{step}</li>)}
            </ol>
            <button ref={doneRef} type="button" onClick={close} style={{ marginTop: 16, width: "100%", padding: "10px 14px", borderRadius: 12, border: 0, background: "#d4af37", color: "#0b1020", fontWeight: 800, cursor: "pointer" }}>Got it</button>
            <button type="button" onClick={close} style={{ marginTop: 8, width: "100%", padding: 6, border: 0, background: "none", color: "#94a3b8", textDecoration: "underline", cursor: "pointer" }}>Skip</button>
          </div>
        </div>
      )}
    </>
  );
}
