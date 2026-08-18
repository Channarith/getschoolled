import React, { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { WebView } from "react-native-webview";
import { translateText } from "../api";
import { useT } from "../i18n";

type Props = {
  svg?: string;
  concept?: string;
  translatedConcept?: string;
  examples?: string[];
  activity?: string;
  profileMode?: string;
  fullscreen?: boolean;
  sourceLanguage?: string;
};

function documentFor(svg: string): string {
  return `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"><style>html,body{margin:0;background:#0b1220;overflow:hidden}svg{display:block;width:100%;height:auto}</style></head><body>${svg}</body></html>`;
}

export default function CourseStoryboardView({
  svg = "",
  concept = "",
  translatedConcept = "",
  examples = [],
  activity = "",
  profileMode = "mixed",
  fullscreen = false,
  sourceLanguage = "en",
}: Props) {
  const { locale } = useT();
  const [localized, setLocalized] = useState<{
    concept: string; examples: string[]; activity: string;
  } | null>(null);
  useEffect(() => {
    let active = true;
    if (locale === sourceLanguage) {
      setLocalized(null);
      return () => { active = false; };
    }
    void Promise.all(
      [concept, ...examples, activity].map(async (text) => {
        if (!text) return "";
        try { return (await translateText(text, sourceLanguage, locale)).text; }
        catch { return text; }
      }),
    ).then((values) => {
      if (!active) return;
      setLocalized({
        concept: values[0],
        examples: values.slice(1, 1 + examples.length),
        activity: values[1 + examples.length] || "",
      });
    });
    return () => { active = false; };
  }, [concept, examples.join("\u0000"), activity, locale, sourceLanguage]);
  if (!svg) return null;
  const shownConcept = translatedConcept || localized?.concept || concept;
  const shownExamples = localized?.examples || examples;
  const shownActivity = localized?.activity || activity;
  return (
    <View style={[styles.wrap, fullscreen && styles.fullscreen]} accessibilityLabel={shownConcept}>
      <WebView
        originWhitelist={["*"]}
        source={{ html: documentFor(svg) }}
        style={styles.webview}
        scrollEnabled={false}
        javaScriptEnabled
        pointerEvents="none"
      />
      <View style={styles.caption}>
        <Text style={styles.concept}>{shownConcept}</Text>
        {shownConcept && shownConcept !== concept ? (
          <Text style={styles.source}>{concept}</Text>
        ) : null}
        {shownExamples.length ? (
          <Text style={styles.examples}>Examples: {shownExamples.join(" · ")}</Text>
        ) : null}
        {shownActivity ? <Text style={styles.activity}>🎯 {shownActivity}</Text> : null}
        <Text style={styles.mode}>Adapted for {profileMode.replace(/_/g, " ")} learning</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    width: "100%",
    height: 330,
    borderRadius: 14,
    overflow: "hidden",
    backgroundColor: "#0b1220",
    marginVertical: 10,
  },
  fullscreen: { height: 520 },
  webview: { flex: 1, backgroundColor: "#0b1220" },
  caption: { padding: 10, backgroundColor: "#f8fafc" },
  concept: { color: "#334155", fontWeight: "700", fontSize: 13 },
  source: { color: "#64748b", fontSize: 11, marginTop: 3 },
  examples: { color: "#475569", fontSize: 11, marginTop: 5 },
  activity: { color: "#92400e", fontSize: 11, marginTop: 5 },
  mode: { color: "#64748b", fontSize: 10, marginTop: 5 },
});
