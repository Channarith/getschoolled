import React, { useEffect, useState } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { Linking, Modal, Platform, Pressable, StyleSheet, Text, View } from "react-native";

import { CLOUD_BASE_URL } from "../config";
import { useT } from "../i18n";
import { theme } from "../theme";
import { APP_VERSION } from "../version";
import MascotSvg from "./MascotSvg";
import { UPDATE_COPY, decideUpdate, fetchAppVersion, type UpdateDecision } from "../updateCheck";

const DISMISSED_KEY = "salareen.update.dismissedVersion";
const CHECKED_KEY = "salareen.update.lastCheckAt";
const DAY_MS = 24 * 60 * 60 * 1000;

/** One small prompt, once a day at most. Never blocks the app unless the build is below the minimum supported. */
export default function UpdatePrompt() {
  const { locale } = useT();
  const [decision, setDecision] = useState<UpdateDecision | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (Platform.OS !== "ios" && Platform.OS !== "android") return;
      try {
        const last = Number((await AsyncStorage.getItem(CHECKED_KEY)) || 0);
        const info = await fetchAppVersion(CLOUD_BASE_URL);
        if (!info || cancelled) return;
        const dismissed = (await AsyncStorage.getItem(DISMISSED_KEY)) || "";
        const d = decideUpdate(APP_VERSION, info, Platform.OS, dismissed, CLOUD_BASE_URL);
        // Respect the once-a-day cadence for soft prompts; a forced update always shows.
        if (d.prompt && (d.force || Date.now() - last > DAY_MS)) setDecision(d);
        if (d.prompt) await AsyncStorage.setItem(CHECKED_KEY, String(Date.now()));
      } catch {
        /* an update check must never break the app */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!decision?.prompt) return null;
  const base = String(locale || "en").toLowerCase().split("-")[0];
  const copy = UPDATE_COPY[base] || UPDATE_COPY.en;

  const later = async () => {
    await AsyncStorage.setItem(DISMISSED_KEY, decision.latest).catch(() => undefined);
    setDecision(null);
  };

  return (
    <Modal transparent animationType="fade" visible onRequestClose={decision.force ? undefined : later}>
      <View style={styles.backdrop}>
        <View style={styles.card} accessibilityViewIsModal>
          <MascotSvg width={96} />
          <Text style={styles.title} accessibilityRole="header">{copy.title}</Text>
          <Text style={styles.body}>{copy.body}</Text>
          <Pressable
            accessibilityRole="button"
            style={styles.primary}
            onPress={() => { void Linking.openURL(decision.url); }}
          >
            <Text style={styles.primaryText}>{copy.update}</Text>
          </Pressable>
          {!decision.force ? (
            <Pressable accessibilityRole="button" style={styles.secondary} onPress={later}>
              <Text style={styles.secondaryText}>{copy.later}</Text>
            </Pressable>
          ) : null}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(5,8,20,0.72)", alignItems: "center", justifyContent: "center", padding: 20 },
  card: { width: "100%", maxWidth: 380, borderRadius: 20, padding: 20, alignItems: "center", backgroundColor: "#0b1020", borderWidth: 2, borderColor: "#d4af37" },
  title: { color: "#fde68a", fontSize: 20, fontWeight: "800", textAlign: "center", marginTop: 8 },
  body: { color: "#e8ecf6", fontSize: 15, textAlign: "center", marginTop: 8, marginBottom: 16 },
  primary: { minHeight: 48, alignSelf: "stretch", borderRadius: 14, backgroundColor: "#d4af37", alignItems: "center", justifyContent: "center" },
  primaryText: { color: "#0b1020", fontWeight: "800", fontSize: 16 },
  secondary: { minHeight: 44, alignSelf: "stretch", alignItems: "center", justifyContent: "center", marginTop: 6 },
  secondaryText: { color: theme?.colors?.muted || "#94a3b8", fontSize: 15 },
});
