/** Settings camera check: permission → preview/capture → progress → complete.
 *
 * Mobile cannot read live pose from pixels without a native module, so pose
 * steps use a still capture the learner confirms. Lighting and distance use a
 * guided self-check with an explicit continue so the flow never stalls waiting
 * on analysis that cannot run locally.
 */

import * as ImagePicker from "expo-image-picker";
import { useEffect, useState } from "react";
import { Image, StyleSheet, Text, View } from "react-native";

import { ensureCameraPermission } from "./cameraPermission";
import PrimaryButton from "./PrimaryButton";
import { trackingContinueEnabled } from "../cameraCheck";
import { useT, type StringKey } from "../i18n";
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

type Step = { id: StepId; title: StringKey; instruction: StringKey; needsPhoto: boolean };

const STEPS: Step[] = [
  { id: "lighting", title: "camera.lightTitle", instruction: "camera.lightBody", needsPhoto: false },
  { id: "distance", title: "camera.distanceTitle", instruction: "camera.distanceBody", needsPhoto: false },
  { id: "look_up", title: "camera.lookUpTitle", instruction: "camera.lookUpBody", needsPhoto: true },
  { id: "look_down", title: "camera.lookDownTitle", instruction: "camera.lookDownBody", needsPhoto: true },
  { id: "look_left", title: "camera.lookLeftTitle", instruction: "camera.lookLeftBody", needsPhoto: true },
  { id: "look_right", title: "camera.lookRightTitle", instruction: "camera.lookRightBody", needsPhoto: true },
  { id: "raise_hands", title: "camera.handsTitle", instruction: "camera.handsBody", needsPhoto: true },
  { id: "voice", title: "camera.voiceTitle", instruction: "camera.voiceBody", needsPhoto: false },
  { id: "photo_id", title: "camera.photoIdTitle", instruction: "camera.photoIdBody", needsPhoto: true },
];

type Props = {
  onDone?: () => void;
};

export default function CameraTrackingCheck({ onDone }: Props) {
  const { t } = useT();
  const [stepIndex, setStepIndex] = useState(0);
  const [statusKey, setStatusKey] = useState<StringKey>("camera.begin");
  const [statusRaw, setStatusRaw] = useState("");
  const [busy, setBusy] = useState(false);
  const [permissionOk, setPermissionOk] = useState(false);
  const [passed, setPassed] = useState<Record<string, boolean>>({});
  const [done, setDone] = useState(false);
  const [photoUri, setPhotoUri] = useState<string | null>(null);

  const step = STEPS[stepIndex];
  const progress = t("camera.stepOf", {
    n: Math.min(stepIndex + 1, STEPS.length),
    total: STEPS.length,
  });

  useEffect(() => {
    setPhotoUri(null);
    if (!permissionOk) return;
    setStatusRaw("");
    setStatusKey(step.needsPhoto ? "camera.captureReady" : "camera.follow");
  }, [stepIndex, permissionOk, step.needsPhoto]);

  const requestPermission = async (): Promise<boolean> => {
    setBusy(true);
    setStatusRaw("");
    setStatusKey("camera.requesting");
    try {
      const picker = await ImagePicker.requestCameraPermissionsAsync();
      if (picker.granted) {
        setPermissionOk(true);
        setStatusKey(step.needsPhoto ? "camera.captureReady" : "camera.follow");
        return true;
      }
      const legacy = await ensureCameraPermission();
      setPermissionOk(legacy);
      setStatusKey(legacy ? "camera.allowed" : "camera.required");
      return legacy;
    } finally {
      setBusy(false);
    }
  };

  const capture = async () => {
    setBusy(true);
    setStatusRaw("");
    setStatusKey("camera.opening");
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
        setStatusKey("camera.canceled");
        return;
      }
      setPhotoUri(shot.assets[0].uri);
      setStatusKey("camera.checkPhoto");
    } catch (e) {
      setStatusRaw((e as Error).message || t("camera.failed"));
    } finally {
      setBusy(false);
    }
  };

  const confirmStep = () => {
    setPassed((p) => ({ ...p, [step.id]: true }));
    setPhotoUri(null);
    if (stepIndex + 1 >= STEPS.length) {
      setDone(true);
      setStatusRaw("");
      setStatusKey("camera.complete");
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
      <Text style={styles.title}>{t("camera.trackTitle")}</Text>
      <Text style={styles.meta}>{t("camera.meta")}</Text>
      <Text style={styles.progress}>{progress}</Text>
      <Text style={styles.stepTitle}>{t(step.title)}</Text>
      <Text style={styles.instruction}>{t(step.instruction)}</Text>
      {photoUri ? <Image source={{ uri: photoUri }} style={styles.preview} /> : null}
      <Text style={styles.status}>{statusRaw || t(statusKey)}</Text>
      <View style={styles.list}>
        {STEPS.map((s, i) => (
          <Text key={s.id} style={styles.listItem}>
            {passed[s.id] ? "✓ " : i === stepIndex ? "→ " : "  "}
            {t(s.title)}
          </Text>
        ))}
      </View>

      {!permissionOk && !done ? (
        <PrimaryButton
          label={busy ? t("camera.working") : t("camera.allow")}
          onPress={() => void requestPermission()}
          disabled={busy}
        />
      ) : null}

      {permissionOk && !done ? (
        <PrimaryButton
          label={t("camera.continue")}
          onPress={confirmStep}
          disabled={!trackingContinueEnabled(step.needsPhoto, Boolean(photoUri), busy)}
          testID="camera-tracking-continue"
        />
      ) : null}

      {photoUri && !done ? (
        <View style={styles.saved} pointerEvents="none" accessibilityRole="text">
          <Text style={styles.savedText}>{t("camera.saved")}</Text>
        </View>
      ) : null}

      {permissionOk && !done && step.needsPhoto && !photoUri ? (
        <PrimaryButton
          label={busy ? t("camera.working") : t("camera.capture")}
          onPress={() => void capture()}
          disabled={busy}
        />
      ) : null}

      {permissionOk && !done && step.needsPhoto ? (
        <PrimaryButton label={t("camera.skip")} variant="ghost" onPress={skipStep} />
      ) : null}

      {done ? <PrimaryButton label={t("camera.done")} onPress={() => onDone?.()} /> : null}
      {photoUri && !done ? (
        <PrimaryButton label={t("camera.retake")} variant="ghost" onPress={() => void capture()} />
      ) : null}
      <PrimaryButton
        label={t("camera.restart")}
        variant="ghost"
        onPress={() => {
          setStepIndex(0);
          setPassed({});
          setDone(false);
          setPhotoUri(null);
          setPermissionOk(false);
          setStatusRaw("");
          setStatusKey("camera.begin");
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
  listItem: { color: theme.colors.muted, fontSize: 13, marginBottom: 2, lineHeight: 18, includeFontPadding: false },
  saved: {
    backgroundColor: "#14532d",
    borderRadius: 8,
    padding: 10,
  },
  savedText: {
    color: "#bbf7d0",
    fontSize: 14,
    fontWeight: "600",
    lineHeight: 18,
    includeFontPadding: false,
  },
});
