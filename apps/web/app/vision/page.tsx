"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  enrollEmbedding,
  identifyEmbedding,
  type IdentifiedFace,
} from "../lib/api";
import { createVisionEngine, type VisionEngine } from "../lib/vision";

// Hybrid on-device face recognition demo. Detection (YuNet) + embedding (SFace)
// run in the browser; only the embedding is sent to the server, which matches it
// against the consented gallery and enforces the compliance gates. The raw
// camera frame never leaves this device.
export default function VisionPage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const engineRef = useRef<VisionEngine | null>(null);

  const [engineState, setEngineState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [cameraOn, setCameraOn] = useState(false);
  const [consent, setConsent] = useState(false);
  const [name, setName] = useState("");
  const [enrolled, setEnrolled] = useState<string[]>([]);
  const [results, setResults] = useState<IdentifiedFace[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const ensureEngine = useCallback(async (): Promise<VisionEngine | null> => {
    if (engineRef.current) return engineRef.current;
    setEngineState("loading");
    setError("");
    try {
      const eng = await createVisionEngine();
      engineRef.current = eng;
      setEngineState("ready");
      return eng;
    } catch (e) {
      setEngineState("error");
      setError(String(e));
      return null;
    }
  }, []);

  const startCamera = useCallback(async () => {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setCameraOn(true);
      }
    } catch (e) {
      setError(`camera unavailable: ${e}`);
    }
    void ensureEngine();
  }, [ensureEngine]);

  const stopCamera = useCallback(() => {
    const v = videoRef.current;
    const stream = v?.srcObject as MediaStream | null;
    stream?.getTracks().forEach((t) => t.stop());
    if (v) v.srcObject = null;
    setCameraOn(false);
  }, []);

  useEffect(() => () => stopCamera(), [stopCamera]);

  async function enroll() {
    setError("");
    if (!name.trim()) {
      setError("enter a student name to enrol");
      return;
    }
    const eng = await ensureEngine();
    if (!eng || !videoRef.current) return;
    const faces = eng.detectAndEmbed(videoRef.current);
    if (faces.length === 0) {
      setStatus("no face detected — center your face and try again");
      return;
    }
    try {
      const r = await enrollEmbedding(name.trim(), faces[0].embedding);
      setEnrolled((prev) => (prev.includes(name.trim()) ? prev : [...prev, name.trim()]));
      setStatus(`enrolled ${r.student_id} (${r.enrollments} sample${r.enrollments === 1 ? "" : "s"})`);
    } catch (e) {
      setError(String(e));
    }
  }

  async function identify() {
    setError("");
    const eng = await ensureEngine();
    if (!eng || !videoRef.current) return;
    const faces = eng.detectAndEmbed(videoRef.current);
    if (faces.length === 0) {
      setStatus("no face detected");
      setResults([]);
      return;
    }
    try {
      // Identity matching only happens for students who have consented; without
      // consent the server still returns presence/attention but no identity.
      const consented = consent ? enrolled : [];
      const r = await identifyEmbedding(faces, consented);
      setResults(r.faces);
      setStatus(`analyzed ${r.faces.length} face(s) on-device; sent embeddings only`);
    } catch (e) {
      setError(String(e));
    }
  }

  const engineLabel =
    engineState === "ready" ? "on-device model ready"
    : engineState === "loading" ? "loading on-device model…"
    : engineState === "error" ? "on-device model failed to load"
    : "on-device model not loaded";

  return (
    <main className="container" style={{ maxWidth: 860 }}>
      <h1>On-device face recognition (hybrid)</h1>
      <p className="muted">
        Detection and embedding run entirely in your browser. Only the 128-d
        face embedding is sent to the server, which matches it against the
        consented gallery and enforces the compliance gates. The raw camera
        frame never leaves this device.
      </p>

      {error && (
        <div className="card" style={{ borderColor: "#ff6b6b" }}>
          <div className="muted">{error}</div>
        </div>
      )}

      <div className="card">
        <div className="row" style={{ gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          {!cameraOn
            ? <button onClick={startCamera} style={{ padding: "10px 16px" }}>Start camera</button>
            : <button onClick={stopCamera} style={{ padding: "10px 16px", background: "#e11d48", color: "#fff" }}>Stop camera</button>}
          <span className="pill" style={{ fontSize: 12 }}>{engineLabel}</span>
          <label style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            I consent to face identification
          </label>
        </div>

        <div style={{ marginTop: 12 }}>
          <video
            ref={videoRef}
            playsInline
            muted
            style={{ width: "100%", maxWidth: 640, borderRadius: 12, background: "#0b1020" }}
          />
        </div>

        <div className="row" style={{ gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          <input
            placeholder="Student name to enrol…"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{ flex: 1, minWidth: 200, padding: 10 }}
          />
          <button onClick={enroll} disabled={!cameraOn} style={{ padding: "10px 16px" }}>
            Enrol this face
          </button>
          <button onClick={identify} disabled={!cameraOn} style={{ padding: "10px 16px", background: "#16a34a", color: "#fff" }}>
            Identify
          </button>
        </div>
        {status && <p className="muted" style={{ marginTop: 8 }}>{status}</p>}
      </div>

      {enrolled.length > 0 && (
        <div className="card">
          <div className="muted">Enrolled on this device: {enrolled.join(", ")}</div>
        </div>
      )}

      {results.length > 0 && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>Results</h2>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left" }}>
                <th>Track</th><th>Identity</th><th>Attention</th><th>Gaze</th><th>Expression</th>
              </tr>
            </thead>
            <tbody>
              {results.map((f) => (
                <tr key={f.track_id} style={{ borderTop: "1px solid var(--border)" }}>
                  <td>{f.track_id}</td>
                  <td>{f.identified ? f.matched_student_id : "anonymous"}</td>
                  <td>{f.attention.toFixed(2)}</td>
                  <td>{f.gaze_frontal.toFixed(2)}</td>
                  <td>{f.expression}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
