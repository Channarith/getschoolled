"use client";

import { useEffect, useRef, useState } from "react";
import {
  createWebcamSession,
  endWebcamSession,
  submitWebcamFrame,
} from "../lib/api";
import { attentionFromFace, createPresenceWatch, yawFromFivePoint, type PresenceCue } from "../lib/learnerFocus";
import { createVisionEngine, type VisionEngine } from "../lib/vision";

type FaceDetectorLike = {
  detect: (source: HTMLVideoElement) => Promise<Array<{ boundingBox: DOMRectReadOnly }>>;
};

type Props = {
  stream: MediaStream | null;
  lessonContext?: string;
  participantId?: string;
  /** Called once when the student has been out of frame long enough to refocus. */
  onAway?: () => void;
  /** Sustained away, return, look-away, or phone-pose cues. YuNet has yaw only. */
  onCue?: (cue: PresenceCue) => void;
  /** 0..1 engagement for this frame. 0 when no face is in frame. */
  onAttention?: (attention: number) => void;
};

function faceDetector(): FaceDetectorLike | null {
  const FD = (globalThis as {
    FaceDetector?: new (opts?: { maxDetectedFaces?: number }) => FaceDetectorLike;
  }).FaceDetector;
  if (!FD) return null;
  try {
    return new FD({ maxDetectedFaces: 1 });
  } catch {
    return null;
  }
}

/**
 * Small lesson self-view. Hiding the picture does not stop the camera: the
 * video element keeps playing and frames keep going to the webcam session.
 */
export default function LessonCameraCorner({
  stream,
  lessonContext = "",
  participantId = "student",
  onAway,
  onCue,
  onAttention,
}: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const onAwayRef = useRef(onAway);
  const onCueRef = useRef(onCue);
  const onAttentionRef = useRef(onAttention);
  onAwayRef.current = onAway;
  onCueRef.current = onCue;
  onAttentionRef.current = onAttention;
  const watchRef = useRef(createPresenceWatch());
  const [hidden, setHidden] = useState(false);
  const [watching, setWatching] = useState(false);
  const [note, setNote] = useState("");

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (!stream) {
      video.srcObject = null;
      setWatching(false);
      return;
    }
    video.srcObject = stream;
    video.muted = true;
    void video.play().catch(() => undefined);
    setWatching(true);

    const detector = faceDetector();
    const sessionRef = { id: null as string | null };
    const engineRef = { current: null as VisionEngine | null };
    let stopped = false;
    let awaySince = 0;
    let nudged = false;

    void createVisionEngine()
      .then((engine) => {
        if (stopped) {
          engine.dispose();
          return;
        }
        engineRef.current = engine;
      })
      .catch(() => undefined);

    void createWebcamSession({
      class_type: "solo",
      student_ids: participantId ? [participantId] : [],
      lesson_context: lessonContext,
    })
      .then((session) => {
        if (stopped) {
          void endWebcamSession(session.session_id);
          return;
        }
        sessionRef.id = session.session_id;
      })
      .catch(() => undefined);

    const timer = window.setInterval(() => {
      if (stopped || video.readyState < 2 || !video.videoWidth) return;
      const canvas = canvasRef.current;
      if (!canvas) return;
      const w = 160;
      const h = 90;
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.drawImage(video, 0, 0, w, h);

      const publish = (
        facePresent: boolean,
        pose?: { yawDeg: number; gazeFrontal: number } | null,
        attention = facePresent ? 1 : 0,
      ) => {
        onAttentionRef.current?.(facePresent ? attention : 0);
        if (facePresent) {
          awaySince = 0;
          nudged = false;
        } else if (!awaySince) {
          awaySince = Date.now();
        } else if (!nudged && Date.now() - awaySince > 20000) {
          nudged = true;
          onAwayRef.current?.();
        }
        const cues = watchRef.current.update({
          atMs: Date.now(),
          facePresent,
          yawDeg: pose?.yawDeg ?? null,
          gazeFrontal: pose?.gazeFrontal ?? null,
          // Five-point YuNet has no pitch or iris gaze. Do not call it a phone.
          allowPoseOnly: false,
          source: "yunet",
        });
        for (const cue of cues) {
          if (cue.type === "notice" || cue.type === "pause") setNote(cue.notice || cue.line);
          if (cue.type === "resume") setNote("");
          onCueRef.current?.(cue);
        }
        const sessionId = sessionRef.id;
        if (!sessionId) return;
        canvas.toBlob((blob) => {
          if (!blob || sessionRef.id !== sessionId || stopped) return;
          void submitWebcamFrame(sessionId, blob, {
            participantId,
            facePresent,
            attention: facePresent ? attention : 0,
          }).catch(() => undefined);
        }, "image/jpeg", 0.7);
      };

      const engine = engineRef.current;
      if (engine) {
        try {
          const detected = engine.detectAndEmbed(video);
          const face = detected[0];
          publish(
            detected.length > 0,
            yawFromFivePoint(face?.landmarks),
            face ? attentionFromFace(face) : 0,
          );
        } catch {
          /* A bad frame is skipped. The camera stays on. */
        }
        return;
      }
      if (!detector) return;
      void detector.detect(video).then(
        (faces) => publish(faces.length > 0),
        () => undefined,
      );
    }, 1000);

    return () => {
      stopped = true;
      window.clearInterval(timer);
      engineRef.current?.dispose();
      engineRef.current = null;
      if (sessionRef.id) void endWebcamSession(sessionRef.id);
    };
  }, [stream, lessonContext, participantId]);

  if (!stream) return null;

  return (
    <div
      style={{
        position: "absolute",
        zIndex: 6,
        top: 14,
        left: 14,
        width: hidden ? "auto" : 176,
        maxWidth: "34vw",
        borderRadius: 12,
        overflow: "hidden",
        background: "rgba(8, 12, 24, 0.78)",
        border: "1px solid rgba(255,255,255,0.28)",
        boxShadow: "0 8px 22px rgba(0,0,0,0.35)",
      }}
    >
      {note ? (
        <p style={{ margin: 0, padding: "6px 8px", fontSize: 12, lineHeight: 1.35, color: "#fef3c7" }}>{note}</p>
      ) : null}
      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        aria-label="Your camera"
        aria-hidden={hidden}
        style={{
          display: "block",
          position: hidden ? "absolute" : "relative",
          width: hidden ? 8 : "100%",
          height: hidden ? 8 : "auto",
          aspectRatio: hidden ? undefined : "16 / 9",
          objectFit: "cover",
          transform: "scaleX(-1)",
          opacity: hidden ? 0 : 1,
        }}
      />
      <canvas ref={canvasRef} hidden />
      <button
        type="button"
        onClick={() => setHidden((value) => !value)}
        aria-pressed={hidden}
        title={
          hidden
            ? "Show your camera preview. Monitoring stays on either way."
            : "Hide the preview. The camera stays on so the teacher can still see you."
        }
        style={{
          position: hidden ? "relative" : "absolute",
          right: hidden ? undefined : 6,
          bottom: hidden ? undefined : 6,
          padding: "4px 8px",
          borderRadius: 999,
          border: "1px solid rgba(255,255,255,0.35)",
          background: "rgba(0,0,0,0.62)",
          color: "#fff",
          fontSize: 11,
          fontWeight: 700,
          cursor: "pointer",
        }}
      >
        {hidden ? "Show camera" : "Hide"}
      </button>
      {hidden ? (
        <div style={{ padding: "6px 8px 8px", color: "#e8ecf6", fontSize: 11, lineHeight: 1.35 }}>
          {watching ? "Camera on. Still watching." : "Camera on."}
        </div>
      ) : null}
    </div>
  );
}
