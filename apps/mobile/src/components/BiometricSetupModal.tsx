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
  previewMobileFace,
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
import AnimatedPressable from "./AnimatedPressable";
import KenBurnsImage from "./KenBurnsImage";
import LiveFaceCamera, { type LiveFaceCameraHandle } from "./LiveFaceCamera";
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
    body: "It helps us know it’s really you in accredited courses. Look into the live camera, like a video call, and turn when the frame asks. Then read one sentence out loud. We keep protected templates only, never the video, audio, or ID images.",
  },
  scan: {
    kicker: "Face check",
    title: "Look straight at the camera.",
    body: "The camera stays on. Turn when the arrow asks. We read your face from the live video, so there is no photo to take.",
  },
  voice: {
    kicker: "Voice check",
    title: "Now read this out loud.",
    body: "Speak naturally for 10 seconds. The recording is deleted from this phone as soon as your voiceprint is made.",
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
  if (status === 503) {
    return { message: "The face check service is unavailable. Try again in a minute." };
  }
  return { message: message || "Could not save your face check. Try again." };
}

export function stillFingerprint(base64: string): string {
  return base64.slice(0, 96);
}

function voiceProblem(reason: unknown): Problem {
  const status = (reason as { status?: number })?.status;
  const message = String((reason as Error)?.message ?? reason);
  if (status === 503) return { message: "The voice check isn’t available right now. Try again in a minute, or set it up later." };
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
  const [scanHint, setScanHint] = useState("Center your face in the frame.");
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

  useEffect(() => {
    if (!visible) return;
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
    setScanHint("Center your face in the frame.");
    baseRef.current = null;
    seenRef.current = {};
    savingRef.current = false;
  }

  async function begin() {
    await withBusy(async () => {
      await setMobileBiometricConsent(studentId, true, minor ? guardian : false);
      const permission = await outsideTheSetupWindow(() => Camera.requestCameraPermissionsAsync());
      if (!permission.granted) {
        setProblem({
          message: "Camera access is off for Salareen. Allow the camera in Settings, then try again.",
          settings: !permission.canAskAgain,
        });
        return;
      }
      resetScan();
      readyRef.current = false;
      setStep("scan");
    });
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
      while (!cancelled) {
        if (savingRef.current) return;
        const seenGen = genRef.current;
        const frameShot = await cameraRef.current?.grabFrame();
        if (cancelled || genRef.current !== seenGen) continue;
        if (!frameShot?.base64) {
          await wait(160);
          continue;
        }
        const fingerprint = stillFingerprint(frameShot.base64);
        if (shotsRef.current.some((shot) => stillFingerprint(shot.base64) === fingerprint)) {
          await wait(80);
          continue;
        }
        const pending = previewMobileFace(studentId, frameShot.base64)
          .then((value) => ({ ok: true as const, value }))
          .catch((reason: unknown) => ({ ok: false as const, reason }));
        const preview = await Promise.race([
          pending,
          wait(2500).then(() => ({ ok: false as const, reason: null })),
        ]);
        if (cancelled || genRef.current !== seenGen) continue;
        if (!preview.ok) {
          const status = (preview.reason as { status?: number } | null)?.status;
          if (status === 503) {
            setProblem({ message: "The face check service is unavailable. Try again in a minute." });
            return;
          }
          misses += 1;
          if (misses === 6) {
            setContourNote("Still watching the live camera. If the lines don’t appear, check your connection.");
          }
          await wait(120);
          continue;
        }
        misses = 0;
        const faces = preview.value.faces;
        const target = shotsRef.current.length === 0 ? null : orderRef.current[shotsRef.current.length - 1] ?? null;
        const face = faces.length === 1 ? faces[0] : null;
        const frame: [number, number] = [
          face?.frame_size?.[0] || frameShot.width || 3,
          face?.frame_size?.[1] || frameShot.height || 4,
        ];
        const geometry = face ? faceGeometry(face.landmarks, face.bbox, frame) : null;
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
        if (face && action !== "none" && action !== "one") {
          const contour = faceContour(face.landmarks, face.bbox);
          setLiveContour({ base64: "", contour, frame, marks: [] });
        } else if (action === "none" || action === "one") {
          setLiveContour(null);
        }
        if (action === "none") {
          noteHint("Center your face in the frame.");
          await wait(180);
          continue;
        }
        if (action === "one") {
          noteHint("Only one face, please.");
          await wait(180);
          continue;
        }
        if (action === "center") {
          noteHint("Center your face in the frame.");
          await wait(180);
          continue;
        }
        if (action === "turn") {
          if (target) noteHint(POSE_COPY[target]);
          await wait(120);
          continue;
        }
        if (!face || !geometry) continue;
        const marks = faceMarksFromJpeg(frameShot.base64, face.landmarks, frame, face.bbox);
        const contour = faceContour(face.landmarks, face.bbox);
        const kept: Shot = { base64: frameShot.base64, contour, frame, marks };
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
        try {
          await enrollMobileFaceImages(
            studentId,
            next.map((shot) => shot.base64),
            orderRef.current,
          );
          if (cancelled) return;
          setShots([]);
          shotsRef.current = [];
          setLiveContour(null);
          setStep("voice");
        } catch (reason) {
          resetScan();
          setProblem(faceEnrollmentProblem(reason));
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
      await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
      const samples: LevelSample[] = [];
      const { recording: active } = await Audio.Recording.createAsync(
        { ...Audio.RecordingOptionsPresets.HIGH_QUALITY, isMeteringEnabled: true },
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
      await discardFile(uri);
      uri = null;
      await enrollMobileVoiceprint(studentId, base64);
      setStep(requireGovernmentId ? "identity" : "complete");
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
      await completeMobileSetup(studentId, skipped);
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
        <View style={[styles.split, !wide && styles.splitStack]}>
          <View style={[styles.artPane, !wide && styles.artBand]}>
            <KenBurnsImage source={step === "voice" ? ART.voice : ART.face} style={StyleSheet.absoluteFill} />
            <View style={styles.frame}>
            {step === "scan" ? (
              <>
                <LiveFaceCamera
                  key={attempt}
                  ref={cameraRef}
                  onReady={() => { readyRef.current = true; }}
                  onError={(message) => setProblem({ message })}
                />
                <View style={styles.liveDot} accessibilityLabel="Live camera" />
                {latest?.contour ? (
                  <Svg
                    style={StyleSheet.absoluteFill}
                    viewBox={`0 0 ${latest.frame[0]} ${latest.frame[1]}`}
                    preserveAspectRatio="xMidYMid slice"
                    testID="face-contour"
                  >
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
              </>
            ) : (
              <KenBurnsImage key={step === "voice" ? "voice" : "face"} source={step === "voice" ? ART.voice : ART.face} duration={16} />
            )}
            {(["TL", "TR", "BL", "BR"] as const).map((corner) => (
              <View key={corner} style={[styles.corner, styles[`corner${corner}`], done && styles.cornerDone]} />
            ))}
            {target ? (
              <Text style={[styles.cue, styles[`cue_${target}`]]} accessibilityElementsHidden>{POSE_ARROW[target]}</Text>
            ) : null}
            {done ? <Text style={styles.check}>✓</Text> : null}
          </View>
          </View>
          <View style={styles.pane}>
          <ScrollView style={styles.paneScroll} contentContainerStyle={[styles.contentInner, wide && styles.contentCenter]}>
          {step === "scan" ? (
            <View style={styles.targets}>
              {order.map((pose, index) => {
                const captured = shots.length > index + 1;
                return (
                  <Text key={pose} style={[styles.target, pose === target && styles.targetNow, captured && styles.targetDone]}>
                    {captured ? "✓" : POSE_ARROW[pose]} {pose}
                  </Text>
                );
              })}
            </View>
          ) : null}
          <Text style={styles.kicker}>{text.kicker}{step === "scan" ? ` · ${Math.max(0, shots.length - 1)} of ${order.length}` : ""}</Text>
          <Text style={styles.title}>{title}</Text>
          <Text style={styles.body}>{text.body}</Text>
          {step === "scan" && latest?.contour ? (
            <Text style={styles.small}>
              Face map ready. The lines are a capture guide. A dot, if one shows, is an optional note about a darker spot. It is not saved, and it is not the identity check.
            </Text>
          ) : null}
          {contourNote ? <Text style={styles.small}>{contourNote}</Text> : null}
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
          <Text style={styles.note}>
            Games and general courses skip this. Accredited courses need it before the first full lesson.
          </Text>
          </ScrollView>
          <View style={styles.actions}>
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
                {shots.length > 0 ? <Action title="Start over" secondary disabled={busy} onPress={resetScan} /> : null}
                {problem ? (
                  <Action title="Try again" disabled={busy} onPress={() => { setProblem(null); readyRef.current = false; setAttempt((n) => n + 1); }} />
                ) : null}
                {canSkip ? <Action title="Set up later" secondary disabled={busy} onPress={() => void finish(true)} /> : null}
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

function Action({ title, onPress, secondary = false, disabled = false }: {
  title: string; onPress: () => void; secondary?: boolean; disabled?: boolean;
}) {
  return (
    <AnimatedPressable
      onPress={onPress}
      disabled={disabled}
      style={[styles.button, secondary && styles.buttonSecondary, disabled && styles.disabled]}
    >
      <Text style={[styles.buttonText, secondary && styles.buttonTextSecondary]}>{title}</Text>
    </AnimatedPressable>
  );
}

const CUE = 48;

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.panel },
  header: {
    flexDirection: "row", alignItems: "center", gap: 12,
    paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: C.border, backgroundColor: C.bg,
  },
  brand: { color: C.text, fontSize: 17, fontWeight: "800" },
  split: { flex: 1, flexDirection: "row", minHeight: 0 },
  splitStack: { flexDirection: "column" },
  artPane: { flex: 1.15, minWidth: 0, alignItems: "center", justifyContent: "center", backgroundColor: C.panel2, overflow: "hidden" },
  artBand: { flex: 0, width: "100%", height: "34%" },
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
  corner: { position: "absolute", width: 40, height: 40, borderColor: C.teal },
  cornerTL: { top: 14, left: 14, borderTopWidth: 4, borderLeftWidth: 4, borderTopLeftRadius: 16 },
  cornerTR: { top: 14, right: 14, borderTopWidth: 4, borderRightWidth: 4, borderTopRightRadius: 16 },
  cornerBL: { bottom: 14, left: 14, borderBottomWidth: 4, borderLeftWidth: 4, borderBottomLeftRadius: 16 },
  cornerBR: { bottom: 14, right: 14, borderBottomWidth: 4, borderRightWidth: 4, borderBottomRightRadius: 16 },
  cornerDone: { borderColor: C.accent },
  liveDot: {
    position: "absolute", top: 18, right: 18, width: 12, height: 12, borderRadius: 6,
    backgroundColor: "#ff4d4f", borderWidth: 2, borderColor: "#ffffff",
  },
  cue: {
    position: "absolute", width: CUE, height: CUE, borderRadius: CUE / 2, overflow: "hidden",
    backgroundColor: C.accent, color: "#ffffff", textAlign: "center", lineHeight: CUE, fontSize: 24, fontWeight: "800",
  },
  cue_left: { left: 10, top: "50%", marginTop: -CUE / 2 },
  cue_right: { right: 10, top: "50%", marginTop: -CUE / 2 },
  cue_up: { top: 10, left: "50%", marginLeft: -CUE / 2 },
  cue_down: { bottom: 10, left: "50%", marginLeft: -CUE / 2 },
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
  buttonText: { color: "#ffffff", fontSize: 16, fontWeight: "800" },
  buttonTextSecondary: { color: C.text },
  disabled: { opacity: .45 },
  note: { color: C.muted, fontSize: 12, lineHeight: 18, marginTop: 22 },
});
