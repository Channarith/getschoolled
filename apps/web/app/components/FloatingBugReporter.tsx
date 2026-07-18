"use client";

import { useState } from "react";
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

/**
 * Small global QA affordance. Clicking it captures the current screen before the
 * dialog appears, then asks only for a short description. Diagnostics contain
 * recent errors/API breadcrumbs and context, never request bodies or auth headers.
 */
export default function FloatingBugReporter() {
  const enabled = useFlag<boolean>("engagement.in_app_bug_reporter", true);
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [description, setDescription] = useState("");
  const [shot, setShot] = useState<BugScreenshotUpload | null>(null);
  const [captureNote, setCaptureNote] = useState("");
  const [capturing, setCapturing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [doneId, setDoneId] = useState("");

  if (!enabled || pathname === "/report-bug") return null;

  async function openReporter() {
    setDoneId("");
    setError("");
    setCapturing(true);
    setCaptureNote("Choose this tab/window to attach what you see.");
    // Must start inside the click gesture for browser screen-share permission.
    const captured = await captureDisplayScreenshot();
    setShot(captured);
    setCaptureNote(captured ? "Current screen attached automatically." : "No automatic screenshot attached.");
    setCapturing(false);
    setOpen(true);
  }

  async function pickFile(file: File | null) {
    if (!file) return;
    try {
      setShot(await fileToScreenshotUpload(file));
      setCaptureNote("Screenshot attached.");
    } catch (cause) {
      setError(friendlyError(cause, "Could not read that screenshot"));
    }
  }

  async function send() {
    if (!description.trim()) {
      setError("Please briefly describe what failed.");
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
          setCaptureNote("Sent without screenshot (attachment upload failed).");
          return;
        }
        throw cause;
      }
    } catch (cause) {
      setError(friendlyError(cause, "Could not send the report — check network and try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        type="button"
        aria-label="Report a bug"
        title="Report a bug"
        disabled={capturing}
        onClick={() => void openReporter()}
        style={{
          position: "fixed",
          right: 14,
          bottom: 18,
          zIndex: 9998,
          width: 42,
          height: 42,
          borderRadius: "50%",
          padding: 0,
          border: "1px solid rgba(255,255,255,0.3)",
          background: "rgba(30,27,75,0.82)",
          color: "#fff",
          boxShadow: "0 4px 16px rgba(0,0,0,0.28)",
          backdropFilter: "blur(8px)",
          fontSize: 19,
          opacity: 0.78,
          cursor: "pointer",
        }}
      >
        {capturing ? "…" : "🐛"}
      </button>

      {open ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Report a bug"
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
                <h2 style={{ margin: 0 }}>🐛 Quick bug report</h2>
                <p className="muted" style={{ margin: "5px 0 0", fontSize: 13 }}>
                  We attach this page, recent errors/API traces, app/device context, and your screenshot.
                </p>
              </div>
              <button type="button" aria-label="Close" disabled={busy} onClick={() => setOpen(false)}>✕</button>
            </div>

            {doneId ? (
              <div style={{ marginTop: 18 }}>
                <strong>Thanks — report {doneId} was sent.</strong>
                <div style={{ marginTop: 14 }}>
                  <button type="button" onClick={() => setOpen(false)}>Close</button>
                </div>
              </div>
            ) : (
              <>
                <label style={{ display: "block", marginTop: 16, fontWeight: 700 }}>
                  What failed?
                  <textarea
                    autoFocus
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                    placeholder="Example: I tapped Start class, but nothing played."
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
                    Choose another screenshot
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
                    {busy ? "Sending…" : "Send report"}
                  </button>
                  <button type="button" disabled={busy} onClick={() => setOpen(false)}>Cancel</button>
                </div>
              </>
            )}
          </section>
        </div>
      ) : null}
    </>
  );
}
