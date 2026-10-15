import { Audio, ResizeMode, Video } from "expo-av";
import * as ImagePicker from "expo-image-picker";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Image,
  Modal,
  Platform,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";

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

type Step = "welcome" | "privacy" | "portrait" | "pose" | "voice" | "identity" | "complete";
const STEPS: Step[] = ["welcome", "privacy", "portrait", "pose", "voice", "identity", "complete"];
const POSES = ["left", "right", "up", "down"] as const;
const PROMPT =
  "Today I’m ready to learn with Salareen. Can you hear my voice clearly? Yes—I’m speaking naturally and confidently.";

const media = {
  welcome: {
    poster: require("../../assets/setup-assistant/welcome.webp"),
    video: require("../../assets/setup-assistant/welcome.mp4"),
  },
  privacy: {
    poster: require("../../assets/setup-assistant/privacy.webp"),
    video: require("../../assets/setup-assistant/privacy.mp4"),
  },
  portrait: {
    poster: require("../../assets/setup-assistant/portrait.webp"),
    video: require("../../assets/setup-assistant/portrait.mp4"),
  },
  pose: {
    poster: require("../../assets/setup-assistant/pose.webp"),
    video: require("../../assets/setup-assistant/pose.mp4"),
  },
  voice: {
    poster: require("../../assets/setup-assistant/voice.webp"),
    video: require("../../assets/setup-assistant/voice.mp4"),
  },
  identity: {
    poster: require("../../assets/setup-assistant/identity.webp"),
    video: require("../../assets/setup-assistant/identity.mp4"),
  },
  complete: {
    poster: require("../../assets/setup-assistant/welcome.webp"),
    video: require("../../assets/setup-assistant/welcome.mp4"),
  },
};

const copy: Record<Step, { kicker: string; title: string; body: string }> = {
  welcome: {
    kicker: "Optional identity setup",
    title: "A simpler way to prove it’s you.",
    body: "Four short checks protect your learning record and unlock accredited courses.",
  },
  privacy: {
    kicker: "Your choice. Your data.",
    title: "Private by design.",
    body: "Media is processed for setup and discarded. Salareen keeps protected identity templates and verification decisions—not raw recordings or ID photos.",
  },
  portrait: {
    kicker: "Check 1 of 4 · Portrait",
    title: "Look naturally at the camera.",
    body: "A three-second timer opens the front camera. Center your face and take one clear photo.",
  },
  pose: {
    kicker: "Check 2 of 4 · Movement",
    title: "Turn gently with the guide.",
    body: "Move only your head and take one photo in each direction.",
  },
  voice: {
    kicker: "Check 3 of 4 · Voice",
    title: "Speak in your everyday voice.",
    body: "Read the sentence for 10 seconds. The recording is discarded after your voiceprint is created.",
  },
  identity: {
    kicker: "Check 4 of 4 · Government ID",
    title: "Verify an accredited learner.",
    body: "Required only for certificates, licenses, and regulated exams. The document image is not retained.",
  },
  complete: {
    kicker: "Setup complete",
    title: "You’re ready to learn.",
    body: "You can review or remove identity setup later in Profile → Settings.",
  },
};

type Props = {
  visible: boolean;
  studentId: string;
  ageBand?: string;
  requireGovernmentId?: boolean;
  onDismiss: () => void;
  onComplete?: () => void;
};

export default function BiometricSetupModal({
  visible,
  studentId,
  ageBand = "adult",
  requireGovernmentId = false,
  onDismiss,
  onComplete,
}: Props) {
  const [step, setStep] = useState<Step>("welcome");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [guardian, setGuardian] = useState(ageBand === "adult");
  const [countdown, setCountdown] = useState(0);
  const [photos, setPhotos] = useState<string[]>([]);
  const [poseIndex, setPoseIndex] = useState(0);
  const [seconds, setSeconds] = useState(10);
  const [hasEnrollment, setHasEnrollment] = useState(false);
  const recordingRef = useRef<Audio.Recording | null>(null);

  useEffect(() => {
    if (!visible) return;
    getMobileSetupState(studentId).then((state) => {
      setHasEnrollment(
        state.portrait.status === "verified"
        || state.voice.status === "verified"
        || state.government_id.status === "verified",
      );
      if (state.voice.status === "verified") setStep(requireGovernmentId ? "identity" : "complete");
      else if (state.portrait.status === "verified") setStep("voice");
    }).catch(() => undefined);
  }, [requireGovernmentId, studentId, visible]);

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
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function consent() {
    await withBusy(async () => {
      await setMobileBiometricConsent(studentId, true, ageBand === "adult" ? false : guardian);
      setStep("portrait");
    });
  }

  async function cameraPhoto(front = true): Promise<string | null> {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) throw new Error("Camera permission is required");
    for (let value = 3; value > 0; value -= 1) {
      setCountdown(value);
      await new Promise<void>((resolve) => setTimeout(() => resolve(), 700));
    }
    setCountdown(0);
    const result = await ImagePicker.launchCameraAsync({
      cameraType: front ? ImagePicker.CameraType.front : ImagePicker.CameraType.back,
      base64: true,
      quality: 0.72,
      allowsEditing: false,
      exif: false,
    });
    return result.canceled ? null : (result.assets[0]?.base64 ?? null);
  }

  async function portrait() {
    await withBusy(async () => {
      const photo = await cameraPhoto();
      if (!photo) return;
      setPhotos([photo]);
      setStep("pose");
    });
  }

  async function posePhoto() {
    await withBusy(async () => {
      const photo = await cameraPhoto();
      if (!photo) return;
      const next = [...photos, photo];
      setPhotos(next);
      if (poseIndex < POSES.length - 1) {
        setPoseIndex((value) => value + 1);
      } else {
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
      for (let value = 10; value > 0; value -= 1) {
        setSeconds(value);
        await new Promise<void>((resolve) => setTimeout(() => resolve(), 1000));
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
      setStep("welcome");
    });
  }

  const scene = media[step];
  const text = copy[step];
  const progress = STEPS.indexOf(step);

  return (
    <Modal visible={visible} animationType="fade" presentationStyle="fullScreen" onRequestClose={onDismiss}>
      <SafeAreaView style={styles.root}>
        <View style={styles.visual}>
          {Platform.OS === "web" ? (
            <Image source={scene.poster} style={styles.media} resizeMode="cover" />
          ) : (
            <Video
              source={scene.video}
              style={styles.media}
              resizeMode={ResizeMode.COVER}
              isLooping
              isMuted
              shouldPlay={visible}
              useNativeControls={false}
            />
          )}
          <View style={styles.scrim} />
          {countdown > 0 ? <Text style={styles.countdown}>{countdown}</Text> : null}
        </View>
        <ScrollView style={styles.content} contentContainerStyle={styles.contentInner}>
          <View style={styles.bars}>
            {STEPS.slice(0, -1).map((item, index) => (
              <View key={item} style={[styles.bar, index <= progress && styles.barActive]} />
            ))}
          </View>
          <Text style={styles.kicker}>{text.kicker}</Text>
          <Text style={styles.title}>
            {step === "pose" ? `Turn ${POSES[poseIndex]}.` : text.title}
          </Text>
          <Text style={styles.body}>{text.body}</Text>
          {step === "voice" ? <Text style={styles.prompt}>{PROMPT}</Text> : null}
          {step === "privacy" && ageBand !== "adult" ? (
            <View style={styles.guardian}>
              <Text style={styles.guardianText}>I am the account owner or guardian and consent to this minor’s setup.</Text>
              <Switch value={guardian} onValueChange={setGuardian} />
            </View>
          ) : null}
          {error ? <Text style={styles.error}>{error}</Text> : null}
          {busy ? <ActivityIndicator color={theme.colors.accent} style={styles.spinner} /> : null}
          <View style={styles.actions}>
            {step === "welcome" ? (
              <>
                <Action title="Continue" onPress={() => setStep("privacy")} />
                {!requireGovernmentId ? <Action title="Set up later" secondary onPress={() => void finish(true)} /> : null}
                {hasEnrollment && !requireGovernmentId ? (
                  <Action title="Remove identity data" secondary disabled={busy} onPress={() => void removeIdentity()} />
                ) : null}
              </>
            ) : null}
            {step === "privacy" ? <Action title="Agree and continue" disabled={busy || (ageBand !== "adult" && !guardian)} onPress={() => void consent()} /> : null}
            {step === "portrait" ? <Action title="Take portrait" disabled={busy} onPress={() => void portrait()} /> : null}
            {step === "pose" ? <Action title={`Capture ${POSES[poseIndex]}`} disabled={busy} onPress={() => void posePhoto()} /> : null}
            {step === "voice" ? <Action title={busy ? `Recording · ${seconds}s` : "Record 10-second sample"} disabled={busy} onPress={() => void recordVoice()} /> : null}
            {step === "identity" ? (
              <>
                <Action title="Photograph ID securely" disabled={busy} onPress={() => void document()} />
                {!requireGovernmentId ? <Action title="Not now" secondary onPress={() => setStep("complete")} /> : null}
              </>
            ) : null}
            {step === "complete" ? <Action title="Finish" disabled={busy} onPress={() => void finish()} /> : null}
          </View>
          <Text style={styles.note}>
            General learning and games never require identity checks. Accredited courses require all checks before the first full lesson.
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
  root: { flex: 1, backgroundColor: "#080b1d" },
  visual: { height: "46%", minHeight: 300, overflow: "hidden", position: "relative" },
  media: { ...StyleSheet.absoluteFillObject, width: "100%", height: "100%" },
  scrim: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(6,9,25,.12)" },
  countdown: {
    position: "absolute", alignSelf: "center", top: "35%", color: "#fff",
    fontSize: 120, fontWeight: "900", textShadowColor: "#000", textShadowRadius: 18,
  },
  content: { flex: 1, marginTop: -34, borderTopLeftRadius: 32, borderTopRightRadius: 32, backgroundColor: "#080b1d" },
  contentInner: { padding: 24, paddingBottom: 46 },
  bars: { flexDirection: "row", gap: 6, marginBottom: 25 },
  bar: { height: 4, flex: 1, borderRadius: 4, backgroundColor: "#29314e" },
  barActive: { backgroundColor: "#72d8ff" },
  kicker: { color: "#72d8ff", fontSize: 12, fontWeight: "900", letterSpacing: 1.8, textTransform: "uppercase" },
  title: { color: "#f8fbff", fontSize: 40, lineHeight: 43, fontWeight: "900", letterSpacing: -1.6, marginTop: 10 },
  body: { color: "#bdc7df", fontSize: 17, lineHeight: 25, marginTop: 14 },
  prompt: { color: "#eef6ff", fontSize: 17, lineHeight: 25, marginTop: 18, padding: 18, borderRadius: 16, backgroundColor: "#131a34" },
  guardian: { flexDirection: "row", alignItems: "center", gap: 12, marginTop: 18, padding: 14, borderRadius: 16, backgroundColor: "#141b35" },
  guardianText: { color: "#dce5f7", flex: 1, lineHeight: 20 },
  error: { color: "#ffb1b1", marginTop: 16 },
  spinner: { marginTop: 18 },
  actions: { gap: 10, marginTop: 24 },
  button: { backgroundColor: "#72d8ff", borderRadius: 999, minHeight: 52, alignItems: "center", justifyContent: "center", paddingHorizontal: 22 },
  buttonSecondary: { backgroundColor: "#1a223e", borderWidth: 1, borderColor: "#3c476b" },
  buttonText: { color: "#071521", fontSize: 16, fontWeight: "800" },
  buttonTextSecondary: { color: "#e7edfa" },
  disabled: { opacity: .5 },
  note: { color: "#7f8aa7", fontSize: 12, lineHeight: 18, marginTop: 22 },
});
