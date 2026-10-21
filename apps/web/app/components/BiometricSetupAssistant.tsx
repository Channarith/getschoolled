"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import Image from "next/image";
import type { Expression } from "./mascot3d/expressions";
import {
  deleteBiometrics,
  enrollBiometricFace,
  enrollVoiceprint,
  getSetupAssistant,
  listStudents,
  setBiometricConsent,
  submitGovernmentId,
  submitOnboardingLearner,
  updateSetupAssistant,
} from "../lib/api";
import { createVisionEngine, type VisionEngine } from "../lib/vision";
import { isConsentMissing, isDeferredUpload } from "../lib/pendingUpload";
import { blobToBase64, dropPendingFace, flushPendingLearnerCheck, queuePendingFace, queuePendingVoice } from "../lib/pendingBiometrics";
import { createMockVisionEngine, learnerCheckMockEnabled } from "../lib/visionMock";
import {
  POSES,
  describeMediaError,
  faceContour,
  faceGeometry,
  cosineSimilarity,
  lightingAction,
  levelFromTimeDomain,
  meanLuma,
  pickRecorderMime,
  poseFromBaseline,
  shuffledPoses,
  svgPath,
  waveformBars,
  type Geometry,
  type LevelSample,
  type LightingAction,
  type MediaProblem,
  type Pose,
} from "../lib/learnerCheck";
import styles from "./BiometricSetupAssistant.module.css";

// MascotMeshy is a WebGL/Three.js component - load it client-only so
// the SSR pass of this screen stays fast and doesn't try to touch
// `window`/`document` on the server.
const MascotMeshy = dynamic(() => import("./MascotMeshy"), { ssr: false });

const VOICE_PROMPT =
  "Today I’m ready to learn with Salareen. Can you hear my voice clearly? Yes—I’m speaking naturally and confidently.";

const VOICE_SECONDS = 10;
const SAVE_TIMEOUT_MS = 12_000;

function withTimeout<T>(promise: Promise<T>, ms: number, label: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(
      () => reject(new Error(`${label} is taking too long. Continue, or try again.`)),
      ms,
    );
    promise.then(
      (value) => {
        window.clearTimeout(timer);
        resolve(value);
      },
      (reason) => {
        window.clearTimeout(timer);
        reject(reason);
      },
    );
  });
}
const WAVE_BARS = 60;
const LIGHT_CHECK_MS = 1200;
// 640×480 is enough for YuNet (it tracks a 320px image) and for the 112px
// face crop. A 960×1280 stream only added copy time.
const CAMERA_VIDEO: MediaTrackConstraints = {
  facingMode: "user",
  width: { ideal: 640 },
  height: { ideal: 480 },
  frameRate: { ideal: 30, max: 30 },
};
// Same-person turned heads land around 0.18–0.35. Stay above the server
// gate (0.18, or 0.22 on an identity process that has not restarted).
const POSE_MATCH_MIN = 0.24;

const POSE_COPY: Record<Pose, string> = {
  left: "Look to your left",
  right: "Look to your right",
  up: "Look up",
  down: "Look down",
};
const POSE_ARROW: Record<Pose, string> = { left: "←", right: "→", up: "↑", down: "↓" };

type Stage = "intro" | "scan" | "voice" | "identity" | "complete";

/**
 * Pick a mood for the mascot that matches what the user is doing right
 * now in the Learner Check. Keep these choices consistent with the
 * copy on each stage so the overall vibe reads correctly:
 *   - intro:    curious  (reading the explainer, deciding to start)
 *   - voice:    cute     (speaking the sentence, no judgment)
 *   - identity: serious  (uploading a government ID is a serious step)
 *   - complete: excited  (celebrate finishing)
 *   - scan:     unused   (we render the live camera instead)
 */
function mascotExpressionFor(stage: Stage): Expression {
  switch (stage) {
    case "intro":
      return "curious";
    case "voice":
      return "cute";
    case "identity":
      return "serious";
    case "complete":
      return "excited";
    default:
      return "cute";
  }
}
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
  if (/\b404\b|student not found|unknown student profile/i.test(message)) {
    return { kind: "save", message: "This learner profile is out of date. Go back to About you and continue again." };
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
  const [faceNote, setFaceNote] = useState<string | null>(null);
  const [faceStatus, setFaceStatus] = useState<"idle" | "saving" | "saved" | "queued" | "failed">("idle");
  const [voiceSaved, setVoiceSaved] = useState(false);
  const [voiceHeld, setVoiceHeld] = useState(false);
  const faceSavedRef = useRef(false);
  const voiceSavedRef = useRef(false);
  const [hint, setHint] = useState("Starting camera…");
  const [targets, setTargets] = useState<Pose[]>(() => [...POSES]);
  const [captured, setCaptured] = useState<Pose[]>([]);
  const [anchored, setAnchored] = useState(false);
  const [lighting, setLighting] = useState<LightingAction>("none");
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [bars, setBars] = useState<number[]>(() => Array(WAVE_BARS).fill(0));
  const [guardianConsent, setGuardianConsent] = useState(ageBand === "adult");
  const [idFile, setIdFile] = useState<File | null>(null);
  const [hasEnrollment, setHasEnrollment] = useState(false);
  const [mock, setMock] = useState(false);
  useEffect(() => setMock(learnerCheckMockEnabled()), []);
  const videoRef = useRef<HTMLVideoElement>(null);
  const contourSvgRef = useRef<SVGSVGElement>(null);
  const outlinePathRef = useRef<SVGPathElement>(null);
  const rightEyePathRef = useRef<SVGPathElement>(null);
  const leftEyePathRef = useRef<SVGPathElement>(null);
  const nosePathRef = useRef<SVGPathElement>(null);
  const mouthPathRef = useRef<SVGPathElement>(null);
  const gridPathRef = useRef<SVGPathElement>(null);
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
  // The page can hand us a learner id left in the browser by an earlier signup.
  // Face and voice consent then 404. Rebind to a learner this account owns.
  const activeStudentRef = useRef(studentId);
  useEffect(() => {
    activeStudentRef.current = studentId;
  }, [studentId]);

  const rememberStudent = useCallback((id: string) => {
    activeStudentRef.current = id;
    try {
      localStorage.setItem("onboarding_student_id", id);
    } catch {
      /* private mode */
    }
  }, []);

  const resolveStudent = useCallback(async (): Promise<string> => {
    const current = activeStudentRef.current;
    try {
      const listed = await listStudents();
      if (listed.students.some((student) => student.id === current)) return current;
      const fallback = listed.students[0]?.id;
      if (fallback) {
        rememberStudent(fallback);
        return fallback;
      }
      const name = localStorage.getItem("onboarding_learner_name")?.trim() || "";
      const age = Number(localStorage.getItem("onboarding_age"));
      if (name && age >= 3 && age <= 120) {
        const created = await submitOnboardingLearner({ learner_name: name, age });
        rememberStudent(created.student.id);
        return created.student.id;
      }
    } catch {
      /* The consent call reports the real failure. */
    }
    return current;
  }, [rememberStudent]);

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
    void flushPendingLearnerCheck();
  }, [studentId]);

  const resetScan = useCallback(() => {
    const order = shuffledPoses();
    faceSavedRef.current = false;
    setFaceStatus("idle");
    setFaceNote(null);
    scanRef.current = { neutral: null, base: null, order, poses: {}, enrolling: false };
    setTargets(order);
    setCaptured([]);
    setAnchored(false);
    if (contourSvgRef.current) contourSvgRef.current.style.visibility = "hidden";
    setElapsed(0);
  }, []);

  const faceSaveRef = useRef<Promise<boolean> | null>(null);
  const consentRef = useRef<Promise<string> | null>(null);
  const nextStage: Stage = requireGovernmentId ? "identity" : "complete";

  // The camera opens before this finishes. Waiting on identity first left the
  // camera light on over the intro screen whenever identity was slow.
  const ensureConsent = useCallback((): Promise<string> => {
    if (consentRef.current) return consentRef.current;
    const pending = (async () => {
      const body = {
        granted: true,
        guardian_granted: minor ? guardianConsent : false,
        retention_days: 365,
      };
      let id = await resolveStudent();
      try {
        await setBiometricConsent(id, body);
      } catch (reason) {
        const missing = /\b404\b|student not found|unknown student profile/i.test(String(reason));
        const name = localStorage.getItem("onboarding_learner_name")?.trim() || "";
        const age = Number(localStorage.getItem("onboarding_age"));
        if (!missing || !name || age < 3 || age > 120) throw reason;
        const created = await submitOnboardingLearner({ learner_name: name, age });
        id = created.student.id;
        rememberStudent(id);
        await setBiometricConsent(id, body);
      }
      // The face save only needs the consent grant. Waiting here for the
      // step update added another identity write before the learner could finish.
      void updateSetupAssistant(id, { current_step: "biometrics" }).catch(() => undefined);
      return id;
    })();
    consentRef.current = pending;
    pending.catch(() => {
      if (consentRef.current === pending) consentRef.current = null;
    });
    return pending;
  }, [guardianConsent, minor, rememberStudent, resolveStudent]);

  // Identity can answer "consent is required" right after it accepted the
  // consent, when the save reaches a server that has not read it yet. The
  // learner already agreed, so send the consent once more and retry.
  const sendWithConsent = useCallback(async (
    send: (id: string) => Promise<unknown>,
    label: string,
  ): Promise<string> => {
    let id = await withTimeout(ensureConsent(), SAVE_TIMEOUT_MS, "Saving consent");
    try {
      await withTimeout(send(id), SAVE_TIMEOUT_MS, label);
    } catch (reason) {
      if (!isConsentMissing(reason)) throw reason;
      consentRef.current = null;
      id = await withTimeout(ensureConsent(), SAVE_TIMEOUT_MS, "Saving consent");
      await withTimeout(send(id), SAVE_TIMEOUT_MS, label);
    }
    return id;
  }, [ensureConsent]);

  // The face save runs while the learner moves on to the voice check. Each
  // check is saved on its own, so a failed face save keeps the voice
  // recording and only the face has to be redone.
  const enrollFace = useCallback((): Promise<boolean> => {
    if (faceSavedRef.current) return Promise.resolve(true);
    if (faceSaveRef.current) return faceSaveRef.current;
    const scan = scanRef.current;
    if (!scan.neutral) return Promise.resolve(false);
    scan.enrolling = true;
    setHint("Face map ready");
    stopMedia();
    setLighting("none");
    setFaceStatus("saving");
    setFaceNote(null);
    setStage("voice");
    const pending = (async () => {
      const vectors = [scan.neutral as number[], ...scan.order.map((pose) => scan.poses[pose] as number[])];
      let id = activeStudentRef.current;
      try {
        id = await sendWithConsent((learner) => enrollBiometricFace(learner, vectors, scan.order), "Saving the face check");
        faceSavedRef.current = true;
        setFaceStatus("saved");
        setFaceNote(null);
        if (voiceSavedRef.current) setStage(nextStage);
        return true;
      } catch (reason) {
        if (isDeferredUpload(reason)) {
          try {
            await queuePendingFace(id, vectors, scan.order, {
              granted: true,
              guardianGranted: minor ? guardianConsent : false,
            });
            faceSavedRef.current = true;
            setFaceStatus("queued");
            setFaceNote("Saved on this computer. We’ll send your face check when you’re connected.");
            if (voiceSavedRef.current) setStage(nextStage);
            return true;
          } catch (keepReason) {
            setFaceStatus("failed");
            setFaceNote(`Couldn’t save your face check: ${String((keepReason as Error)?.message ?? keepReason)}`);
            return false;
          }
        }
        setFaceStatus("failed");
        setFaceNote(`Couldn’t save your face check: ${String((reason as Error)?.message ?? reason)}`);
        return false;
      } finally {
        scan.enrolling = false;
        faceSaveRef.current = null;
      }
    })();
    faceSaveRef.current = pending;
    return pending;
  }, [guardianConsent, minor, nextStage, sendWithConsent, stopMedia]);

  // Look-target scan: track head direction from the live landmarks and keep
  // one embedding per target, in a fresh random order each attempt.
  useEffect(() => {
    if (stage !== "scan") return;
    let cancelled = false;
    let clock = 0;
    let processing = false;
    let lastLightCheck = 0;
    let torchOn = false;
    let screenLight = false;
    const probe = document.createElement("canvas");
    probe.width = 48;
    probe.height = 64;
    let locking = false;
    let retryAt = 0;
    let raf = 0;

    function stillFrame(video: HTMLVideoElement): HTMLCanvasElement | null {
      const width = video.videoWidth;
      const height = video.videoHeight;
      if (!width || !height) return null;
      const still = document.createElement("canvas");
      still.width = width;
      still.height = height;
      const ctx = still.getContext("2d", { willReadFrequently: true });
      if (!ctx) return null;
      ctx.drawImage(video, 0, 0, width, height);
      return still;
    }

    function hideLiveContour() {
      const svg = contourSvgRef.current;
      if (svg) svg.style.visibility = "hidden";
    }

    function showLiveContour(
      shape: ReturnType<typeof faceContour>,
      frame: [number, number],
      bbox: number[] | undefined,
    ) {
      const svg = contourSvgRef.current;
      if (!svg) return;
      svg.setAttribute("viewBox", `0 0 ${frame[0]} ${frame[1]}`);
      svg.style.visibility = "visible";
      if (!shape && bbox) {
        const [x, y, width, height] = bbox;
        const cx = x + width / 2;
        const cy = y + height / 2;
        outlinePathRef.current?.setAttribute(
          "d",
          `M ${cx} ${y} C ${x + width * 0.06} ${y + height * 0.18}, ${x} ${y + height * 0.72}, ${cx} ${y + height} C ${x + width} ${y + height * 0.72}, ${x + width * 0.94} ${y + height * 0.18}, ${cx} ${y} Z`,
        );
        rightEyePathRef.current?.setAttribute("d", "");
        leftEyePathRef.current?.setAttribute("d", "");
        nosePathRef.current?.setAttribute("d", "");
        mouthPathRef.current?.setAttribute("d", "");
        gridPathRef.current?.setAttribute("d", "");
        return;
      }
      if (!shape) return;
      outlinePathRef.current?.setAttribute("d", svgPath(shape.outline, true));
      rightEyePathRef.current?.setAttribute("d", svgPath(shape.rightEye, true));
      leftEyePathRef.current?.setAttribute("d", svgPath(shape.leftEye, true));
      nosePathRef.current?.setAttribute("d", svgPath(shape.nose));
      mouthPathRef.current?.setAttribute("d", svgPath(shape.mouth));
      gridPathRef.current?.setAttribute("d", shape.grid.map((line) => svgPath(line)).join(" "));
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
            video: CAMERA_VIDEO,
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
        engineRef.current ??= mock ? createMockVisionEngine() : await createVisionEngine();
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
      setHint("Center your face in the circle.");
      const started = performance.now();
      clock = window.setInterval(() => setElapsed((performance.now() - started) / 1000), 250);
      const loop = () => {
        if (cancelled) return;
        const startedAt = performance.now();
        tick();
        const elapsed = performance.now() - startedAt;
        raf = window.setTimeout(loop, Math.max(16, 40 - elapsed));
      };
      raf = window.setTimeout(loop, 0);
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
        const faces = engine.detect(video);
        if (faces.length !== 1) {
          hideLiveContour();
          setHint(faces.length ? "Only one face, please." : "Center your face in the circle.");
          return;
        }
        const face = faces[0];
        const frame = (face.frame_size ?? [video.videoWidth, video.videoHeight]) as [number, number];
        const shape = faceContour(face.landmarks, 32, face.bbox);
        showLiveContour(shape, frame, face.bbox);
        if (!shape || !face.landmarks) return;
        const landmarks = face.landmarks;
        const geometry = faceGeometry(face.landmarks ?? [], face.bbox ?? [0, 0, frame[0], frame[1]], frame);
        if (!geometry) return;
        if (!scan.base) {
          if (!geometry.centered) {
            setHint("Center your face in the circle.");
            return;
          }
          if (locking) return;
          locking = true;
          const geometryNow = geometry;
          const marks = landmarks.map((point) => [point[0], point[1]]);
          const still = stillFrame(video);
          window.setTimeout(() => {
            if (cancelled) return;
            try {
              const vector = still ? engine.embedAt(still, marks) : null;
              locking = false;
              if (!vector?.length || scan.base) return;
              scan.base = geometryNow;
              scan.neutral = vector;
              setAnchored(true);
              setHint(`Checking distinctive features. ${POSE_COPY[scan.order[0]]}`);
            } catch {
              locking = false;
            }
          }, 0);
          return;
        }
        const target = scan.order.find((pose) => scan.poses[pose] == null);
        if (!target || locking || now < retryAt) return;
        const pose = poseFromBaseline(scan.base, geometry);
        if (pose !== target) {
          setHint(POSE_COPY[target]);
          return;
        }
        locking = true;
        const poseTarget = target;
        const marks = landmarks.map((point) => [point[0], point[1]]);
        const still = stillFrame(video);
        window.setTimeout(() => {
          if (cancelled) return;
          try {
            const vector = still && scan.neutral ? engine.embedAt(still, marks) : null;
            const score = vector && scan.neutral ? cosineSimilarity(scan.neutral, vector) : 0;
            if (!vector?.length || score < POSE_MATCH_MIN) {
              locking = false;
              retryAt = performance.now() + 450;
              setHint(`${POSE_COPY[poseTarget]}. Ease back a little and hold.`);
              return;
            }
            scan.poses[poseTarget] = vector;
            setCaptured(scan.order.filter((item) => (scan.poses[item]?.length ?? 0) > 0));
            locking = false;
            const next = scan.order.find((item) => !(scan.poses[item]?.length));
            if (next) setHint(`Checking distinctive features. ${POSE_COPY[next]}`);
            else void enrollFace();
          } catch {
            locking = false;
          }
        }, 0);
      } finally {
        processing = false;
      }
    }

    void start();
    return () => {
      cancelled = true;
      window.clearTimeout(raf);
      window.clearInterval(clock);
      stopMedia();
    };
  }, [attempt, enrollFace, mock, resetScan, stage, stopMedia]);

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
      let finishRecording: (blob: Blob) => void = () => undefined;
      const finished = new Promise<Blob>((resolve) => {
        finishRecording = resolve;
      });
      const clipType = () => recorder.mimeType || mimeType || "audio/mp4";
      recorder.onerror = () => finishRecording(new Blob(chunks, { type: clipType() }));
      recorder.onstop = () => finishRecording(new Blob(chunks, { type: clipType() }));
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
      // Safari often never fires onstop unless data is requested, which left
      // the page on "Saving your voice check…" with no buttons.
      const stopTimer = window.setTimeout(
        () => finishRecording(new Blob(chunks, { type: clipType() })),
        2000,
      );
      if (recorder.state !== "inactive") {
        try { recorder.requestData(); } catch { /* not supported on every browser */ }
        recorder.stop();
      } else {
        finishRecording(new Blob(chunks, { type: clipType() }));
      }
      let blob: Blob | null = await finished;
      window.clearTimeout(stopTimer);
      chunks = [];
      cancelAnimationFrame(frame);
      setElapsed(VOICE_SECONDS);
      setRecording(false);
      stopMedia();
      if (!blob.size) throw new Error("silent");
      try {
        const clip = blob;
        await sendWithConsent((learner) => enrollVoiceprint(learner, clip), "Saving the voice check");
        voiceSavedRef.current = true;
        setVoiceHeld(false);
        setVoiceSaved(true);
        if (faceSavedRef.current) setStage(nextStage);
      } catch (reason) {
        if (!blob || !isDeferredUpload(reason)) throw reason;
        await queuePendingVoice(
          activeStudentRef.current,
          { mime: blob.type || "audio/webm", base64: await blobToBase64(blob) },
          { granted: true, guardianGranted: minor ? guardianConsent : false },
        );
        voiceSavedRef.current = true;
        setVoiceHeld(true);
        setVoiceSaved(true);
        setProblem(null);
        setFaceNote((current) => current ?? "Saved on this computer. We’ll send your voice check when you’re connected.");
        if (faceSavedRef.current) setStage(nextStage);
      } finally {
        blob = null;
      }
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

  function begin() {
    setProblem(null);
    // Start the camera prompt in this tap. Waiting on the network first makes
    // phones show Allow and then ignore the tap.
    const cameraPromise = navigator.mediaDevices?.getUserMedia?.({
      video: CAMERA_VIDEO,
      audio: false,
    });
    pendingCameraRef.current = cameraPromise ?? null;
    cameraPromise?.catch(() => undefined);
    setStage("scan");
  }

  async function submitId() {
    if (!idFile) return;
    setBusy(true);
    setProblem(null);
    try {
      const result = await submitGovernmentId(await resolveStudent(), "government_id", idFile);
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

  function finish() {
    // The learner can move on while this flag is saved. Waiting on identity
    // held the last step for as long as that write took.
    void updateSetupAssistant(activeStudentRef.current, { current_step: "complete", complete: true }).catch(() => undefined);
    onComplete?.();
  }

  function skip() {
    stopMedia();
    void updateSetupAssistant(activeStudentRef.current, {
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
      await deleteBiometrics(await resolveStudent());
      setHasEnrollment(false);
    } catch (reason) {
      setProblem({ kind: "save", message: String((reason as Error)?.message ?? reason) });
    } finally {
      setBusy(false);
    }
  }

  function openCamera() {
    const cameraPromise = navigator.mediaDevices?.getUserMedia?.({
      video: CAMERA_VIDEO,
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

  function redoFace() {
    setProblem(null);
    setFaceNote(null);
    setFaceStatus("idle");
    faceSavedRef.current = false;
    void dropPendingFace(activeStudentRef.current);
    openCamera();
    setStage("scan");
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
        {mock && <span className={styles.mockBadge} data-testid="learner-check-mock">Mock face data</span>}
        <nav className={styles.steps} aria-label="Learner Check steps">
          <span data-state={stage === "intro" || stage === "scan" ? "now" : "done"}>Face</span>
          <span data-state={stage === "voice" ? "now" : stage === "identity" || stage === "complete" ? "done" : "next"}>Voice</span>
        </nav>
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
                <li><b>Private</b> This device reads your face and voice first. We send the check when you’re connected, and we don’t keep the video.</li>
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
              <span className={styles.eyebrow}>Voice check · {VOICE_SECONDS} seconds</span>
              <h1>
                {recording ? "Keep reading…"
                  : busy ? "Saving your voice check…"
                  : voiceSaved && faceStatus === "saving" ? "Saving your face check…"
                  : voiceSaved && voiceHeld ? "Voice check saved on this device."
                  : voiceSaved ? "Voice check saved."
                  : "Voice check"}
              </h1>
              <ul className={styles.status} aria-label="Learner Check progress">
                <li data-state={faceStatus} data-testid="face-status">
                  Face check: {faceStatus === "saved" ? "saved" : faceStatus === "queued" ? "saved on this device" : faceStatus === "failed" ? "not saved" : "saving…"}
                </li>
                <li data-state={voiceSaved ? (voiceHeld ? "queued" : "saved") : "idle"} data-testid="voice-status">
                  Voice check: {voiceSaved ? (voiceHeld ? "saved on this device" : "saved") : "not recorded yet"}
                </li>
              </ul>
              {!voiceSaved && <p>Read this sentence out loud. The bars move when your microphone hears you.</p>}
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

          {faceNote && stage === "voice" && (
            <p className={faceStatus === "failed" ? styles.error : styles.lightNote} role={faceStatus === "failed" ? "alert" : "status"} aria-live={faceStatus === "failed" ? "assertive" : "polite"}>{faceNote}</p>
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
                  onClick={begin}
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
                {faceStatus === "failed" && !recording && !busy && (
                  <button className={voiceSaved ? styles.primary : styles.secondary} onClick={redoFace}>
                    Redo face check
                  </button>
                )}
                {!voiceSaved && (
                  <button className={styles.primary} disabled={busy} onClick={() => void recordVoice()}>
                    {recording
                      ? `Recording… ${Math.max(0, Math.ceil(VOICE_SECONDS - elapsed))}s`
                      : problem ? "Try the voice check again" : "Start voice check"}
                  </button>
                )}
                {voiceSaved && (
                  <button className={styles.primary} onClick={() => setStage(nextStage)}>Continue</button>
                )}
                {canSkip && (
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
          {/* The pane backdrop illustration only reads correctly during the
              live camera scan stage - on the other stages we're rendering
              the animated mascot in the frame and the static art behind it
              would compete visually. Scan stage keeps the backdrop. */}
          {stage === "scan" && (
            <Image key={art} className={styles.paneArt} src={`/setup-assistant/${art}.webp`} alt="" fill sizes="50vw" />
          )}
          <div className={styles.frame} data-done={stage === "complete" || stage === "identity" ? "true" : undefined}>
            <span className={`${styles.corner} ${styles.cornerTL}`} aria-hidden="true" />
            <span className={`${styles.corner} ${styles.cornerTR}`} aria-hidden="true" />
            <span className={`${styles.corner} ${styles.cornerBL}`} aria-hidden="true" />
            <span className={`${styles.corner} ${styles.cornerBR}`} aria-hidden="true" />
            <div className={styles.mirror} style={stage === "scan" ? undefined : { display: "none" }}>
                <video
                  ref={videoRef}
                  className={styles.camera}
                  autoPlay
                  muted
                  playsInline
                  aria-label="Live camera feed for Learner Check face scan"
                  aria-describedby="learner-check-scan-desc"
                />
                <div
                  className={styles.faceGuide}
                  data-locked={anchored ? "true" : "false"}
                  aria-hidden="true"
                />
                <svg
                  ref={contourSvgRef}
                  className={styles.contour}
                  preserveAspectRatio="xMidYMid slice"
                  style={{ visibility: "hidden" }}
                  aria-hidden="true"
                >
                  <path ref={outlinePathRef} className={styles.outline} />
                  <path ref={rightEyePathRef} className={styles.feature} />
                  <path ref={leftEyePathRef} className={styles.feature} />
                  <path ref={nosePathRef} className={styles.feature} />
                  <path ref={mouthPathRef} className={styles.feature} />
                  <path ref={gridPathRef} className={styles.grid} />
                </svg>
              </div>
              <div
                className={styles.mascotStage}
                style={stage === "scan" ? { visibility: "hidden", pointerEvents: "none" } : undefined}
                aria-hidden={stage === "scan"}
              >
                <MascotMeshy
                  expression={mascotExpressionFor(stage)}
                  motion="idle"
                  idleRotation
                  fill
                  backdrop="#071422"
                  holdStone
                  paused={stage === "scan"}
                />
              </div>
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
