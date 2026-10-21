import { Audio } from "expo-av";
import * as FileSystem from "expo-file-system";
import { Camera } from "expo-camera";
import * as ImagePicker from "expo-image-picker";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Image,
  Linking,
  Modal,
  Platform,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Svg, { Line, Path, Rect } from "react-native-svg";

import {
  completeMobileSetup,
  deleteMobileBiometrics,
  enrollMobileFaceQuick,
  enrollMobileVoiceprint,
  getMobileSetupState,
  setMobileBiometricConsent,
  submitMobileGovernmentId,
} from "../api";
import {
  SETUP_COLORS as C,
  isSilentTake,
  meteringToLevel,
  svgPath,
  waveformBars,
  withTimeout,
  type LevelSample,
} from "../learnerCheck";
import {
  FRAME_HINT,
  detectDeviceFaces,
  frameForFaces,
  frameVerdict,
  isOnDeviceReaderMissing,
  scanDiagnostics,
  scanFailureMessage,
  type DeviceStroke,
  type ScanStats,
  type VerdictCounts,
} from "../deviceFace";
import { isConsentMissing, isDeferredUpload } from "../pendingUpload";
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
import ScanRing from "./ScanRing";
import { useLayoutMetrics } from "../layout";

type Step = "welcome" | "scan" | "voice" | "identity" | "complete";
const STEPS: Step[] = ["welcome", "scan", "voice", "identity", "complete"];
const PROMPT =
  "Today I’m ready to learn with Salareen. Can you hear my voice clearly? Yes—I’m speaking naturally and confidently.";
const VOICE_SECONDS = 10;
const WAVE_BARS = 40;

/** Straight-on stills per face check. Identity needs five for an ID match. */
export const FACE_PHOTOS = 5;
/** Give up on one round after this long without five good stills. */
const SCAN_LIMIT_MS = 20_000;
/** A save slower than this waits on the phone and sends when identity answers. */
export const SAVE_TIMEOUT_MS = 15_000;
/** Camera restarts allowed after a still never came back. */
const MAX_CAMERA_STALLS = 2;

type FaceState = "idle" | "saving" | "saved" | "queued" | "failed";

const ART = {
  face: require("../../assets/setup-assistant/face-scan.webp"),
  voice: require("../../assets/setup-assistant/voice.webp"),
};

const copy: Record<Step, { kicker: string; title: string; body: string }> = {
  welcome: {
    kicker: "Optional · about 1 minute",
    title: "Set up your Salareen Learner Check.",
    body: "It helps us know it’s really you in accredited courses. The camera stays live, the outline follows your face, then you read one sentence out loud.",
  },
  scan: {
    kicker: "Face check",
    title: "Look at the camera.",
    body: "Hold the phone at eye level. The outline follows your face on this live camera. Nothing is saved as a photo.",
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

type Problem = { message: string; settings?: boolean; detail?: string };

/** Size of the still as the learner sees it (turned upright). Falls back to what the camera reported. */
async function uprightSize(uri: string, fallback: [number, number]): Promise<[number, number]> {
  try {
    return await withTimeout(new Promise<[number, number]>((resolve, reject) => {
      Image.getSize(uri, (width, height) => resolve([width, height]), reject);
    }), 1500, "Reading the picture size timed out.");
  } catch {
    return fallback;
  }
}

async function discardFile(uri: string | null | undefined) {
  if (!uri) return;
  await FileSystem.deleteAsync(uri, { idempotent: true }).catch(() => undefined);
}

export function faceEnrollmentProblem(reason: unknown): Problem {
  const status = (reason as { status?: number })?.status;
  const message = String((reason as Error)?.message ?? reason).replace(/^Error:\s*/, "");
  if (status === 422) {
    return { message: message || "Those photos did not pass the face check. Hold the phone at eye level in good light and try again." };
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
  const [captured, setCaptured] = useState(0);
  const [faceSeen, setFaceSeen] = useState(false);
  const [liveStrokes, setLiveStrokes] = useState<{ strokes: DeviceStroke[]; frame: [number, number] } | null>(null);
  const [pendingNote, setPendingNote] = useState("");
  const [scanHint, setScanHint] = useState("Look at the camera.");
  const [attempt, setAttempt] = useState(0);
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [bars, setBars] = useState<number[]>(() => Array(WAVE_BARS).fill(0));
  const [hasEnrollment, setHasEnrollment] = useState(false);
  const [faceState, setFaceStateValue] = useState<FaceState>("idle");
  const [faceNote, setFaceNote] = useState("");
  const [voiceDone, setVoiceDone] = useState(false);
  // The setup screen is its own window. Android and iOS draw the system
  // "Allow" prompt behind that window, so the button is visible but dead.
  // Hide this window before asking, and bring it back after the prompt closes.
  const [systemPrompt, setSystemPrompt] = useState(false);
  const recordingRef = useRef<Audio.Recording | null>(null);
  const minor = ageBand !== "adult";
  const canSkip = !requireGovernmentId;
  const consentRef = useRef<Promise<void> | null>(null);
  const faceStateRef = useRef<FaceState>("idle");
  const faceSaveRef = useRef<Promise<boolean> | null>(null);
  const voiceDoneRef = useRef(false);
  const stallsRef = useRef(0);

  function setFaceState(next: FaceState) {
    faceStateRef.current = next;
    setFaceStateValue(next);
  }

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

  // Identity can say "consent is required" right after it took the consent,
  // when the upload reaches a server that has not read it yet. The learner
  // already agreed, so send the consent once more and retry the upload.
  async function sendWithConsent(send: () => Promise<unknown>): Promise<void> {
    try {
      await ensureConsent();
    } catch (reason) {
      // A dropped consent call is not a refusal. Ask once more before giving up.
      if (!isDeferredUpload(reason)) throw reason;
      consentRef.current = null;
      await ensureConsent();
    }
    try {
      await send();
    } catch (reason) {
      if (!isConsentMissing(reason)) throw reason;
      consentRef.current = null;
      await ensureConsent();
      await send();
    }
  }

  useEffect(() => {
    if (!visible) return;
    consentRef.current = null;
    faceSaveRef.current = null;
    voiceDoneRef.current = false;
    setVoiceDone(false);
    setFaceState("idle");
    setFaceNote("");
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

  const cameraRef = useRef<LiveFaceCameraHandle>(null);
  const readyRef = useRef(false);
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
    setCaptured(0);
    setFaceSeen(false);
    setLiveStrokes(null);
    setPendingNote("");
    setScanHint("Look at the camera.");
  }

  async function begin() {
    setBusy(true);
    setProblem(null);
    try {
      // Ask for the microphone here too, so the voice step never has to hide
      // this screen for a system prompt in the middle of recording.
      const [camera, microphone] = await Promise.all([
        Camera.getCameraPermissionsAsync(),
        Audio.getPermissionsAsync().catch(() => null),
      ]);
      let permission = camera;
      if (!camera.granted || (microphone && !microphone.granted && microphone.canAskAgain)) {
        permission = await outsideTheSetupWindow(async () => {
          const asked = camera.granted ? camera : await Camera.requestCameraPermissionsAsync();
          if (asked.granted && microphone && !microphone.granted && microphone.canAskAgain) {
            await Audio.requestPermissionsAsync().catch(() => undefined);
          }
          return asked;
        });
      }
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
      stallsRef.current = 0;
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

  // Face check: keep five quick straight-on stills from the live preview.
  // The phone checks each one (one face, centered, close enough, looking at
  // the camera, eyes open) and drops the rest, so there is nothing to follow.
  useEffect(() => {
    if (!visible || step !== "scan") return;
    let cancelled = false;
    const wait = (ms: number) => new Promise<void>((resolve) => {
      setTimeout(resolve, ms);
    });
    const run = async () => {
      const opened = Date.now();
      while (!cancelled && !readyRef.current) {
        if (Date.now() - opened > 8000) {
          setProblem({ message: "The camera didn’t start. Close other apps using the camera and try again." });
          return;
        }
        await wait(80);
      }
      // Let exposure and focus settle before the first still.
      await wait(250);
      const gen = genRef.current;
      const kept: string[] = [];
      const prints = new Set<string>();
      const started = Date.now();
      let readFailures = 0;
      const seen: VerdictCounts = {};
      let upright: [number, number] | null = null;
      let emptyStreak = 0;
      const stats: ScanStats = {
        grabbed: 0, grabMissed: 0, faceFrames: 0, emptyFrames: 0, readFailures: 0,
        size: null, upright: null, lastGrabError: "", lastReadError: "",
      };
      const detail = () => scanDiagnostics(stats, seen);
      while (!cancelled && genRef.current === gen && kept.length < FACE_PHOTOS) {
        if (stallsRef.current > MAX_CAMERA_STALLS) return;
        if (Date.now() - started > SCAN_LIMIT_MS) {
          setFaceSeen(false);
          console.warn(`[face] scan gave up: ${detail()}`);
          setProblem({ message: scanFailureMessage(seen), detail: detail() });
          return;
        }
        const shot = await cameraRef.current?.grabFrame({ retainFile: true, includeBase64: false });
        if (cancelled || genRef.current !== gen) {
          await discardFile(shot?.uri);
          return;
        }
        if (!shot?.uri) {
          stats.grabMissed += 1;
          stats.lastGrabError = cameraRef.current?.lastError() ?? "";
          await wait(60);
          continue;
        }
        stats.grabbed += 1;
        let faces: Awaited<ReturnType<typeof detectDeviceFaces>> = [];
        try {
          // The outline read is slower. Once a good frame is kept, the rest
          // only need the quick one-face check and the outline stays drawn.
          // After several empty reads the quick detector may be the problem, so
          // switch to the slower, more forgiving one.
          faces = await detectDeviceFaces(shot.uri, { contours: kept.length === 0, accurate: emptyStreak >= 4 });
        } catch (reason) {
          await discardFile(shot.uri);
          if (cancelled) return;
          if (isOnDeviceReaderMissing(reason)) {
            setProblem({
              message: "This app doesn’t include the on-device face reader yet. Update the app, then try the face check again.",
            });
            return;
          }
          readFailures += 1;
          stats.readFailures = readFailures;
          stats.lastReadError = String((reason as Error)?.message ?? reason);
          if (readFailures >= 8) {
            console.warn(`[face] reader failed: ${detail()}`);
            setProblem({ message: "This phone couldn’t read the camera. Try again.", detail: detail() });
            return;
          }
          await wait(60);
          continue;
        }
        let size: [number, number] = [shot.width || 3, shot.height || 4];
        if (Platform.OS === "ios") {
          // The still can be stored sideways. Measure the upright picture once.
          upright = upright ?? await uprightSize(shot.uri, size);
          size = upright;
        }
        stats.size = size;
        stats.upright = upright;
        if (faces.length) {
          stats.faceFrames += 1;
          emptyStreak = 0;
        } else {
          stats.emptyFrames += 1;
          emptyStreak += 1;
        }
        const frame = frameForFaces(size, faces);
        const verdict = frameVerdict(faces, frame);
        seen[verdict] = (seen[verdict] ?? 0) + 1;
        const face = faces.length ? faces.reduce((a, b) => (b.faceWidth > a.faceWidth ? b : a)) : null;
        setFaceSeen(verdict === "ok");
        if (face?.strokes.length) setLiveStrokes({ strokes: face.strokes, frame });
        else if (!face) setLiveStrokes(null);
        if (verdict !== "ok") {
          noteHint(FRAME_HINT[verdict]);
          await discardFile(shot.uri);
          continue;
        }
        let base64 = "";
        try {
          base64 = await FileSystem.readAsStringAsync(shot.uri, { encoding: FileSystem.EncodingType.Base64 });
        } catch {
          base64 = "";
        }
        await discardFile(shot.uri);
        if (!base64) continue;
        const print = stillFingerprint(base64);
        if (prints.has(print)) continue;
        prints.add(print);
        kept.push(base64);
        setCaptured(kept.length);
        noteHint(kept.length < FACE_PHOTOS ? "Hold still…" : "Saving your face check…");
      }
      if (cancelled || genRef.current !== gen || kept.length < FACE_PHOTOS) return;

      // Save in the background and go straight to the voice check, as the
      // web app does. The voice step waits for the result before finishing.
      const saving = saveFace(kept);
      setCaptured(0);
      setFaceSeen(false);
      if (!voiceDoneRef.current) {
        setStep("voice");
        return;
      }
      // Redoing the face after the voice is saved: wait for this save, and
      // go back to the voice step to show it if it fails again.
      setBusy(true);
      const saved = await saving;
      setBusy(false);
      if (cancelled) return;
      setStep(saved ? (requireGovernmentId ? "identity" : "complete") : "voice");
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [visible, step, attempt, studentId, requireGovernmentId]);

  function saveFace(photos: string[]): Promise<boolean> {
    if (faceSaveRef.current) return faceSaveRef.current;
    setFaceState("saving");
    setFaceNote("");
    const pending = (async () => {
      try {
        await withTimeout(
          sendWithConsent(() => enrollMobileFaceQuick(studentId, photos)),
          SAVE_TIMEOUT_MS,
          "Saving the face check is taking too long.",
        );
        setFaceState("saved");
        return true;
      } catch (reason) {
        if (isDeferredUpload(reason)) {
          try {
            await queuePendingFace(studentId, photos, {
              granted: true,
              guardianGranted: minor ? guardian : false,
            });
            setPendingNote("Saved on this phone. We’ll send your face check when you’re connected.");
            setFaceState("queued");
            return true;
          } catch (keepReason) {
            setFaceNote(String((keepReason as Error)?.message ?? keepReason));
            setFaceState("failed");
            return false;
          }
        }
        setFaceNote(faceEnrollmentProblem(reason).message);
        setFaceState("failed");
        return false;
      } finally {
        faceSaveRef.current = null;
      }
    })();
    faceSaveRef.current = pending;
    return pending;
  }

  function redoFace() {
    setProblem(null);
    setFaceState("idle");
    setFaceNote("");
    resetScan();
    readyRef.current = false;
    stallsRef.current = 0;
    setStep("scan");
    setAttempt((n) => n + 1);
  }

  // A still that never returns usually means the camera session wedged. Start
  // it again instead of leaving the learner on "Look at the camera."
  function onCameraStall() {
    if (stallsRef.current > MAX_CAMERA_STALLS) return;
    stallsRef.current += 1;
    if (stallsRef.current > MAX_CAMERA_STALLS) {
      setProblem({ message: "The camera stopped responding. Close other apps using the camera and try again." });
      return;
    }
    resetScan();
    readyRef.current = false;
    setAttempt((n) => n + 1);
  }

  async function recordVoice() {
    setBusy(true);
    setProblem(null);
    setElapsed(0);
    setBars(Array(WAVE_BARS).fill(0));
    let uri: string | null = null;
    try {
      let permission = await Audio.getPermissionsAsync();
      if (!permission.granted) {
        permission = await outsideTheSetupWindow(() => Audio.requestPermissionsAsync());
      }
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
      let peakDb: number | null = null;
      let sawMetering = false;
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
          if (status.metering != null) {
            sawMetering = true;
            peakDb = peakDb == null ? status.metering : Math.max(peakDb, status.metering);
          }
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
      // The phone knows when it heard nothing. Say so now instead of sending
      // ten silent seconds to the server and waiting for it to refuse them.
      if (isSilentTake(peakDb, sawMetering)) throw new Error("silent");
      const base64 = await FileSystem.readAsStringAsync(uri, { encoding: FileSystem.EncodingType.Base64 });
      const recordedUri = uri;
      try {
        await withTimeout(
          sendWithConsent(() => enrollMobileVoiceprint(studentId, base64)),
          SAVE_TIMEOUT_MS,
          "Saving the voice check is taking too long.",
        );
        await discardFile(recordedUri);
        uri = null;
        await continueAfterVoice();
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
        await continueAfterVoice();
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

  // The face save started while the learner read the sentence. Wait for it
  // here so a failed face save is shown now, with a way to redo only the face.
  async function continueAfterVoice() {
    voiceDoneRef.current = true;
    setVoiceDone(true);
    await faceSaveRef.current;
    if (faceStateRef.current === "failed") return;
    setStep(requireGovernmentId ? "identity" : "complete");
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
      if (!skipped) {
        await faceSaveRef.current;
        if (faceStateRef.current === "failed") {
          setStep("voice");
          return;
        }
      }
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
  const title = step === "scan"
    ? scanHint
    : step === "voice" && recording ? "Keep reading…" : text.title;
  const done = step === "identity" || step === "complete";
  const progress = STEPS.indexOf(step);
  const { isMedium, isExpanded } = useLayoutMetrics();
  const wide = isMedium || isExpanded;
  const scanning = step === "scan";
  const [frameBox, setFrameBox] = useState({ width: 0, height: 0 });
  const guideSize = frameBox.width > 0 ? Math.min(Math.round(frameBox.width * 0.72), 420) : 0;

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
                    onStall={onCameraStall}
                  />
                </View>
                <View style={styles.overlay} pointerEvents="none" collapsable={false}>
                <View style={styles.faceGuideWrap}>
                  <View style={guideSize ? { width: guideSize, height: guideSize } : styles.faceGuideAuto}>
                    <View
                      style={[
                        styles.faceGuide,
                        guideSize ? { width: guideSize, height: guideSize, maxWidth: guideSize, aspectRatio: undefined } : null,
                        faceSeen && styles.faceGuideOn,
                      ]}
                      testID="face-guide"
                    />
                    {guideSize ? (
                      <View style={StyleSheet.absoluteFill} pointerEvents="none">
                        <ScanRing size={guideSize} progress={captured / FACE_PHOTOS} found={faceSeen} />
                      </View>
                    ) : null}
                  </View>
                </View>
                <View style={styles.liveDot} accessibilityLabel="Live camera" />
                {liveStrokes && frameBox.width > 0 ? (
                  <Svg
                    style={styles.mesh}
                    width={frameBox.width}
                    height={frameBox.height}
                    viewBox={`0 0 ${liveStrokes.frame[0]} ${liveStrokes.frame[1]}`}
                    preserveAspectRatio="xMidYMid slice"
                    pointerEvents="none"
                    testID="face-contour"
                  >
                    {liveStrokes.strokes.map((stroke, index) => (
                      <Path
                        key={`stroke-${index}`}
                        d={svgPath(stroke.points, stroke.closed)}
                        fill="none"
                        stroke={index === 0 ? "#f4fcff" : "#d7f4ff"}
                        strokeWidth={Math.max(index === 0 ? 1.75 : 1.15, liveStrokes.frame[0] / (index === 0 ? 220 : 340))}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    ))}
                  </Svg>
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
            <View
              style={styles.shotRow}
              accessibilityRole="progressbar"
              accessibilityLabel="Face check"
              accessibilityValue={{ min: 0, max: FACE_PHOTOS, now: captured }}
            >
              {Array.from({ length: FACE_PHOTOS }, (_, index) => (
                <View key={index} style={[styles.shotDot, index < captured && styles.shotDotOn]} />
              ))}
            </View>
          ) : null}
          <Text style={[styles.kicker, scanning && styles.scanKicker]}>{text.kicker}</Text>
          <Text style={[styles.title, scanning && styles.scanTitle]}>{title}</Text>
          <Text style={[styles.body, scanning && styles.scanBody]}>{text.body}</Text>
          {pendingNote ? <Text style={[styles.small, scanning && styles.scanBody]}>{pendingNote}</Text> : null}
          {step === "voice" && faceState === "saving" ? (
            <Text style={styles.small}>Saving your face check…</Text>
          ) : null}
          {step === "voice" && faceState === "failed" ? (
            <Text style={styles.error} accessibilityRole="alert">
              {voiceDone ? `Your voice check is saved. ${faceNote}` : faceNote}
            </Text>
          ) : null}
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
          {problem?.detail ? <Text style={[styles.small, scanning && styles.scanBody]} selectable>{problem.detail}</Text> : null}
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
                {problem ? (
                  <Action title="Try again" glass disabled={busy} onPress={redoFace} />
                ) : null}
                {canSkip ? <Action title="Set up later" secondary glass disabled={busy} onPress={() => void finish(true)} /> : null}
              </>
            ) : null}
            {step === "voice" && faceState === "failed" ? (
              <Action title="Redo face check" disabled={busy || recording} onPress={redoFace} />
            ) : null}
            {step === "voice" && voiceDone && faceState === "failed" && canSkip ? (
              <Action title="Set up later" secondary disabled={busy} onPress={() => void finish(true)} />
            ) : null}
            {step === "voice" && !voiceDone ? (
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
  faceGuideAuto: { width: "72%", maxWidth: 420, aspectRatio: 1 },
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
  shotRow: { flexDirection: "row", gap: 10, justifyContent: "center", paddingTop: 10 },
  shotDot: {
    width: 14, height: 14, borderRadius: 7,
    borderWidth: 2, borderColor: "rgba(255,255,255,0.85)", backgroundColor: "rgba(15, 23, 42, 0.25)",
  },
  shotDotOn: { backgroundColor: "#7ee0a1", borderColor: "#ffffff" },
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
