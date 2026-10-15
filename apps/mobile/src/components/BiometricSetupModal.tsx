import { Audio } from "expo-av";
import * as ImagePicker from "expo-image-picker";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import Svg, { Circle, Line } from "react-native-svg";

import {
  completeMobileSetup,
  deleteMobileBiometrics,
  enrollMobileFaceImages,
  enrollMobileVoiceprint,
  getMobileSetupState,
  setMobileBiometricConsent,
  submitMobileGovernmentId,
} from "../api";
import { theme } from "../theme";
import AnimatedPressable from "./AnimatedPressable";
import KenBurnsImage from "./KenBurnsImage";

type Step = "welcome" | "scan" | "voice" | "identity" | "complete";
const STEPS: Step[] = ["welcome", "scan", "voice", "identity", "complete"];
const POSES = ["left", "right", "up", "down"] as const;
const PROMPT =
  "Today I’m ready to learn with Salareen. Can you hear my voice clearly? Yes—I’m speaking naturally and confidently.";
const TICKS = 72;
// Ring quarter (tick centre index) lit by each captured pose; 0 = 3 o'clock.
const POSE_TICK: Record<(typeof POSES)[number], number> = { right: 0, down: 18, left: 36, up: 54 };

const ART = {
  face: require("../../assets/setup-assistant/face-scan.webp"),
  voice: require("../../assets/setup-assistant/voice.webp"),
};

const copy: Record<Step, { kicker: string; title: string; body: string }> = {
  welcome: {
    kicker: "Optional · about 1 minute",
    title: "Set up Face & Voice ID.",
    body: "A quick face scan from five angles, then one sentence read out loud. Only protected templates are kept — never your photos, audio, or ID images.",
  },
  scan: {
    kicker: "Face scan",
    title: "Look straight at the camera.",
    body: "We’ll open the front camera five times: straight on, then left, right, up, and down. Move only your head.",
  },
  voice: {
    kicker: "Voice check",
    title: "Now read this out loud.",
    body: "Speak naturally for 10 seconds. The recording is discarded after your voiceprint is created.",
  },
  identity: {
    kicker: "Accredited course · Government ID",
    title: "One last check.",
    body: "Courses that lead to a certificate or license need a government ID match. The image is checked once and discarded.",
  },
  complete: {
    kicker: "Face & Voice ID is set up",
    title: "You’re all set.",
    body: "Review or remove it any time in Profile → Settings → Camera check.",
  },
};

function TickRing({ lit, progress = 0, done = false }: { lit: boolean[]; progress?: number; done?: boolean }) {
  const size = 300;
  const c = size / 2;
  return (
    <Svg width="100%" height="100%" viewBox={`0 0 ${size} ${size}`} style={StyleSheet.absoluteFillObject}>
      {Array.from({ length: TICKS }, (_, index) => {
        const angle = (index / TICKS) * Math.PI * 2;
        const on = done || lit[index];
        const inner = 132;
        const outer = inner + (on ? 14 : 9);
        return (
          <Line
            key={index}
            x1={c + Math.cos(angle) * inner}
            y1={c + Math.sin(angle) * inner}
            x2={c + Math.cos(angle) * outer}
            y2={c + Math.sin(angle) * outer}
            stroke={on ? "#30d158" : "rgba(255,255,255,0.25)"}
            strokeWidth={3.5}
            strokeLinecap="round"
          />
        );
      })}
      {progress > 0 ? (
        <Circle
          cx={c}
          cy={c}
          r={124}
          fill="none"
          stroke="#8be9ff"
          strokeWidth={3}
          strokeDasharray={`${progress * 2 * Math.PI * 124} ${2 * Math.PI * 124}`}
          transform={`rotate(-90 ${c} ${c})`}
        />
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
  const [error, setError] = useState("");
  const [guardian, setGuardian] = useState(ageBand === "adult");
  const [photos, setPhotos] = useState<string[]>([]);
  const [lit, setLit] = useState<boolean[]>(() => Array(TICKS).fill(false));
  const [seconds, setSeconds] = useState(0);
  const [hasEnrollment, setHasEnrollment] = useState(false);
  const recordingRef = useRef<Audio.Recording | null>(null);
  const minor = ageBand !== "adult";

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
    const recording = recordingRef.current;
    recordingRef.current = null;
    if (!recording) return;
    try {
      const status = await recording.getStatusAsync();
      if (status.isRecording) await recording.stopAndUnloadAsync();
    } catch { /* best-effort cleanup */ }
  }, []);

  useEffect(() => () => { void stopRecording(); }, [stopRecording]);

  async function withBusy(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (reason) {
      setError(String(reason).replace(/^Error:\s*/, ""));
    } finally {
      setBusy(false);
    }
  }

  async function begin() {
    await withBusy(async () => {
      await setMobileBiometricConsent(studentId, true, minor ? guardian : false);
      setPhotos([]);
      setLit(Array(TICKS).fill(false));
      setStep("scan");
    });
  }

  async function cameraPhoto(front = true): Promise<string | null> {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) throw new Error("Camera permission is required");
    const result = await ImagePicker.launchCameraAsync({
      cameraType: front ? ImagePicker.CameraType.front : ImagePicker.CameraType.back,
      base64: true,
      quality: 0.72,
      allowsEditing: false,
      exif: false,
    });
    return result.canceled ? null : (result.assets[0]?.base64 ?? null);
  }

  function lightPose(pose: (typeof POSES)[number]) {
    setLit((current) => {
      const next = [...current];
      for (let offset = -9; offset < 9; offset += 1) next[(POSE_TICK[pose] + offset + TICKS) % TICKS] = true;
      return next;
    });
  }

  async function capture() {
    await withBusy(async () => {
      const photo = await cameraPhoto();
      if (!photo) return;
      const next = [...photos, photo];
      setPhotos(next);
      if (next.length > 1) lightPose(POSES[next.length - 2]);
      if (next.length === POSES.length + 1) {
        await enrollMobileFaceImages(studentId, next);
        setStep("voice");
      }
    });
  }

  async function recordVoice() {
    await withBusy(async () => {
      const permission = await Audio.requestPermissionsAsync();
      if (!permission.granted) throw new Error("Microphone permission is required");
      await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY,
      );
      recordingRef.current = recording;
      for (let value = 1; value <= 10; value += 1) {
        await new Promise<void>((resolve) => setTimeout(() => resolve(), 1000));
        setSeconds(value);
      }
      await recording.stopAndUnloadAsync();
      recordingRef.current = null;
      const uri = recording.getURI();
      if (!uri) throw new Error("No audio was recorded");
      const blob = await (await fetch(uri)).blob();
      const base64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(String(reader.result).split(",")[1] ?? "");
        reader.onerror = reject;
        reader.readAsDataURL(blob);
      });
      await enrollMobileVoiceprint(studentId, base64);
      setSeconds(0);
      setStep(requireGovernmentId ? "identity" : "complete");
    });
  }

  async function document() {
    await withBusy(async () => {
      const photo = await cameraPhoto(false);
      if (!photo) return;
      const result = await submitMobileGovernmentId(studentId, photo);
      if (result.status !== "verified") {
        throw new Error("The portrait on this ID did not match. Use a clear, well-lit image and try again.");
      }
      setStep("complete");
    });
  }

  async function finish(skipped = false) {
    await withBusy(async () => {
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
  const nextPose = photos.length === 0 ? null : POSES[photos.length - 1];
  const title = step === "scan" && nextPose ? `Now turn ${nextPose}.` : text.title;
  const done = step === "identity" || step === "complete";
  const progress = STEPS.indexOf(step);

  return (
    <Modal visible={visible} animationType="fade" presentationStyle="fullScreen" onRequestClose={onDismiss}>
      <SafeAreaView style={styles.root}>
        <KenBurnsImage source={step === "voice" ? ART.voice : ART.face} opacity={0.28} />
        <View style={styles.scrim} />
        <ScrollView contentContainerStyle={styles.contentInner}>
          <View style={styles.bars}>
            {STEPS.slice(0, -1).map((item, index) => (
              <View key={item} style={[styles.bar, index <= progress && styles.barActive]} />
            ))}
          </View>
          {stepLabel ? <Text style={styles.stepLabel}>{stepLabel}</Text> : null}
          <View style={styles.ringWrap}>
            <View style={styles.lens}>
              <KenBurnsImage key={step === "voice" ? "voice" : "face"} source={step === "voice" ? ART.voice : ART.face} duration={16} />
              {done ? <Text style={styles.check}>✓</Text> : null}
            </View>
            <TickRing lit={lit} progress={step === "voice" ? seconds / 10 : 0} done={done} />
          </View>
          {step === "scan" ? (
            <View style={styles.poses}>
              {POSES.map((pose, index) => (
                <Text key={pose} style={[styles.pose, photos.length > index + 1 && styles.poseDone]}>
                  {photos.length > index + 1 ? "✓ " : ""}{pose}
                </Text>
              ))}
            </View>
          ) : null}
          <Text style={styles.kicker}>{text.kicker}</Text>
          <Text style={styles.title}>{title}</Text>
          <Text style={styles.body}>{text.body}</Text>
          {step === "voice" ? <Text style={styles.prompt}>{PROMPT}</Text> : null}
          {step === "welcome" && minor ? (
            <View style={styles.guardian}>
              <Text style={styles.guardianText}>I’m the parent or guardian and I agree to this learner’s Face & Voice ID setup.</Text>
              <Switch value={guardian} onValueChange={setGuardian} />
            </View>
          ) : null}
          {error ? <Text style={styles.error}>{error}</Text> : null}
          {busy && step !== "voice" ? <ActivityIndicator color={theme.colors.accent} style={styles.spinner} /> : null}
          <View style={styles.actions}>
            {step === "welcome" ? (
              <>
                <Action title="Get started" disabled={busy || (minor && !guardian)} onPress={() => void begin()} />
                {!requireGovernmentId ? <Action title="Set up later" secondary onPress={() => void finish(true)} /> : null}
                {hasEnrollment && !requireGovernmentId ? (
                  <Action title="Remove saved identity" secondary disabled={busy} onPress={() => void removeIdentity()} />
                ) : null}
              </>
            ) : null}
            {step === "scan" ? (
              <>
                <Action
                  title={photos.length === 0 ? "Open camera" : `Capture ${nextPose}`}
                  disabled={busy}
                  onPress={() => void capture()}
                />
                {!requireGovernmentId ? <Action title="Set up later" secondary onPress={() => void finish(true)} /> : null}
              </>
            ) : null}
            {step === "voice" ? (
              <Action
                title={busy ? `Recording… ${10 - seconds}s` : "Start recording"}
                disabled={busy}
                onPress={() => void recordVoice()}
              />
            ) : null}
            {step === "identity" ? (
              <>
                <Action title="Photograph ID securely" disabled={busy} onPress={() => void document()} />
                {!requireGovernmentId ? <Action title="Not now" secondary onPress={() => setStep("complete")} /> : null}
              </>
            ) : null}
            {step === "complete" ? <Action title="Continue" disabled={busy} onPress={() => void finish()} /> : null}
          </View>
          <Text style={styles.note}>
            Games and general courses never need Face & Voice ID. Accredited and certification courses require it before the first full lesson.
          </Text>
        </ScrollView>
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

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#04060f" },
  scrim: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(4,6,15,.6)" },
  contentInner: { padding: 24, paddingBottom: 46 },
  bars: { flexDirection: "row", gap: 6, marginBottom: 12 },
  bar: { height: 4, flex: 1, borderRadius: 4, backgroundColor: "rgba(255,255,255,.18)" },
  barActive: { backgroundColor: "#8be9ff" },
  stepLabel: { color: "rgba(244,247,255,.7)", fontSize: 13, marginBottom: 8 },
  ringWrap: { width: "86%", maxWidth: 340, aspectRatio: 1, alignSelf: "center", marginVertical: 12 },
  lens: {
    position: "absolute", top: "13%", left: "13%", right: "13%", bottom: "13%",
    borderRadius: 999, overflow: "hidden", backgroundColor: "#0b1020",
    borderWidth: 1, borderColor: "rgba(255,255,255,.14)",
  },
  check: {
    ...StyleSheet.absoluteFillObject, textAlign: "center", textAlignVertical: "center",
    lineHeight: 220, fontSize: 96, color: "#30d158", backgroundColor: "rgba(4,6,15,.55)",
  },
  poses: { flexDirection: "row", flexWrap: "wrap", gap: 8, justifyContent: "center", marginBottom: 8 },
  pose: {
    color: "rgba(244,247,255,.6)", backgroundColor: "rgba(255,255,255,.08)", borderRadius: 999,
    paddingHorizontal: 12, paddingVertical: 6, overflow: "hidden", textTransform: "capitalize",
  },
  poseDone: { color: "#7ef29d", backgroundColor: "rgba(48,209,88,.2)" },
  kicker: { color: "#8be9ff", fontSize: 12, fontWeight: "900", letterSpacing: 1.8, textTransform: "uppercase", marginTop: 8 },
  title: { color: "#f8fbff", fontSize: 34, lineHeight: 38, fontWeight: "900", letterSpacing: -1.2, marginTop: 8 },
  body: { color: "#c9d2e8", fontSize: 16, lineHeight: 23, marginTop: 10 },
  prompt: {
    color: "#eef6ff", fontSize: 17, lineHeight: 25, marginTop: 16, padding: 18, borderRadius: 18,
    backgroundColor: "rgba(255,255,255,.07)", borderWidth: 1, borderColor: "rgba(139,233,255,.25)",
  },
  guardian: {
    flexDirection: "row", alignItems: "center", gap: 12, marginTop: 16, padding: 14, borderRadius: 16,
    backgroundColor: "rgba(255,214,10,.1)", borderWidth: 1, borderColor: "rgba(255,214,10,.3)",
  },
  guardianText: { color: "#f1f4fb", flex: 1, lineHeight: 20 },
  error: { color: "#ffb1b1", marginTop: 16 },
  spinner: { marginTop: 18 },
  actions: { gap: 10, marginTop: 22 },
  button: { backgroundColor: "#f4f7ff", borderRadius: 999, minHeight: 52, alignItems: "center", justifyContent: "center", paddingHorizontal: 22 },
  buttonSecondary: { backgroundColor: "rgba(255,255,255,.12)" },
  buttonText: { color: "#04060f", fontSize: 16, fontWeight: "800" },
  buttonTextSecondary: { color: "#f4f7ff" },
  disabled: { opacity: .45 },
  note: { color: "#8590ad", fontSize: 12, lineHeight: 18, marginTop: 22 },
});
