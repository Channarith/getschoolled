"use client";

import { useEffect, useRef, useState } from "react";
import { getFaceEnrollment, verifyFace } from "../lib/api";
import { decideFaceScan, FACE_SCAN_LIMIT_MS } from "../lib/faceGateDecision";
import { createVisionEngine, type VisionEngine } from "../lib/vision";

export type FacePurpose = "start" | "checkpoint" | "resume";

type Props = {
  studentId: string;
  purpose: FacePurpose;
  onMatched: (token: string) => void;
  onTimeout: () => void;
  onNeedEnroll: () => void;
};

const COPY: Record<FacePurpose, string> = {
  start: "Look at the camera so we can confirm it is you before this course starts.",
  checkpoint: "Look at the camera so we can confirm it is you before this test.",
  resume: "Look at the camera so we can confirm it is you before the lesson continues.",
};

export default function FaceMatchGate({
  studentId,
  purpose,
  onMatched,
  onTimeout,
  onNeedEnroll,
}: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const engineRef = useRef<VisionEngine | null>(null);
  const doneRef = useRef(false);
  const onMatchedRef = useRef(onMatched);
  const onTimeoutRef = useRef(onTimeout);
  const onNeedEnrollRef = useRef(onNeedEnroll);
  onMatchedRef.current = onMatched;
  onTimeoutRef.current = onTimeout;
  onNeedEnrollRef.current = onNeedEnroll;
  const [secondsLeft, setSecondsLeft] = useState(60);
  const [status, setStatus] = useState("Starting camera…");

  useEffect(() => {
    let timer = 0;
    let stopped = false;
    const started = Date.now();
    const streamHolder: { current: MediaStream | null } = { current: null };

    const finish = (fn: () => void) => {
      if (doneRef.current || stopped) return;
      doneRef.current = true;
      window.clearInterval(timer);
      fn();
    };

    async function tick() {
      if (doneRef.current || stopped) return;
      const elapsed = Date.now() - started;
      setSecondsLeft(Math.max(0, Math.ceil((FACE_SCAN_LIMIT_MS - elapsed) / 1000)));
      const video = videoRef.current;
      const engine = engineRef.current;
      let matched = false;
      if (video && engine && video.readyState >= 2) {
        try {
          const faces = engine.detectAndEmbed(video);
          if (faces.length > 0) {
            const result = await verifyFace(studentId, faces[0].embedding, purpose);
            matched = true;
            finish(() => onMatchedRef.current(result.token));
            return;
          }
          setStatus("No face in frame yet. Center your face.");
        } catch (err) {
          const message = String(err);
          if (message.includes("enroll a face")) {
            finish(() => onNeedEnrollRef.current());
            return;
          }
          if (message.includes("face does not match")) {
            setStatus("That is not the enrolled face. The enrolled student needs to be in frame.");
          }
        }
      }
      if (decideFaceScan(matched, elapsed) === "timeout") {
        setStatus("We could not confirm it is you.");
        finish(() => onTimeoutRef.current());
      }
    }

    void (async () => {
      try {
        const status = await getFaceEnrollment(studentId);
        if (!status.face_enrolled) {
          finish(() => onNeedEnrollRef.current());
          return;
        }
      } catch {
        finish(() => onNeedEnrollRef.current());
        return;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        if (stopped) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamHolder.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
        engineRef.current = await createVisionEngine();
        setStatus(COPY[purpose]);
        timer = window.setInterval(() => { void tick(); }, 700);
        void tick();
      } catch {
        setStatus("Camera is required to continue.");
        finish(() => onTimeoutRef.current());
      }
    })();

    return () => {
      stopped = true;
      window.clearInterval(timer);
      streamHolder.current?.getTracks().forEach((track) => track.stop());
    };
  }, [purpose, studentId]);

  return (
    <div
      role="dialog"
      aria-label="Face check"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 80,
        background: "rgba(2,6,23,0.82)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
    >
      <div className="card" style={{ maxWidth: 420, width: "100%" }}>
        <h2 style={{ marginTop: 0 }}>Confirm it is you</h2>
        <p className="muted">{COPY[purpose]}</p>
        <video
          ref={videoRef}
          muted
          playsInline
          style={{ width: "100%", borderRadius: 12, background: "#020617", minHeight: 180 }}
        />
        <p style={{ marginBottom: 0 }}>
          {status} <strong>{secondsLeft}s</strong>
        </p>
      </div>
    </div>
  );
}
