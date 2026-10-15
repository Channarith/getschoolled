"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Image from "next/image";
import {
  deleteBiometrics,
  enrollBiometricFace,
  enrollVoiceprint,
  getSetupAssistant,
  setBiometricConsent,
  submitGovernmentId,
  updateSetupAssistant,
} from "../lib/api";
import { createVisionEngine, type VisionEngine } from "../lib/vision";
import styles from "./BiometricSetupAssistant.module.css";

const VOICE_PROMPT =
  "Today I’m ready to learn with Salareen. Can you hear my voice clearly? Yes—I’m speaking naturally and confidently.";

const TICKS = 72;
const VOICE_SECONDS = 10;
const SCAN_INTERVAL_MS = 160;
// Normalized nose offset (fraction of eye distance / eye-mouth height) that
// counts as a deliberate head turn.
const YAW_THRESHOLD = 0.16;
const PITCH_THRESHOLD = 0.1;
const COVERAGE_TARGET = 0.75;

type Stage = "intro" | "scan" | "voice" | "identity" | "complete";
type Pose = "left" | "right" | "up" | "down";
const POSES: Pose[] = ["left", "right", "up", "down"];

type Props = {
  studentId: string;
  ageBand?: string;
  requireGovernmentId?: boolean;
  allowSkip?: boolean;
  /** Shown above the headline, e.g. "Step 3 of 4". */
  stepLabel?: string;
  onComplete?: () => void;
  onSkip?: () => void;
  onBack?: () => void;
};

type Geometry = { yaw: number; pitch: number; centered: boolean };

function faceGeometry(landmarks: number[][], bbox: number[], frame: number[]): Geometry | null {
  if (landmarks.length < 5) return null;
  const [rightEye, leftEye, nose, rightMouth, leftMouth] = landmarks;
  const eyeMid = [(rightEye[0] + leftEye[0]) / 2, (rightEye[1] + leftEye[1]) / 2];
  const mouthMid = [(rightMouth[0] + leftMouth[0]) / 2, (rightMouth[1] + leftMouth[1]) / 2];
  const eyeDist = Math.hypot(leftEye[0] - rightEye[0], leftEye[1] - rightEye[1]);
  const faceHeight = mouthMid[1] - eyeMid[1];
  if (eyeDist <= 1 || faceHeight <= 1) return null;
  const axisX = (eyeMid[0] + mouthMid[0]) / 2;
  const cx = bbox[0] + bbox[2] / 2;
  const cy = bbox[1] + bbox[3] / 2;
  return {
    yaw: (nose[0] - axisX) / eyeDist,
    pitch: (nose[1] - eyeMid[1]) / faceHeight,
    centered:
      Math.abs(cx / frame[0] - 0.5) < 0.2 && Math.abs(cy / frame[1] - 0.5) < 0.22,
  };
}

function formatClock(seconds: number) {
  return `00:${String(Math.floor(seconds)).padStart(2, "0")}`;
}

export default function BiometricSetupAssistant({
  studentId,
  ageBand = "adult",
  requireGovernmentId = false,
  allowSkip = true,
  stepLabel,
  onComplete,
  onSkip,
  onBack,
}: Props) {
  const [stage, setStage] = useState<Stage>("intro");
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [hint, setHint] = useState("Starting camera…");
  const [lit, setLit] = useState<boolean[]>(() => Array(TICKS).fill(false));
  const [captured, setCaptured] = useState<Pose[]>([]);
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [levels, setLevels] = useState<number[]>(() => Array(TICKS).fill(0));
  const [guardianConsent, setGuardianConsent] = useState(ageBand === "adult");
  const [idFile, setIdFile] = useState<File | null>(null);
  const [hasEnrollment, setHasEnrollment] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const engineRef = useRef<VisionEngine | null>(null);
  const scanRef = useRef<{
    neutral: number[] | null;
    base: Geometry | null;
    poses: Partial<Record<Pose, number[]>>;
    lit: boolean[];
    enrolling: boolean;
  }>({ neutral: null, base: null, poses: {}, lit: Array(TICKS).fill(false), enrolling: false });

  const minor = ageBand !== "adult";

  const stopMedia = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);

  useEffect(() => () => stopMedia(), [stopMedia]);

  useEffect(() => {
    getSetupAssistant(studentId).then((state) => {
      setHasEnrollment(
        state.portrait.status === "verified"
        || state.voice.status === "verified"
        || state.government_id.status === "verified",
      );
    }).catch(() => undefined);
  }, [studentId]);

  const resetScan = useCallback(() => {
    scanRef.current = {
      neutral: null, base: null, poses: {}, lit: Array(TICKS).fill(false), enrolling: false,
    };
    setLit(Array(TICKS).fill(false));
    setCaptured([]);
    setElapsed(0);
  }, []);

  const enrollFace = useCallback(async () => {
    const scan = scanRef.current;
    if (scan.enrolling || !scan.neutral) return;
    scan.enrolling = true;
    setHint("Saving your Face ID…");
    try {
      const vectors = [scan.neutral, ...POSES.map((pose) => scan.poses[pose] as number[])];
      await enrollBiometricFace(studentId, vectors, POSES);
      stopMedia();
      setStage("voice");
    } catch (reason) {
      setError(String(reason));
      resetScan();
    }
  }, [resetScan, stopMedia, studentId]);

  // Face ID-style scan: track head direction from the live landmarks, light
  // the ring ticks the user sweeps through, and keep one embedding per pose.
  useEffect(() => {
    if (stage !== "scan") return;
    let cancelled = false;
    let timer = 0;
    let clock = 0;
    let processing = false;

    async function start() {
      setError("");
      resetScan();
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "user", width: { ideal: 960 }, height: { ideal: 960 } },
          audio: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
        setHint("Loading face model…");
        engineRef.current ??= await createVisionEngine();
      } catch (reason) {
        setError(`Camera unavailable: ${String(reason)}`);
        return;
      }
      if (cancelled) return;
      setHint("Position your face inside the circle.");
      const started = performance.now();
      clock = window.setInterval(() => setElapsed((performance.now() - started) / 1000), 250);
      timer = window.setInterval(tick, SCAN_INTERVAL_MS);
    }

    function tick() {
      const video = videoRef.current;
      const engine = engineRef.current;
      const scan = scanRef.current;
      if (processing || !video || !engine || scan.enrolling) return;
      processing = true;
      try {
        const faces = engine.detectAndEmbed(video);
        if (faces.length !== 1) {
          setHint(faces.length ? "Only one face, please." : "Position your face inside the circle.");
          return;
        }
        const face = faces[0];
        const frame = face.frame_size ?? [video.videoWidth, video.videoHeight];
        const geometry = faceGeometry(face.landmarks ?? [], face.bbox ?? [0, 0, frame[0], frame[1]], frame);
        if (!geometry) return;
        if (!scan.base) {
          if (!geometry.centered) {
            setHint("Center your face in the circle.");
            return;
          }
          scan.base = geometry;
          scan.neutral = face.embedding;
          setHint("Slowly move your head to complete the circle.");
          return;
        }
        // The preview is mirrored, so flip yaw to match what the user sees.
        const dx = -(geometry.yaw - scan.base.yaw) / YAW_THRESHOLD;
        const dy = (geometry.pitch - scan.base.pitch) / PITCH_THRESHOLD;
        const magnitude = Math.hypot(dx, dy);
        if (magnitude < 1) return;
        const angle = Math.atan2(dy, dx);
        const center = Math.round(((angle + Math.PI * 2) % (Math.PI * 2)) / (Math.PI * 2) * TICKS) % TICKS;
        for (let offset = -3; offset <= 3; offset += 1) {
          scan.lit[(center + offset + TICKS) % TICKS] = true;
        }
        setLit([...scan.lit]);

        const pose: Pose = Math.abs(dx) >= Math.abs(dy)
          ? (dx < 0 ? "left" : "right")
          : (dy < 0 ? "up" : "down");
        if (!scan.poses[pose]) {
          scan.poses[pose] = face.embedding;
          setCaptured(POSES.filter((item) => scan.poses[item]));
        }
        const coverage = scan.lit.filter(Boolean).length / TICKS;
        const missing = POSES.filter((item) => !scan.poses[item]);
        if (missing.length === 0 && coverage >= COVERAGE_TARGET) {
          void enrollFace();
        } else if (missing.length) {
          setHint(`Keep going — now tilt ${missing[0]}.`);
        } else {
          setHint("Almost there — finish the circle.");
        }
      } finally {
        processing = false;
      }
    }

    void start();
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      window.clearInterval(clock);
      stopMedia();
    };
  }, [attempt, enrollFace, resetScan, stage, stopMedia]);

  async function recordVoice() {
    setError("");
    setBusy(true);
    let audioContext: AudioContext | null = null;
    let frame = 0;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      audioContext = new AudioContext();
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      audioContext.createMediaStreamSource(stream).connect(analyser);
      const bins = new Uint8Array(analyser.frequencyBinCount);
      const started = performance.now();
      const draw = () => {
        analyser.getByteFrequencyData(bins);
        setLevels(Array.from({ length: TICKS }, (_, index) => {
          const bin = bins[Math.floor((index % (TICKS / 2)) / (TICKS / 2) * bins.length * 0.7)];
          return bin / 255;
        }));
        setElapsed((performance.now() - started) / 1000);
        frame = requestAnimationFrame(draw);
      };
      frame = requestAnimationFrame(draw);

      const recorder = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };
      const finished = new Promise<Blob>((resolve, reject) => {
        recorder.onerror = () => reject(new Error("Voice recording failed"));
        recorder.onstop = () => resolve(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }));
      });
      setRecording(true);
      recorder.start();
      await new Promise<void>((resolve) => window.setTimeout(resolve, VOICE_SECONDS * 1000));
      recorder.stop();
      const blob = await finished;
      cancelAnimationFrame(frame);
      setRecording(false);
      setLevels(Array(TICKS).fill(0));
      stopMedia();
      await enrollVoiceprint(studentId, blob);
      setStage(requireGovernmentId ? "identity" : "complete");
    } catch (reason) {
      setError(String(reason));
    } finally {
      cancelAnimationFrame(frame);
      void audioContext?.close();
      setRecording(false);
      setBusy(false);
    }
  }

  async function begin() {
    setBusy(true);
    setError("");
    try {
      await setBiometricConsent(studentId, {
        granted: true,
        guardian_granted: minor ? guardianConsent : false,
        retention_days: 365,
      });
      await updateSetupAssistant(studentId, { current_step: "biometrics" });
      setStage("scan");
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function submitId() {
    if (!idFile) return;
    setBusy(true);
    setError("");
    try {
      const result = await submitGovernmentId(studentId, "government_id", idFile);
      if (result.status !== "verified") {
        throw new Error("The portrait on this ID did not match. Use a clear, well-lit image and try again.");
      }
      setStage("complete");
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function finish() {
    await updateSetupAssistant(studentId, { current_step: "complete", complete: true }).catch(() => undefined);
    onComplete?.();
  }

  async function skip() {
    stopMedia();
    await updateSetupAssistant(studentId, {
      current_step: "complete",
      skipped_biometrics: true,
      complete: true,
    }).catch(() => undefined);
    onSkip?.();
  }

  async function removeIdentity() {
    setBusy(true);
    setError("");
    try {
      await deleteBiometrics(studentId);
      setHasEnrollment(false);
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  const coverage = lit.filter(Boolean).length / TICKS;
  const ringDone = stage === "complete" || stage === "identity";
  const art = stage === "voice" ? "voice" : "face-scan";

  return (
    <main className={styles.shell} data-stage={stage}>
      <div className={styles.backdrop} aria-hidden="true">
        <Image key={art} className={styles.art} src={`/setup-assistant/${art}.webp`} alt="" fill priority sizes="100vw" />
        <div className={styles.glow} />
        <div className={styles.grain} />
      </div>

      <header className={styles.topbar}>
        <span className={styles.brand}>Salareen</span>
        {stepLabel && <span className={styles.stepLabel}>{stepLabel}</span>}
        {(stage === "scan" || recording) && (
          <span className={styles.rec} aria-live="polite">
            <i /> REC {formatClock(elapsed)}
          </span>
        )}
      </header>

      <section className={styles.stageArea}>
        <div className={styles.ringWrap}>
          <svg className={styles.ring} viewBox="0 0 400 400" aria-hidden="true">
            {Array.from({ length: TICKS }, (_, index) => {
              const angle = (index / TICKS) * Math.PI * 2;
              const level = stage === "voice" ? levels[index] : 0;
              const on = ringDone || lit[index];
              const inner = 176;
              const outer = inner + (on ? 18 : 11) + level * 22;
              return (
                <line
                  key={index}
                  x1={200 + Math.cos(angle) * inner}
                  y1={200 + Math.sin(angle) * inner}
                  x2={200 + Math.cos(angle) * outer}
                  y2={200 + Math.sin(angle) * outer}
                  className={on ? styles.tickOn : level > 0.05 ? styles.tickVoice : styles.tick}
                  style={{ transitionDelay: ringDone ? `${index * 8}ms` : undefined }}
                />
              );
            })}
            {stage === "voice" && recording && (
              <circle
                className={styles.voiceArc}
                cx="200" cy="200" r="166"
                pathLength={100}
                strokeDasharray={`${Math.min(100, (elapsed / VOICE_SECONDS) * 100)} 100`}
              />
            )}
          </svg>
          <div className={styles.lens}>
            {stage === "scan" ? (
              <video ref={videoRef} className={styles.camera} muted playsInline />
            ) : (
              <Image className={styles.lensArt} src={`/setup-assistant/${art}.webp`} alt="" fill sizes="420px" />
            )}
            {stage === "scan" && <div className={styles.scanLine} aria-hidden="true" />}
            {ringDone && <div className={styles.check} aria-hidden="true">✓</div>}
          </div>
        </div>

        <div className={styles.copy}>
          {stage === "intro" && (
            <>
              <span className={styles.eyebrow}>Optional · about 1 minute</span>
              <h1>Set up Face &amp; Voice ID.</h1>
              <p>
                First, a quick face scan — slowly move your head in a circle, just like setting up Face ID.
                Then read one sentence out loud so we can recognize your voice.
              </p>
              <ul className={styles.facts}>
                <li><b>Face scan</b> Turn left, right, up and down until the ring turns green.</li>
                <li><b>Voice check</b> Read a short sentence for {VOICE_SECONDS} seconds.</li>
                <li><b>Private</b> Only protected templates are kept — never the video, audio, or ID photos.</li>
              </ul>
              {minor && (
                <label className={styles.consent}>
                  <input
                    type="checkbox"
                    checked={guardianConsent}
                    onChange={(event) => setGuardianConsent(event.target.checked)}
                  />
                  I’m the parent or guardian and I agree to this learner’s Face &amp; Voice ID setup.
                </label>
              )}
            </>
          )}
          {stage === "scan" && (
            <>
              <span className={styles.eyebrow}>Face scan · {Math.round(coverage * 100)}%</span>
              <h1>{hint}</h1>
              <div className={styles.poses}>
                {POSES.map((pose) => (
                  <span key={pose} className={captured.includes(pose) ? styles.poseDone : ""}>
                    {captured.includes(pose) ? "✓ " : ""}{pose}
                  </span>
                ))}
              </div>
            </>
          )}
          {stage === "voice" && (
            <>
              <span className={styles.eyebrow}>Voice check</span>
              <h1>{recording ? "Keep reading…" : "Now read this out loud."}</h1>
              <blockquote className={styles.prompt}>{VOICE_PROMPT}</blockquote>
            </>
          )}
          {stage === "identity" && (
            <>
              <span className={styles.eyebrow}>Accredited course · Government ID</span>
              <h1>One last check.</h1>
              <p>
                Courses that lead to a certificate or license need a government ID match.
                The image is checked once and then discarded.
              </p>
              <label className={styles.file}>
                Choose a clear JPEG or PNG of the front of the ID
                <input
                  type="file"
                  accept="image/jpeg,image/png"
                  onChange={(event) => setIdFile(event.target.files?.[0] ?? null)}
                />
              </label>
            </>
          )}
          {stage === "complete" && (
            <>
              <span className={styles.eyebrow}>Face &amp; Voice ID is set up</span>
              <h1>You’re all set.</h1>
              <p>Review or remove it any time in Profile → Settings → Camera check.</p>
            </>
          )}

          {error && <p className={styles.error} role="alert">{error}</p>}

          <div className={styles.actions}>
            {stage === "intro" && (
              <>
                <button
                  className={styles.primary}
                  disabled={busy || (minor && !guardianConsent)}
                  onClick={() => void begin()}
                >Get started</button>
                {allowSkip && !requireGovernmentId && (
                  <button className={styles.secondary} onClick={() => void skip()}>Set up later</button>
                )}
                {onBack && <button className={styles.ghost} onClick={onBack}>Back</button>}
                {hasEnrollment && !requireGovernmentId && (
                  <button className={styles.ghost} disabled={busy} onClick={() => void removeIdentity()}>
                    Remove saved identity
                  </button>
                )}
              </>
            )}
            {stage === "scan" && (
              <>
                {error && (
                  <button className={styles.primary} onClick={() => setAttempt((value) => value + 1)}>
                    Try again
                  </button>
                )}
                {allowSkip && !requireGovernmentId && (
                  <button className={styles.secondary} onClick={() => void skip()}>Set up later</button>
                )}
              </>
            )}
            {stage === "voice" && (
              <>
                <button className={styles.primary} disabled={busy} onClick={() => void recordVoice()}>
                  {recording ? `Recording… ${Math.max(0, Math.ceil(VOICE_SECONDS - elapsed))}s` : "Start recording"}
                </button>
                {allowSkip && !requireGovernmentId && !busy && (
                  <button className={styles.secondary} onClick={() => void skip()}>Set up later</button>
                )}
              </>
            )}
            {stage === "identity" && (
              <>
                <button className={styles.primary} disabled={busy || !idFile} onClick={() => void submitId()}>
                  {busy ? "Checking securely…" : "Verify ID"}
                </button>
                {!requireGovernmentId && (
                  <button className={styles.secondary} onClick={() => setStage("complete")}>Not now</button>
                )}
              </>
            )}
            {stage === "complete" && (
              <button className={styles.primary} onClick={() => void finish()}>Continue</button>
            )}
          </div>
          <p className={styles.footnote}>
            Games and general courses never need Face &amp; Voice ID. Accredited and certification courses
            (like driver’s ed and food safety) require it before the first full lesson.
          </p>
        </div>
      </section>
    </main>
  );
}
