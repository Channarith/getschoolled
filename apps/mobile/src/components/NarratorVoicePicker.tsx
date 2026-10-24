import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { DEFAULT_VOICE_ID, getSelectedVoice, loadCloneVoices, setSelectedVoice, type CloneVoice } from "../cloneVoice";
import { theme } from "../theme";
import AnimatedPressable from "./AnimatedPressable";

/** Narrator voice for the demos: Salane (default) or a consented company voice. Hidden until a voice is published. */
export default function NarratorVoicePicker() {
  const [voices, setVoices] = useState<CloneVoice[]>([]);
  const [choice, setChoice] = useState(DEFAULT_VOICE_ID);

  useEffect(() => {
    let alive = true;
    void (async () => {
      const list = await loadCloneVoices();
      const saved = await getSelectedVoice();
      if (!alive) return;
      setVoices(list);
      setChoice(list.some((v) => v.id === saved) ? saved : DEFAULT_VOICE_ID);
    })();
    return () => { alive = false; };
  }, []);

  if (!voices.length) return null;
  const options = [{ id: DEFAULT_VOICE_ID, label: "Salane (default)", ai_label: "" }, ...voices];
  const current = voices.find((v) => v.id === choice);
  return (
    <View style={styles.wrap} accessibilityRole="radiogroup">
      <Text style={styles.caption}>Narrator voice</Text>
      <View style={styles.row}>
        {options.map((opt) => {
          const selected = choice === opt.id;
          return (
            <AnimatedPressable
              key={opt.id}
              testID={`narrator-voice-${opt.id}`}
              accessibilityRole="button"
              accessibilityState={{ selected }}
              onPress={() => { setChoice(opt.id); void setSelectedVoice(opt.id); }}
              style={[styles.option, selected && styles.optionOn]}
            >
              <Text style={[styles.optionText, selected && styles.optionTextOn]}>{opt.label}</Text>
            </AnimatedPressable>
          );
        })}
      </View>
      {current ? <Text style={styles.note}>{current.ai_label}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginTop: 10, gap: 8 },
  caption: { color: theme.colors.text, fontWeight: "700", fontSize: 14 },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  option: {
    minHeight: 44, paddingVertical: 10, paddingHorizontal: 12, borderRadius: theme.radius.md, borderWidth: 1,
    borderColor: theme.colors.border, backgroundColor: "rgba(29, 39, 70, 0.85)", alignItems: "center", justifyContent: "center",
  },
  optionOn: { borderColor: theme.colors.brand, backgroundColor: "rgba(14, 165, 233, 0.18)" },
  optionText: { color: theme.colors.text, fontWeight: "700", textAlign: "center", lineHeight: 18 },
  optionTextOn: { color: theme.colors.accent },
  note: { color: theme.colors.text, opacity: 0.75, fontSize: 12 },
});
