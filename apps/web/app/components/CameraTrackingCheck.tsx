"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  enrollVoiceSample,
  listStudents,
  type StudentProfile,
} from "../lib/api";
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
import { estimateDistanceFromFaceBox } from "../lib/cameraCheckDistance";
import {
  detectBlink,
  eyeRegionLuma,
  pickVisionColor,
  randomVisionChars,
  spokenMatchesChars,
  spokenMatchesColor,
} from "../lib/cameraCheckVisionTests";
import { localeToBcp47 } from "../lib/tts";
import { useT } from "../lib/i18n";

type AutoStepId = TrackingPose | "lighting" | "distance";
type ManualStepId = "voice" | "vision_chars" | "vision_color" | "vision_blink" | "photo_id";
type StepId = AutoStepId | ManualStepId;

type Step = {
  id: StepId;
  titleKey: string;
  instructionKey?: string;
  auto?: boolean;
};

const STEPS: Step[] = [
  { id: "lighting", titleKey: "cameraCheck.step.lighting", auto: true },
  { id: "distance", titleKey: "cameraCheck.step.distance", auto: true },
  { id: "look_up", titleKey: "cameraCheck.step.lookUp", auto: true },
  { id: "look_down", titleKey: "cameraCheck.step.lookDown", auto: true },
  { id: "look_left", titleKey: "cameraCheck.step.lookLeft", auto: true },
  { id: "look_right", titleKey: "cameraCheck.step.lookRight", auto: true },
  { id: "raise_hands", titleKey: "cameraCheck.step.raiseHands", auto: true },
  { id: "voice", titleKey: "cameraCheck.step.voice" },
  { id: "vision_chars", titleKey: "cameraCheck.step.visionChars" },
  { id: "vision_color", titleKey: "cameraCheck.step.visionColor" },
  { id: "vision_blink", titleKey: "cameraCheck.step.visionBlink", auto: true },
  { id: "photo_id", titleKey: "cameraCheck.step.photoId" },
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

function speechRecognitionAvailable(): boolean {
  const root = globalThis as { SpeechRecognition?: unknown; webkitSpeechRecognition?: unknown };
  return Boolean(root.SpeechRecognition || root.webkitSpeechRecognition);
}

function listenOnce(lang: string, timeoutMs = 9000): Promise<string> {
  return new Promise((resolve, reject) => {
    const root = globalThis as {
      SpeechRecognition?: new () => {
        lang: string;
        interimResults: boolean;
        maxAlternatives: number;
        start: () => void;
        stop: () => void;
        onresult: ((e: { results: { [i: number]: { [j: number]: { transcript: string } } } }) => void) | null;
        onerror: (() => void) | null;
      };
      webkitSpeechRecognition?: new () => {
        lang: string;
        interimResults: boolean;
        maxAlternatives: number;
        start: () => void;
        stop: () => void;
        onresult: ((e: { results: { [i: number]: { [j: number]: { transcript: string } } } }) => void) | null;
        onerror: (() => void) | null;
      };
    };
    const SR = root.SpeechRecognition || root.webkitSpeechRecognition;
    if (!SR) {
      reject(new Error("Speech recognition unavailable"));
      return;
    }
    const rec = new SR();
    rec.lang = lang;
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    const timer = window.setTimeout(() => {
      try { rec.stop(); } catch { /* */ }
      reject(new Error("timeout"));
    }, timeoutMs);
    rec.onresult = (e) => {
      window.clearTimeout(timer);
      resolve(e.results[0]?.[0]?.transcript ?? "");
    };
    rec.onerror = () => {
      window.clearTimeout(timer);
      reject(new Error("speech error"));
    };
    rec.start();
  });
}

type Props = {
  embedded?: boolean;
  onComplete?: () => void;
};

export default function CameraTrackingCheck({ embedded = false, onComplete }: Props) {
  const { t, locale } = useT();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const overlayRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const detectorRef = useRef<FaceDetectorLike | null>(null);
  const prevGridRef = useRef<number[][] | null>(null);
  const holdRef = useRef<number | null>(null);
  const prevEyeLumaRef = useRef<number | null>(null);
  const blinkCountRef = useRef(0);

  const [stepIndex, setStepIndex] = useState(0);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [passed, setPassed] = useState<Record<string, boolean>>({});
  const [lighting, setLighting] = useState<LightingReadiness | null>(null);
  const [distanceM, setDistanceM] = useState<number | null>(null);
  const [distanceBand, setDistanceBand] = useState<"too_close" | "too_far" | "good" | "unknown">("unknown");
  const [handsHint, setHandsHint] = useState(false);
  const [faceBox, setFaceBox] = useState<{ x: number; y: number; width: number; height: number } | null>(null);
  const [done, setDone] = useState(false);
  const [detectorReady, setDetectorReady] = useState(true);

  const [students, setStudents] = useState<StudentProfile[]>([]);
  const [voiceBusy, setVoiceBusy] = useState(false);
  const [voiceMsg, setVoiceMsg] = useState("");
  const [visionChars] = useState(() => randomVisionChars(7));
  const [visionColor] = useState(() => pickVisionColor());
  const [heardText, setHeardText] = useState("");
  const [listenBusy, setListenBusy] = useState(false);
  const [idPreview, setIdPreview] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const step = STEPS[stepIndex];
  const progressLabel = useMemo(
    () => `Step ${Math.min(stepIndex + 1, STEPS.length)} of ${STEPS.length}`,
    [stepIndex],
  );
  const speechLang = localeToBcp47(locale);

  useEffect(() => {
    listStudents().then((r) => setStudents(r.students)).catch(() => setStudents([]));
  }, []);

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((tr) => tr.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);

  const advance = useCallback(() => {
    setPassed((p) => ({ ...p, [STEPS[stepIndex].id]: true }));
    holdRef.current = null;
    blinkCountRef.current = 0;
    prevEyeLumaRef.current = null;
    if (stepIndex + 1 >= STEPS.length) {
      setDone(true);
      setStatus(t("cameraCheck.done"));
      stopStream();
      onComplete?.();
      return;
    }
    setStepIndex((i) => i + 1);
    setStatus("");
  }, [onComplete, stepIndex, stopStream, t]);

  const drawOverlay = useCallback(
    (box: { x: number; y: number; width: number; height: number } | null, dist: number | null) => {
      const overlay = overlayRef.current;
      const video = videoRef.current;
      if (!overlay || !video?.videoWidth) return;
      overlay.width = video.clientWidth;
      overlay.height = video.clientHeight;
      const ctx = overlay.getContext("2d");
      if (!ctx) return;
      ctx.clearRect(0, 0, overlay.width, overlay.height);
      if (box) {
        const x = box.x * overlay.width;
        const y = box.y * overlay.height;
        const w = box.width * overlay.width;
        const h = box.height * overlay.height;
        ctx.strokeStyle = "#38bdf8";
        ctx.lineWidth = 2;
        ctx.strokeRect(x, y, w, h);
        ctx.fillStyle = "rgba(14,165,233,0.12)";
        ctx.fillRect(x, y, w, h);
      }
      ctx.fillStyle = "rgba(15,23,42,0.72)";
      ctx.fillRect(8, 8, 168, 72);
      ctx.fillStyle = "#e2e8f0";
      ctx.font = "12px system-ui, sans-serif";
      ctx.fillText(
        dist != null ? t("cameraCheck.distanceGood", { m: dist.toFixed(2) }) : t("cameraCheck.distanceUnknown"),
        14,
        28,
      );
      if (lighting) {
        ctx.fillText(
          `${t("cameraCheck.light")} ${(lighting.metrics.lightQualityScore * 100).toFixed(0)}% · ${t("cameraCheck.sharp")} ${(lighting.metrics.sharpnessScore * 100).toFixed(0)}%`,
          14,
          48,
        );
        ctx.fillText(
          `${t("cameraCheck.hands")}: ${handsHint ? "✓" : "—"} · ${detectorReady ? t("cameraCheck.contoursOn") : t("cameraCheck.contoursOff")}`,
          14,
          68,
        );
      }
    },
    [detectorReady, handsHint, lighting, t],
  );

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
      const mid = grid.slice(8, 28).flatMap((row) => row.slice(16, 48));
      const mean = mid.reduce((a, b) => a + b, 0) / Math.max(1, mid.length);
      const varSum = mid.reduce((a, b) => a + (b - mean) ** 2, 0) / Math.max(1, mid.length);
      if (varSum > 0.004 && mean > 0.08 && mean < 0.92) {
        boxNorm = { x: 0.3, y: 0.25, width: 0.4, height: 0.5 };
      }
    }

    setFaceBox(boxNorm);
    const dist = estimateDistanceFromFaceBox(boxNorm, video.videoWidth, video.videoHeight);
    setDistanceM(dist.distanceM);
    setDistanceBand(dist.band);

    const hands = raiseHandsHintFromGrids(prevGridRef.current, grid);
    setHandsHint(hands);
    prevGridRef.current = grid;
    const pose = inferTrackingPose(boxNorm, { raiseHandsHint: hands });
    const readiness = verdictFromMetrics(metrics, {
      facePresent: !!boxNorm,
      nightVision: false,
    });
    setLighting(readiness);
    drawOverlay(boxNorm, dist.distanceM);

    const currentStep = STEPS[stepIndex];
    const target = currentStep.id;
    if (!currentStep.auto) return;

    const now = Date.now();
    let matched = false;

    if (target === "lighting") {
      matched = readiness.verdict === "ready";
      setStatus(matched ? readiness.message : readiness.message);
    } else if (target === "distance") {
      matched = dist.band === "good";
      if (dist.band === "too_close" && dist.distanceM != null) {
        setStatus(t("cameraCheck.distanceClose", { m: dist.distanceM.toFixed(2) }));
      } else if (dist.band === "too_far" && dist.distanceM != null) {
        setStatus(t("cameraCheck.distanceFar", { m: dist.distanceM.toFixed(2) }));
      } else if (matched && dist.distanceM != null) {
        setStatus(t("cameraCheck.distanceGood", { m: dist.distanceM.toFixed(2) }));
      } else {
        setStatus(t("cameraCheck.distanceUnknown"));
      }
    } else if (target === "raise_hands") {
      matched = hands || pose === "raise_hands";
      setStatus(matched ? "Hands detected — hold…" : "Raise both hands beside your head");
    } else if (target === "vision_blink") {
      const eye = eyeRegionLuma(grid, boxNorm);
      if (detectBlink(prevEyeLumaRef.current, eye ?? 0)) {
        blinkCountRef.current += 1;
      }
      prevEyeLumaRef.current = eye;
      matched = blinkCountRef.current >= 2;
      setStatus(matched ? "Blinks detected ✓" : t("cameraCheck.visionBlinkPrompt"));
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
  }, [advance, done, drawOverlay, stepIndex, t]);

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
        stream.getTracks().forEach((tr) => tr.stop());
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

  async function recordVoiceName() {
    setVoiceBusy(true);
    setVoiceMsg("");
    audioChunksRef.current = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      const rec = new MediaRecorder(stream, { mimeType: mime });
      mediaRecorderRef.current = rec;
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };
      rec.start(100);
      setVoiceMsg(t("cameraCheck.voiceRecording"));
      await new Promise((r) => setTimeout(r, 4500));
      await new Promise<void>((resolve) => {
        rec.onstop = () => resolve();
        rec.stop();
      });
      stream.getTracks().forEach((tr) => tr.stop());
      const blob = new Blob(audioChunksRef.current, { type: mime });
      const student = students[0];
      if (!student) throw new Error("Sign in and complete your profile first");
      const displayName = student.display_name || "Student";
      await enrollVoiceSample(student.id, blob, displayName);
      setVoiceMsg(t("cameraCheck.voiceSaved"));
      advance();
    } catch (e) {
      setVoiceMsg(String(e));
    } finally {
      setVoiceBusy(false);
    }
  }

  async function listenForVision(kind: "chars" | "color") {
    if (!speechRecognitionAvailable()) {
      setHeardText("Speech recognition not available — type your answer below.");
      return;
    }
    setListenBusy(true);
    setHeardText("");
    try {
      const transcript = await listenOnce(speechLang);
      setHeardText(t("cameraCheck.visionHeard", { text: transcript }));
      const ok =
        kind === "chars"
          ? spokenMatchesChars(transcript, visionChars)
          : spokenMatchesColor(transcript, visionColor, locale);
      if (ok) {
        setTimeout(() => advance(), 600);
      } else {
        setHeardText(`${transcript} — please try again`);
      }
    } catch {
      setHeardText("Could not hear you — try again or use manual continue.");
    } finally {
      setListenBusy(false);
    }
  }

  function captureIdPhoto() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !video.videoWidth) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.88);
    setIdPreview(dataUrl);
    try {
      sessionStorage.setItem("aoep_camera_check_id_preview", dataUrl.slice(0, 200000));
    } catch { /* quota */ }
    advance();
  }

  return (
    <div className={embedded ? undefined : "card"} style={{ maxWidth: 680 }}>
      <h3 style={{ marginTop: 0 }}>{t("cameraCheck.title")}</h3>
      <p className="muted" style={{ marginTop: 0 }}>
        {t("cameraCheck.intro")}
      </p>
      <p style={{ fontWeight: 600, marginBottom: 6 }}>{progressLabel}</p>
      <p style={{ marginTop: 0 }}>
        <strong>{t(step.titleKey)}</strong>
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
        <canvas
          ref={overlayRef}
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            pointerEvents: "none",
            transform: "scaleX(-1)",
          }}
        />
        <canvas ref={canvasRef} style={{ display: "none" }} />
        {step.id === "vision_color" && (
          <div
            style={{
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              width: 120,
              height: 120,
              borderRadius: 16,
              background: visionColor.hex,
              border: "4px solid #fff",
              boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
            }}
          />
        )}
      </div>

      {error ? (
        <p style={{ color: "var(--danger, #ef4444)" }} role="alert">
          {error}
        </p>
      ) : (
        <p className="muted" style={{ fontSize: 13 }}>
          {status}
          {lighting && step.id === "lighting" && (
            <>
              {" "}
              · {lighting.message}
            </>
          )}
          {distanceM != null && step.id !== "lighting" && (
            <> · {t("cameraCheck.distance")} {distanceM.toFixed(2)} m</>
          )}
        </p>
      )}

      {step.id === "vision_chars" && (
        <p style={{ fontSize: 28, letterSpacing: 6, fontWeight: 700, textAlign: "center" }}>
          {visionChars}
        </p>
      )}

      <ol style={{ paddingLeft: 18, fontSize: 13 }}>
        {STEPS.map((s, i) => (
          <li key={s.id} style={{ opacity: i === stepIndex ? 1 : 0.65 }}>
            {passed[s.id] ? "✓ " : i === stepIndex ? "→ " : ""}
            {t(s.titleKey)}
          </li>
        ))}
      </ol>

      {step.id === "voice" && (
        <div style={{ marginBottom: 12 }}>
          <p className="muted">{t("cameraCheck.voicePrompt")}</p>
          <button type="button" disabled={voiceBusy} onClick={() => void recordVoiceName()}>
            {voiceBusy ? t("cameraCheck.voiceRecording") : t("cameraCheck.voiceRecord")}
          </button>
          {voiceMsg && <p className="muted">{voiceMsg}</p>}
        </div>
      )}

      {(step.id === "vision_chars" || step.id === "vision_color") && (
        <div style={{ marginBottom: 12 }}>
          <p className="muted">
            {step.id === "vision_chars"
              ? t("cameraCheck.visionCharsPrompt")
              : t("cameraCheck.visionColorPrompt")}
          </p>
          <button type="button" disabled={listenBusy} onClick={() => void listenForVision(step.id === "vision_chars" ? "chars" : "color")}>
            {listenBusy ? "Listening…" : t("cameraCheck.visionListen")}
          </button>
          {heardText && <p className="muted">{heardText}</p>}
          <button type="button" style={{ marginLeft: 8 }} onClick={advance}>
            {t("cameraCheck.manualContinue")}
          </button>
        </div>
      )}

      {step.id === "photo_id" && (
        <div style={{ marginBottom: 12 }}>
          <p className="muted">{t("cameraCheck.idPrompt")}</p>
          <button type="button" onClick={captureIdPhoto}>
            {t("cameraCheck.idCapture")}
          </button>
          {idPreview && (
            <p className="muted" style={{ color: "#047857" }}>
              {t("cameraCheck.idCaptured")}
            </p>
          )}
        </div>
      )}

      {done && (
        <p style={{ color: "#047857", fontWeight: 600 }}>
          {t("cameraCheck.done")}
        </p>
      )}

      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        {!done && !detectorReady && step.auto && step.id !== "lighting" && step.id !== "raise_hands" && step.id !== "distance" && step.id !== "vision_blink" ? (
          <button type="button" onClick={advance}>
            {t("cameraCheck.manualContinue")}
          </button>
        ) : null}
        <button
          type="button"
          onClick={() => {
            setDone(false);
            setStepIndex(0);
            setPassed({});
            holdRef.current = null;
            blinkCountRef.current = 0;
            setStatus("Restarting…");
            setIdPreview(null);
            setHeardText("");
            setVoiceMsg("");
            if (!streamRef.current) void openStream();
          }}
        >
          {t("cameraCheck.restart")}
        </button>
        {!embedded && (
          <a href="/account" style={{ alignSelf: "center", fontSize: 14 }}>
            {t("cameraCheck.backAccount")}
          </a>
        )}
      </div>
    </div>
  );
}
