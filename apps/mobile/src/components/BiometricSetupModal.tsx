import { Audio } from "expo-av";
import * as FileSystem from "expo-file-system";
import { Camera } from "expo-camera";
import * as ImagePicker from "expo-image-picker";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Linking,
  Modal,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Svg, { Circle, Line, Path, Rect } from "react-native-svg";

import {
  completeMobileSetup,
  deleteMobileBiometrics,
  enrollMobileFaceImages,
  enrollMobileVoiceprint,
  getMobileSetupState,
  setMobileBiometricConsent,
  submitMobileGovernmentId,
} from "../api";
import {
  SETUP_COLORS as C,
  faceContour,
  faceGeometry,
  faceMarksFromJpeg,
  meteringToLevel,
  poseFromBaseline,
  shuffledPoses,
  svgPath,
  waveformBars,
  type FaceContour,
  type FaceMark,
  type Geometry,
  type LevelSample,
  type Pose,
} from "../learnerCheck";
import { detectDeviceFaces, faceDistanceCue, isOnDeviceReaderMissing, type DeviceStroke } from "../deviceFace";
import { isDeferredUpload } from "../pendingUpload";
import {
  flushPendingLearnerCheck,
  queuePendingFace,
  queuePendingVoice,
  rememberPendingConsent,
} from "../pendingBiometrics";
import AnimatedPressable from "./AnimatedPressable";
import KenBurnsImage from "./KenBurnsImage";
import LiveFaceCamera, { type LiveFaceCameraHandle } from "./LiveFaceCamera";
import MobileMascotMeshy from "./MobileMascotMeshy";
import { useLayoutMetrics } from "../layout";

type Step = "welcome" | "scan" | "voice" | "identity" | "complete";
const STEPS: Step[] = ["welcome", "scan", "voice", "identity", "complete"];
const PROMPT =
  "Today I’m ready to learn with Salareen. Can you hear my voice clearly? Yes—I’m speaking naturally and confidently.";
const VOICE_SECONDS = 10;
const WAVE_BARS = 40;

const POSE_COPY: Record<Pose, string> = {
  left: "Look to your left",
  right: "Look to your right",
  up: "Look up",
  down: "Look down",
};
const POSE_ARROW: Record<Pose, string> = { left: "←", right: "→", up: "↑", down: "↓" };

const ART = {
  face: require("../../assets/setup-assistant/face-scan.webp"),
  voice: require("../../assets/setup-assistant/voice.webp"),
};

const copy: Record<Step, { kicker: string; title: string; body: string }> = {
  welcome: {
    kicker: "Optional · about 1 minute",
    title: "Set up your Salareen Learner Check.",
    body: "It helps us know it’s really you in accredited courses. This phone reads your face and your voice. Turn when the frame asks, then read one sentence out loud. We send that check when you’re connected.",
  },
  scan: {
    kicker: "Face check",
    title: "Look straight at the camera.",
    body: "This phone reads your face. Turn when the arrow asks. The lines follow you on the device. We send the check when you’re connected.",
  },
  voice: {
    kicker: "Voice check",
    title: "Now read this out loud.",
    body: "Speak naturally for 10 seconds. The recording stays on this phone until the voice check is sent.",
  },
  identity: {
    kicker: "Accredited course · Government ID",
    title: "One last check.",
    body: "Courses that lead to a certificate or license need a government ID match. The image is checked once and discarded.",
  },
  complete: {
    kicker: "Salareen Learner Check is set up",
    title: "You’re all set.",
    body: "Review or remove it any time in Profile → Settings → Camera check.",
  },
};

type Shot = {
  base64: string;
  contour: FaceContour | null;
  strokes: DeviceStroke[];
  frame: [number, number];
  /**
   * Overlay rings for this preview only. Coordinates are not enrolled.
   */
  marks: FaceMark[];
};

export type LiveFrameCode = "anchor" | "keep" | "none" | "one" | "center" | "turn";

/** What to do with one live frame. Sideways looks accept either mirror direction. */
export function liveFrameAction(
  faceCount: number,
  centered: boolean,
  hasAnchor: boolean,
  target: Pose | null,
  seen: Pose | null,
  otherSideways: Pose | null,
): LiveFrameCode {
  if (faceCount > 1) return "one";
  if (faceCount !== 1) return "none";
  if (!hasAnchor) return centered ? "anchor" : "center";
  if (!target) return "center";
  return stillMatchesTarget(target, seen, otherSideways) ? "keep" : "turn";
}

type Problem = { message: string; settings?: boolean };

async function discardFile(uri: string | null | undefined) {
  if (!uri) return;
  await FileSystem.deleteAsync(uri, { idempotent: true }).catch(() => undefined);
}

export function faceEnrollmentProblem(reason: unknown): Problem {
  const status = (reason as { status?: number })?.status;
  const message = String((reason as Error)?.message ?? reason).replace(/^Error:\s*/, "");
  if (status === 422) {
    return { message: message || "Those photos did not pass the face check. Follow each look prompt and try again." };
  }
  if (status === 503 || status === 502) {
    const detail = message && !/unavailable/i.test(message) ? ` ${message}` : "";
    return { message: `The face check service is unavailable.${detail} Try again in a minute.` };
  }
  return { message: message || "Could not save your face check. Try again." };
}

/**
 * Identity of one JPEG still. The first bytes are the JFIF header, which is
 * the same for every photo from this camera, so a prefix compare treated every
 * later look (up, right, down, left) as a duplicate of the neutral portrait
 * and the contour never moved. Sample the compressed scan instead.
 */
export function stillFingerprint(base64: string): string {
  const length = base64.length;
  if (length < 180) return base64;
  const mid = Math.floor(length / 2);
  return `${length}:${base64.slice(mid, mid + 64)}:${base64.slice(-64)}`;
}

function voiceProblem(reason: unknown): Problem {
  const status = (reason as { status?: number })?.status;
  const message = String((reason as Error)?.message ?? reason);
  if (status === 503 || status === 502) {
    const detail = message.replace(/^Error:\s*/, "");
    const extra = detail && !/unavailable/i.test(detail) ? ` ${detail}` : "";
    return { message: `The voice check isn’t available right now.${extra} Try again in a minute, or set it up later.` };
  }
  if (/silent|too quiet/i.test(message)) return { message: "We couldn’t hear you. Hold the phone closer and read the sentence out loud." };
  if (/clipped/i.test(message)) return { message: "That was too loud. Hold the phone a little farther away and try again." };
  if (/between 8 and 15|too short|decoded/i.test(message)) {
    return { message: "The recording didn’t come through in full. Try again and keep reading until the bar fills." };
  }
  return { message: `Couldn’t save your voice check: ${message.replace(/^Error:\s*/, "")}` };
}

/** On a still we can’t know if the camera mirrored the photo, so left/right only
 *  has to be a clear sideways turn (opposite to the other sideways shot). */
export function stillMatchesTarget(target: Pose, seen: Pose | null, otherSideways: Pose | null): boolean {
  if (!seen) return false;
  const sideways = (pose: Pose) => pose === "left" || pose === "right";
  if (!sideways(target)) return seen === target;
  return sideways(seen) && seen !== otherSideways;
}

function Waveform({ bars, progress }: { bars: number[]; progress: number }) {
  const width = bars.length * 10;
  return (
    <Svg width="100%" height={64} viewBox={`0 0 ${width} 64`} preserveAspectRatio="none">
      {bars.map((level, index) => {
        const height = Math.max(3, level * 60);
        const filled = (index + 0.5) / bars.length <= progress;
        return (
          <Rect
            key={index}
            x={index * 10 + 2}
            y={32 - height / 2}
            width={6}
            height={height}
            rx={3}
            fill={filled ? C.accent : C.border}
          />
        );
      })}
      {progress > 0 ? (
        <Line x1={progress * width} x2={progress * width} y1={0} y2={64} stroke={C.warm} strokeWidth={2.5} />
      ) : null}
    </Svg>
  );
}

type Props = {
  visible: boolean;
  studentId: string;
  ageBand?: string;
  requireGovernmentId?: boolean;
  stepLabel?: string;
  onDismiss: () => void;
  onComplete?: () => void;
};

export default function BiometricSetupModal({
  visible,
  studentId,
  ageBand = "adult",
  requireGovernmentId = false,
  stepLabel,
  onDismiss,
  onComplete,
}: Props) {
  const [step, setStep] = useState<Step>("welcome");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [guardian, setGuardian] = useState(ageBand === "adult");
  const [order, setOrder] = useState<Pose[]>(() => shuffledPoses());
  const [shots, setShots] = useState<Shot[]>([]);
  const [contourNote, setContourNote] = useState("");
  const [pendingNote, setPendingNote] = useState("");
  const [scanHint, setScanHint] = useState("Center your face in the circle.");
  const [liveContour, setLiveContour] = useState<Shot | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [bars, setBars] = useState<number[]>(() => Array(WAVE_BARS).fill(0));
  const [hasEnrollment, setHasEnrollment] = useState(false);
  // The setup screen is its own window. Android and iOS draw the system
  // "Allow" prompt behind that window, so the button is visible but dead.
  // Hide this window before asking, and bring it back after the prompt closes.
  const [systemPrompt, setSystemPrompt] = useState(false);
  const recordingRef = useRef<Audio.Recording | null>(null);
  const baseRef = useRef<Geometry | null>(null);
  const seenRef = useRef<Partial<Record<Pose, Pose>>>({});
  const minor = ageBand !== "adult";
  const canSkip = !requireGovernmentId;
  const consentRef = useRef<Promise<void> | null>(null);

  // Face and voice uploads wait for consent. Sent on its own, a slow consent
  // landed after the face upload and identity refused it with 409.
  function ensureConsent(): Promise<void> {
    if (!consentRef.current) {
      const pending = setMobileBiometricConsent(studentId, true, minor ? guardian : false)
        .then(() => undefined);
      consentRef.current = pending;
      pending.catch(() => {
        if (consentRef.current === pending) consentRef.current = null;
      });
    }
    return consentRef.current;
  }

  useEffect(() => {
    if (!visible) return;
    consentRef.current = null;
    void flushPendingLearnerCheck();
    getMobileSetupState(studentId).then((state) => {
      setHasEnrollment(
        state.portrait.status === "verified"
        || state.voice.status === "verified"
        || state.government_id.status === "verified",
      );
    }).catch(() => undefined);
  }, [studentId, visible]);

  const stopRecording = useCallback(async () => {
    const active = recordingRef.current;
    recordingRef.current = null;
    if (!active) return;
    try {
      const status = await active.getStatusAsync();
      if (status.isRecording) await active.stopAndUnloadAsync();
    } catch { /* best-effort cleanup */ }
    await discardFile(active.getURI());
  }, []);

  const shotsRef = useRef<Shot[]>([]);
  shotsRef.current = shots;
  const orderRef = useRef(order);
  orderRef.current = order;
  const cameraRef = useRef<LiveFaceCameraHandle>(null);
  const readyRef = useRef(false);
  const savingRef = useRef(false);
  const genRef = useRef(0);
  useEffect(() => () => {
    void stopRecording();
  }, [stopRecording]);

  async function withBusy(action: () => Promise<void>) {
    setBusy(true);
    setProblem(null);
    try {
      await action();
    } catch (reason) {
      setProblem({ message: String((reason as Error)?.message ?? reason).replace(/^Error:\s*/, "") });
    } finally {
      setBusy(false);
    }
  }

  function resetScan() {
    genRef.current += 1;
    shotsRef.current = [];
    setShots([]);
    setLiveContour(null);
    setOrder(shuffledPoses());
    setContourNote("");
    setPendingNote("");
    setScanHint("Center your face in the circle.");
    baseRef.current = null;
    seenRef.current = {};
    savingRef.current = false;
  }

  async function begin() {
    setBusy(true);
    setProblem(null);
    try {
      const permission = await outsideTheSetupWindow(() => Camera.requestCameraPermissionsAsync());
      if (!permission.granted) {
        setProblem({
          message: "Camera access is off for Salareen. Allow the camera in Settings, then try again.",
          settings: !permission.canAskAgain,
        });
        return;
      }
      const guardianGranted = minor ? guardian : false;
      await rememberPendingConsent(studentId, guardianGranted).catch(() => undefined);
      consentRef.current = null;
      void ensureConsent().catch(() => undefined);
      resetScan();
      readyRef.current = false;
      setStep("scan");
    } finally {
      setBusy(false);
    }
  }

  async function outsideTheSetupWindow<T>(action: () => Promise<T>): Promise<T> {
    setSystemPrompt(true);
    await new Promise<void>((resolve) => {
      setTimeout(() => resolve(), 450);
    });
    try {
      return await action();
    } finally {
      setSystemPrompt(false);
    }
  }

  async function takePhoto(front: boolean): Promise<ImagePicker.ImagePickerAsset | null> {
    return outsideTheSetupWindow(async () => {
      const permission = await ImagePicker.requestCameraPermissionsAsync();
      if (!permission.granted) {
        setProblem({
          message: "Camera access is off for Salareen. Allow the camera in Settings, then try again.",
          settings: !permission.canAskAgain,
        });
        return null;
      }
      const result = await ImagePicker.launchCameraAsync({
        cameraType: front ? ImagePicker.CameraType.front : ImagePicker.CameraType.back,
        base64: true,
        quality: 0.6,
        allowsEditing: false,
        exif: false,
      });
      if (result.canceled) return null;
      return result.assets[0] ?? null;
    });
  }

  function noteHint(next: string) {
    setScanHint((prev) => (prev === next ? prev : next));
  }

  useEffect(() => {
    if (!visible || step !== "scan") return;
    let cancelled = false;
    const wait = (ms: number) => new Promise<void>((resolve) => {
      setTimeout(resolve, ms);
    });

    const run = async () => {
      const started = Date.now();
      while (!cancelled && !readyRef.current) {
        if (Date.now() - started > 8000) {
          setProblem({ message: "The camera didn’t start. Close other apps using the camera and try again." });
          return;
        }
        await wait(80);
      }
      let misses = 0;
      const saveTimeout = <T,>(promise: Promise<T>, ms: number) => new Promise<T>((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error("Saving the face check is taking too long.")), ms);
        promise.then(
          (value) => { clearTimeout(timer); resolve(value); },
          (reason) => { clearTimeout(timer); reject(reason); },
        );
      });
      while (!cancelled) {
        if (savingRef.current) return;
        // The on-device reader needs a still file. Space the samples so the shutter is not a burst.
        await wait(700);
        if (cancelled) return;
        const seenGen = genRef.current;
        const frameShot = await cameraRef.current?.grabFrame({ retainFile: true, includeBase64: false });
        if (cancelled || genRef.current !== seenGen) {
          await discardFile(frameShot?.uri);
          continue;
        }
        if (!frameShot?.uri) {
          await wait(160);
          continue;
        }
        let faces: Awaited<ReturnType<typeof detectDeviceFaces>> = [];
        try {
          faces = await detectDeviceFaces(frameShot.uri);
        } catch (reason) {
          await discardFile(frameShot.uri);
          if (cancelled) return;
          if (isOnDeviceReaderMissing(reason)) {
            setProblem({
              message: "This app doesn’t include the on-device face reader yet. Rebuild the app, then the face check runs on this phone.",
            });
            return;
          }
          misses += 1;
          if (misses === 6) setContourNote("Still reading the camera on this device.");
          await wait(160);
          continue;
        }
        if (cancelled || genRef.current !== seenGen) {
          await discardFile(frameShot.uri);
          continue;
        }
        misses = 0;
        const face = faces.length === 1 ? faces[0] : null;
        const frame: [number, number] = [frameShot.width || 3, frameShot.height || 4];
        const geometry = face?.landmarks ? faceGeometry(face.landmarks, face.bbox, frame) : null;
        const target = shotsRef.current.length === 0 ? null : orderRef.current[shotsRef.current.length - 1] ?? null;
        const seen = geometry && baseRef.current ? poseFromBaseline(baseRef.current, geometry) : null;
        const otherSideways = target === "left" ? seenRef.current.right ?? null
          : target === "right" ? seenRef.current.left ?? null : null;
        const action = liveFrameAction(
          faces.length,
          Boolean(geometry?.centered),
          Boolean(baseRef.current),
          target,
          seen,
          otherSideways,
        );
        const preview: Shot | null = face ? {
          base64: "",
          contour: face.landmarks ? faceContour(face.landmarks, face.bbox) : null,
          strokes: face.strokes,
          frame,
          marks: [],
        } : null;
        if (preview && action !== "one") setLiveContour(preview);
        else if (action === "none" || action === "one") setLiveContour(null);
        if (face?.smiling != null && face.smiling > 0.7 && !baseRef.current) setContourNote("Smile seen.");
        if (!baseRef.current && face) {
          const cue = faceDistanceCue(face.faceWidth, Math.max(frame[0], frame[1]));
          if (cue !== "ok") {
            noteHint(cue === "closer" ? "Move a little closer." : "Move back a little.");
            await discardFile(frameShot.uri);
            await wait(180);
            continue;
          }
        }
        if (action === "none") {
          noteHint("Center your face in the circle.");
          await discardFile(frameShot.uri);
          await wait(180);
          continue;
        }
        if (action === "one") {
          noteHint("Only one face, please.");
          await discardFile(frameShot.uri);
          await wait(180);
          continue;
        }
        if (action === "center") {
          noteHint("Center your face in the circle.");
          await discardFile(frameShot.uri);
          await wait(180);
          continue;
        }
        if (action === "turn") {
          if (target) noteHint(POSE_COPY[target]);
          await discardFile(frameShot.uri);
          await wait(120);
          continue;
        }
        if (!face?.landmarks || !geometry) {
          await discardFile(frameShot.uri);
          continue;
        }
        let base64 = "";
        try {
          base64 = await FileSystem.readAsStringAsync(frameShot.uri, { encoding: FileSystem.EncodingType.Base64 });
        } catch {
          base64 = "";
        }
        await discardFile(frameShot.uri);
        if (!base64) continue;
        if (shotsRef.current.some((shot) => stillFingerprint(shot.base64) === stillFingerprint(base64))) {
          await wait(120);
          continue;
        }
        const marks = faceMarksFromJpeg(base64, face.landmarks, frame, face.bbox);
        const kept: Shot = {
          base64,
          contour: faceContour(face.landmarks, face.bbox),
          strokes: face.strokes,
          frame,
          marks,
        };
        if (action === "anchor") {
          baseRef.current = geometry;
          noteHint(POSE_COPY[orderRef.current[0]]);
        } else if (target && seen) {
          seenRef.current[target] = seen;
          const nextPose = orderRef.current[shotsRef.current.length];
          if (nextPose) noteHint(POSE_COPY[nextPose]);
        }
        const next = [...shotsRef.current, kept];
        shotsRef.current = next;
        setShots(next);
        setLiveContour(kept);
        if (next.length < orderRef.current.length + 1) continue;
        savingRef.current = true;
        noteHint("Saving your face check…");
        setBusy(true);
        const images = next.map((shot) => shot.base64);
        const poses = orderRef.current;
        const moveOn = () => {
          setShots([]);
          shotsRef.current = [];
          setLiveContour(null);
          setStep("voice");
        };
        try {
          await saveTimeout(
            ensureConsent().then(() => enrollMobileFaceImages(studentId, images, poses)),
            12000,
          );
          if (cancelled) return;
          moveOn();
        } catch (reason) {
          if (isDeferredUpload(reason)) {
            try {
              await queuePendingFace(studentId, images, poses, {
                granted: true,
                guardianGranted: minor ? guardian : false,
              });
              setPendingNote("Saved on this phone. We’ll send your face check when you’re connected.");
              if (!cancelled) moveOn();
            } catch (keepReason) {
              resetScan();
              setProblem({ message: String((keepReason as Error)?.message ?? keepReason) });
            }
          } else {
            resetScan();
            setProblem(faceEnrollmentProblem(reason));
          }
        } finally {
          savingRef.current = false;
          setBusy(false);
        }
        return;
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [visible, step, attempt, studentId]);

  async function recordVoice() {
    setBusy(true);
    setProblem(null);
    setElapsed(0);
    setBars(Array(WAVE_BARS).fill(0));
    let uri: string | null = null;
    try {
      const permission = await outsideTheSetupWindow(() => Audio.requestPermissionsAsync());
      if (!permission.granted) {
        setProblem({
          message: "Microphone access is off for Salareen. Allow the microphone in Settings, then try again.",
          settings: !permission.canAskAgain,
        });
        return;
      }
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
        staysActiveInBackground: false,
        shouldDuckAndroid: true,
        playThroughEarpieceAndroid: false,
      });
      const samples: LevelSample[] = [];
      // AAC in an m4a container on both platforms. The voice service decodes
      // that with ffmpeg; a 3gp/AMR clip from an Android default is easier to lose.
      const { recording: active } = await Audio.Recording.createAsync(
        {
          isMeteringEnabled: true,
          android: {
            extension: ".m4a",
            outputFormat: Audio.AndroidOutputFormat.MPEG_4,
            audioEncoder: Audio.AndroidAudioEncoder.AAC,
            sampleRate: 44100,
            numberOfChannels: 1,
            bitRate: 128000,
          },
          ios: {
            extension: ".m4a",
            outputFormat: Audio.IOSOutputFormat.MPEG4AAC,
            audioQuality: Audio.IOSAudioQuality.HIGH,
            sampleRate: 44100,
            numberOfChannels: 1,
            bitRate: 128000,
          },
          web: { mimeType: "audio/webm", bitsPerSecond: 128000 },
        },
        (status) => {
          if (!status.isRecording) return;
          const t = status.durationMillis / 1000;
          // Some Android devices report no metering; keep a low "listening" bar.
          samples.push({ t, level: status.metering == null ? 0.12 : meteringToLevel(status.metering) });
          setBars(waveformBars(samples, VOICE_SECONDS, WAVE_BARS));
          setElapsed(Math.min(VOICE_SECONDS, t));
        },
        100,
      );
      recordingRef.current = active;
      setRecording(true);
      await new Promise<void>((resolve) => setTimeout(() => resolve(), VOICE_SECONDS * 1000 + 200));
      await active.stopAndUnloadAsync();
      recordingRef.current = null;
      setRecording(false);
      setElapsed(VOICE_SECONDS);
      uri = active.getURI();
      if (!uri) throw new Error("No audio was recorded");
      const base64 = await FileSystem.readAsStringAsync(uri, { encoding: FileSystem.EncodingType.Base64 });
      const recordedUri = uri;
      try {
        await ensureConsent();
        await enrollMobileVoiceprint(studentId, base64);
        await discardFile(recordedUri);
        uri = null;
        setStep(requireGovernmentId ? "identity" : "complete");
      } catch (reason) {
        if (!isDeferredUpload(reason)) {
          await discardFile(recordedUri);
          uri = null;
          throw reason;
        }
        await queuePendingVoice(studentId, recordedUri, {
          granted: true,
          guardianGranted: minor ? guardian : false,
        });
        await discardFile(recordedUri);
        uri = null;
        setPendingNote((current) => (
          current
            ? "Saved on this phone. We’ll send your face and voice checks when you’re connected."
            : "Saved on this phone. We’ll send your voice check when you’re connected."
        ));
        setStep(requireGovernmentId ? "identity" : "complete");
      }
    } catch (reason) {
      setProblem(voiceProblem(reason));
    } finally {
      await stopRecording();
      await discardFile(uri);
      await Audio.setAudioModeAsync({ allowsRecordingIOS: false }).catch(() => undefined);
      setRecording(false);
      setBusy(false);
    }
  }

  async function document() {
    await withBusy(async () => {
      const asset = await takePhoto(false);
      if (!asset?.base64) return;
      try {
        const result = await submitMobileGovernmentId(studentId, asset.base64);
        if (result.status !== "verified") {
          throw new Error("The portrait on this ID did not match. Use a clear, well-lit image and try again.");
        }
      } finally {
        await discardFile(asset.uri);
      }
      setStep("complete");
    });
  }

  async function finish(skipped = false) {
    await withBusy(async () => {
      await stopRecording();
      resetScan();
      try {
        await completeMobileSetup(studentId, skipped);
      } catch (reason) {
        if (!isDeferredUpload(reason)) throw reason;
      }
      onComplete?.();
      onDismiss();
    });
  }

  async function removeIdentity() {
    await withBusy(async () => {
      await deleteMobileBiometrics(studentId);
      setHasEnrollment(false);
    });
  }

  const text = copy[step];
  const target = step === "scan" && shots.length > 0 ? order[shots.length - 1] : null;
  const title = step === "scan"
    ? scanHint
    : step === "voice" && recording ? "Keep reading…" : text.title;
  const done = step === "identity" || step === "complete";
  const progress = STEPS.indexOf(step);
  const latest = liveContour;
  const { isMedium, isExpanded } = useLayoutMetrics();
  const wide = isMedium || isExpanded;
  const scanning = step === "scan";
  const [frameBox, setFrameBox] = useState({ width: 0, height: 0 });

  return (
    <Modal visible={visible && !systemPrompt} animationType="fade" presentationStyle="fullScreen" onRequestClose={onDismiss}>
      <SafeAreaView style={styles.root} edges={["top", "left", "right", "bottom"]}>
        <View style={styles.header}>
          <Text style={styles.brand}>Salareen</Text>
          <View style={styles.bars}>
            {STEPS.slice(0, -1).map((item, index) => (
              <View key={item} style={[styles.bar, index <= progress && styles.barActive]} />
            ))}
          </View>
          {stepLabel ? <Text style={styles.stepLabel}>{stepLabel}</Text> : null}
        </View>
        <View style={[styles.split, !wide && styles.splitStack, scanning && styles.scanSplit]}>
          <View style={[styles.artPane, !wide && step !== "scan" && styles.artBand, scanning && styles.scanArtFull]}>
            {!scanning ? <KenBurnsImage source={step === "voice" ? ART.voice : ART.face} style={StyleSheet.absoluteFill} /> : null}
            <View
              style={scanning ? styles.frameFill : styles.frame}
              onLayout={(event) => {
                const next = {
                  width: Math.round(event.nativeEvent.layout.width),
                  height: Math.round(event.nativeEvent.layout.height),
                };
                setFrameBox((current) => (
                  current.width === next.width && current.height === next.height ? current : next
                ));
              }}
            >
            {step === "scan" ? (
              <>
                <View style={styles.cameraClip} collapsable={false}>
                  <LiveFaceCamera
                    key={attempt}
                    ref={cameraRef}
                    style={styles.cameraLayer}
                    onReady={() => { readyRef.current = true; }}
                    onError={(message) => setProblem({ message })}
                  />
                </View>
                <View style={styles.overlay} pointerEvents="none" collapsable={false}>
                <View style={styles.faceGuideWrap}>
                  <View
                    style={[styles.faceGuide, latest?.contour || latest?.strokes.length ? styles.faceGuideOn : null]}
                    testID="face-guide"
                  />
                </View>
                <View style={styles.liveDot} accessibilityLabel="Live camera" />
                {(latest?.strokes.length || latest?.contour) && frameBox.width > 0 ? (
                  <Svg
                    style={styles.mesh}
                    width={frameBox.width}
                    height={frameBox.height}
                    viewBox={`0 0 ${latest.frame[0]} ${latest.frame[1]}`}
                    preserveAspectRatio="xMidYMid slice"
                    pointerEvents="none"
                    testID="face-contour"
                  >
                    {latest.strokes.length > 0 ? latest.strokes.map((stroke, index) => (
                      <Path
                        key={`stroke-${index}`}
                        d={svgPath(stroke.points, stroke.closed)}
                        fill="none"
                        stroke={index === 0 ? "#f4fcff" : "#d7f4ff"}
                        strokeWidth={Math.max(index === 0 ? 1.75 : 1.15, latest.frame[0] / (index === 0 ? 220 : 340))}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    )) : latest.contour ? (
                      <>
                    <Path
                      d={svgPath(latest.contour.outline, true)}
                      fill="none"
                      stroke="#f4fcff"
                      strokeWidth={Math.max(1.75, latest.frame[0] / 220)}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                    {latest.contour.grid.map((line, index) => (
                      <Path
                        key={`grid-${index}`}
                        d={svgPath(line)}
                        fill="none"
                        stroke="#d7f4ff"
                        strokeWidth={Math.max(1.15, latest.frame[0] / 340)}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    ))}
                    {[latest.contour.rightEye, latest.contour.leftEye, latest.contour.mouth].map((line, index) => (
                      <Path
                        key={`feat-${index}`}
                        d={svgPath(line, true)}
                        fill="none"
                        stroke="#d7f4ff"
                        strokeWidth={Math.max(1.15, latest.frame[0] / 340)}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    ))}
                    <Path
                      d={svgPath(latest.contour.nose)}
                      fill="none"
                      stroke="#d7f4ff"
                      strokeWidth={Math.max(1.15, latest.frame[0] / 340)}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                      </>
                    ) : null}
                    {latest.marks.map((mark, index) => (
                      <Circle
                        key={`${mark.region}-${index}`}
                        cx={mark.point[0]}
                        cy={mark.point[1]}
                        r={Math.max(5, latest.frame[0] / 110)}
                        fill="none"
                        stroke="#ffe3a3"
                        strokeWidth={Math.max(1.5, latest.frame[0] / 280)}
                      />
                    ))}
                  </Svg>
                ) : null}
                {!target ? (
                  <View style={styles.straight}>
                    <Text style={styles.straightText}>Look straight</Text>
                  </View>
                ) : null}
                </View>
              </>
            ) : (
              <>
                <KenBurnsImage key={step === "voice" ? "voice" : "face"} source={step === "voice" ? ART.voice : ART.face} duration={16} />
                <MobileMascotMeshy
                  scene={
                    step === "voice" ? { kind: "tutoring" }
                      : step === "complete" ? { kind: "dance" }
                        : { kind: "idle" }
                  }
                  style={StyleSheet.absoluteFill}
                />
              </>
            )}
            {scanning ? null : (["TL", "TR", "BL", "BR"] as const).map((corner) => (
              <View key={corner} style={[styles.corner, styles[`corner${corner}`], done && styles.cornerDone]} />
            ))}
            {done ? <Text style={styles.check}>✓</Text> : null}
          </View>
          </View>
          <View style={[styles.pane, scanning && styles.scanHud]} pointerEvents={scanning ? "box-none" : "auto"}>
          <ScrollView
            style={scanning ? undefined : styles.paneScroll}
            contentContainerStyle={[styles.contentInner, wide && styles.contentCenter, scanning && styles.scanContent]}
            scrollEnabled={!scanning}
          >
          {scanning ? (
            <View style={styles.poseRow}>
              {order.map((pose, index) => {
                const captured = shots.length > index + 1;
                const now = pose === target;
                return (
                  <View key={pose} style={[styles.poseChip, styles.poseChipOnCamera, now && styles.poseChipNowGlass, captured && styles.poseChipDoneGlass]}>
                    <Text style={[styles.poseChipText, styles.poseChipTextOnCamera, now && styles.poseChipTextNow, captured && styles.poseChipTextOn]}>
                      {captured ? "✓" : POSE_ARROW[pose]} {pose}
                    </Text>
                  </View>
                );
              })}
            </View>
          ) : null}
          <Text style={[styles.kicker, scanning && styles.scanKicker]}>{text.kicker}{step === "scan" ? ` · ${Math.max(0, shots.length - 1)} of ${order.length}` : ""}</Text>
          <Text style={[styles.title, scanning && styles.scanTitle]}>{title}</Text>
          <Text style={[styles.body, scanning && styles.scanBody]}>{text.body}</Text>
          {step === "scan" && latest?.contour ? (
            <Text style={styles.small}>
              Face map ready. The lines are a capture guide. A dot, if one shows, is an optional note about a darker spot. It is not saved, and it is not the identity check.
            </Text>
          ) : null}
          {contourNote ? <Text style={[styles.small, scanning && styles.scanBody]}>{contourNote}</Text> : null}
          {pendingNote ? <Text style={[styles.small, scanning && styles.scanBody]}>{pendingNote}</Text> : null}
          {step === "voice" ? (
            <>
              <Text style={styles.prompt}>{PROMPT}</Text>
              <View style={styles.wave} accessibilityRole="progressbar" accessibilityLabel="Voice recording" accessibilityValue={{ min: 0, max: VOICE_SECONDS, now: Math.round(elapsed) }}>
                <Waveform bars={bars} progress={Math.min(1, elapsed / VOICE_SECONDS)} />
                <Text style={styles.waveTime}>{Math.floor(elapsed)}s / {VOICE_SECONDS}s</Text>
              </View>
            </>
          ) : null}
          {step === "welcome" && minor ? (
            <View style={styles.guardian}>
              <Text style={styles.guardianText}>I’m the parent or guardian, and I agree to this learner’s Salareen Learner Check.</Text>
              <Switch value={guardian} onValueChange={setGuardian} trackColor={{ true: C.accent, false: C.border }} />
            </View>
          ) : null}
          {problem ? <Text style={styles.error} accessibilityRole="alert">{problem.message}</Text> : null}
          {busy && !recording ? <ActivityIndicator color={C.accent} style={styles.spinner} /> : null}
          {!scanning ? (
            <Text style={styles.note}>
              Games and general courses skip this. Accredited courses need it before the first full lesson.
            </Text>
          ) : null}
          </ScrollView>
          <View style={[styles.actions, scanning && styles.scanActions]} pointerEvents="auto">
            {problem?.settings ? (
              <Action title="Open Settings" onPress={() => void Linking.openSettings()} />
            ) : null}
            {step === "welcome" ? (
              <>
                <Action title="Get started" disabled={busy || (minor && !guardian)} onPress={() => void begin()} />
                {canSkip ? <Action title="Set up later" secondary onPress={() => void finish(true)} /> : null}
                {hasEnrollment && canSkip ? (
                  <Action title="Remove saved check" secondary disabled={busy} onPress={() => void removeIdentity()} />
                ) : null}
              </>
            ) : null}
            {step === "scan" ? (
              <>
                {shots.length > 0 ? <Action title="Start over" secondary glass disabled={busy} onPress={resetScan} /> : null}
                {problem ? (
                  <Action title="Try again" glass disabled={busy} onPress={() => { setProblem(null); readyRef.current = false; setAttempt((n) => n + 1); }} />
                ) : null}
                {canSkip ? <Action title="Set up later" secondary glass disabled={busy} onPress={() => void finish(true)} /> : null}
              </>
            ) : null}
            {step === "voice" ? (
              <>
                <Action
                  title={recording ? `Recording… ${Math.max(0, Math.ceil(VOICE_SECONDS - elapsed))}s` : problem ? "Try again" : "Start recording"}
                  disabled={busy}
                  onPress={() => void recordVoice()}
                />
                {canSkip && !busy ? <Action title="Set up later" secondary onPress={() => void finish(true)} /> : null}
              </>
            ) : null}
            {step === "identity" ? (
              <>
                <Action title="Photograph ID securely" disabled={busy} onPress={() => void document()} />
                {canSkip ? <Action title="Not now" secondary onPress={() => setStep("complete")} /> : null}
              </>
            ) : null}
            {step === "complete" ? <Action title="Continue" disabled={busy} onPress={() => void finish()} /> : null}
          </View>
          </View>
        </View>
      </SafeAreaView>
    </Modal>
  );
}

function Action({ title, onPress, secondary = false, disabled = false, glass = false }: {
  title: string; onPress: () => void; secondary?: boolean; disabled?: boolean; glass?: boolean;
}) {
  return (
    <AnimatedPressable
      onPress={onPress}
      disabled={disabled}
      style={[
        styles.button,
        secondary && styles.buttonSecondary,
        glass && (secondary ? styles.buttonGlassSecondary : styles.buttonGlass),
        disabled && styles.disabled,
      ]}
    >
      <Text style={[styles.buttonText, secondary && !glass && styles.buttonTextSecondary]}>{title}</Text>
    </AnimatedPressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.panel },
  header: {
    flexDirection: "row", alignItems: "center", gap: 12,
    paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: C.border, backgroundColor: C.bg,
  },
  brand: { color: C.text, fontSize: 17, fontWeight: "800" },
  split: { flex: 1, flexDirection: "row", minHeight: 0 },
  splitStack: { flexDirection: "column" },
  scanSplit: { position: "relative" },
  artPane: { flex: 1.15, minWidth: 0, alignItems: "center", justifyContent: "center", backgroundColor: C.panel2, overflow: "hidden" },
  artBand: { flex: 0, width: "100%", height: "34%" },
  scanArtFull: { ...StyleSheet.absoluteFillObject, flex: 0, width: "100%", height: "100%" },
  pane: { flex: 1, minWidth: 0, minHeight: 0, backgroundColor: C.panel },
  paneScroll: { flex: 1 },
  contentInner: { flexGrow: 1, padding: 20, gap: 8 },
  contentCenter: { justifyContent: "center" },
  bars: { flex: 1, flexDirection: "row", gap: 6, maxWidth: 220 },
  bar: { height: 4, flex: 1, borderRadius: 4, backgroundColor: C.border },
  barActive: { backgroundColor: C.accent },
  stepLabel: { color: C.muted, fontSize: 13, fontWeight: "600" },
  frame: {
    width: "72%", maxWidth: 420, aspectRatio: 3 / 4, maxHeight: "86%",
    borderRadius: 16, overflow: "hidden", backgroundColor: "#111111", borderWidth: 1, borderColor: C.border,
  },
  frameFill: {
    ...StyleSheet.absoluteFillObject,
    borderRadius: 0, overflow: "hidden", backgroundColor: "#111111",
  },
  scanHud: {
    position: "absolute", left: 0, right: 0, bottom: 0, zIndex: 20, elevation: 20,
    backgroundColor: "rgba(8, 16, 28, 0.22)",
    borderTopLeftRadius: 22, borderTopRightRadius: 22,
  },
  scanContent: { flexGrow: 0, paddingTop: 12, paddingBottom: 0, gap: 4 },
  scanKicker: { color: "#9ee7df", marginTop: 0 },
  scanTitle: { color: "#ffffff", fontSize: 26, lineHeight: 30, marginTop: 2 },
  scanBody: { color: "#e7eef8", marginTop: 4 },
  scanActions: { borderTopWidth: 0, backgroundColor: "transparent", paddingTop: 4 },
  cameraClip: { ...StyleSheet.absoluteFillObject, zIndex: 0, elevation: 0, overflow: "hidden" },
  cameraLayer: { zIndex: 0, elevation: 0 },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 8,
    elevation: 8,
    backgroundColor: "transparent",
  },
  faceGuideWrap: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center",
    justifyContent: "center",
    paddingBottom: "16%",
    zIndex: 5,
  },
  faceGuide: {
    width: "72%",
    maxWidth: 420,
    aspectRatio: 1,
    borderRadius: 999,
    borderWidth: 4,
    borderColor: "rgba(255,255,255,0.96)",
    backgroundColor: "transparent",
  },
  faceGuideOn: { borderColor: "#b6ffcf" },
  mesh: { position: "absolute", top: 0, left: 0, zIndex: 6, elevation: 6 },
  corner: { position: "absolute", width: 28, height: 28, borderColor: C.teal, zIndex: 12, elevation: 12 },
  cornerTL: { top: 14, left: 14, borderTopWidth: 4, borderLeftWidth: 4, borderTopLeftRadius: 16 },
  cornerTR: { top: 14, right: 14, borderTopWidth: 4, borderRightWidth: 4, borderTopRightRadius: 16 },
  cornerBL: { bottom: 14, left: 14, borderBottomWidth: 4, borderLeftWidth: 4, borderBottomLeftRadius: 16 },
  cornerBR: { bottom: 14, right: 14, borderBottomWidth: 4, borderRightWidth: 4, borderBottomRightRadius: 16 },
  cornerDone: { borderColor: C.accent },
  liveDot: {
    position: "absolute", top: 18, right: 18, width: 12, height: 12, borderRadius: 6,
    backgroundColor: "#ff4d4f", borderWidth: 2, borderColor: "#ffffff", zIndex: 6, elevation: 6,
  },
  cueAnchor: { position: "absolute", zIndex: 6, elevation: 6 },
  cue: {
    minWidth: 64, minHeight: 48, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 16,
    alignItems: "center", justifyContent: "center",
  },
  cueOn: { backgroundColor: "rgba(47, 107, 216, 0.42)" },
  cueIdle: { backgroundColor: "rgba(15, 23, 42, 0.28)", borderWidth: 1, borderColor: "rgba(255,255,255,0.8)" },
  cueText: { color: "#ffffff", fontSize: 18, fontWeight: "800", lineHeight: 20 },
  cueLabel: { color: "#ffffff", fontSize: 11, fontWeight: "800", textTransform: "capitalize", lineHeight: 13 },
  cue_left: { left: 8, top: "38%" },
  cue_right: { right: 8, top: "38%" },
  cue_up: { top: 28, left: 0, right: 0, alignItems: "center" },
  cue_down: { bottom: "34%", left: 0, right: 0, alignItems: "center" },
  straight: {
    position: "absolute", top: "44%", left: 0, right: 0, alignItems: "center", zIndex: 5, elevation: 5,
  },
  straightText: {
    color: "#ffffff", fontSize: 15, fontWeight: "800", backgroundColor: "rgba(15, 23, 42, 0.28)",
    overflow: "hidden", borderRadius: 12, paddingHorizontal: 12, paddingVertical: 6,
  },
  poseRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, justifyContent: "center", paddingHorizontal: 12, paddingTop: 8 },
  poseChip: {
    minHeight: 36, borderRadius: 12, paddingHorizontal: 10, alignItems: "center", justifyContent: "center",
    backgroundColor: C.panel, borderWidth: 1, borderColor: C.border,
  },
  poseChipOnCamera: { backgroundColor: "rgba(15, 23, 42, 0.22)", borderColor: "rgba(255,255,255,0.72)" },
  poseChipNowGlass: { backgroundColor: "rgba(47, 107, 216, 0.38)", borderColor: "rgba(255,255,255,0.9)" },
  poseChipDoneGlass: { backgroundColor: "rgba(15, 157, 143, 0.4)", borderColor: "rgba(255,255,255,0.72)" },
  poseChipTextOnCamera: { color: "#ffffff" },
  poseChipNow: { borderColor: C.accent, backgroundColor: C.panel },
  poseChipDone: { backgroundColor: C.teal, borderColor: C.teal },
  poseChipText: { color: C.text, fontWeight: "800", textTransform: "capitalize" },
  poseChipTextNow: { color: C.accent },
  poseChipTextOn: { color: "#ffffff" },
  check: {
    ...StyleSheet.absoluteFillObject, textAlign: "center", textAlignVertical: "center",
    lineHeight: 300, fontSize: 96, fontWeight: "800", color: "#ffffff", backgroundColor: "rgba(15,157,143,.55)",
  },
  targets: { flexDirection: "row", flexWrap: "wrap", gap: 8, justifyContent: "center", marginBottom: 8 },
  target: {
    minWidth: 72, minHeight: 40, textAlign: "center", textAlignVertical: "center", lineHeight: 38,
    color: C.muted, backgroundColor: C.panel, borderWidth: 1, borderColor: C.border, borderRadius: 12,
    paddingHorizontal: 10, overflow: "hidden", textTransform: "capitalize", fontWeight: "700",
  },
  targetNow: { color: C.accent, borderColor: C.accent },
  targetDone: { color: "#ffffff", backgroundColor: C.teal, borderColor: C.teal },
  kicker: { color: C.teal, fontSize: 12, fontWeight: "800", letterSpacing: 1.2, textTransform: "uppercase", marginTop: 8 },
  title: { color: C.text, fontSize: 30, lineHeight: 34, fontWeight: "900", letterSpacing: -0.8, marginTop: 8 },
  body: { color: C.muted, fontSize: 16, lineHeight: 23, marginTop: 10 },
  small: { color: C.muted, fontSize: 13, lineHeight: 18, marginTop: 8 },
  prompt: {
    color: C.text, fontSize: 18, lineHeight: 26, fontWeight: "600", marginTop: 16, padding: 16, borderRadius: 14,
    backgroundColor: C.panel2, borderLeftWidth: 4, borderLeftColor: C.accent,
  },
  wave: {
    marginTop: 14, paddingHorizontal: 12, paddingTop: 10, paddingBottom: 26, borderRadius: 14,
    backgroundColor: C.panel, borderWidth: 1, borderColor: C.border,
  },
  waveTime: { position: "absolute", right: 12, bottom: 6, fontSize: 12, fontWeight: "700", color: C.muted },
  guardian: {
    flexDirection: "row", alignItems: "center", gap: 12, marginTop: 16, padding: 14, borderRadius: 14,
    backgroundColor: C.panel, borderWidth: 1, borderColor: C.border,
  },
  guardianText: { color: C.text, flex: 1, lineHeight: 20 },
  error: {
    color: C.danger, marginTop: 16, padding: 12, borderRadius: 12, overflow: "hidden",
    backgroundColor: C.dangerSoft, borderWidth: 1, borderColor: "#fecaca",
  },
  spinner: { marginTop: 18 },
  actions: {
    gap: 8, paddingHorizontal: 16, paddingTop: 12, paddingBottom: 16,
    borderTopWidth: 1, borderTopColor: C.border, backgroundColor: C.panel,
  },
  button: { backgroundColor: C.accent, borderRadius: 12, minHeight: 52, alignItems: "center", justifyContent: "center", paddingHorizontal: 22 },
  buttonSecondary: { backgroundColor: C.panel, borderWidth: 1, borderColor: C.border },
  buttonGlass: { backgroundColor: "rgba(47, 107, 216, 0.42)", borderWidth: 1, borderColor: "rgba(255,255,255,0.55)" },
  buttonGlassSecondary: { backgroundColor: "rgba(255, 255, 255, 0.22)", borderWidth: 1, borderColor: "rgba(255,255,255,0.7)" },
  buttonText: { color: "#ffffff", fontSize: 16, fontWeight: "800" },
  buttonTextSecondary: { color: C.text },
  disabled: { opacity: .45 },
  note: { color: C.muted, fontSize: 12, lineHeight: 18, marginTop: 22 },
});
