import { useCallback, useRef, useState } from "react";
import {
  ActivityIndicator, Platform, Pressable, StyleSheet, Text, View,
} from "react-native";
import { WebView, type WebViewMessageEvent } from "react-native-webview";
import { CURRICULUM_URL } from "../config";

const WORLDS_URL = `${CURRICULUM_URL.replace("/curriculum", "")}/worlds`;

const INJECTED_JS = `
  window.__SALAREEN_NATIVE__ = true;
  window.__SALAREEN_PLATFORM__ = '${Platform.OS}';
  window.__notifyNative = function(type, payload) {
    if (window.ReactNativeWebView) {
      window.ReactNativeWebView.postMessage(JSON.stringify({ type, payload }));
    }
  };
  true;
`;

type NativeMessage =
  | { type: "xp_earned";  payload: { xp: number; total: number } }
  | { type: "gem_earned"; payload: { gems: number } }
  | { type: "quest_done"; payload: { questId: string; title: string } }
  | { type: "exit_game";  payload: null };

interface WorldsScreenProps {
  onBack: () => void;
}

export default function WorldsScreen({ onBack }: WorldsScreenProps) {
  const webViewRef = useRef<WebView>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [xpEarned, setXpEarned] = useState(0);

  const handleMessage = useCallback((event: WebViewMessageEvent) => {
    try {
      const msg: NativeMessage = JSON.parse(event.nativeEvent.data);
      switch (msg.type) {
        case "xp_earned":
          setXpEarned(prev => prev + msg.payload.xp);
          break;
        case "exit_game":
          onBack();
          break;
        default:
          break;
      }
    } catch {
      /* ignore malformed messages */
    }
  }, [onBack]);

  if (error) {
    return (
      <View style={styles.errorContainer}>
        <Text style={styles.errorEmoji}>🌍</Text>
        <Text style={styles.errorTitle}>Salareen Worlds</Text>
        <Text style={styles.errorMsg}>
          Could not load the game. Make sure you're connected to the internet.
        </Text>
        <Text style={styles.errorDetail}>{error}</Text>
        <Pressable style={styles.retryBtn} onPress={() => { setError(null); setLoading(true); }}>
          <Text style={styles.retryText}>Try Again</Text>
        </Pressable>
        <Pressable style={styles.backBtn} onPress={onBack}>
          <Text style={styles.backText}>← Back</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      {/* iOS back button — visible on top-left since there is no hardware back */}
      {Platform.OS === 'ios' && (
        <Pressable style={styles.iosBackBtn} onPress={onBack}>
          <Text style={styles.iosBackText}>← Back</Text>
        </Pressable>
      )}
      <WebView
        ref={webViewRef}
        source={{ uri: WORLDS_URL }}
        style={styles.webview}
        injectedJavaScript={INJECTED_JS}
        onMessage={handleMessage}
        onLoadStart={() => setLoading(true)}
        onLoadEnd={() => setLoading(false)}
        onError={(e: {nativeEvent: {description: string}}) => setError(e.nativeEvent.description)}
        onHttpError={(e: {nativeEvent: {statusCode: number; description: string}}) => setError(`HTTP ${e.nativeEvent.statusCode}: ${e.nativeEvent.description}`)}
        javaScriptEnabled
        domStorageEnabled
        allowsFullscreenVideo
        mediaPlaybackRequiresUserAction={false}
        allowsInlineMediaPlayback
        scrollEnabled={false}
        overScrollMode="never"
        bounces={false}
        mixedContentMode="compatibility"
      />

      {loading && (
        <View style={styles.loadingOverlay}>
          <Text style={styles.loadingEmoji}>🌍</Text>
          <Text style={styles.loadingTitle}>Loading Salareen Worlds...</Text>
          <ActivityIndicator color="#6366f1" size="large" style={{ marginTop: 16 }} />
          <Text style={styles.loadingTip}>
            {LOADING_TIPS[Math.floor(Math.random() * LOADING_TIPS.length)]}
          </Text>
        </View>
      )}

      {xpEarned > 0 && !loading && (
        <View style={styles.xpToast} pointerEvents="none">
          <Text style={styles.xpToastText}>⭐ +{xpEarned} XP</Text>
        </View>
      )}
    </View>
  );
}

const LOADING_TIPS = [
  "💡 The turtle is faster than the rocket. It's a cosmic thing.",
  "💡 Gerald the rabbit is definitely fast. He says so himself.",
  "💡 π the Squirrel has eaten 314 pies. The doctor is concerned.",
  "💡 Reginald the Accountant Sloth is still calculating your taxes. From 1987.",
  "💡 Percival the Victorian Ghost doesn't know he's a ghost. Don't tell him.",
  "💡 Chef Étienne would like to remind you that cooking is CHEMISTRY.",
  "💡 Jasper the Jazz Octopus plays 8 instruments simultaneously. All at once. Loudly.",
  "💡 Dr. Reginald the Rock has opinions. He's had 300 million years to form them.",
];

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#07080f" },
  webview: { flex: 1 },
  iosBackBtn: {
    position: "absolute",
    top: 52,
    left: 16,
    zIndex: 20,
    backgroundColor: "rgba(0,0,0,0.55)",
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  iosBackText: { color: "#fff", fontSize: 15, fontWeight: "700" },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "#07080f",
    alignItems: "center",
    justifyContent: "center",
    padding: 32,
    gap: 10,
    zIndex: 10,
  },
  loadingEmoji: { fontSize: 64 },
  loadingTitle: { color: "#fff", fontSize: 22, fontWeight: "900", textAlign: "center" },
  loadingTip: {
    color: "#6366f1",
    fontSize: 13,
    textAlign: "center",
    marginTop: 24,
    maxWidth: 300,
    lineHeight: 20,
    fontStyle: "italic",
  },
  xpToast: {
    position: "absolute",
    top: 60,
    alignSelf: "center",
    backgroundColor: "rgba(99,102,241,0.9)",
    borderRadius: 20,
    paddingHorizontal: 20,
    paddingVertical: 8,
  },
  xpToastText: { color: "#fff", fontWeight: "800", fontSize: 16 },
  errorContainer: {
    flex: 1,
    backgroundColor: "#07080f",
    alignItems: "center",
    justifyContent: "center",
    padding: 32,
    gap: 12,
  },
  errorEmoji: { fontSize: 64 },
  errorTitle: { color: "#fff", fontSize: 24, fontWeight: "900" },
  errorMsg: { color: "#94a3b8", fontSize: 15, textAlign: "center", lineHeight: 22 },
  errorDetail: { color: "#475569", fontSize: 11, textAlign: "center" },
  retryBtn: {
    backgroundColor: "#6366f1",
    borderRadius: 12,
    paddingHorizontal: 32,
    paddingVertical: 14,
    marginTop: 8,
  },
  retryText: { color: "#fff", fontWeight: "800", fontSize: 16 },
  backBtn: { paddingHorizontal: 16, paddingVertical: 8 },
  backText: { color: "#6366f1", fontSize: 14 },
});
