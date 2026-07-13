"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  LocalSessionRecorder,
  deleteRecording,
  formatDuration,
  formatSize,
  getRecordingBlob,
  isRecordingSupported,
  listRecordings,
  saveBlobToDisk,
  saveRecording,
  suggestedFilename,
  type RecordingMeta,
} from "../lib/localRecorder";

/**
 * Record the live session locally and play it back — everything stays on the
 * user's device (IndexedDB + Save-to-disk), never the cloud.
 */
export default function LocalRecorder({ roomId, title }: { roomId: string; title: string }) {
  const [supported, setSupported] = useState(false);
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [showLibrary, setShowLibrary] = useState(false);
  const [items, setItems] = useState<RecordingMeta[]>([]);
  const [playUrl, setPlayUrl] = useState("");
  const [playTitle, setPlayTitle] = useState("");
  const [error, setError] = useState("");
  const recorderRef = useRef<LocalSessionRecorder | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => { setSupported(isRecordingSupported()); }, []);

  const refresh = useCallback(async () => {
    try { setItems(await listRecordings(roomId)); } catch { setItems([]); }
  }, [roomId]);

  useEffect(() => { if (showLibrary) void refresh(); }, [showLibrary, refresh]);

  useEffect(() => () => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (playUrl) URL.revokeObjectURL(playUrl);
  }, [playUrl]);

  async function startRec() {
    setError("");
    const rec = new LocalSessionRecorder();
    try {
      await rec.start();   // prompts the user to share the tab + mic
    } catch (e) {
      setError((e as Error)?.message || "Could not start recording.");
      return;
    }
    recorderRef.current = rec;
    setRecording(true);
    setElapsed(0);
    timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
  }

  async function stopRec() {
    const rec = recorderRef.current;
    if (!rec) return;
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    setRecording(false);
    try {
      const saved = await rec.stop({ roomId, title });
      await saveRecording(saved);                 // local playback library (IndexedDB)
      await saveBlobToDisk(saved.blob, suggestedFilename(saved));  // to hard drive
      await refresh();
      setShowLibrary(true);
    } catch (e) {
      setError((e as Error)?.message || "Could not save recording.");
    } finally {
      recorderRef.current = null;
    }
  }

  async function play(id: string, t: string) {
    setError("");
    const blob = await getRecordingBlob(id);
    if (!blob) { setError("Recording not found on this device."); return; }
    if (playUrl) URL.revokeObjectURL(playUrl);
    setPlayUrl(URL.createObjectURL(blob));
    setPlayTitle(t);
  }

  async function download(id: string, meta: RecordingMeta) {
    const blob = await getRecordingBlob(id);
    if (blob) await saveBlobToDisk(blob, suggestedFilename(meta));
  }

  async function remove(id: string) {
    await deleteRecording(id);
    await refresh();
  }

  if (!supported) return null;

  return (
    <>
      <button
        type="button"
        onClick={() => (recording ? void stopRec() : void startRec())}
        title="Record this session to your device (not the cloud)"
        style={{
          background: recording ? "#dc2626" : "rgba(255,255,255,0.08)",
          color: "#fff", border: "1px solid rgba(255,255,255,0.2)", borderRadius: 8,
          padding: "4px 10px", fontSize: 12, cursor: "pointer",
        }}
      >
        {recording ? `⏹ Stop rec · ${formatDuration(elapsed * 1000)}` : "⏺ Record (local)"}
      </button>
      <button
        type="button"
        onClick={() => setShowLibrary((v) => !v)}
        style={{
          background: "rgba(255,255,255,0.08)", color: "#fff",
          border: "1px solid rgba(255,255,255,0.2)", borderRadius: 8,
          padding: "4px 10px", fontSize: 12, cursor: "pointer",
        }}
      >
        📼 Recordings
      </button>

      {error ? (
        <span style={{ color: "#fca5a5", fontSize: 12 }}>{error}</span>
      ) : null}

      {showLibrary ? (
        <div
          style={{
            position: "fixed", right: 16, bottom: 16, width: 340, maxHeight: "60vh",
            overflowY: "auto", background: "rgba(15,7,32,0.97)", zIndex: 80,
            border: "1px solid rgba(167,139,250,0.4)", borderRadius: 12, padding: 12,
            color: "#f8fafc",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <strong>My recordings (this device)</strong>
            <button type="button" onClick={() => setShowLibrary(false)} style={{ cursor: "pointer" }}>✕</button>
          </div>
          <p className="muted" style={{ fontSize: 11, color: "#c4b5fd", marginTop: 0 }}>
            Saved locally on your hard drive — never uploaded to the cloud.
          </p>
          {items.length === 0 ? (
            <p className="muted" style={{ fontSize: 13 }}>No recordings yet. Tap “Record (local)”.</p>
          ) : (
            items.map((r) => (
              <div key={r.id} style={{ borderTop: "1px solid rgba(255,255,255,0.1)", padding: "8px 0", fontSize: 13 }}>
                <div style={{ fontWeight: 600 }}>{r.title}</div>
                <div className="muted" style={{ fontSize: 11, color: "#a5b4fc" }}>
                  {new Date(r.createdAt).toLocaleString()} · {formatDuration(r.durationMs)} · {formatSize(r.size)}
                </div>
                <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
                  <button type="button" onClick={() => void play(r.id, r.title)} style={{ cursor: "pointer" }}>▶ Play</button>
                  <button type="button" onClick={() => void download(r.id, r)} style={{ cursor: "pointer" }}>⬇ Save</button>
                  <button type="button" onClick={() => void remove(r.id)} style={{ cursor: "pointer", marginLeft: "auto" }}>🗑</button>
                </div>
              </div>
            ))
          )}
        </div>
      ) : null}

      {playUrl ? (
        <div
          role="dialog"
          aria-modal="true"
          onClick={() => { URL.revokeObjectURL(playUrl); setPlayUrl(""); }}
          style={{
            position: "fixed", inset: 0, zIndex: 90, background: "rgba(0,0,0,0.8)",
            display: "flex", alignItems: "center", justifyContent: "center", padding: 16,
          }}
        >
          <div onClick={(e) => e.stopPropagation()} style={{ maxWidth: 900, width: "100%" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", color: "#fff", marginBottom: 8 }}>
              <strong>{playTitle}</strong>
              <button type="button" onClick={() => { URL.revokeObjectURL(playUrl); setPlayUrl(""); }} style={{ cursor: "pointer" }}>✕ Close</button>
            </div>
            {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
            <video src={playUrl} controls autoPlay style={{ width: "100%", borderRadius: 12, background: "#000" }} />
          </div>
        </div>
      ) : null}
    </>
  );
}
