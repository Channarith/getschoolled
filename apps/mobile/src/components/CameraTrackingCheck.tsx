/** Settings camera check: permission → preview/capture → progress → complete.
 *
 * Mobile cannot read live pose from pixels without a native module, so pose
 * steps use a still capture the learner confirms. Lighting and distance use a
 * guided self-check with an explicit continue so the flow never stalls waiting
 * on analysis that cannot run locally.
 */

import * as ImagePicker from "expo-image-picker";
import { useEffect, useMemo, useState } from "react";
import { Image, StyleSheet, Text, View } from "react-native";

import { ensureCameraPermission } from "./cameraPermission";
import PrimaryButton from "./PrimaryButton";
import { theme } from "../theme";

type StepId =
  | "lighting"
  | "distance"
  | "look_up"
  | "look_down"
  | "look_left"
  | "look_right"
  | "raise_hands"
  | "voice"
  | "photo_id";

type Step = { id: StepId; title: string; instruction: string; needsPhoto: boolean };

const STEPS: Step[] = [
  {
    id: "lighting",
    title: "Lighting & focus",
    instruction: "Face a lamp or window so your face is bright and sharp.",
    needsPhoto: false,
  },
  {
    id: "distance",
    title: "Camera distance",
    instruction: "Sit about an arm's length from the camera.",
    needsPhoto: false,
  },
  {
    id: "look_up",
    title: "Look up",
    instruction: "Look toward the ceiling, then take a photo.",
    needsPhoto: true,
  },
  {
    id: "look_down",
    title: "Look down",
    instruction: "Look toward your desk, then take a photo.",
    needsPhoto: true,
  },
  {
    id: "look_left",
    title: "Look left",
    instruction: "Turn toward your left, then take a photo.",
    needsPhoto: true,
  },
  {
    id: "look_right",
    title: "Look right",
    instruction: "Turn toward your right, then take a photo.",
    needsPhoto: true,
  },
  {
    id: "raise_hands",
    title: "Raise both hands",
    instruction: "Raise both hands beside your head, then take a photo.",
    needsPhoto: true,
  },
  {
    id: "voice",
    title: "Voice check",
    instruction: "In class you may be asked to say your name. Tap continue when ready.",
    needsPhoto: false,
  },
  {
    id: "photo_id",
    title: "Photo ID (optional)",
    instruction: "Hold a photo ID to the camera, or skip if you verify later.",
    needsPhoto: true,
  },
];

type Props = {
  onDone?: () => void;
};

export default function CameraTrackingCheck({ onDone }: Props) {
  const [stepIndex, setStepIndex] = useState(0);
  const [status, setStatus] = useState("Tap Allow camera to begin.");
  const [busy, setBusy] = useState(false);
  const [permissionOk, setPermissionOk] = useState(false);
  const [passed, setPassed] = useState<Record<string, boolean>>({});
  const [done, setDone] = useState(false);
  const [photoUri, setPhotoUri] = useState<string | null>(null);

  const step = STEPS[stepIndex];
  const progress = useMemo(
    () => `Step ${Math.min(stepIndex + 1, STEPS.length)} of ${STEPS.length}`,
    [stepIndex],
  );

  useEffect(() => {
    setPhotoUri(null);
    if (step.needsPhoto && permissionOk) {
      setStatus("Tap Capture when you are in position.");
    } else if (!step.needsPhoto && permissionOk) {
      setStatus("Follow the step, then tap Continue.");
    }
  }, [stepIndex, permissionOk, step.needsPhoto]);

  const requestPermission = async (): Promise<boolean> => {
    setBusy(true);
    setStatus("Requesting camera permission…");
    try {
      const picker = await ImagePicker.requestCameraPermissionsAsync();
      if (picker.granted) {
        setPermissionOk(true);
        setStatus(
          step.needsPhoto ? "Tap Capture when you are in position." : "Follow the step, then tap Continue.",
        );
        return true;
      }
      const legacy = await ensureCameraPermission();
      setPermissionOk(legacy);
      setStatus(legacy ? "Camera allowed." : "Camera permission is required.");
      return legacy;
    } finally {
      setBusy(false);
    }
  };

  const capture = async () => {
    setBusy(true);
    setStatus("Opening camera…");
    try {
      const ok = permissionOk || (await requestPermission());
      if (!ok) return;
      const shot = await ImagePicker.launchCameraAsync({
        allowsEditing: false,
        quality: 0.4,
        base64: false,
        exif: false,
        cameraType: ImagePicker.CameraType.front,
      });
      if (shot.canceled || !shot.assets?.[0]?.uri) {
        setStatus("Capture canceled — try again or skip.");
        return;
      }
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
  };

  const skipStep = () => {
    setPhotoUri(null);
    confirmStep();
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

      {!permissionOk && !done ? (
        <PrimaryButton
          label={busy ? "Working…" : "Allow camera"}
          onPress={() => void requestPermission()}
          disabled={busy}
        />
      ) : null}

      {permissionOk && !done && !step.needsPhoto ? (
        <PrimaryButton label="Continue" onPress={confirmStep} />
      ) : null}

      {photoUri && !done ? (
        <PrimaryButton label="Photo matches the step — continue" onPress={confirmStep} />
      ) : null}

      {permissionOk && !done && step.needsPhoto && !photoUri ? (
        <PrimaryButton
          label={busy ? "Working…" : "Capture"}
          onPress={() => void capture()}
          disabled={busy}
        />
      ) : null}

      {permissionOk && !done && step.needsPhoto ? (
        <PrimaryButton label="Skip this step" variant="ghost" onPress={skipStep} />
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
          setPermissionOk(false);
          setStatus("Tap Allow camera to begin.");
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
