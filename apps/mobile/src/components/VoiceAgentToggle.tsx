import { StyleSheet, Text, View } from "react-native";

import { useT, type StringKey } from "../i18n";
import { theme } from "../theme";
import type { VoiceAgentChoice } from "../voiceAgentPref";
import AnimatedPressable from "./AnimatedPressable";

type VoicePhase = "idle" | "checking" | "live" | "unavailable";

/** Button label for the lesson voice control. English strings fall back in i18n. */
export function lessonVoiceButtonKey(
  agent: VoiceAgentChoice,
  voiceOn: boolean,
  phase: VoicePhase,
): StringKey {
  if (!voiceOn) return agent === "xai" ? "lesson.xaiOff" : "lesson.salaOff";
  if (agent === "xai" && phase === "unavailable") return "lesson.xaiUnavailable";
  if (phase === "live") return agent === "xai" ? "lesson.xaiOn" : "lesson.salaOn";
  return agent === "xai" ? "lesson.xaiStarting" : "lesson.salaStarting";
}

type Props = {
  value: VoiceAgentChoice;
  onChange: (next: VoiceAgentChoice) => void;
};

export default function VoiceAgentToggle({ value, onChange }: Props) {
  const { t } = useT();
  const options: { id: VoiceAgentChoice; label: string; testID: string }[] = [
    { id: "sala", label: t("settings.voiceAgentSala"), testID: "voice-agent-sala" },
    { id: "xai", label: t("settings.voiceAgentXai"), testID: "voice-agent-xai" },
  ];
  return (
    <View style={styles.wrap} accessibilityRole="radiogroup">
      <Text style={styles.caption}>{t("settings.voiceAgent")}</Text>
      <View style={styles.row}>
        {options.map((opt) => {
          const selected = value === opt.id;
          return (
            <AnimatedPressable
              key={opt.id}
              testID={opt.testID}
              accessibilityRole="button"
              accessibilityState={{ selected }}
              onPress={() => onChange(opt.id)}
              style={[styles.option, selected && styles.optionOn]}
            >
              <Text style={[styles.optionText, selected && styles.optionTextOn]}>{opt.label}</Text>
            </AnimatedPressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginTop: 10, gap: 8 },
  caption: { color: theme.colors.text, fontWeight: "700", fontSize: 14 },
  row: { flexDirection: "row", gap: 8 },
  option: {
    flex: 1,
    minHeight: 44,
    paddingVertical: 10,
    paddingHorizontal: 8,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: theme.colors.border,
    backgroundColor: "rgba(29, 39, 70, 0.85)",
    alignItems: "center",
    justifyContent: "center",
  },
  optionOn: {
    borderColor: theme.colors.brand,
    backgroundColor: "rgba(14, 165, 233, 0.18)",
  },
  optionText: {
    color: theme.colors.text,
    fontWeight: "700",
    textAlign: "center",
    lineHeight: 18,
  },
  optionTextOn: { color: theme.colors.accent },
});
