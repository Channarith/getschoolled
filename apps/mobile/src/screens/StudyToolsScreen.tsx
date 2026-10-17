import { useEffect, useState } from "react";
import { ScrollView, StyleSheet, Text } from "react-native";

import { ORCHESTRATOR_URL } from "../api";
import PrimaryButton from "../components/PrimaryButton";

export default function StudyToolsScreen({
  mode,
  onBack,
}: {
  mode: "homework" | "training";
  onBack: () => void;
}) {
  const [body, setBody] = useState("Loading…");

  useEffect(() => {
    if (mode !== "training") {
      setBody("Homework grading is on. Submit written work from the web homework page while this screen lists the training catalog.");
      return;
    }
    let cancel = false;
    void fetch(`${ORCHESTRATOR_URL}/api/training/capabilities`)
      .then(async (res) => {
        const text = await res.text();
        if (!res.ok) throw new Error(text || "training catalog unavailable");
        return text;
      })
      .then((text) => {
        if (!cancel) setBody(text);
      })
      .catch((err: unknown) => {
        if (!cancel) setBody(err instanceof Error ? err.message : "training catalog unavailable");
      });
    return () => {
      cancel = true;
    };
  }, [mode]);

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <PrimaryButton label="Back" onPress={onBack} variant="ghost" />
      <Text style={styles.title}>{mode === "training" ? "Training" : "Homework"}</Text>
      <Text style={styles.body}>{body}</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: 16, gap: 12 },
  title: { fontSize: 24, fontWeight: "700" },
  body: { fontSize: 14 },
});
