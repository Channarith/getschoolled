/** Mid-class overlay when lighting/blur blocks recognition. */

import { Modal, StyleSheet, Text, View } from "react-native";

import {
  QUALITY_DISCONNECT_SECONDS,
  qualityDisconnectCopy,
  type LightingVerdict,
} from "../cameraLighting";
import { theme } from "../theme";
import PrimaryButton from "./PrimaryButton";

type Props = {
  visible: boolean;
  verdict: LightingVerdict;
  secondsLeft: number;
  onLeaveNow: () => void;
};

export default function CameraQualityGateOverlay({
  visible,
  verdict,
  secondsLeft,
  onLeaveNow,
}: Props) {
  if (!visible) return null;
  const copy = qualityDisconnectCopy(verdict);
  return (
    <Modal visible transparent animationType="fade">
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <Text style={styles.kicker}>Camera check required</Text>
          <Text style={styles.title}>{copy.title}</Text>
          <Text style={styles.body}>{copy.message}</Text>
          {copy.tips.map((tip) => (
            <Text key={tip} style={styles.tip}>
              • {tip}
            </Text>
          ))}
          <Text style={styles.countdown}>
            Leaving class in {secondsLeft}s
          </Text>
          <Text style={styles.meta}>
            Default wait is {QUALITY_DISCONNECT_SECONDS} seconds. Fix lighting or
            focus, then rejoin. Practice in Settings → Camera check.
          </Text>
          <PrimaryButton label="Leave now" onPress={onLeaveNow} />
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(15,23,42,0.72)",
    justifyContent: "center",
    padding: 20,
  },
  card: {
    backgroundColor: theme.colors.panel,
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  kicker: {
    color: "#b45309",
    fontWeight: "700",
    fontSize: 12,
    textTransform: "uppercase",
    letterSpacing: 0.4,
  },
  title: {
    color: theme.colors.text,
    fontSize: 22,
    fontWeight: "700",
    marginTop: 8,
    marginBottom: 8,
  },
  body: { color: theme.colors.text, lineHeight: 20, marginBottom: 8 },
  tip: { color: theme.colors.muted, marginBottom: 2 },
  countdown: {
    color: "#b91c1c",
    fontWeight: "700",
    fontSize: 16,
    marginTop: 12,
    marginBottom: 4,
  },
  meta: { color: theme.colors.muted, fontSize: 12, marginBottom: 14 },
});
