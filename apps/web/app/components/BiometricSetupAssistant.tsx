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
import {
  POSES,
  describeMediaError,
  faceContour,
  faceGeometry,
  faceMarks,
  lightingAction,
  levelFromTimeDomain,
  meanLuma,
  pickRecorderMime,
  poseFromBaseline,
  shuffledPoses,
  stableFaceMarks,
  svgPath,
  waveformBars,
  type FaceContour,
  type FaceMark,
  type Geometry,
  type LevelSample,
  type LightingAction,
  type MediaProblem,
  type Pose,
} from "../lib/learnerCheck";
import styles from "./BiometricSetupAssistant.module.css";

const VOICE_PROMPT =
  "Today I’m ready to learn with Salareen. Can you hear my voice clearly? Yes—I’m speaking naturally and confidently.";

const VOICE_SECONDS = 10;
const WAVE_BARS = 60;
// 110 ms ≈ 9 fps. We split the slow SFace embed off the hot path (see tick()
// below), so this interval drives only landmark detection + mesh rendering,
// which is cheap enough to run this fast on CPU.
const SCAN_INTERVAL_MS = 110;
const LIGHT_CHECK_MS = 1200;

const POSE_COPY: Record<Pose, string> = {
  left: "Look to your left",
  right: "Look to your right",
  up: "Look up",
  down: "Look down",
};
const POSE_ARROW: Record<Pose, string> = { left: "←", right: "→", up: "↑", down: "↓" };

type Stage = "intro" | "scan" | "voice" | "identity" | "complete";
type Problem = { kind: MediaProblem | "service" | "save"; message: string };

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

function formatClock(seconds: number) {
  return `00:${String(Math.floor(seconds)).padStart(2, "0")}`;
}

function voiceProblem(reason: unknown): Problem {
  const message = String((reason as Error)?.message ?? reason);
  if (/^503\b/.test(message)) {
    return { kind: "service", message: "The voice check isn’t available right now. Try again in a minute, or set it up later." };
  }
  if (/silent|too quiet/i.test(message)) {
    return { kind: "save", message: "We couldn’t hear you. Move closer to the microphone and read the sentence out loud." };
  }
  if (/clipped/i.test(message)) {
    return { kind: "save", message: "That was too loud. Hold the device a little farther away and try again." };
  }
  if (/between 8 and 15|too short|decoded/i.test(message)) {
    return { kind: "save", message: "The recording didn’t come through in full. Try again and keep reading until the bar fills." };
  }
  return { kind: "save", message: `Couldn’t save your voice check: ${message}` };
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
  const [problem, setProblem] = useState<Problem | null>(null);
  const [hint, setHint] = useState("Starting camera…");
  const [targets, setTargets] = useState<Pose[]>(() => [...POSES]);
  const [captured, setCaptured] = useState<Pose[]>([]);
  const [anchored, setAnchored] = useState(false);
  const [contour, setContour] = useState<{ shape: FaceContour; frame: [number, number]; marks: FaceMark[] } | null>(null);
  const [lighting, setLighting] = useState<LightingAction>("none");
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [bars, setBars] = useState<number[]>(() => Array(WAVE_BARS).fill(0));
  const [guardianConsent, setGuardianConsent] = useState(ageBand === "adult");
  const [idFile, setIdFile] = useState<File | null>(null);
  const [hasEnrollment, setHasEnrollment] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const pendingCameraRef = useRef<Promise<MediaStream> | null>(null);
  const engineRef = useRef<VisionEngine | null>(null);
  const scanRef = useRef<{
    neutral: number[] | null;
    base: Geometry | null;
    order: Pose[];
    poses: Partial<Record<Pose, number[]>>;
    enrolling: boolean;
  }>({ neutral: null, base: null, order: [...POSES], poses: {}, enrolling: false });

  const minor = ageBand !== "adult";
  const canSkip = allowSkip && !requireGovernmentId;

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
    const order = shuffledPoses();
    scanRef.current = { neutral: null, base: null, order, poses: {}, enrolling: false };
    setTargets(order);
    setCaptured([]);
    setAnchored(false);
    setContour(null);
    setElapsed(0);
  }, []);

  const enrollFace = useCallback(async () => {
    const scan = scanRef.current;
    if (scan.enrolling || !scan.neutral) return;
    scan.enrolling = true;
    setHint("Face map ready");
    try {
      const vectors = [scan.neutral, ...scan.order.map((pose) => scan.poses[pose] as number[])];
      await enrollBiometricFace(studentId, vectors, scan.order);
      stopMedia();
      setLighting("none");
      setStage("voice");
    } catch (reason) {
      setProblem({ kind: "save", message: `Couldn’t save your face check: ${String((reason as Error)?.message ?? reason)}` });
      stopMedia();
    }
  }, [stopMedia, studentId]);

  // Look-target scan: track head direction from the live landmarks and keep
  // one embedding per target, in a fresh random order each attempt.
  useEffect(() => {
    if (stage !== "scan") return;
    let cancelled = false;
    let timer = 0;
    let clock = 0;
    let processing = false;
    let lastLightCheck = 0;
    let torchOn = false;
    let screenLight = false;
    const probe = document.createElement("canvas");
    probe.width = 48;
    probe.height = 64;
    const markProbe = document.createElement("canvas");
    const markHistory: FaceMark[][] = [];

    function sampleMarks(
      video: HTMLVideoElement,
      landmarks: number[][],
      box: number[] | undefined,
      frame: [number, number],
    ): FaceMark[] {
      const srcW = frame[0] || video.videoWidth;
      const srcH = frame[1] || video.videoHeight;
      if (!srcW || !srcH) return [];
      const tw = 180;
      const scale = tw / srcW;
      const th = Math.max(1, Math.round(srcH * scale));
      if (markProbe.width !== tw) markProbe.width = tw;
      if (markProbe.height !== th) markProbe.height = th;
      const ctx = markProbe.getContext("2d", { willReadFrequently: true });
      if (!ctx) return [];
      ctx.drawImage(video, 0, 0, tw, th);
      const scaledBox = box && box.length >= 4
        ? [box[0] * scale, box[1] * scale, box[2] * scale, box[3] * scale]
        : null;
      return faceMarks(
        ctx.getImageData(0, 0, tw, th).data,
        tw,
        th,
        landmarks.map(([x, y]) => [x * scale, y * scale]),
        scaledBox,
      ).map((mark) => ({
        ...mark,
        point: [mark.point[0] / scale, mark.point[1] / scale],
      }));
    }

    async function start() {
      setProblem(null);
      setLighting("none");
      resetScan();
      setHint("Starting camera…");
      try {
        const pending = pendingCameraRef.current;
        pendingCameraRef.current = null;
        const stream = pending
          ? await pending
          : await navigator.mediaDevices.getUserMedia({
            video: { facingMode: "user", width: { ideal: 960 }, height: { ideal: 1280 } },
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
      } catch (reason) {
        if (!cancelled) setProblem(describeMediaError(reason, "camera"));
        return;
      }
      setHint("Loading face model…");
      try {
        engineRef.current ??= await createVisionEngine();
      } catch (reason) {
        if (cancelled) return;
        stopMedia();
        const err = reason as Error;
        setProblem(describeMediaError(
          err?.name === "ModelLoadError" ? err : Object.assign(new Error(String(err?.message ?? err)), { name: "ModelLoadError" }),
          "camera",
        ));
        return;
      }
      if (cancelled) return;
      setHint("Center your face in the frame.");
      const started = performance.now();
      clock = window.setInterval(() => setElapsed((performance.now() - started) / 1000), 250);
      timer = window.setInterval(tick, SCAN_INTERVAL_MS);
    }

    async function checkLight(video: HTMLVideoElement) {
      const ctx = probe.getContext("2d", { willReadFrequently: true });
      if (!ctx) return;
      ctx.drawImage(video, 0, 0, probe.width, probe.height);
      const luma = meanLuma(ctx.getImageData(0, 0, probe.width, probe.height).data, 1);
      if (torchOn || screenLight) return;
      const track = streamRef.current?.getVideoTracks()[0];
      const caps = (track?.getCapabilities?.() ?? {}) as { torch?: boolean };
      const action = lightingAction(luma, Boolean(caps.torch));
      if (action === "torch" && track) {
        try {
          await track.applyConstraints({ advanced: [{ torch: true } as MediaTrackConstraintSet] });
          torchOn = true;
          setLighting("torch");
          return;
        } catch {
          /* fall through to the screen light */
        }
      }
      if (action !== "none") {
        screenLight = true;
        setLighting("screen");
      }
    }

    function tick() {
      const video = videoRef.current;
      const engine = engineRef.current;
      const scan = scanRef.current;
      if (processing || !video || !engine || scan.enrolling || video.readyState < 2) return;
      processing = true;
      try {
        const now = performance.now();
        if (now - lastLightCheck > LIGHT_CHECK_MS) {
          lastLightCheck = now;
          void checkLight(video);
        }
        // Fast path for every tick: YuNet landmarks only. SFace (the slow
        // 38 MB ONNX net) is skipped unless we are about to capture — either
        // the neutral baseline or a matched pose. This keeps the pose
        // feedback responsive at ~10 fps even on CPU.
        const needsEmbedding = !scan.base;
        let faces = needsEmbedding
          ? engine.detectAndEmbed(video)
          : engine.detect(video);
        if (faces.length !== 1) {
          markHistory.length = 0;
          setContour(null);
          setHint(faces.length ? "Only one face, please." : "Center your face in the frame.");
          return;
        }
        let face = faces[0];
        const frame = (face.frame_size ?? [video.videoWidth, video.videoHeight]) as [number, number];
        // Fewer mesh samples than the 32-point default: 18 lines look just
        // as readable and cut SVG path cost by ~45%, which matters because
        // this re-renders every scan tick.
        const shape = faceContour(face.landmarks, 18, face.bbox);
        if (!shape || !face.landmarks) {
          markHistory.length = 0;
          setContour(null);
        } else {
          // Pixels stay in this canvas. The mesh and any mark are drawn from
          // them here; the frame is not uploaded.
          const found = sampleMarks(video, face.landmarks, face.bbox, frame);
          markHistory.push(found);
          if (markHistory.length > 5) markHistory.shift();
          setContour({ shape, frame, marks: stableFaceMarks(markHistory, 3) });
        }
        const geometry = faceGeometry(face.landmarks ?? [], face.bbox ?? [0, 0, frame[0], frame[1]], frame);
        if (!geometry) return;
        if (!scan.base) {
          if (!geometry.centered) {
            setHint("Center your face in the frame.");
            return;
          }
          scan.base = geometry;
          scan.neutral = face.embedding;
          setAnchored(true);
          setHint(`Checking distinctive features. ${POSE_COPY[scan.order[0]]}`);
          return;
        }
        const target = scan.order.find((pose) => !scan.poses[pose]);
        if (!target) return;
        const pose = poseFromBaseline(scan.base, geometry);
        if (pose !== target) {
          setHint(POSE_COPY[target]);
          return;
        }
        // The pose matches — now (and only now) run the full embed step so
        // we have a vector to store for this pose.
        const embedded = engine.detectAndEmbed(video);
        if (embedded.length !== 1) {
          // Face moved out of frame between detect and embed — retry next tick.
          return;
        }
        face = embedded[0];
        scan.poses[target] = face.embedding;
        const done = scan.order.filter((item) => scan.poses[item]);
        setCaptured(done);
        const next = scan.order.find((item) => !scan.poses[item]);
        if (next) {
          setHint(`Checking distinctive features. ${POSE_COPY[next]}`);
        } else {
          void enrollFace();
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
    const micPromise = navigator.mediaDevices?.getUserMedia?.({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    micPromise?.catch(() => undefined);
    setProblem(null);
    setBusy(true);
    setElapsed(0);
    setBars(Array(WAVE_BARS).fill(0));
    let audioContext: AudioContext | null = null;
    let frame = 0;
    let chunks: Blob[] = [];
    let stream: MediaStream;
    if (typeof window.MediaRecorder === "undefined" || !micPromise) {
      setProblem(describeMediaError({ name: "NotSupportedError" }, "microphone"));
      setBusy(false);
      return;
    }
    try {
      stream = await micPromise;
    } catch (reason) {
      setProblem(describeMediaError(reason, "microphone"));
      setBusy(false);
      return;
    }
    streamRef.current = stream;
    try {
      const Context = window.AudioContext
        ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      const samples: LevelSample[] = [];
      let analyser: AnalyserNode | null = null;
      let buffer = new Uint8Array(0);
      if (Context) {
        audioContext = new Context();
        await audioContext.resume().catch(() => undefined);
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 1024;
        audioContext.createMediaStreamSource(stream).connect(analyser);
        buffer = new Uint8Array(analyser.fftSize);
      }

      const mimeType = pickRecorderMime(MediaRecorder.isTypeSupported?.bind(MediaRecorder));
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };
      const finished = new Promise<Blob>((resolve, reject) => {
        recorder.onerror = () => reject(new Error("Voice recording failed"));
        recorder.onstop = () => resolve(new Blob(chunks, { type: recorder.mimeType || mimeType || "audio/webm" }));
      });
      recorder.start(250);
      setRecording(true);
      const started = performance.now();
      const draw = () => {
        const t = (performance.now() - started) / 1000;
        if (analyser) {
          analyser.getByteTimeDomainData(buffer);
          samples.push({ t, level: levelFromTimeDomain(buffer) });
        }
        setBars(waveformBars(samples, VOICE_SECONDS, WAVE_BARS));
        setElapsed(Math.min(VOICE_SECONDS, t));
        if (t < VOICE_SECONDS) frame = requestAnimationFrame(draw);
      };
      frame = requestAnimationFrame(draw);
      await new Promise<void>((resolve) => window.setTimeout(resolve, VOICE_SECONDS * 1000 + 150));
      if (recorder.state !== "inactive") recorder.stop();
      let blob: Blob | null = await finished;
      chunks = [];
      cancelAnimationFrame(frame);
      setElapsed(VOICE_SECONDS);
      setRecording(false);
      stopMedia();
      if (!blob.size) throw new Error("silent");
      try {
        await enrollVoiceprint(studentId, blob);
      } finally {
        blob = null;
      }
      setStage(requireGovernmentId ? "identity" : "complete");
    } catch (reason) {
      setProblem(voiceProblem(reason));
    } finally {
      chunks = [];
      cancelAnimationFrame(frame);
      void audioContext?.close().catch(() => undefined);
      stopMedia();
      setRecording(false);
      setBusy(false);
    }
  }

  async function begin() {
    setBusy(true);
    setProblem(null);
    // Start the camera prompt in this tap. Waiting on the network first makes
    // phones show Allow and then ignore the tap.
    const cameraPromise = navigator.mediaDevices?.getUserMedia?.({
      video: { facingMode: "user", width: { ideal: 960 }, height: { ideal: 1280 } },
      audio: false,
    });
    pendingCameraRef.current = cameraPromise ?? null;
    cameraPromise?.catch(() => undefined);
    try {
      await setBiometricConsent(studentId, {
        granted: true,
        guardian_granted: minor ? guardianConsent : false,
        retention_days: 365,
      });
      await updateSetupAssistant(studentId, { current_step: "biometrics" });
      setStage("scan");
    } catch (reason) {
      pendingCameraRef.current = null;
      cameraPromise?.then((stream) => stream.getTracks().forEach((track) => track.stop())).catch(() => undefined);
      setProblem({ kind: "save", message: String((reason as Error)?.message ?? reason) });
    } finally {
      setBusy(false);
    }
  }

  async function submitId() {
    if (!idFile) return;
    setBusy(true);
    setProblem(null);
    try {
      const result = await submitGovernmentId(studentId, "government_id", idFile);
      if (result.status !== "verified") {
        throw new Error("The portrait on this ID did not match. Use a clear, well-lit image and try again.");
      }
      setStage("complete");
    } catch (reason) {
      setProblem({ kind: "save", message: String((reason as Error)?.message ?? reason) });
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
    setProblem(null);
    try {
      await deleteBiometrics(studentId);
      setHasEnrollment(false);
    } catch (reason) {
      setProblem({ kind: "save", message: String((reason as Error)?.message ?? reason) });
    } finally {
      setBusy(false);
    }
  }

  function openCamera() {
    const cameraPromise = navigator.mediaDevices?.getUserMedia?.({
      video: { facingMode: "user", width: { ideal: 960 }, height: { ideal: 1280 } },
      audio: false,
    });
    pendingCameraRef.current = cameraPromise ?? null;
    cameraPromise?.catch(() => undefined);
  }

  function retryScan() {
    setProblem(null);
    openCamera();
    setAttempt((value) => value + 1);
  }

  const art = stage === "voice" ? "voice" : "face-scan";
  const target = targets.find((pose) => !captured.includes(pose));
  const scanning = stage === "scan" && !problem;
  const progress = Math.min(1, elapsed / VOICE_SECONDS);

  return (
    <main className={`${styles.shell} aoep-immersive-setup aoep-viewport-shell`} data-stage={stage} data-light={lighting}>
      <header className={styles.topbar}>
        <span className={styles.brand}>Salareen</span>
        {stepLabel && <span className={styles.stepLabel}>{stepLabel}</span>}
        {(stage === "scan" || recording) && (
          <span className={styles.rec} aria-live="polite">
            <i /> {formatClock(elapsed)}
          </span>
        )}
      </header>

      <section className={styles.stageArea}>
        <div className={styles.copy}>
          {stage === "intro" && (
            <>
              <span className={styles.eyebrow}>Optional · about 1 minute</span>
              <h1>Set up your Salareen Learner Check.</h1>
              <p>
                Confirms it’s you in accredited courses. Four look prompts, then one sentence out loud.
              </p>
              <ul className={styles.facts}>
                <li><b>Face check</b> Look left, right, up and down when the frame asks.</li>
                <li><b>Voice check</b> Read a short sentence for {VOICE_SECONDS} seconds.</li>
                <li><b>Private</b> We keep protected templates only, never the video, audio, or ID photo.</li>
              </ul>
              {minor && (
                <label className={styles.consent}>
                  <input
                    type="checkbox"
                    checked={guardianConsent}
                    onChange={(event) => setGuardianConsent(event.target.checked)}
                  />
                  I’m the parent or guardian, and I agree to this learner’s Salareen Learner Check.
                </label>
              )}
            </>
          )}
          {stage === "scan" && (
            <>
              <span className={styles.eyebrow}>Face check · {captured.length} of {targets.length}</span>
              <h1 id="learner-check-scan-heading" aria-live="polite">{problem ? "Let’s fix that." : hint}</h1>
              <p id="learner-check-scan-desc" className={styles.meshNote}>
                Checking distinctive features. Face map ready means the looks were captured and the lines followed your face. The map is a capture guide. It is not proof that nobody else could look similar. A dot, if one shows, is an optional note about a darker spot and is not saved.
              </p>
              <ol className={styles.targets} aria-label="Look prompts">
                {targets.map((pose) => (
                  <li
                    key={pose}
                    className={captured.includes(pose) ? styles.targetDone : pose === target ? styles.targetNow : ""}
                  >
                    <span aria-hidden="true">{captured.includes(pose) ? "✓" : POSE_ARROW[pose]}</span> {pose}
                  </li>
                ))}
              </ol>
              {lighting === "torch" && (
                <p className={styles.lightNote}>It’s a little dark, so we turned on your camera light.</p>
              )}
              {lighting === "screen" && (
                <p className={styles.lightNote}>
                  It’s a little dark, so the screen is glowing white to light your face. Turning up your
                  screen brightness helps too.
                </p>
              )}
            </>
          )}
          {stage === "voice" && (
            <>
              <span className={styles.eyebrow}>Voice check</span>
              <h1>{recording ? "Keep reading…" : busy ? "Saving your voice check…" : "Now read this out loud."}</h1>
              <blockquote className={styles.prompt}>{VOICE_PROMPT}</blockquote>
              <div className={styles.wave} role="progressbar" aria-label="Voice recording" aria-valuemin={0} aria-valuemax={VOICE_SECONDS} aria-valuenow={Math.round(elapsed)}>
                <svg viewBox={`0 0 ${WAVE_BARS * 10} 64`} preserveAspectRatio="none" aria-hidden="true">
                  {bars.map((level, index) => {
                    const height = Math.max(3, level * 60);
                    const filled = (index + 0.5) / WAVE_BARS <= progress;
                    return (
                      <rect
                        key={index}
                        x={index * 10 + 2}
                        y={32 - height / 2}
                        width={6}
                        height={height}
                        rx={3}
                        className={filled ? styles.barOn : styles.bar}
                      />
                    );
                  })}
                  {(recording || progress > 0) && (
                    <line className={styles.marker} x1={progress * WAVE_BARS * 10} x2={progress * WAVE_BARS * 10} y1={0} y2={64} />
                  )}
                </svg>
                <span className={styles.waveTime}>{Math.floor(elapsed)}s / {VOICE_SECONDS}s</span>
              </div>
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
              <span className={styles.eyebrow}>Salareen Learner Check is set up</span>
              <h1>You’re all set.</h1>
              <p>Review or remove it any time in Profile → Settings → Camera check.</p>
            </>
          )}

          {problem && (
            <p className={styles.error} role="alert" aria-live="assertive" data-kind={problem.kind}>{problem.message}</p>
          )}

          <p className={styles.footnote}>
            Games and general courses skip this. Accredited courses, such as driver’s ed, need it before the first full lesson.
          </p>
          <div className={styles.actions}>
            {stage === "intro" && (
              <>
                <button
                  className={styles.primary}
                  disabled={busy || (minor && !guardianConsent)}
                  onClick={() => void begin()}
                >Get started</button>
                {canSkip && (
                  <button className={styles.secondary} onClick={() => void skip()}>Set up later</button>
                )}
                {onBack && <button className={styles.ghost} onClick={onBack}>Back</button>}
                {hasEnrollment && !requireGovernmentId && (
                  <button className={styles.ghost} disabled={busy} onClick={() => void removeIdentity()}>
                    Remove saved check
                  </button>
                )}
              </>
            )}
            {stage === "scan" && (
              <>
                {problem && <button className={styles.primary} onClick={retryScan}>Try again</button>}
                {canSkip && (
                  <button className={styles.secondary} onClick={() => void skip()}>Set up later</button>
                )}
              </>
            )}
            {stage === "voice" && (
              <>
                <button className={styles.primary} disabled={busy} onClick={() => void recordVoice()}>
                  {recording
                    ? `Recording… ${Math.max(0, Math.ceil(VOICE_SECONDS - elapsed))}s`
                    : problem ? "Try again" : "Start recording"}
                </button>
                {canSkip && !busy && (
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
        </div>

        <div
          className={styles.frameWrap}
          role="region"
          aria-labelledby={stage === "scan" ? "learner-check-scan-heading" : undefined}
          aria-describedby={stage === "scan" ? "learner-check-scan-desc" : undefined}
        >
          <Image key={art} className={styles.paneArt} src={`/setup-assistant/${art}.webp`} alt="" fill sizes="50vw" />
          <div className={styles.frame} data-done={stage === "complete" || stage === "identity" ? "true" : undefined}>
            <span className={`${styles.corner} ${styles.cornerTL}`} aria-hidden="true" />
            <span className={`${styles.corner} ${styles.cornerTR}`} aria-hidden="true" />
            <span className={`${styles.corner} ${styles.cornerBL}`} aria-hidden="true" />
            <span className={`${styles.corner} ${styles.cornerBR}`} aria-hidden="true" />
            {stage === "scan" ? (
              <div className={styles.mirror}>
                <video
                  ref={videoRef}
                  className={styles.camera}
                  muted
                  playsInline
                  aria-label="Live camera feed for Learner Check face scan"
                  aria-describedby="learner-check-scan-desc"
                />
                {contour && scanning && (
                  <svg
                    className={styles.contour}
                    viewBox={`0 0 ${contour.frame[0]} ${contour.frame[1]}`}
                    preserveAspectRatio="xMidYMid slice"
                    aria-hidden="true"
                  >
                    <path className={styles.outline} d={svgPath(contour.shape.outline, true)} />
                    {contour.shape.grid.map((line, index) => (
                      <path key={`grid-${index}`} d={svgPath(line)} />
                    ))}
                    <path d={svgPath(contour.shape.rightEye, true)} />
                    <path d={svgPath(contour.shape.leftEye, true)} />
                    <path d={svgPath(contour.shape.nose)} />
                    <path d={svgPath(contour.shape.mouth, true)} />
                    {contour.marks.map((mark, index) => (
                      <circle
                        key={`${mark.region}-${index}`}
                        className={styles.mark}
                        data-region={mark.region}
                        cx={mark.point[0]}
                        cy={mark.point[1]}
                        r={Math.max(5, contour.frame[0] / 110)}
                      >
                        <title>{mark.region}</title>
                      </circle>
                    ))}
                  </svg>
                )}
              </div>
            ) : (
              <Image className={styles.frameArt} src={`/setup-assistant/${art}.webp`} alt="" fill sizes="420px" />
            )}
            {scanning && target && anchored && (
              <span className={styles.cue} data-pose={target} aria-hidden="true">{POSE_ARROW[target]}</span>
            )}
            {(stage === "complete" || stage === "identity") && (
              <div className={styles.check} aria-hidden="true">✓</div>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}
