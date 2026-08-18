/**
 * FaceVoiceEnrollModal — Settings face + voice ID enrolment for mobile.
 *
 * Two-step flow shown inside a bottom-sheet style Modal:
 *   Step 1: "Say your name" — records the user's voice via expo-av,
 *           converts to base64, uploads to the identity service.
 *   Step 2: Confirmation with voice enrolment status.
 *
 * The face-embedding enrolment (YuNet/SFace) is done via the web-side vision
 * engine on the web app; on mobile we focus on the voice sample because
 * expo-camera does not bundle the WASM models. A future native integration
 * can slot in here if needed.
 *
 * Usage:
 *   <FaceVoiceEnrollModal
 *     visible={showEnroll}
 *     studentId={students[0]?.id}
 *     studentName={students[0]?.display_name ?? ""}
 *     onDismiss={() => setShowEnroll(false)}
 *     onEnrolled={() => { setShowEnroll(false); refreshStudent(); }}
 *   />
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Modal,
  Platform,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Audio } from "expo-av";

import { enrollVoiceSample, getVoiceEnrollmentStatus, type VoiceEnrollmentStatus } from "../api";
import AnimatedPressable from "./AnimatedPressable";
import PrimaryButton from "./PrimaryButton";
import GlassPanel from "./GlassPanel";
import { theme } from "../theme";

type Step = "intro" | "requesting_perm" | "recording" | "uploading" | "done" | "error";

type Props = {
  visible: boolean;
  studentId: string;
  studentName: string;
  onDismiss: () => void;
  onEnrolled: (status: VoiceEnrollmentStatus) => void;
};

export default function FaceVoiceEnrollModal({
  visible,
  studentId,
  studentName,
  onDismiss,
  onEnrolled,
}: Props) {
  const [step, setStep] = useState<Step>("intro");
  const [errorMsg, setErrorMsg] = useState("");
  const [secondsLeft, setSecondsLeft] = useState(5);
  const [dots, setDots] = useState("");
  const recordingRef = useRef<Audio.Recording | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Reset state whenever the modal re-opens.
  useEffect(() => {
    if (visible) {
      setStep("intro");
      setErrorMsg("");
      setSecondsLeft(5);
    }
  }, [visible]);

  // Animated dots for recording indicator.
  useEffect(() => {
    if (step !== "recording") { setDots(""); return; }
    const id = setInterval(() => setDots((d) => (d.length >= 3 ? "" : d + ".")), 400);
    return () => clearInterval(id);
  }, [step]);

  const cleanup = useCallback(async () => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    if (countdownRef.current) { clearInterval(countdownRef.current); countdownRef.current = null; }
    const rec = recordingRef.current;
    if (rec) {
      recordingRef.current = null;
      try {
        const status = await rec.getStatusAsync();
        if (status.isRecording) await rec.stopAndUnloadAsync();
      } catch { /* ignore */ }
    }
  }, []);

  useEffect(() => {
    if (!visible) void cleanup();
  }, [visible, cleanup]);

  // ------------------------------------------------------------------ //
  // Recording flow
  // ------------------------------------------------------------------ //
  const startRecording = useCallback(async () => {
    setStep("requesting_perm");
    setErrorMsg("");

    const { granted } = await Audio.requestPermissionsAsync();
    if (!granted) {
      setErrorMsg("Microphone permission denied. Please enable it in device settings.");
      setStep("error");
      return;
    }

    try {
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });
      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY,
      );
      recordingRef.current = recording;
    } catch (e) {
      setErrorMsg(`Could not start recording: ${e}`);
      setStep("error");
      return;
    }

    setStep("recording");
    setSecondsLeft(5);

    // Countdown.
    countdownRef.current = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) { clearInterval(countdownRef.current!); return 0; }
        return s - 1;
      });
    }, 1000);

    // Auto-stop after 5 s.
    timerRef.current = setTimeout(() => void stopRecording(), 5000);
  }, []);

  const stopRecording = useCallback(async () => {
    await cleanup();
    const rec = recordingRef.current;
    recordingRef.current = null;

    if (!rec) {
      setErrorMsg("Recording was not started.");
      setStep("error");
      return;
    }

    setStep("uploading");

    let uri: string | undefined;
    try {
      await rec.stopAndUnloadAsync();
      uri = rec.getURI() ?? undefined;
    } catch (e) {
      setErrorMsg(`Could not stop recording: ${e}`);
      setStep("error");
      return;
    }

    if (!uri) {
      setErrorMsg("No audio file produced. Please try again.");
      setStep("error");
      return;
    }

    // Read the file as base64 using fetch + FileReader (no expo-file-system dep).
    let b64: string;
    try {
      const response = await fetch(uri);
      const blob = await response.blob();
      b64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => {
          const result = reader.result as string;
          // result is "data:<mime>;base64,<data>" — strip the data-URL prefix.
          resolve(result.split(",")[1] ?? "");
        };
        reader.onerror = reject;
        reader.readAsDataURL(blob);
      });
    } catch (e) {
      setErrorMsg(`Could not read audio: ${e}`);
      setStep("error");
      return;
    }

    // Determine MIME type from URI extension.
    const ext = uri.split(".").pop()?.toLowerCase() ?? "";
    const mime =
      ext === "m4a" ? "audio/m4a" :
      ext === "mp4" ? "audio/mp4" :
      ext === "wav" ? "audio/wav" :
      "audio/m4a";

    // Upload.
    try {
      await enrollVoiceSample(studentId, b64, mime, studentName);
      const status = await getVoiceEnrollmentStatus(studentId);
      setStep("done");
      onEnrolled(status);
    } catch (e) {
      setErrorMsg(`Upload failed: ${e}`);
      setStep("error");
    }
  }, [cleanup, studentId, studentName, onEnrolled]);

  // ------------------------------------------------------------------ //
  // Render
  // ------------------------------------------------------------------ //
  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={() => {
        void cleanup();
        onDismiss();
      }}
    >
      <View style={styles.backdrop}>
        <GlassPanel style={styles.sheet} padded>
          {/* Header */}
          <Text style={styles.title}>Face & Voice ID</Text>
          <Text style={styles.sub}>
            Say your name aloud so the platform can recognise your voice during
            lessons and attendance checks.
          </Text>

          {/* Step-specific content */}
          {step === "intro" && (
            <IntroContent name={studentName} />
          )}

          {step === "requesting_perm" && (
            <View style={styles.center}>
              <ActivityIndicator color={theme.colors.accent} />
              <Text style={styles.hint}>Requesting microphone permission…</Text>
            </View>
          )}

          {step === "recording" && (
            <RecordingContent secondsLeft={secondsLeft} dots={dots} />
          )}

          {step === "uploading" && (
            <View style={styles.center}>
              <ActivityIndicator color={theme.colors.accent} />
              <Text style={styles.hint}>Saving your voice sample…</Text>
            </View>
          )}

          {step === "done" && (
            <DoneContent name={studentName} />
          )}

          {step === "error" && (
            <View style={styles.center}>
              <Text style={styles.errorText}>{errorMsg}</Text>
            </View>
          )}

          {/* Actions */}
          <View style={styles.actions}>
            {step === "intro" && (
              <PrimaryButton
                label="🎤  Start recording"
                onPress={() => void startRecording()}
                variant="netflix"
              />
            )}
            {step === "recording" && (
              <PrimaryButton
                label="⏹  Stop early"
                onPress={() => void stopRecording()}
                variant="brand"
              />
            )}
            {step === "done" && (
              <PrimaryButton label="Done" onPress={onDismiss} variant="netflix" />
            )}
            {step === "error" && (
              <>
                <PrimaryButton
                  label="Try again"
                  onPress={() => void startRecording()}
                  variant="brand"
                />
                <PrimaryButton label="Cancel" onPress={onDismiss} variant="ghost" />
              </>
            )}
            {(step === "intro") && (
              <PrimaryButton label="Skip" onPress={onDismiss} variant="ghost" />
            )}
          </View>
        </GlassPanel>
      </View>
    </Modal>
  );
}

// ---- Sub-components ------------------------------------------------------ //

function IntroContent({ name }: { name: string }) {
  return (
    <View style={{ gap: 8, marginVertical: 12 }}>
      <View style={styles.infoRow}>
        <Text style={styles.emoji}>🎙️</Text>
        <Text style={styles.infoText}>
          Your microphone will record for up to <Text style={{ fontWeight: "700" }}>5 seconds</Text>.
        </Text>
      </View>
      <View style={styles.infoRow}>
        <Text style={styles.emoji}>🗣️</Text>
        <Text style={styles.infoText}>
          Say your name clearly:{" "}
          <Text style={{ fontStyle: "italic", color: theme.colors.accent }}>"{name}"</Text>
        </Text>
      </View>
      <View style={styles.infoRow}>
        <Text style={styles.emoji}>🔒</Text>
        <Text style={styles.infoText}>
          The audio is stored securely on your profile and used only for identity
          verification and lesson attendance tracking.
        </Text>
      </View>
    </View>
  );
}

function RecordingContent({ secondsLeft, dots }: { secondsLeft: number; dots: string }) {
  return (
    <View style={styles.center}>
      {/* Animated waveform bars */}
      <View style={styles.waveform}>
        {Array.from({ length: 16 }).map((_, i) => (
          <View
            key={i}
            style={[
              styles.bar,
              { height: 8 + Math.round(Math.random() * 24) },
            ]}
          />
        ))}
      </View>
      <Text style={[styles.hint, { color: "#ef4444", fontWeight: "700" }]}>
        🔴 Recording{dots}
      </Text>
      <Text style={styles.sub}>
        Say your name now — {secondsLeft}s remaining
      </Text>
    </View>
  );
}

function DoneContent({ name }: { name: string }) {
  return (
    <View style={styles.center}>
      <Text style={{ fontSize: 48 }}>✅</Text>
      <Text style={[styles.hint, { color: theme.colors.success, fontWeight: "700" }]}>
        Voice enrolled!
      </Text>
      <Text style={styles.sub}>
        Voice sample saved for{" "}
        <Text style={{ fontWeight: "700" }}>{name}</Text>. Your face + voice are
        now linked to your profile.
      </Text>
    </View>
  );
}

// ---- Styles -------------------------------------------------------------- //

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.6)",
    justifyContent: "flex-end",
  },
  sheet: {
    marginHorizontal: 0,
    borderBottomLeftRadius: 0,
    borderBottomRightRadius: 0,
    borderTopLeftRadius: theme.radius.lg,
    borderTopRightRadius: theme.radius.lg,
    paddingBottom: Platform.OS === "ios" ? 32 : 20,
  },
  title: {
    ...theme.typography.title,
    color: theme.colors.text,
    marginBottom: 4,
  },
  sub: {
    color: theme.colors.muted,
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 8,
  },
  hint: {
    color: theme.colors.text,
    fontSize: 14,
    marginTop: 10,
    textAlign: "center",
  },
  center: {
    alignItems: "center",
    gap: 8,
    paddingVertical: 16,
  },
  actions: {
    gap: 10,
    marginTop: 16,
  },
  infoRow: {
    flexDirection: "row",
    gap: 10,
    alignItems: "flex-start",
  },
  emoji: { fontSize: 20, lineHeight: 22 },
  infoText: {
    flex: 1,
    color: theme.colors.text,
    fontSize: 14,
    lineHeight: 20,
  },
  errorText: {
    color: "#ff8a8a",
    textAlign: "center",
    fontSize: 14,
  },
  waveform: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    height: 40,
    marginBottom: 8,
  },
  bar: {
    width: 4,
    borderRadius: 2,
    backgroundColor: "#ef4444",
  },
});
