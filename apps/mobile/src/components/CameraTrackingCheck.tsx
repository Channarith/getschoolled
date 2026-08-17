/** Settings camera check: lighting + look up/down/left/right + raise hands.
 *
 * The previous build synthesized a "face grid" from the current step id and
 * then matched the pose against it — every photo passed every step (integrity
 * theater). Mobile has no pixel-level pose access without a native module, so
 * the check is now a guided self-verify: capture per step, see the photo, and
 * confirm the pose was captured. That still walks the learner through every
 * tracking dimension their camera must cover.
 */

import * as ImagePicker from "expo-image-picker";
import { useMemo, useState } from "react";
import { Image, StyleSheet, Text, View } from "react-native";

import { ensureCameraPermission } from "./cameraPermission";
import PrimaryButton from "./PrimaryButton";
import { theme } from "../theme";

type StepId = "lighting" | "look_up" | "look_down" | "look_left" | "look_right" | "raise_hands";

type Step = { id: StepId; title: string; instruction: string };

const STEPS: Step[] = [
  {
    id: "lighting",
    title: "Lighting & focus",
    instruction: "Take a clear, well-lit face photo. Avoid dark rooms and blur.",
  },
  {
    id: "look_up",
    title: "Look up",
    instruction: "Look toward the ceiling, then take a photo.",
  },
  {
    id: "look_down",
    title: "Look down",
    instruction: "Look toward your desk, then take a photo.",
  },
  {
    id: "look_left",
    title: "Look left",
    instruction: "Turn toward your left, then take a photo.",
  },
  {
    id: "look_right",
    title: "Look right",
    instruction: "Turn toward your right, then take a photo.",
  },
  {
    id: "raise_hands",
    title: "Raise both hands",
    instruction: "Raise both hands beside your head, then take a photo.",
  },
];

type Props = {
  onDone?: () => void;
};

export default function CameraTrackingCheck({ onDone }: Props) {
  const [stepIndex, setStepIndex] = useState(0);
  const [status, setStatus] = useState("Tap Capture to begin.");
  const [busy, setBusy] = useState(false);
  const [passed, setPassed] = useState<Record<string, boolean>>({});
  const [done, setDone] = useState(false);
  const [photoUri, setPhotoUri] = useState<string | null>(null);

  const step = STEPS[stepIndex];
  const progress = useMemo(
    () => `Step ${Math.min(stepIndex + 1, STEPS.length)} of ${STEPS.length}`,
    [stepIndex],
  );

  const capture = async () => {
    setBusy(true);
    setStatus("Opening camera…");
    try {
      const ok = await ensureCameraPermission();
      if (!ok) {
        setStatus("Camera permission is required.");
        return;
      }
      const shot = await ImagePicker.launchCameraAsync({
        allowsEditing: false,
        quality: 0.4,
        base64: false,
        exif: false,
      });
      if (shot.canceled || !shot.assets?.[0]?.uri) {
        setStatus("Capture canceled — try again.");
        return;
      }
      // Show the photo and let the learner confirm the pose — the app cannot
      // measure pose from a compressed file without a native decoder.
      setPhotoUri(shot.assets[0].uri);
      setStatus("Check the photo, then confirm below.");
    } catch (e) {
      setStatus((e as Error).message || "Camera check failed.");
    } finally {
      setBusy(false);
    }
  };

  const confirmStep = () => {
    setPassed((p) => ({ ...p, [step.id]: true }));
    setPhotoUri(null);
    if (stepIndex + 1 >= STEPS.length) {
      setDone(true);
      setStatus("All checks complete — your camera covers every tracking angle.");
      onDone?.();
      return;
    }
    setStepIndex((i) => i + 1);
    setStatus("Tap Capture for the next step.");
  };

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>Camera & tracking check</Text>
      <Text style={styles.meta}>
        Solo and group classes need a clear camera for presence, attention, movement,
        and integrity tracking.
      </Text>
      <Text style={styles.progress}>{progress}</Text>
      <Text style={styles.stepTitle}>{step.title}</Text>
      <Text style={styles.instruction}>{step.instruction}</Text>
      {photoUri ? <Image source={{ uri: photoUri }} style={styles.preview} /> : null}
      <Text style={styles.status}>{status}</Text>
      <View style={styles.list}>
        {STEPS.map((s, i) => (
          <Text key={s.id} style={styles.listItem}>
            {passed[s.id] ? "✓ " : i === stepIndex ? "→ " : "  "}
            {s.title}
          </Text>
        ))}
      </View>
      {photoUri && !done ? (
        <PrimaryButton label="Photo matches the step — continue" onPress={confirmStep} />
      ) : null}
      {!done && !photoUri ? (
        <PrimaryButton
          label={busy ? "Working…" : "Capture"}
          onPress={() => void capture()}
          disabled={busy}
        />
      ) : null}
      {done ? <PrimaryButton label="Done" onPress={() => onDone?.()} /> : null}
      {photoUri && !done ? (
        <PrimaryButton label="Retake" variant="ghost" onPress={() => void capture()} />
      ) : null}
      <PrimaryButton
        label="Restart"
        variant="ghost"
        onPress={() => {
          setStepIndex(0);
          setPassed({});
          setDone(false);
          setPhotoUri(null);
          setStatus("Tap Capture to begin.");
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 8 },
  title: { color: theme.colors.text, fontSize: 18, fontWeight: "700" },
  meta: { color: theme.colors.muted, fontSize: 13, lineHeight: 18 },
  progress: { color: theme.colors.accent, fontWeight: "600", marginTop: 4 },
  stepTitle: { color: theme.colors.text, fontSize: 16, fontWeight: "700" },
  instruction: { color: theme.colors.text, lineHeight: 20 },
  preview: {
    width: "100%",
    height: 200,
    borderRadius: 10,
    backgroundColor: "#0b1220",
    marginVertical: 6,
  },
  status: { color: theme.colors.muted, fontSize: 13 },
  list: { marginVertical: 6 },
  listItem: { color: theme.colors.muted, fontSize: 13, marginBottom: 2 },
});
