"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getMe, getToken, submitBugReport, type BugScreenshotUpload } from "../lib/api";
import {
  bugReportBase,
  captureDisplayScreenshot,
  fileToScreenshotUpload,
} from "../lib/bugReport";
import { installClientLog } from "../lib/clientLog";
import { friendlyError } from "../lib/errors";
import { useFlag } from "../lib/flags";

const CATEGORIES = [
  { id: "bug", label: "Something broke" },
  { id: "crash", label: "Crash or freeze" },
  { id: "ux", label: "Confusing / hard to use" },
  { id: "other", label: "Other" },
] as const;

export default function ReportBugPage() {
  const enabled = useFlag<boolean>("engagement.in_app_bug_reporter", true);
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<string>("bug");
  const [shots, setShots] = useState<BugScreenshotUpload[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [doneId, setDoneId] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => {
    installClientLog();
  }, []);

  if (!enabled) {
    return (
      <main className="container" style={{ maxWidth: 640 }}>
        <h1>Bug reporting is unavailable</h1>
        <p className="muted">Please use the Contact page if you still need help.</p>
        <Link href="/contact">Contact support</Link>
      </main>
    );
  }

  async function onPickFile(file: File | null) {
    if (!file) return;
    try {
      const upload = await fileToScreenshotUpload(file);
      setShots((prev) => [...prev, upload].slice(0, 3));
      setNote(`Attached ${file.name}`);
    } catch (e) {
      setError(friendlyError(e, "Could not read that image"));
    }
  }

  async function onCaptureScreen() {
    setBusy(true);
    setError("");
    try {
      const shot = await captureDisplayScreenshot();
      if (!shot?.data_base64) {
        setError("Screen capture was cancelled or is not supported in this browser.");
        return;
      }
      setShots((prev) => [...prev, shot].slice(0, 3));
      setNote("Screen capture attached");
    } finally {
      setBusy(false);
    }
  }

  async function onSubmit() {
    if (!description.trim()) {
      setError("Please describe what happened.");
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
          /* optional */
        }
      }
      const base = bugReportBase();
      const res = await submitBugReport({
        ...base,
        description: description.trim(),
        category,
        email,
        user_id: userId,
        screenshots: shots,
      });
      setDoneId(res.id);
      setDescription("");
      setShots([]);
    } catch (e) {
      setError(friendlyError(e, "Could not send the report"));
    } finally {
      setBusy(false);
    }
  }

  if (doneId) {
    return (
      <main className="container" style={{ maxWidth: 640 }}>
        <h1>Thanks — we got it</h1>
        <p className="muted">
          Your report <code>{doneId}</code> was saved with logs and any screenshots you attached.
          That helps us reproduce and fix issues faster.
        </p>
        <Link href="/">← Back to home</Link>
      </main>
    );
  }

  return (
    <main className="container" style={{ maxWidth: 640 }}>
      <h1>Report a bug</h1>
      <p className="muted">
        Tell us what went wrong. We automatically attach your page, app version, and recent
        error logs — plus any screenshots you add. This gives our team free QA signal so we can fix
        issues faster.
      </p>

      <label style={{ display: "block", marginTop: 16, fontWeight: 600 }}>What happened?</label>
      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        rows={5}
        placeholder="Steps to reproduce, what you expected, what you saw instead…"
        style={{
          width: "100%", marginTop: 6, borderRadius: 10, border: "1px solid var(--border)",
          padding: 12, background: "var(--panel)", color: "var(--text)",
        }}
      />

      <div style={{ marginTop: 14 }}>
        <span style={{ fontWeight: 600 }}>Category</span>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
          {CATEGORIES.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => setCategory(c.id)}
              style={{
                borderRadius: 999, padding: "6px 12px", cursor: "pointer",
                border: category === c.id ? "2px solid var(--accent)" : "1px solid var(--border)",
                background: category === c.id ? "rgba(99,102,241,0.12)" : "var(--panel)",
                color: "var(--text)",
              }}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ marginTop: 18, display: "flex", flexWrap: "wrap", gap: 8 }}>
        <label style={{
          display: "inline-block", padding: "8px 14px", borderRadius: 8,
          border: "1px solid var(--border)", cursor: "pointer", background: "var(--panel)",
        }}>
          📎 Add screenshot
          <input
            type="file"
            accept="image/*"
            hidden
            onChange={(e) => void onPickFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <button type="button" onClick={() => void onCaptureScreen()} disabled={busy}
          style={{ padding: "8px 14px", borderRadius: 8 }}>
          🖥 Capture screen
        </button>
      </div>
      {note ? <p className="muted" style={{ marginTop: 8 }}>{note} · {shots.length}/3 attached</p> : null}

      {error ? <p style={{ color: "#f87171", marginTop: 12 }}>{error}</p> : null}

      <div style={{ marginTop: 20, display: "flex", gap: 10 }}>
        <button
          type="button"
          onClick={() => void onSubmit()}
          disabled={busy}
          style={{ background: "var(--accent)", color: "#fff", padding: "10px 18px", borderRadius: 8 }}
        >
          {busy ? "Sending…" : "Send report"}
        </button>
        <Link href="/contact" style={{ alignSelf: "center" }}>Contact support instead</Link>
      </div>
    </main>
  );
}
