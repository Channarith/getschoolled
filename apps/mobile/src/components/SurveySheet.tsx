import { useState } from "react";
import {
  Modal, ScrollView, StyleSheet, Switch, Text, TextInput, View,
} from "react-native";

import type { SurveyTemplate } from "../api";
import AnimatedPressable from "./AnimatedPressable";
import GlassPanel from "./GlassPanel";
import PrimaryButton from "./PrimaryButton";
import { theme } from "../theme";

type Props = {
  visible: boolean;
  template: SurveyTemplate | null;
  busy?: boolean;
  onSubmit: (answers: Record<string, string | number | boolean>) => void;
  onClose: () => void;
};

export default function SurveySheet({ visible, template, busy, onSubmit, onClose }: Props) {
  const [answers, setAnswers] = useState<Record<string, string | number | boolean>>({});

  if (!template) return null;

  function setAnswer(id: string, value: string | number | boolean) {
    setAnswers((prev) => ({ ...prev, [id]: value }));
  }

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.scrim}>
        <GlassPanel style={styles.card}>
          <ScrollView contentContainerStyle={{ gap: 12 }}>
            <Text style={styles.title}>{template.title}</Text>
            {template.subtitle ? <Text style={styles.sub}>{template.subtitle}</Text> : null}
            {template.questions.map((q) => (
              <View key={q.id} style={styles.q}>
                <Text style={styles.prompt}>{q.prompt}{q.required ? " *" : ""}</Text>
                {q.type === "bool" ? (
                  <Switch
                    value={Boolean(answers[q.id])}
                    onValueChange={(v) => setAnswer(q.id, v)}
                  />
                ) : q.type === "choice" && q.options ? (
                  <View style={styles.opts}>
                    {q.options.map((opt) => {
                      const on = answers[q.id] === opt;
                      return (
                        <AnimatedPressable
                          key={opt}
                          onPress={() => setAnswer(q.id, opt)}
                          style={[styles.opt, on && styles.optOn]}
                        >
                          <Text style={[styles.optText, on && styles.optTextOn]}>{opt}</Text>
                        </AnimatedPressable>
                      );
                    })}
                  </View>
                ) : q.type === "rating" ? (
                  <View style={styles.opts}>
                    {[1, 2, 3, 4, 5].map((n) => {
                      const on = Number(answers[q.id]) === n;
                      return (
                        <AnimatedPressable
                          key={n}
                          onPress={() => setAnswer(q.id, n)}
                          style={[styles.rate, on && styles.optOn]}
                        >
                          <Text style={[styles.optText, on && styles.optTextOn]}>{n}</Text>
                        </AnimatedPressable>
                      );
                    })}
                  </View>
                ) : (
                  <TextInput
                    style={styles.input}
                    value={String(answers[q.id] ?? "")}
                    onChangeText={(v) => setAnswer(q.id, v)}
                    placeholderTextColor={theme.colors.muted}
                    multiline
                  />
                )}
              </View>
            ))}
            <PrimaryButton
              label="Submit"
              onPress={() => onSubmit(answers)}
              loading={busy}
              disabled={busy}
              variant="netflix"
            />
            <PrimaryButton label="Skip" onPress={onClose} variant="ghost" />
          </ScrollView>
        </GlassPanel>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  scrim: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.65)",
    justifyContent: "flex-end",
    padding: 16,
    paddingBottom: 32,
  },
  card: { maxHeight: "85%" },
  title: { color: theme.colors.text, fontSize: 20, fontWeight: "800" },
  sub: { color: theme.colors.muted, fontSize: 14, lineHeight: 20 },
  q: { gap: 8 },
  prompt: { color: theme.colors.text, fontSize: 14, fontWeight: "700" },
  opts: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  opt: {
    borderRadius: theme.radius.pill,
    borderWidth: 1,
    borderColor: theme.colors.border,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  optOn: { borderColor: theme.colors.netflix, backgroundColor: "rgba(229,9,20,0.15)" },
  optText: { color: theme.colors.muted, fontSize: 13, fontWeight: "600" },
  optTextOn: { color: "#fff" },
  rate: {
    width: 40, height: 40, borderRadius: 20, alignItems: "center", justifyContent: "center",
    borderWidth: 1, borderColor: theme.colors.border,
  },
  input: {
    borderWidth: 1, borderColor: theme.colors.border, borderRadius: 10,
    padding: 12, color: theme.colors.text, backgroundColor: "rgba(0,0,0,0.2)",
    minHeight: 44,
  },
});
