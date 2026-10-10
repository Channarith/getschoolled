"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/** Tell an embedded lab to hide or show its own menus and buttons. */
export function postChrome(frame: HTMLIFrameElement | null, hidden: boolean) {
  frame?.contentWindow?.postMessage({ type: "salareen-chrome", hidden }, "*");
}

/**
 * Full-screen shell for the vision arcade and On the Go.
 * In full screen, Hide options / Show options covers the selections and buttons.
 */
export function ImmersiveFrame({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  const stageRef = useRef<HTMLDivElement>(null);
  const [full, setFull] = useState(false);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    const onChange = () => {
      const on = document.fullscreenElement === stageRef.current;
      setFull(on);
      if (!on) {
        setHidden(false);
        postChrome(stageRef.current?.querySelector("iframe") ?? null, false);
      }
    };
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  function toggleFull() {
    const stage = stageRef.current;
    if (!stage) return;
    if (document.fullscreenElement) {
      void document.exitFullscreen().catch(() => undefined);
      return;
    }
    void stage.requestFullscreen?.().catch(() => undefined);
  }

  function toggleOptions() {
    const next = !hidden;
    setHidden(next);
    postChrome(stageRef.current?.querySelector("iframe") ?? null, next);
  }

  return (
    <div
      ref={stageRef}
      className="immersive-stage"
      style={{
        position: "relative",
        background: full ? "#0f172a" : "transparent",
        height: full ? "100%" : undefined,
        display: full ? "flex" : "block",
        flexDirection: "column",
      }}
    >
      <style>{`
        .immersive-stage:fullscreen { background:#0f172a; }
        .immersive-stage:fullscreen iframe {
          height:100% !important; min-height:0 !important;
          border:0; border-radius:0;
        }
      `}</style>
      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
          gap: 8,
          marginBottom: full ? 0 : 8,
          position: full ? "absolute" : "relative",
          top: full ? 12 : undefined,
          right: full ? 12 : undefined,
          zIndex: 6,
        }}
      >
        {full ? (
          <button type="button" onClick={toggleOptions} aria-pressed={hidden}>
            {hidden ? "Show options" : "Hide options"}
          </button>
        ) : null}
        <button type="button" onClick={toggleFull} aria-pressed={full}>
          {full ? "Exit full screen" : "Full screen"}
        </button>
      </div>
      <div style={full ? { flex: 1, minHeight: 0, height: "100%" } : undefined} aria-label={title}>
        {children}
      </div>
    </div>
  );
}
