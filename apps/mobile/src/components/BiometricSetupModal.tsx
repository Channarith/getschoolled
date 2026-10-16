import { Audio } from "expo-av";
import * as FileSystem from "expo-file-system";
import * as ImagePicker from "expo-image-picker";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Image,
  Linking,
  Modal,
  SafeAreaView,
  ScrollView,
  useWindowDimensions,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
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
    body: "It helps us know it’s really you in accredited courses. Take five quick selfies as the frame asks, then read one sentence out loud. We keep protected templates only, never your photos, audio, or ID images.",
  },
  scan: {
    kicker: "Face check",
    title: "Look straight at the camera.",
    body: "Checking distinctive features. Face a window or a lamp so your face is well lit. Face map ready means these looks were captured. The lines guide the photo. They are not proof that nobody else could look similar.",
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
  uri: string;
  contour: FaceContour | null;
  frame: [number, number];
  /**
   * Overlay rings for this preview only. Coordinates are not enrolled and
   * are dropped when the photo is deleted.
   */
  marks: FaceMark[];
};

type Problem = { message: string; settings?: boolean };

async function discardFile(uri: string | null | undefined) {
  if (!uri) return;
  await FileSystem.deleteAsync(uri, { idempotent: true }).catch(() => undefined);
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
  useEffect(() => () => {
    void stopRecording();
    shotsRef.current.forEach((shot) => void discardFile(shot.uri));
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
    shotsRef.current.forEach((shot) => void discardFile(shot.uri));
    setShots([]);
    setOrder(shuffledPoses());
    setContourNote("");
    baseRef.current = null;
    seenRef.current = {};
  }

  async function begin() {
    await withBusy(async () => {
      await setMobileBiometricConsent(studentId, true, minor ? guardian : false);
      resetScan();
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

  async function capture() {
    await withBusy(async () => {
      const asset = await takePhoto(true);
      if (!asset?.base64) return;
      const target = shots.length === 0 ? null : order[shots.length - 1];
      let contour: FaceContour | null = null;
      let marks: FaceMark[] = [];
      let frame: [number, number] = [asset.width || 3, asset.height || 4];
      const preview = await previewMobileFace(studentId, asset.base64).catch(() => null);
      if (preview) {
        if (preview.faces.length !== 1) {
          await discardFile(asset.uri);
          setProblem({
            message: preview.faces.length
              ? "Only one face, please. Try again."
              : "We couldn’t see your face clearly. Face a window or lamp and try again.",
          });
          return;
        }
        const face = preview.faces[0];
        frame = [face.frame_size[0] || frame[0], face.frame_size[1] || frame[1]];
        contour = faceContour(face.landmarks, face.bbox);
        // The still is decoded on this phone for the markers. Only the region
        // and point are kept; the JPEG is deleted with the preview file.
        marks = faceMarksFromJpeg(asset.base64, face.landmarks, frame, face.bbox);
        const geometry = faceGeometry(face.landmarks, face.bbox, frame);
        if (geometry && !target) baseRef.current = geometry;
        if (geometry && target && baseRef.current) {
          const seen = poseFromBaseline(baseRef.current, geometry);
          const otherSideways = target === "left" ? seenRef.current.right ?? null
            : target === "right" ? seenRef.current.left ?? null : null;
          if (!stillMatchesTarget(target, seen, otherSideways)) {
            await discardFile(asset.uri);
            setProblem({ message: `${seen ? "Almost." : "Turn a little more."} ${POSE_COPY[target]}, then take the photo again.` });
            return;
          }
          if (seen) seenRef.current[target] = seen;
        }
      } else {
        setContourNote("Face mesh unavailable right now; your photos are still checked when you finish.");
      }
      const next = [...shots, { base64: asset.base64, uri: asset.uri, contour, frame, marks }];
      setShots(next);
      if (next.length === order.length + 1) {
        try {
          await enrollMobileFaceImages(studentId, next.map((shot) => shot.base64), order);
        } catch (reason) {
          next.forEach((shot) => void discardFile(shot.uri));
          resetScan();
          throw reason;
        }
        next.forEach((shot) => void discardFile(shot.uri));
        setShots([]);
        setStep("voice");
      }
    });
  }

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
  const title = step === "scan" && target
    ? POSE_COPY[target]
    : step === "voice" && recording ? "Keep reading…" : text.title;
  const done = step === "identity" || step === "complete";
  const progress = STEPS.indexOf(step);
  const latest = shots[shots.length - 1];
  const wide = useWindowDimensions().width >= 800;

  return (
    <Modal visible={visible && !systemPrompt} animationType="fade" presentationStyle="fullScreen" onRequestClose={onDismiss}>
      <SafeAreaView style={styles.root}>
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
            {step === "scan" && latest ? (
              <>
                <Image source={{ uri: latest.uri }} style={StyleSheet.absoluteFill} resizeMode="cover" />
                {latest.contour ? (
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
                <Action
                  title={shots.length === 0 ? "Take the first photo" : `Take photo: ${target}`}
                  disabled={busy}
                  onPress={() => void capture()}
                />
                {shots.length > 0 ? <Action title="Start over" secondary disabled={busy} onPress={resetScan} /> : null}
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
