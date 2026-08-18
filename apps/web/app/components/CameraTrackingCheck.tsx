"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  DEFAULT_LIGHTING_THRESHOLDS,
  analyzeLuminanceGrid,
  inferTrackingPose,
  luminanceGridFromImageData,
  raiseHandsHintFromGrids,
  verdictFromMetrics,
  type LightingReadiness,
  type TrackingPose,
} from "../lib/cameraLighting";

type StepId = TrackingPose | "lighting";

type Step = {
  id: StepId;
  title: string;
  instruction: string;
};

const STEPS: Step[] = [
  {
    id: "lighting",
    title: "Lighting & focus",
    instruction: "Sit in a well-lit spot facing the camera. Hold still until we say the picture looks clear.",
  },
  {
    id: "look_up",
    title: "Look up",
    instruction: "Keep your shoulders still and look toward the ceiling for a moment.",
  },
  {
    id: "look_down",
    title: "Look down",
    instruction: "Look toward your desk or the bottom of the screen.",
  },
  {
    id: "look_left",
    title: "Look left",
    instruction: "Turn your eyes/head toward your left (camera right on a mirrored preview).",
  },
  {
    id: "look_right",
    title: "Look right",
    instruction: "Turn your eyes/head toward your right.",
  },
  {
    id: "raise_hands",
    title: "Raise both hands",
    instruction: "Raise both hands beside your head so we can confirm motion tracking.",
  },
];

type FaceDetectorLike = {
  detect: (source: HTMLVideoElement) => Promise<Array<{ boundingBox: DOMRectReadOnly }>>;
};

function faceDetectorAvailable(): FaceDetectorLike | null {
  const FD = (
    globalThis as {
      FaceDetector?: new (opts?: { maxDetectedFaces?: number }) => FaceDetectorLike;
    }
  ).FaceDetector;
  if (!FD) return null;
  try {
    return new FD({ maxDetectedFaces: 1 });
  } catch {
    return null;
  }
}

type Props = {
  /** Compact mode for embedding under Account settings. */
  embedded?: boolean;
  onComplete?: () => void;
};

export default function CameraTrackingCheck({ embedded = false, onComplete }: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const detectorRef = useRef<FaceDetectorLike | null>(null);
  const prevGridRef = useRef<number[][] | null>(null);
  const holdRef = useRef<number | null>(null);

  const [stepIndex, setStepIndex] = useState(0);
  const [status, setStatus] = useState("Starting camera…");
  const [error, setError] = useState("");
  const [passed, setPassed] = useState<Record<string, boolean>>({});
  const [lighting, setLighting] = useState<LightingReadiness | null>(null);
  const [done, setDone] = useState(false);
  // FaceDetector (Shape Detection API) is absent in stable Chrome/Safari/
  // Firefox — pose steps then get a manual confirm instead of never completing.
  const [detectorReady, setDetectorReady] = useState(true);

  const step = STEPS[stepIndex];
  const progressLabel = useMemo(
    () => `Step ${Math.min(stepIndex + 1, STEPS.length)} of ${STEPS.length}`,
    [stepIndex],
  );

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);

  const advance = useCallback(() => {
    setPassed((p) => ({ ...p, [STEPS[stepIndex].id]: true }));
    holdRef.current = null;
    if (stepIndex + 1 >= STEPS.length) {
      setDone(true);
      setStatus("All checks passed — tracking looks good.");
      stopStream();
      onComplete?.();
      return;
    }
    setStepIndex((i) => i + 1);
    setStatus("Nice — next pose…");
  }, [onComplete, stepIndex, stopStream]);

  const sample = useCallback(async () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !video.videoWidth || done) return;
    const w = 64;
    const h = 36;
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, w, h);
    const { data } = ctx.getImageData(0, 0, w, h);
    const grid = luminanceGridFromImageData(data, w, h, w, h);
    const metrics = analyzeLuminanceGrid(grid, DEFAULT_LIGHTING_THRESHOLDS);

    let boxNorm: { x: number; y: number; width: number; height: number } | null = null;
    const detector = detectorRef.current;
    if (detector) {
      try {
        const faces = await detector.detect(video);
        const face = faces[0];
        if (face) {
          boxNorm = {
            x: face.boundingBox.x / video.videoWidth,
            y: face.boundingBox.y / video.videoHeight,
            width: face.boundingBox.width / video.videoWidth,
            height: face.boundingBox.height / video.videoHeight,
          };
        }
      } catch {
        boxNorm = null;
      }
    } else {
      // Coarse stand-in when FaceDetector is unavailable.
      const mid = grid.slice(8, 28).flatMap((row) => row.slice(16, 48));
      const mean = mid.reduce((a, b) => a + b, 0) / Math.max(1, mid.length);
      const varSum = mid.reduce((a, b) => a + (b - mean) ** 2, 0) / Math.max(1, mid.length);
      if (varSum > 0.004 && mean > 0.08 && mean < 0.92) {
        boxNorm = { x: 0.3, y: 0.25, width: 0.4, height: 0.5 };
      }
    }

    const hands = raiseHandsHintFromGrids(prevGridRef.current, grid);
    prevGridRef.current = grid;
    const pose = inferTrackingPose(boxNorm, { raiseHandsHint: hands });
    const readiness = verdictFromMetrics(metrics, {
      facePresent: !!boxNorm,
      nightVision: false,
    });
    setLighting(readiness);

    const now = Date.now();
    const target = STEPS[stepIndex].id;
    let matched = false;
    if (target === "lighting") {
      matched = readiness.verdict === "ready";
      setStatus(matched ? "Lighting looks good — hold…" : readiness.message);
    } else if (target === "raise_hands") {
      matched = hands || pose === "raise_hands";
      setStatus(matched ? "Hands detected — hold…" : "Raise both hands beside your head");
    } else {
      matched = pose === target;
      setStatus(matched ? "Pose matched — hold…" : `Waiting for: ${target.replace(/_/g, " ")}`);
    }

    if (matched) {
      if (holdRef.current == null) holdRef.current = now;
      if (now - (holdRef.current || now) >= 900) advance();
    } else {
      holdRef.current = null;
    }
  }, [advance, done, stepIndex]);

  const streamRefAlive = useRef(true);
  const openStream = useCallback(async () => {
    setError("");
    detectorRef.current = faceDetectorAvailable();
    setDetectorReady(detectorRef.current !== null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
      if (!streamRefAlive.current) {
        // Unmounted (or restarted) while the prompt was pending — don't leak.
        stream.getTracks().forEach((t) => t.stop());
        return;
      }
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => undefined);
      }
      setStatus("Camera ready");
    } catch {
      setError("Camera permission is required for this check.");
    }
  }, []);

  useEffect(() => {
    streamRefAlive.current = true;
    void openStream();
    return () => {
      streamRefAlive.current = false;
      stopStream();
    };
  }, [stopStream, openStream]);

  useEffect(() => {
    if (done || error) return;
    const id = window.setInterval(() => {
      void sample();
    }, 350);
    return () => window.clearInterval(id);
  }, [done, error, sample]);

  return (
    <div className={embedded ? undefined : "card"} style={{ maxWidth: 640 }}>
      <h3 style={{ marginTop: 0 }}>Camera & tracking check</h3>
      <p className="muted" style={{ marginTop: 0 }}>
        Solo and group classes need a clear, well-lit camera so we can track presence,
        attention, movement, and integrity. Walk through each cue below.
      </p>
      <p style={{ fontWeight: 600, marginBottom: 6 }}>{progressLabel}</p>
      <p style={{ marginTop: 0 }}>
        <strong>{step.title}</strong> — {step.instruction}
      </p>

      <div
        style={{
          position: "relative",
          background: "#0f172a",
          borderRadius: 12,
          overflow: "hidden",
          aspectRatio: "4 / 3",
        }}
      >
        <video
          ref={videoRef}
          muted
          playsInline
          autoPlay
          style={{ width: "100%", height: "100%", objectFit: "cover", transform: "scaleX(-1)" }}
        />
        <canvas ref={canvasRef} style={{ display: "none" }} />
      </div>

      {error ? (
        <p style={{ color: "var(--danger, #ef4444)" }} role="alert">
          {error}
        </p>
      ) : (
        <p className="muted" style={{ fontSize: 13 }}>
          {status}
          {lighting
            ? ` · light ${(lighting.metrics.lightQualityScore * 100).toFixed(0)}% · sharp ${(lighting.metrics.sharpnessScore * 100).toFixed(0)}%`
            : ""}
        </p>
      )}

      <ol style={{ paddingLeft: 18, fontSize: 13 }}>
        {STEPS.map((s, i) => (
          <li key={s.id} style={{ opacity: i === stepIndex ? 1 : 0.65 }}>
            {passed[s.id] ? "✓ " : i === stepIndex ? "→ " : ""}
            {s.title}
          </li>
        ))}
      </ol>

      {done && (
        <p style={{ color: "#047857", fontWeight: 600 }}>
          Ready for class. You can close this page or return to Account.
        </p>
      )}

      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        {!done && !detectorReady && step.id !== "lighting" && step.id !== "raise_hands" ? (
          <button type="button" onClick={advance}>
            I held the pose — continue
          </button>
        ) : null}
        <button
          type="button"
          onClick={() => {
            setDone(false);
            setStepIndex(0);
            setPassed({});
            holdRef.current = null;
            setStatus("Restarting…");
            // advance() stopped the stream on completion — reopen it.
            if (!streamRef.current) void openStream();
          }}
        >
          Restart check
        </button>
        {!embedded && (
          <a href="/account" style={{ alignSelf: "center", fontSize: 14 }}>
            Back to account
          </a>
        )}
      </div>
    </div>
  );
}
