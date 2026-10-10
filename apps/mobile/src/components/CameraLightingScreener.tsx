/** Pre-class camera & lighting check (mobile).
 *
 * Mobile has no pixel-level frame access without a native module, and the old
 * implementation scored the JPEG's *compressed file bytes* as if they were
 * pixels — entropy-coded data reads as simultaneously under- and over-exposed,
 * so typical users were locked out (and accidental passes were fail-open).
 * The honest gate: verify camera permission and show the learner their own
 * preview. Saving the photo turns Continue on. The green row is a status,
 * not a second tap.
 */

import * as ImagePicker from "expo-image-picker";
import { useCallback, useState } from "react";
import { ActivityIndicator, Image, StyleSheet, Text, View } from "react-native";

import { cameraContinueEnabled } from "../cameraCheck";
import { ensureCameraPermission } from "./cameraPermission";
import PrimaryButton from "./PrimaryButton";
import { useT } from "../i18n";
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
  const [busy, setBusy] = useState(false);
  const [previewUri, setPreviewUri] = useState<string | null>(null);
  const [error, setError] = useState("");

  const capture = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const allowed = await ensureCameraPermission();
      if (!allowed) {
        setError(t("camera.permission"));
        return;
      }
      const perm = await ImagePicker.requestCameraPermissionsAsync();
      if (!perm.granted) {
        setError(t("camera.permission"));
        return;
      }
      const shot = await ImagePicker.launchCameraAsync({
        quality: 0.45,
        base64: false,
        exif: false,
        allowsEditing: false,
      });
      if (shot.canceled || !shot.assets?.[0]) return;
      setPreviewUri(shot.assets[0].uri);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("camera.failed"));
    } finally {
      setBusy(false);
    }
  }, [t]);

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>{heading}</Text>
      <Text style={styles.body}>{t("camera.body")}</Text>

      {previewUri ? (
        <Image source={{ uri: previewUri }} style={styles.preview} />
      ) : (
        <View style={[styles.preview, styles.previewEmpty]}>
          <Text style={styles.muted}>{t("camera.empty")}</Text>
        </View>
      )}

      {error ? <Text style={styles.error}>{error}</Text> : null}

      {previewUri ? (
        <View style={styles.confirm} pointerEvents="none" accessibilityRole="text">
          <Text style={styles.confirmText}>{t("camera.saved")}</Text>
        </View>
      ) : null}

      <View style={{ marginTop: 10 }}>
        <PrimaryButton
          label={t("camera.continue")}
          onPress={onReady}
          disabled={!cameraContinueEnabled(Boolean(previewUri), busy)}
          variant="netflix"
          testID="camera-continue"
        />
      </View>

      {busy ? (
        <ActivityIndicator color={theme.colors.accent} style={{ marginVertical: 12 }} />
      ) : (
        <PrimaryButton
          label={previewUri ? t("camera.retake") : t("camera.open")}
          onPress={() => void capture()}
          variant={previewUri ? "ghost" : "netflix"}
        />
      )}
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
