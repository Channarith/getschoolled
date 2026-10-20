/** Pre-class camera & lighting check (mobile).
 *
 * The camera stays on, like a video call. Continue turns on once that live
 * preview is actually showing — there is no still to take.
 */

import { Camera } from "expo-camera";
import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { cameraContinueEnabled } from "../cameraCheck";
import LiveFaceCamera from "./LiveFaceCamera";
import PrimaryButton from "./PrimaryButton";
import { useT } from "../i18n";
import { cameraPreviewHeight, useLayoutMetrics } from "../layout";
import { theme } from "../theme";

type Props = {
  onReady: () => void;
  title?: string;
};

export default function CameraLightingScreener({
  onReady,
  title,
}: Props) {
  const { t } = useT();
  const heading = title || t("camera.title");
  const { widthClass } = useLayoutMetrics();
  const previewHeight = cameraPreviewHeight(widthClass);
  const [allowed, setAllowed] = useState(false);
  const [live, setLive] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let current = true;
    Camera.requestCameraPermissionsAsync().then((perm) => {
      if (!current) return;
      if (!perm.granted) setError(t("camera.permission"));
      else setAllowed(true);
    }).catch((e: unknown) => {
      if (!current) return;
      setError(e instanceof Error ? e.message : t("camera.failed"));
    });
    return () => { current = false; };
  }, [t]);

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>{heading}</Text>
      <Text style={styles.body}>{t("camera.body")}</Text>

      {allowed ? (
        <View style={[styles.preview, { height: previewHeight }]}>
          <LiveFaceCamera onReady={() => setLive(true)} onError={(message) => setError(message)} />
        </View>
      ) : (
        <View style={[styles.preview, styles.previewEmpty, { height: previewHeight }]}>
          <Text style={styles.muted}>{error || t("camera.empty")}</Text>
        </View>
      )}

      {error && allowed ? <Text style={styles.error}>{error}</Text> : null}

      {live ? (
        <View style={styles.confirm} pointerEvents="none" accessibilityRole="text">
          <Text style={styles.confirmText}>{t("camera.saved")}</Text>
        </View>
      ) : null}

      <View style={{ marginTop: 10 }}>
        <PrimaryButton
          label={t("camera.continue")}
          onPress={onReady}
          disabled={!cameraContinueEnabled(live, false)}
          variant="netflix"
          testID="camera-continue"
        />
        <PrimaryButton
          label={t("camera.skip")}
          onPress={onReady}
          variant="ghost"
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { padding: 16, gap: 8 },
  title: { fontSize: 20, fontWeight: "700", color: theme.colors.text },
  body: { fontSize: 14, color: theme.colors.muted, lineHeight: 20 },
  muted: { color: theme.colors.muted },
  preview: {
    width: "100%",
    height: 220,
    borderRadius: 10,
    overflow: "hidden",
    backgroundColor: "#0b1220",
    marginVertical: 8,
  },
  previewEmpty: { alignItems: "center", justifyContent: "center" },
  error: { color: "#ef4444", marginVertical: 4 },
  confirm: {
    backgroundColor: "#14532d",
    borderRadius: 8,
    padding: 10,
    marginTop: 4,
  },
  confirmText: {
    color: "#bbf7d0",
    fontSize: 14,
    fontWeight: "600",
    lineHeight: 18,
    includeFontPadding: false,
  },
});
