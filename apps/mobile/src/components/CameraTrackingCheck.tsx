/** Settings camera check: permission → live preview → progress → complete.
 *
 * The front camera stays on for the whole check. Pose steps are held in that
 * live view; only the optional ID step grabs one frame, and it does that
 * without opening the system camera.
 */

import { Camera } from "expo-camera";
import { useEffect, useRef, useState } from "react";
import { Image, StyleSheet, Text, View } from "react-native";

import LiveFaceCamera, { type LiveFaceCameraHandle } from "./LiveFaceCamera";
import PrimaryButton from "./PrimaryButton";
import { trackingContinueEnabled } from "../cameraCheck";
import { useT, type StringKey } from "../i18n";
import { cameraPreviewHeight, useLayoutMetrics } from "../layout";
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
  const { widthClass } = useLayoutMetrics();
  const previewHeight = cameraPreviewHeight(widthClass);
  const [stepIndex, setStepIndex] = useState(0);
  const [statusKey, setStatusKey] = useState<StringKey>("camera.begin");
  const [statusRaw, setStatusRaw] = useState("");
  const [busy, setBusy] = useState(false);
  const [permissionOk, setPermissionOk] = useState(false);
  const [passed, setPassed] = useState<Record<string, boolean>>({});
  const [done, setDone] = useState(false);
  const [photoUri, setPhotoUri] = useState<string | null>(null);
  const [cameraReady, setCameraReady] = useState(false);
  const cameraRef = useRef<LiveFaceCameraHandle>(null);

  const step = STEPS[stepIndex];
  const progress = t("camera.stepOf", {
    n: Math.min(stepIndex + 1, STEPS.length),
    total: STEPS.length,
  });

  const facing = step.id === "photo_id" ? "back" : "front";

  useEffect(() => {
    setCameraReady(false);
  }, [facing]);

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
      const perm = await Camera.requestCameraPermissionsAsync();
      setPermissionOk(perm.granted);
      setStatusKey(perm.granted ? "camera.allowed" : "camera.required");
      return perm.granted;
    } catch (e) {
      setStatusRaw((e as Error).message || t("camera.failed"));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const captureId = async () => {
    setBusy(true);
    setStatusRaw("");
    try {
      const frame = await cameraRef.current?.grabFrame();
      if (!frame?.base64) {
        setStatusKey("camera.canceled");
        return;
      }
      setPhotoUri(`data:image/jpeg;base64,${frame.base64}`);
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
      {permissionOk && !done ? (
        <View style={[styles.preview, { height: previewHeight }]}>
          <LiveFaceCamera
            key={facing}
            ref={cameraRef}
            facing={facing}
            onReady={() => setCameraReady(true)}
          />
        </View>
      ) : null}
      {photoUri && step.id === "photo_id" ? (
        <Image source={{ uri: photoUri }} style={[styles.preview, { height: previewHeight }]} />
      ) : null}
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
          disabled={!trackingContinueEnabled(
            step.needsPhoto,
            step.id === "photo_id" ? Boolean(photoUri) : cameraReady,
            busy,
          )}
          testID="camera-tracking-continue"
        />
      ) : null}

      {photoUri && !done ? (
        <View style={styles.saved} pointerEvents="none" accessibilityRole="text">
          <Text style={styles.savedText}>{t("camera.saved")}</Text>
        </View>
      ) : null}

      {permissionOk && !done && step.id === "photo_id" && !photoUri ? (
        <PrimaryButton
          label={busy ? t("camera.working") : t("camera.capture")}
          onPress={() => void captureId()}
          disabled={busy || !cameraReady}
        />
      ) : null}

      {permissionOk && !done && step.needsPhoto ? (
        <PrimaryButton label={t("camera.skip")} variant="ghost" onPress={skipStep} />
      ) : null}

      {done ? <PrimaryButton label={t("camera.done")} onPress={() => onDone?.()} /> : null}
      {photoUri && !done ? (
        <PrimaryButton label={t("camera.retake")} variant="ghost" onPress={() => { setPhotoUri(null); setStatusKey("camera.captureReady"); }} />
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
    overflow: "hidden",
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
