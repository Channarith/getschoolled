"use client";

import { useEffect, useRef, useState } from "react";
import {
  enrollFaceTemplate,
  enrollVoiceSample,
  listStudents,
  recordConsent,
} from "../lib/api";
import { createVisionEngine, type VisionEngine } from "../lib/vision";

type Props = {
  learnerName: string;
  onComplete: () => void;
  busy?: boolean;
};

/** Capture a replacement face template and a spoken-name sample for the learner. */
export default function FaceVoiceSetup({ learnerName, onComplete, busy = false }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const engineRef = useRef<VisionEngine | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const [studentId, setStudentId] = useState("");
  const [cameraOn, setCameraOn] = useState(false);
  const [faceSaved, setFaceSaved] = useState(false);
  const [voiceSaved, setVoiceSaved] = useState(false);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    listStudents().then((rows) => {
      setStudentId(rows.students[0]?.id || "");
    }).catch((err) => setError(String(err)));
  }, []);

  useEffect(() => () => {
    const stream = videoRef.current?.srcObject as MediaStream | null;
    stream?.getTracks().forEach((track) => track.stop());
  }, []);

  async function startCamera() {
    setError("");
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      setCameraOn(true);
    }
    engineRef.current = engineRef.current || await createVisionEngine();
  }

  async function saveFace() {
    setError("");
    if (!studentId) {
      setError("No learner profile yet.");
      return;
    }
    if (!engineRef.current || !videoRef.current) {
      setError("Start the camera first.");
      return;
    }
    const faces = engineRef.current.detectAndEmbed(videoRef.current);
    if (faces.length === 0) {
      setError("No face detected. Center your face and try again.");
      return;
    }
    await recordConsent({
      scope: "face_recognition",
      granted: true,
      student_id: studentId,
      written: true,
    });
    await enrollFaceTemplate(studentId, faces[0].embedding);
    setFaceSaved(true);
    setStatus("Face saved. Now say your name.");
  }

  async function recordName() {
    setError("");
    if (!studentId) return;
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    chunksRef.current = [];
    const recorder = new MediaRecorder(stream);
    recorderRef.current = recorder;
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };
    recorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop());
      try {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        await enrollVoiceSample(studentId, blob, learnerName || "learner");
        setVoiceSaved(true);
        setStatus("Voice saved. You can continue.");
      } catch (err) {
        setError(String(err));
      } finally {
        setRecording(false);
      }
    };
    recorder.start();
    setRecording(true);
    window.setTimeout(() => {
      if (recorder.state === "recording") recorder.stop();
    }, 4000);
  }

  return (
    <>
      <h2 style={{ marginTop: 0 }}>Face and voice</h2>
      <p className="muted">
        This face is who must be present to start a course, continue after a pause, and take a test.
        Say your name so the profile has your voice on file. You can redo both later in Settings.
      </p>
      <video
        ref={videoRef}
        muted
        playsInline
        style={{ width: "100%", borderRadius: 12, background: "#020617", minHeight: 180 }}
      />
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
        <button type="button" disabled={busy || cameraOn} onClick={() => void startCamera().catch((err) => setError(String(err)))}>
          Start camera
        </button>
        <button type="button" disabled={busy || !cameraOn || faceSaved} onClick={() => void saveFace().catch((err) => setError(String(err)))}>
          {faceSaved ? "Face saved" : "Save my face"}
        </button>
        <button type="button" disabled={busy || !faceSaved || recording || voiceSaved} onClick={() => void recordName().catch((err) => setError(String(err)))}>
          {recording ? "Listening…" : voiceSaved ? "Voice saved" : "Say my name"}
        </button>
        <button type="button" className="btn primary" disabled={busy || !faceSaved || !voiceSaved} onClick={onComplete}>
          Finish setup
        </button>
      </div>
      {status ? <p className="muted">{status}</p> : null}
      {error ? <p style={{ color: "#f87171" }}>{error}</p> : null}
    </>
  );
}
