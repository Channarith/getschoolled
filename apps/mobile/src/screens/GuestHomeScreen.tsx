import { useState } from "react";
import {
  Image, Pressable, ScrollView, StyleSheet, Text, View,
} from "react-native";

import AuthScreen from "./AuthScreen";
import DemoWebScreen from "./DemoWebScreen";
import { useAndroidBack } from "../hooks/useAndroidBack";
import { useT } from "../i18n";
import { MASCOT_IMAGES } from "../mascots/imageAssets";
import { PUBLIC_DEMOS, type PublicDemo } from "../publicDemos";
import { theme } from "../theme";

type Step = "landing" | "demos" | "login";

export default function GuestHomeScreen() {
  const { t, locale } = useT();
  const [step, setStep] = useState<Step>("landing");
  const [demo, setDemo] = useState<PublicDemo | null>(null);
  const mascot = MASCOT_IMAGES[locale] ?? MASCOT_IMAGES.en;

  useAndroidBack(() => {
    if (demo) {
      setDemo(null);
      return true;
    }
    if (step !== "landing") {
      setStep("landing");
      return true;
    }
    return false;
  });

  if (demo) {
    return <DemoWebScreen demo={demo} onBack={() => setDemo(null)} />;
  }
  if (step === "login") {
    return <AuthScreen onBack={() => setStep("landing")} />;
  }
  if (step === "demos") {
    return (
      <ScrollView
        testID="guest-demos"
        contentContainerStyle={styles.demoContent}
        style={styles.fill}
      >
        <Pressable onPress={() => setStep("landing")} testID="guest-back" hitSlop={8}>
          <Text style={styles.back}>{t("guest.back")}</Text>
        </Pressable>
        <Image source={mascot} style={styles.mascotSmall} resizeMode="contain" accessibilityIgnoresInvertColors />
        <Text style={styles.kicker}>{t("guest.kicker")}</Text>
        {PUBLIC_DEMOS.map((item) => (
          <Pressable
            key={item.id}
            testID={`guest-demo-${item.id}`}
            style={styles.card}
            onPress={() => setDemo(item)}
          >
            <Text style={styles.emoji}>{item.emoji}</Text>
            <Text style={styles.cardTitle}>{item.title}</Text>
            <Text style={styles.cardSubtitle}>{item.subtitle}</Text>
            <Text style={styles.cardBody}>{item.description}</Text>
          </Pressable>
        ))}
      </ScrollView>
    );
  }

  return (
    <View testID="guest-landing" style={styles.landing}>
      <Text style={styles.brand}>Salareen</Text>
      <Image
        source={mascot}
        style={styles.mascot}
        resizeMode="contain"
        accessibilityLabel="Salareen mascot"
      />
      <Text style={styles.kicker}>{t("guest.kicker")}</Text>
      <Pressable
        testID="guest-try-demo"
        style={styles.primary}
        onPress={() => setStep("demos")}
      >
        <Text style={styles.primaryText}>{t("guest.tryDemo")}</Text>
      </Pressable>
      <Pressable
        testID="guest-log-in"
        style={styles.secondary}
        onPress={() => setStep("login")}
      >
        <Text style={styles.secondaryText}>{t("guest.logIn")}</Text>
      </Pressable>
    </View>
  );
}

const cream = "#f4e9d8";

const styles = StyleSheet.create({
  fill: { flex: 1 },
  landing: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 28,
    paddingBottom: 36,
  },
  brand: {
    color: "#fff",
    fontSize: 32,
    fontWeight: "700",
    letterSpacing: 4,
    textTransform: "uppercase",
    marginBottom: 18,
  },
  mascot: { width: 140, height: 140, marginBottom: 8 },
  mascotSmall: { width: 72, height: 72, alignSelf: "center", marginBottom: 8 },
  kicker: {
    color: "#fff",
    fontSize: 15,
    fontWeight: "600",
    marginBottom: 28,
    textAlign: "center",
  },
  primary: {
    backgroundColor: cream,
    borderRadius: 12,
    minWidth: 184,
    paddingVertical: 16,
    paddingHorizontal: 42,
    marginBottom: 14,
  },
  primaryText: { color: "#0b1020", fontSize: 16, fontWeight: "600", textAlign: "center" },
  secondary: {
    borderRadius: 12,
    minWidth: 184,
    paddingVertical: 16,
    paddingHorizontal: 42,
    borderWidth: 1.5,
    borderColor: "rgba(244,233,216,0.75)",
  },
  secondaryText: { color: cream, fontSize: 16, fontWeight: "600", textAlign: "center" },
  demoContent: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 40 },
  back: { color: "rgba(255,255,255,0.7)", fontSize: 16, marginBottom: 12 },
  card: {
    backgroundColor: "rgba(15,23,42,0.78)",
    borderRadius: theme.radius.lg,
    borderWidth: 1,
    borderColor: theme.colors.border,
    padding: 22,
    marginTop: 14,
  },
  emoji: { fontSize: 36 },
  cardTitle: { color: "#fff", fontSize: 20, fontWeight: "700", marginTop: 8 },
  cardSubtitle: { color: "#a5b4fc", fontSize: 13, fontWeight: "700", marginTop: 2 },
  cardBody: { color: theme.colors.muted, fontSize: 15, marginTop: 8, lineHeight: 21 },
});
