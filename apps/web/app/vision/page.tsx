"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  enrollEmbedding,
  enrollVoiceSample,
  getVoiceEnrollmentStatus,
  identifyEmbedding,
  listStudents,
  type IdentifiedFace,
  type StudentProfile,
  type VoiceEnrollmentStatus,
} from "../lib/api";
import { createVisionEngine, type VisionEngine } from "../lib/vision";

// Hybrid on-device face recognition + voice-name enrollment.
//
// Face flow: detection (YuNet) + embedding (SFace) run in the browser; only
// the 128-d embedding is sent to the server. The raw camera frame never leaves
// this device.
//
// Voice flow: after enrolling a face the student is prompted to say their name
// aloud. The audio is captured via MediaRecorder (WebM/Opus) and uploaded to
// the identity service, where it is stored on the student profile for later
// analytics and voice-based presence verification.
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
  // Which pipeline step failed, so the UI can tell the user something more
  // useful than a bare toString() of the exception. The user reported Vision
  // Play camera + gestures were flaky — most of the time it's one of:
  //   - "camera": getUserMedia was blocked / dismissed / no device
  //   - "model":  YuNet / SFace ONNX fetch failed (offline or 404 from CDN)
  //   - "runtime": OpenCV.js never finished bootstrapping (slow network)
  //   - "inference": the frame produced no detection (bad lighting / angle)
  // We classify and surface each with its own banner + retry affordance.
  type ErrorStage = "camera" | "model" | "runtime" | "inference" | "unknown";
  const [errorStage, setErrorStage] = useState<ErrorStage>("unknown");

  // Voice enrollment state
  const [voiceStep, setVoiceStep] = useState<"idle" | "prompting" | "recording" | "uploading" | "done" | "error">("idle");
  const [voiceStatus, setVoiceStatus] = useState("");
  const [voiceError, setVoiceError] = useState("");
  const [pendingEnrollName, setPendingEnrollName] = useState("");
  const [pendingStudentId, setPendingStudentId] = useState("");
  const [voiceEnrollment, setVoiceEnrollment] = useState<VoiceEnrollmentStatus | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load student profile to get the canonical student ID.
  const [students, setStudents] = useState<StudentProfile[]>([]);
  useEffect(() => {
    listStudents().then((r) => setStudents(r.students)).catch(() => undefined);
  }, []);

  // Refresh voice enrollment status for the first student (the account's default profile).
  const refreshVoiceStatus = useCallback(async (studentId: string) => {
    try {
      const status = await getVoiceEnrollmentStatus(studentId);
      setVoiceEnrollment(status);
    } catch {
      setVoiceEnrollment(null);
    }
  }, []);

  useEffect(() => {
    if (students.length > 0) void refreshVoiceStatus(students[0].id);
  }, [students, refreshVoiceStatus]);

  const ensureEngine = useCallback(async (): Promise<VisionEngine | null> => {
    if (engineRef.current) return engineRef.current;
    setEngineState("loading");
    setError("");
    setErrorStage("unknown");
    try {
      const eng = await createVisionEngine();
      engineRef.current = eng;
      setEngineState("ready");
      return eng;
    } catch (e) {
      const msg = String(e);
      // Loose classifier — the exception names from opencvRuntime.ModelLoadError
      // and from the model fetchers include "model" / "opencv.js" / "onnx" so
      // we can tell the user which step died.
      const stage: ErrorStage =
        /opencv\.js|cv runtime|wait.*cv/i.test(msg)
          ? "runtime"
          : /\.onnx|yunet|sface|model/i.test(msg)
            ? "model"
            : "unknown";
      setEngineState("error");
      setErrorStage(stage);
      setError(msg);
      return null;
    }
  }, []);

  const startCamera = useCallback(async () => {
    setError("");
    setErrorStage("unknown");
    try {
      // Prefer environment camera on mobile (back-facing) so kids can point it
      // at a worksheet; fall back to any camera if "environment" is missing.
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "user" } },
        audio: false,
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setCameraOn(true);
      }
    } catch (e) {
      // Classify the common camera failure modes so the banner can tell the
      // user WHY the camera didn't come up — a bare "NotAllowedError" is
      // meaningless to kids/parents.
      const name = (e as DOMException)?.name || "";
      const msg = String(e);
      let hint = "";
      if (name === "NotAllowedError" || /denied|permission/i.test(msg)) {
        hint = "You denied camera access. Click the camera icon in the address bar to allow it, then press Start again.";
      } else if (name === "NotFoundError" || /no.*device|not.*found/i.test(msg)) {
        hint = "No camera was found. Plug in a webcam (or enable the laptop camera) and try again.";
      } else if (name === "NotReadableError" || /in use|busy/i.test(msg)) {
        hint = "Another app (Zoom, Teams, OBS) is using the camera. Close it and try again.";
      } else {
        hint = "Camera could not start. Try again, and if that fails, reload the page.";
      }
      setErrorStage("camera");
      setError(`${hint}  (details: ${msg})`);
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

  // ------------------------------------------------------------------ //
  // Face enrollment
  // ------------------------------------------------------------------ //
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
      setStatus(`Face enrolled for ${r.student_id} (${r.enrollments} sample${r.enrollments === 1 ? "" : "s"})`);

      // Trigger voice enrollment step immediately after face enroll.
      // Find the matching student profile for the identity service call.
      const matchedStudent = students.find(
        (s) => s.display_name.toLowerCase() === name.trim().toLowerCase()
      ) ?? students[0];
      if (matchedStudent) {
        setPendingStudentId(matchedStudent.id);
      }
      setPendingEnrollName(name.trim());
      setVoiceStep("prompting");
      setVoiceError("");
      setVoiceStatus("");
    } catch (e) {
      setError(String(e));
    }
  }

  async function identify() {
    setError("");
    setErrorStage("unknown");
    const eng = await ensureEngine();
    if (!eng || !videoRef.current) return;
    const faces = eng.detectAndEmbed(videoRef.current);
    if (faces.length === 0) {
      setErrorStage("inference");
      setError(
        "No face was detected in this frame. Move so your whole face is visible, improve the lighting, or step closer to the camera (and remove hats / glasses glare), then press Identify again.",
      );
      setResults([]);
      return;
    }
    try {
      const consented = consent ? enrolled : [];
      const r = await identifyEmbedding(faces, consented);
      setResults(r.faces);
      setStatus(`analyzed ${r.faces.length} face(s) on-device; sent embeddings only`);
    } catch (e) {
      setError(String(e));
    }
  }

  // ------------------------------------------------------------------ //
  // Voice capture
  // ------------------------------------------------------------------ //
  async function startVoiceRecording() {
    setVoiceError("");
    audioChunksRef.current = [];
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    } catch (e) {
      setVoiceError(`Microphone unavailable: ${e}`);
      setVoiceStep("error");
      return;
    }

    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "";

    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});
    mediaRecorderRef.current = recorder;
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunksRef.current.push(e.data);
    };
    recorder.start(100); // collect 100 ms chunks
    setVoiceStep("recording");
    setVoiceStatus("Recording… say your name clearly");

    // Auto-stop after 5 seconds.
    recordingTimerRef.current = setTimeout(() => void stopVoiceRecording(), 5000);
  }

  async function stopVoiceRecording() {
    if (recordingTimerRef.current) {
      clearTimeout(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === "inactive") return;

    await new Promise<void>((resolve) => {
      recorder.onstop = () => resolve();
      recorder.stop();
    });

    // Stop all mic tracks.
    const stream = recorder.stream;
    stream?.getTracks().forEach((t) => t.stop());
    mediaRecorderRef.current = null;

    if (audioChunksRef.current.length === 0) {
      setVoiceError("No audio captured — please try again");
      setVoiceStep("prompting");
      return;
    }

    const mimeType = audioChunksRef.current[0].type || "audio/webm";
    const blob = new Blob(audioChunksRef.current, { type: mimeType });
    await uploadVoiceSample(blob, mimeType);
  }

  async function uploadVoiceSample(blob: Blob, _mime: string) {
    setVoiceStep("uploading");
    setVoiceStatus("Saving your voice sample…");

    const studentId = pendingStudentId || students[0]?.id;
    if (!studentId) {
      setVoiceError("No student profile found — please sign in first");
      setVoiceStep("error");
      return;
    }

    try {
      await enrollVoiceSample(studentId, blob, pendingEnrollName);
      setVoiceStep("done");
      setVoiceStatus("Voice enrolled! Your face + voice are now linked to your profile.");
      void refreshVoiceStatus(studentId);
    } catch (e) {
      setVoiceError(`Upload failed: ${e}`);
      setVoiceStep("error");
    }
  }

  function dismissVoiceStep() {
    setVoiceStep("idle");
    setVoiceError("");
    setVoiceStatus("");
    if (mediaRecorderRef.current?.state !== "inactive") {
      mediaRecorderRef.current?.stop();
    }
    if (recordingTimerRef.current) clearTimeout(recordingTimerRef.current);
  }

  // ------------------------------------------------------------------ //
  // Render helpers
  // ------------------------------------------------------------------ //
  const engineLabel =
    engineState === "ready" ? "on-device model ready"
    : engineState === "loading" ? "loading on-device model…"
    : engineState === "error" ? "on-device model failed to load"
    : "on-device model not loaded";

  return (
    <main className="container" style={{ maxWidth: 860 }}>
      <h1>Salareen Learner Check (Settings)</h1>
      <p className="muted">
        Enrol your face and voice so the platform can recognise you during lessons.
        Detection and face embedding run entirely in your browser — only the 128-d
        embedding is sent to the server. Your voice sample (saying your name) is
        stored securely on your profile for identity verification and attendance analytics.
      </p>

      {/* Existing voice enrollment badge */}
      {voiceEnrollment?.voice_enrolled && voiceStep === "idle" && (
        <div className="card" style={{ borderColor: "#16a34a", marginBottom: 0 }}>
          <span style={{ color: "#16a34a", fontWeight: 600 }}>
            ✓ Voice enrolled
          </span>
          {" — "}
          <span className="muted">
            Name on file: <strong>{voiceEnrollment.voice_name_text}</strong>
            {voiceEnrollment.voice_enrolled_at
              ? ` · enrolled ${new Date(voiceEnrollment.voice_enrolled_at * 1000).toLocaleDateString()}`
              : ""}
          </span>
        </div>
      )}

      {/* Structured diagnostic banner. One of the top sources of user
          frustration on Vision Play was a cryptic single-line red error with
          no action — this surfaces which step failed, what the user can do
          about it, and a retry button right next to the message. */}
      {error && (
        <div
          className="card"
          role="alert"
          style={{
            borderColor: "#ff6b6b",
            background: "rgba(255,107,107,0.08)",
          }}
        >
          <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
            <span style={{ fontSize: 24 }} aria-hidden="true">
              {errorStage === "camera" ? "📷" :
               errorStage === "model" ? "📦" :
               errorStage === "runtime" ? "⚙️" :
               errorStage === "inference" ? "👀" : "⚠️"}
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <strong style={{ display: "block", marginBottom: 4 }}>
                {errorStage === "camera" ? "Camera couldn't start"
                  : errorStage === "model" ? "Vision model failed to download"
                  : errorStage === "runtime" ? "OpenCV runtime didn't finish loading"
                  : errorStage === "inference" ? "No face detected in this frame"
                  : "Vision Play ran into a problem"}
              </strong>
              <div className="muted" style={{ fontSize: 14, lineHeight: 1.5 }}>{error}</div>
              <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                {errorStage === "camera" && (
                  <button
                    type="button"
                    onClick={() => void startCamera()}
                    style={{ padding: "8px 14px", background: "#3b82f6", color: "#fff", border: 0, borderRadius: 8, cursor: "pointer" }}
                  >
                    Enable camera
                  </button>
                )}
                {(errorStage === "model" || errorStage === "runtime") && (
                  <button
                    type="button"
                    onClick={() => { engineRef.current = null; void ensureEngine(); }}
                    style={{ padding: "8px 14px", background: "#3b82f6", color: "#fff", border: 0, borderRadius: 8, cursor: "pointer" }}
                  >
                    Retry model load
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => { setError(""); setErrorStage("unknown"); }}
                  style={{ padding: "8px 14px", background: "transparent", color: "inherit", border: "1px solid var(--border)", borderRadius: 8, cursor: "pointer" }}
                >
                  Dismiss
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ---- Camera + face enroll ---- */}
      <div className="card">
        {!cameraOn && !error && (
          <div
            style={{
              padding: 14,
              marginBottom: 12,
              borderRadius: 10,
              background: "rgba(59,130,246,0.08)",
              border: "1px dashed rgba(59,130,246,0.45)",
              display: "flex",
              gap: 12,
              alignItems: "center",
              flexWrap: "wrap",
            }}
          >
            <span style={{ fontSize: 24 }}>📷</span>
            <span style={{ flex: 1, minWidth: 220 }}>
              Vision Play needs your camera. We'll ask the browser for permission;
              nothing leaves your device until you choose to enrol or identify.
            </span>
            <button
              type="button"
              onClick={() => void startCamera()}
              style={{ padding: "10px 18px", background: "#3b82f6", color: "#fff", border: 0, borderRadius: 10, cursor: "pointer", fontWeight: 600 }}
            >
              Enable camera
            </button>
          </div>
        )}
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
            placeholder="Your name (for enrolment)…"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{ flex: 1, minWidth: 200, padding: 10 }}
          />
          <button
            onClick={enroll}
            disabled={!cameraOn}
            style={{ padding: "10px 16px" }}
          >
            Enrol face
          </button>
          <button
            onClick={identify}
            disabled={!cameraOn}
            style={{ padding: "10px 16px", background: "#16a34a", color: "#fff" }}
          >
            Identify
          </button>
        </div>
        {status && <p className="muted" style={{ marginTop: 8 }}>{status}</p>}
      </div>

      {/* ---- Voice enrollment panel ---- */}
      {voiceStep !== "idle" && (
        <VoiceEnrollPanel
          step={voiceStep}
          name={pendingEnrollName}
          status={voiceStatus}
          error={voiceError}
          onStart={() => void startVoiceRecording()}
          onStop={() => void stopVoiceRecording()}
          onDismiss={dismissVoiceStep}
        />
      )}

      {/* Re-enrol voice manually */}
      {voiceStep === "idle" && students.length > 0 && (
        <div className="card">
          <h2 style={{ marginTop: 0, fontSize: 16 }}>Re-enrol voice</h2>
          <p className="muted" style={{ marginBottom: 12 }}>
            Record yourself saying your name to update the voice sample on your profile.
          </p>
          <button
            onClick={() => {
              setPendingStudentId(students[0].id);
              setPendingEnrollName(students[0].display_name);
              setVoiceStep("prompting");
            }}
            style={{ padding: "10px 16px" }}
          >
            🎤 Record voice sample
          </button>
        </div>
      )}

      {enrolled.length > 0 && (
        <div className="card">
          <div className="muted">Enrolled on this device: {enrolled.join(", ")}</div>
        </div>
      )}

      {results.length > 0 && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>Identification results</h2>
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

// ------------------------------------------------------------------ //
// Voice enrol panel sub-component
// ------------------------------------------------------------------ //
type VoiceEnrollPanelProps = {
  step: "prompting" | "recording" | "uploading" | "done" | "error";
  name: string;
  status: string;
  error: string;
  onStart: () => void;
  onStop: () => void;
  onDismiss: () => void;
};

function VoiceEnrollPanel({ step, name, status, error, onStart, onStop, onDismiss }: VoiceEnrollPanelProps) {
  return (
    <div
      className="card"
      style={{
        borderColor: step === "done" ? "#16a34a" : step === "error" ? "#ff6b6b" : "#3b82f6",
        marginTop: 16,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
        <span style={{ fontSize: 28 }}>
          {step === "done" ? "✅" : step === "error" ? "❌" : step === "recording" ? "🔴" : "🎤"}
        </span>
        <div>
          <strong style={{ display: "block" }}>
            {step === "done"
              ? "Voice enrolled!"
              : step === "error"
                ? "Voice enrolment failed"
                : step === "uploading"
                  ? "Saving voice sample…"
                  : step === "recording"
                    ? "Recording… speak now"
                    : `Say your name: "${name}"`}
          </strong>
          {(status || error) && (
            <span className="muted" style={{ fontSize: 13, color: error ? "#ff6b6b" : undefined }}>
              {error || status}
            </span>
          )}
        </div>
      </div>

      {step === "prompting" && (
        <div style={{ display: "flex", gap: 8 }}>
          <p className="muted" style={{ flex: 1, margin: 0, fontSize: 13 }}>
            Your microphone will record for up to 5 seconds. Say your name clearly and naturally — for example,{" "}
            <em>{`"${name}"`}</em>.
            This voice sample will be saved to your profile for identity tracking and attendance analytics.
          </p>
        </div>
      )}

      {/* Recording waveform indicator */}
      {step === "recording" && (
        <div style={{ display: "flex", gap: 3, alignItems: "center", height: 24, marginBottom: 8 }}>
          {Array.from({ length: 20 }).map((_, i) => (
            <div
              key={i}
              style={{
                width: 3,
                borderRadius: 2,
                background: "#ef4444",
                height: `${Math.round(4 + Math.random() * 20)}px`,
                animation: "pulse 0.4s ease-in-out infinite alternate",
                animationDelay: `${i * 0.05}s`,
              }}
            />
          ))}
        </div>
      )}

      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        {step === "prompting" && (
          <button onClick={onStart} style={{ padding: "10px 18px", background: "#3b82f6", color: "#fff", border: "none", borderRadius: 8, cursor: "pointer" }}>
            🎤 Start recording
          </button>
        )}
        {step === "recording" && (
          <button onClick={onStop} style={{ padding: "10px 18px", background: "#ef4444", color: "#fff", border: "none", borderRadius: 8, cursor: "pointer" }}>
            ⏹ Stop recording
          </button>
        )}
        {(step === "done" || step === "error") && (
          <button onClick={onDismiss} style={{ padding: "10px 18px", background: "#4b5563", color: "#fff", border: "none", borderRadius: 8, cursor: "pointer" }}>
            Dismiss
          </button>
        )}
        {step !== "uploading" && step !== "recording" && (
          <button
            onClick={onDismiss}
            style={{ padding: "10px 18px", background: "transparent", border: "1px solid #4b5563", color: "inherit", borderRadius: 8, cursor: "pointer" }}
          >
            Skip
          </button>
        )}
      </div>
    </div>
  );
}
