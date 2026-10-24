"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";

import {
  getMe,
  getToken,
  submitBugReport,
  type BugScreenshotUpload,
} from "../lib/api";
import {
  bugReportBase,
  captureDisplayScreenshot,
  fileToScreenshotUpload,
} from "../lib/bugReport";
import { friendlyError, isBugScreenshotTooLargeError, isOfflineError } from "../lib/errors";
import { useFlag } from "../lib/flags";
import { useT } from "../lib/i18n";

import { bugButtonHidden, defaultBugPosition } from "../lib/bugButtonPlacement";

const SIZE = 42;
const STORAGE_KEY = "aoep-bug-button-position";
type Point = { x: number; y: number };

function clamp(p: Point): Point {
  if (typeof window === "undefined") return p;
  return {
    x: Math.max(0, Math.min(p.x, window.innerWidth - SIZE)),
    y: Math.max(0, Math.min(p.y, window.innerHeight - SIZE)),
  };
}

/**
 * Small global QA affordance. Clicking it captures the current screen before the
 * dialog appears, then asks only for a short description. Diagnostics contain
 * recent errors/API breadcrumbs and context, never request bodies or auth headers.
 */
export default function FloatingBugReporter() {
  const enabled = useFlag<boolean>("engagement.in_app_bug_reporter", true);
  const { t } = useT();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [description, setDescription] = useState("");
  const [shot, setShot] = useState<BugScreenshotUpload | null>(null);
  const [captureNote, setCaptureNote] = useState("");
  const [capturing, setCapturing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [doneId, setDoneId] = useState("");

  const [position, setPosition] = useState<Point>({ x: 0, y: 0 });
  const positionRef = useRef(position);
  const dragRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    origin: Point;
    distance: number;
  } | null>(null);

  useEffect(() => {
    let next = defaultBugPosition(pathname, window.innerWidth, window.innerHeight, SIZE);
    try {
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null") as Point | null;
      if (stored && Number.isFinite(stored.x) && Number.isFinite(stored.y)) next = stored;
    } catch { /* use default */ }
    next = clamp(next);
    positionRef.current = next;
    setPosition(next);
    const onResize = () => {
      const resized = clamp(positionRef.current);
      positionRef.current = resized;
      setPosition(resized);
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  if (!enabled || bugButtonHidden(pathname)) return null;

  async function openReporter() {
    setDoneId("");
    setError("");
    setCapturing(true);
    setCaptureNote(t("bug.chooseTab"));
    // Must start inside the click gesture for browser screen-share permission.
    const captured = await captureDisplayScreenshot();
    setShot(captured);
    setCaptureNote(captured ? t("bug.attachedAuto") : t("bug.noShot"));
    setCapturing(false);
    setOpen(true);
  }

  async function pickFile(file: File | null) {
    if (!file) return;
    try {
      setShot(await fileToScreenshotUpload(file));
      setCaptureNote(t("bug.attached"));
    } catch (cause) {
      setError(friendlyError(cause, t("bug.readFailed")));
    }
  }

  async function send() {
    if (!description.trim()) {
      setError(t("bug.describe"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      let email = "";
      let userId = "";
      if (getToken()) {
        try {
          const me = await getMe();
          email = me.email || "";
          userId = me.id || "";
        } catch {
          /* Identity context is optional. */
        }
      }
      const base = bugReportBase({
        reporter: "floating_button",
        captured_before_dialog: Boolean(shot),
      });
      const payload = {
        ...base,
        description: description.trim(),
        category: "bug",
        email,
        user_id: userId,
        screenshots: shot ? [shot] : [],
      };
      try {
        const result = await submitBugReport(payload);
        setDoneId(result.id);
        setDescription("");
      } catch (cause) {
        // Large attachments (or flaky uploads of them) should not block the text
        // report — retry once without the screenshot so QA still gets the signal.
        if (shot && (isOfflineError(cause) || isBugScreenshotTooLargeError(cause))) {
          const result = await submitBugReport({ ...payload, screenshots: [] });
          setDoneId(result.id);
          setDescription("");
          setShot(null);
          setCaptureNote(t("bug.sentWithout"));
          return;
        }
        throw cause;
      }
    } catch (cause) {
      setError(friendlyError(cause, t("bug.sendFailed")));
    } finally {
      setBusy(false);
    }
  }

  function move(event: React.PointerEvent<HTMLButtonElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    drag.distance = Math.max(drag.distance, Math.abs(dx) + Math.abs(dy));
    const next = clamp({ x: drag.origin.x + dx, y: drag.origin.y + dy });
    positionRef.current = next;
    setPosition(next);
  }

  function finish(event: React.PointerEvent<HTMLButtonElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    dragRef.current = null;
    event.currentTarget.releasePointerCapture(event.pointerId);
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(positionRef.current)); } catch { /* optional */ }
    if (drag.distance < 8) void openReporter();
  }

  return (
    <>
      <button
        type="button"
        aria-label={t("bug.report")}
        title={t("bug.drag")}
        disabled={capturing}
        onPointerDown={(event) => {
          event.currentTarget.setPointerCapture(event.pointerId);
          dragRef.current = {
            pointerId: event.pointerId,
            startX: event.clientX,
            startY: event.clientY,
            origin: positionRef.current,
            distance: 0,
          };
        }}
        onPointerMove={move}
        onPointerUp={finish}
        onPointerCancel={() => { dragRef.current = null; }}
        style={{
          position: "fixed",
          left: position.x,
          top: position.y,
          zIndex: 9998,
          width: SIZE,
          height: SIZE,
          borderRadius: "50%",
          padding: 0,
          border: "1px solid rgba(255,255,255,0.3)",
          background: "rgba(30,27,75,0.82)",
          color: "#fff",
          boxShadow: "0 4px 16px rgba(0,0,0,0.28)",
          backdropFilter: "blur(8px)",
          fontSize: 19,
          opacity: 0.78,
          cursor: capturing ? "wait" : "grab",
          touchAction: "none",
          userSelect: "none",
        }}
      >
        {capturing ? "…" : "🐛"}
      </button>

      {open ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={t("bug.report")}
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 9999,
            display: "grid",
            placeItems: "center",
            padding: 16,
            background: "rgba(3,7,18,0.66)",
          }}
          onMouseDown={(event) => {
            if (event.currentTarget === event.target && !busy) setOpen(false);
          }}
        >
          <section
            className="card"
            style={{ width: "min(520px, 100%)", maxHeight: "90vh", overflow: "auto", padding: 20 }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
              <div>
                <h2 style={{ margin: 0 }}>🐛 {t("bug.title")}</h2>
                <p className="muted" style={{ margin: "5px 0 0", fontSize: 13 }}>
                  {t("bug.body")}
                </p>
              </div>
              <button type="button" aria-label={t("bug.close")} disabled={busy} onClick={() => setOpen(false)}>✕</button>
            </div>

            {doneId ? (
              <div style={{ marginTop: 18 }}>
                <strong>{t("bug.thanks", { id: doneId })}</strong>
                <div style={{ marginTop: 14 }}>
                  <button type="button" onClick={() => setOpen(false)}>{t("bug.close")}</button>
                </div>
              </div>
            ) : (
              <>
                <label style={{ display: "block", marginTop: 16, fontWeight: 700 }}>
                  {t("bug.whatFailed")}
                  <textarea
                    autoFocus
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                    placeholder={t("bug.placeholder")}
                    rows={4}
                    style={{
                      display: "block",
                      width: "100%",
                      marginTop: 6,
                      padding: 10,
                      borderRadius: 9,
                      border: "1px solid var(--border)",
                      background: "var(--panel)",
                      color: "var(--text)",
                    }}
                  />
                </label>

                <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  <span className="muted" style={{ fontSize: 12 }}>{captureNote}</span>
                  <label style={{ cursor: "pointer", fontSize: 13, textDecoration: "underline" }}>
                    {t("bug.chooseFile")}
                    <input
                      type="file"
                      accept="image/*"
                      hidden
                      onChange={(event) => void pickFile(event.target.files?.[0] ?? null)}
                    />
                  </label>
                </div>
                {error ? <p style={{ color: "#f87171", fontSize: 13 }}>{error}</p> : null}
                <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void send()}
                    style={{ background: "var(--accent)", color: "#fff" }}
                  >
                    {busy ? t("bug.sending") : t("bug.send")}
                  </button>
                  <button type="button" disabled={busy} onClick={() => setOpen(false)}>{t("bug.cancel")}</button>
                </div>
              </>
            )}
          </section>
        </div>
      ) : null}
    </>
  );
}
