"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  DEFAULT_LIGHTING_THRESHOLDS,
  NIGHT_VISION_THRESHOLDS,
  analyzeLuminanceGrid,
  isLightingReady,
  luminanceGridFromImageData,
  tryApplyExposureConstraints,
  verdictFromMetrics,
  type LightingReadiness,
  type LightingVerdict,
} from "../lib/cameraLighting";

type Props = {
  /** Called once when the learner may start class. */
  onReady: () => void;
  /** Optional skip for staff/demo — not shown by default. */
  allowSkip?: boolean;
  onSkip?: () => void;
  title?: string;
};

type FaceDetectorLike = {
  detect: (source: HTMLVideoElement) => Promise<Array<{ boundingBox: DOMRectReadOnly }>>;
};

function faceDetectorAvailable(): FaceDetectorLike | null {
  const FD = (globalThis as { FaceDetector?: new (opts?: { maxDetectedFaces?: number }) => FaceDetectorLike }).FaceDetector;
  if (!FD) return null;
  try {
    return new FD({ maxDetectedFaces: 1 });
  } catch {
    return null;
  }
}

export default function CameraLightingScreener({
  onReady,
  allowSkip = false,
  onSkip,
  title = "Camera and lighting check",
}: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const faceHoldStartRef = useRef<number | null>(null);
  const optimizedRef = useRef(false);
  const detectorRef = useRef<FaceDetectorLike | null>(null);

  const [nightVision, setNightVision] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);
  const [readiness, setReadiness] = useState<LightingReadiness | null>(null);
  const [optimizing, setOptimizing] = useState(false);

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);

  const sampleOnce = useCallback(async (): Promise<LightingReadiness | null> => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !video.videoWidth) return null;
    const w = 64;
    const h = 36;
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0, w, h);
    const { data } = ctx.getImageData(0, 0, w, h);
    const grid = luminanceGridFromImageData(data, w, h, w, h);
    const thresholds = nightVision ? NIGHT_VISION_THRESHOLDS : DEFAULT_LIGHTING_THRESHOLDS;
    const metrics = analyzeLuminanceGrid(grid, thresholds);

    let faceHit = false;
    const detector = detectorRef.current;
    if (detector) {
      try {
        const faces = await detector.detect(video);
        faceHit = faces.length > 0;
      } catch {
        faceHit = false;
      }
    } else {
      // Coarse fallback: a mid-frame blob with usable contrast counts as a face stand-in.
      const mid = grid.slice(8, 28).flatMap((row) => row.slice(16, 48));
      const mean = mid.reduce((a, b) => a + b, 0) / Math.max(1, mid.length);
      const varSum = mid.reduce((a, b) => a + (b - mean) ** 2, 0) / Math.max(1, mid.length);
      faceHit = varSum > 0.004 && mean > 0.08 && mean < 0.92;
    }

    const now = Date.now();
    if (faceHit) {
      if (faceHoldStartRef.current == null) faceHoldStartRef.current = now;
    } else {
      faceHoldStartRef.current = null;
    }
    const facePresent =
      faceHoldStartRef.current != null &&
      now - faceHoldStartRef.current >= thresholds.faceHoldMs;

    return verdictFromMetrics(metrics, { facePresent, nightVision, thresholds });
  }, [nightVision]);

  const openCamera = useCallback(async () => {
    setBusy(true);
    setError("");
    stopStream();
    detectorRef.current = faceDetectorAvailable();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "user",
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => undefined);
      }
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Camera permission is required for class.",
      );
    } finally {
      setBusy(false);
    }
  }, [stopStream]);

  useEffect(() => {
    void openCamera();
    return () => stopStream();
  }, [openCamera, stopStream]);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      if (cancelled || !streamRef.current) return;
      const result = await sampleOnce();
      if (cancelled || !result) return;
      setReadiness(result);

      if (
        !optimizedRef.current &&
        (result.verdict === "fixable" ||
          result.verdict === "blocked_dark" ||
          result.verdict === "blocked_bright")
      ) {
        optimizedRef.current = true;
        setOptimizing(true);
        const track = streamRef.current.getVideoTracks()[0];
        if (track) await tryApplyExposureConstraints(track);
        setOptimizing(false);
      }
    };
    const id = setInterval(() => {
      void tick();
    }, 400);
    void tick();
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [sampleOnce]);

  const ready = readiness ? isLightingReady(readiness.verdict) : false;

  return (
    <div className="card" style={{ maxWidth: 560 }}>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      <p className="muted" style={{ marginTop: 0 }}>
        We need a clear view of your face before class starts. Too dark, washed out,
        or blurry cameras cannot track attention reliably.
      </p>

      <div
        style={{
          position: "relative",
          background: "#0b1220",
          borderRadius: 8,
          overflow: "hidden",
          aspectRatio: "16 / 9",
        }}
      >
        <video
          ref={videoRef}
          playsInline
          muted
          style={{ width: "100%", height: "100%", objectFit: "cover", transform: "scaleX(-1)" }}
        />
        <canvas ref={canvasRef} style={{ display: "none" }} />
        {nightVision && (
          <span
            style={{
              position: "absolute",
              top: 8,
              left: 8,
              background: "#14532d",
              color: "#bbf7d0",
              fontSize: 12,
              fontWeight: 700,
              padding: "4px 8px",
              borderRadius: 4,
            }}
          >
            Night vision
          </span>
        )}
      </div>

      {error && (
        <p style={{ color: "var(--danger, #ef4444)" }} role="alert">
          {error}
        </p>
      )}

      {readiness && (
        <div style={{ marginTop: 12 }}>
          <VerdictBadge verdict={readiness.verdict} />
          <p style={{ marginBottom: 4 }}>{readiness.message}</p>
          {readiness.tips.length > 0 && (
            <ul className="muted" style={{ marginTop: 0 }}>
              {readiness.tips.map((tip) => (
                <li key={tip}>{tip}</li>
              ))}
            </ul>
          )}
          <p className="muted" style={{ fontSize: 12 }}>
            light {(readiness.metrics.lightQualityScore * 100).toFixed(0)}% · sharp{" "}
            {(readiness.metrics.sharpnessScore * 100).toFixed(0)}% · face{" "}
            {readiness.facePresent ? "held" : "looking…"}
            {optimizing ? " · auto-adjusting…" : ""}
          </p>
        </div>
      )}

      <label
        style={{
          display: "flex",
          gap: 8,
          alignItems: "center",
          marginTop: 12,
          fontSize: 14,
        }}
      >
        <input
          type="checkbox"
          checked={nightVision}
          onChange={(e) => {
            optimizedRef.current = false;
            faceHoldStartRef.current = null;
            setNightVision(e.target.checked);
          }}
        />
        Enable Night vision (low-light rooms only)
      </label>

      <div className="row" style={{ marginTop: 14, gap: 8, flexWrap: "wrap" }}>
        <button type="button" onClick={() => void openCamera()} disabled={busy}>
          Re-check
        </button>
        <button
          type="button"
          onClick={() => {
            stopStream();
            onReady();
          }}
          disabled={!ready || busy}
        >
          Continue to class
        </button>
        {allowSkip && onSkip && (
          <button type="button" onClick={onSkip} style={{ background: "transparent" }}>
            Skip check
          </button>
        )}
      </div>
    </div>
  );
}

function VerdictBadge({ verdict }: { verdict: LightingVerdict }) {
  const color =
    verdict === "ready"
      ? "#16a34a"
      : verdict === "fixable"
        ? "#ca8a04"
        : "#dc2626";
  return (
    <span
      style={{
        display: "inline-block",
        background: color,
        color: "#fff",
        fontSize: 12,
        fontWeight: 700,
        padding: "2px 8px",
        borderRadius: 4,
        textTransform: "uppercase",
        letterSpacing: "0.04em",
        marginBottom: 6,
      }}
    >
      {verdict.replace(/_/g, " ")}
    </span>
  );
}
