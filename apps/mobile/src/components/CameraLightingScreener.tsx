/** Pre-class camera & lighting check (mobile).
 *
 * Mobile has no pixel-level frame access without a native module, and the old
 * implementation scored the JPEG's *compressed file bytes* as if they were
 * pixels — entropy-coded data reads as simultaneously under- and over-exposed,
 * so typical users were locked out (and accidental passes were fail-open).
 * The honest gate: verify camera permission, show the learner their own
 * preview, and let them confirm they look clear before class.
 */

import * as ImagePicker from "expo-image-picker";
import { useCallback, useState } from "react";
import { ActivityIndicator, Image, StyleSheet, Text, View } from "react-native";

import AnimatedPressable from "./AnimatedPressable";
import { ensureCameraPermission } from "./cameraPermission";
import PrimaryButton from "./PrimaryButton";
import { theme } from "../theme";

type Props = {
  onReady: () => void;
  title?: string;
};

export default function CameraLightingScreener({
  onReady,
  title = "Camera and lighting check",
}: Props) {
  const [busy, setBusy] = useState(false);
  const [previewUri, setPreviewUri] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState("");

  const capture = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const allowed = await ensureCameraPermission();
      if (!allowed) {
        setError("Camera permission is required for class.");
        return;
      }
      const perm = await ImagePicker.requestCameraPermissionsAsync();
      if (!perm.granted) {
        setError("Camera permission is required for class.");
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
      setConfirmed(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Camera check failed");
    } finally {
      setBusy(false);
    }
  }, []);

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.body}>
        Take a face photo before class and check it: your face should be clearly
        visible, well lit, and sharp. Dark or blurry cameras cannot track
        attention reliably.
      </Text>

      {previewUri ? (
        <Image source={{ uri: previewUri }} style={styles.preview} />
      ) : (
        <View style={[styles.preview, styles.previewEmpty]}>
          <Text style={styles.muted}>No photo yet</Text>
        </View>
      )}

      {error ? <Text style={styles.error}>{error}</Text> : null}

      {previewUri && !confirmed ? (
        <AnimatedPressable
          onPress={() => setConfirmed(true)}
          style={styles.confirm}
        >
          <Text style={styles.confirmText}>
            ☑ My face is clearly visible in this photo
          </Text>
        </AnimatedPressable>
      ) : null}

      {busy ? (
        <ActivityIndicator color={theme.colors.accent} style={{ marginVertical: 12 }} />
      ) : (
        <PrimaryButton
          label={previewUri ? "Retake photo" : "Open camera & check"}
          onPress={() => void capture()}
        />
      )}

      <View style={{ marginTop: 10 }}>
        <PrimaryButton
          label="Continue to class"
          onPress={onReady}
          disabled={!confirmed || busy}
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
  confirmText: { color: "#bbf7d0", fontSize: 14, fontWeight: "600" },
});
