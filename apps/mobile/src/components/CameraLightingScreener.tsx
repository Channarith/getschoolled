/** Pre-class camera/lighting gate for mobile lessons. */

import * as ImagePicker from "expo-image-picker";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Image,
  StyleSheet,
  Text,
  View,
} from "react-native";

import {
  DEFAULT_LIGHTING_THRESHOLDS,
  NIGHT_VISION_THRESHOLDS,
  analyzeLuminanceGrid,
  isLightingReady,
  verdictFromMetrics,
  type LightingReadiness,
} from "../cameraLighting";
import { theme } from "../theme";
import AnimatedPressable from "./AnimatedPressable";
import { ensureCameraPermission } from "./cameraPermission";
import PrimaryButton from "./PrimaryButton";

type Props = {
  onReady: () => void;
  title?: string;
};

/**
 * Score an ImagePicker JPEG/PNG base64 payload.
 *
 * React Native has no canvas, so we build a coarse luminance grid from sampled
 * decoded bytes (past the container header). Dark photos cluster low, blown-out
 * photos high; mid-frame variance stands in for "face present". Fail closed when
 * decode fails — never report ready on an empty sample.
 */
export function analyzePhotoBase64(
  base64: string,
  nightVision: boolean,
): LightingReadiness {
  const thresholds = nightVision ? NIGHT_VISION_THRESHOLDS : DEFAULT_LIGHTING_THRESHOLDS;
  let raw: string;
  try {
    const decode =
      (globalThis as { atob?: (s: string) => string }).atob ||
      ((s: string) => {
        // Hermes / RN fallback without Node Buffer typings.
        const chars =
          "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=";
        let output = "";
        let i = 0;
        const str = s.replace(/[^A-Za-z0-9+/=]/g, "");
        while (i < str.length) {
          const enc1 = chars.indexOf(str.charAt(i++));
          const enc2 = chars.indexOf(str.charAt(i++));
          const enc3 = chars.indexOf(str.charAt(i++));
          const enc4 = chars.indexOf(str.charAt(i++));
          const chr1 = (enc1 << 2) | (enc2 >> 4);
          const chr2 = ((enc2 & 15) << 4) | (enc3 >> 2);
          const chr3 = ((enc3 & 3) << 6) | enc4;
          output += String.fromCharCode(chr1);
          if (enc3 !== 64) output += String.fromCharCode(chr2);
          if (enc4 !== 64) output += String.fromCharCode(chr3);
        }
        return output;
      });
    raw = decode(base64);
  } catch {
    const metrics = analyzeLuminanceGrid(
      Array.from({ length: 36 }, () => Array(64).fill(0.05)),
      thresholds,
    );
    return verdictFromMetrics(metrics, { facePresent: false, nightVision, thresholds });
  }

  const samples: number[] = [];
  const step = Math.max(1, Math.floor(raw.length / 4096));
  for (let i = 256; i < raw.length; i += step) {
    samples.push(raw.charCodeAt(i) / 255);
  }
  const gridW = 64;
  const gridH = 36;
  const grid: number[][] = [];
  if (samples.length < 64) {
    for (let y = 0; y < gridH; y++) grid.push(Array(gridW).fill(0.05));
  } else {
    for (let y = 0; y < gridH; y++) {
      const row: number[] = [];
      for (let x = 0; x < gridW; x++) {
        row.push(samples[(y * gridW + x) % samples.length]);
      }
      grid.push(row);
    }
  }
  const metrics = analyzeLuminanceGrid(grid, thresholds);
  const mid = grid.slice(8, 28).flatMap((row) => row.slice(16, 48));
  const mean = mid.reduce((a, b) => a + b, 0) / Math.max(1, mid.length);
  const variance =
    mid.reduce((a, b) => a + (b - mean) ** 2, 0) / Math.max(1, mid.length);
  const facePresent = variance > 0.002 && mean > 0.08 && mean < 0.92;
  return verdictFromMetrics(metrics, { facePresent, nightVision, thresholds });
}

export default function CameraLightingScreener({
  onReady,
  title = "Camera and lighting check",
}: Props) {
  const [nightVision, setNightVision] = useState(false);
  const [busy, setBusy] = useState(false);
  const [previewUri, setPreviewUri] = useState<string | null>(null);
  const [readiness, setReadiness] = useState<LightingReadiness | null>(null);
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
        base64: true,
        exif: false,
        allowsEditing: false,
      });
      if (shot.canceled || !shot.assets?.[0]) return;
      const asset = shot.assets[0];
      setPreviewUri(asset.uri);
      if (!asset.base64) {
        setError("Could not read the photo. Try again.");
        return;
      }
      setReadiness(analyzePhotoBase64(asset.base64, nightVision));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Camera check failed");
    } finally {
      setBusy(false);
    }
  }, [nightVision]);

  const ready = readiness ? isLightingReady(readiness.verdict) : false;

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.body}>
        Take a clear face photo before class. Too dark, washed out, or blurry
        cameras cannot track attention reliably.
      </Text>

      {previewUri ? (
        <Image source={{ uri: previewUri }} style={styles.preview} />
      ) : (
        <View style={[styles.preview, styles.previewEmpty]}>
          <Text style={styles.muted}>No photo yet</Text>
        </View>
      )}

      {error ? <Text style={styles.error}>{error}</Text> : null}

      {readiness ? (
        <View style={styles.result}>
          <Text style={styles.verdict}>{readiness.verdict.replace(/_/g, " ")}</Text>
          <Text style={styles.body}>{readiness.message}</Text>
          {nightVision ? <Text style={styles.badge}>Night vision</Text> : null}
        </View>
      ) : null}

      <AnimatedPressable
        onPress={() => {
          setNightVision((v) => !v);
          setReadiness(null);
        }}
        style={styles.toggle}
      >
        <Text style={styles.toggleText}>
          {nightVision ? "☑" : "☐"} Enable Night vision (low light only)
        </Text>
      </AnimatedPressable>

      {busy ? (
        <ActivityIndicator color={theme.colors.accent} style={{ marginVertical: 12 }} />
      ) : (
        <PrimaryButton label="Open camera & check" onPress={() => void capture()} />
      )}

      <View style={{ marginTop: 10 }}>
        <PrimaryButton
          label="Continue to class"
          onPress={onReady}
          disabled={!ready || busy}
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
  result: { gap: 4, marginTop: 4 },
  verdict: {
    alignSelf: "flex-start",
    backgroundColor: theme.colors.accent,
    color: "#fff",
    overflow: "hidden",
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
    fontSize: 12,
    fontWeight: "700",
    textTransform: "uppercase",
  },
  badge: {
    alignSelf: "flex-start",
    backgroundColor: "#14532d",
    color: "#bbf7d0",
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
    fontSize: 12,
    fontWeight: "700",
  },
  toggle: { paddingVertical: 8 },
  toggleText: { color: theme.colors.text, fontSize: 14 },
});
