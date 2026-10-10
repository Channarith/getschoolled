import { useEffect, useState } from "react";
import {
  ActivityIndicator, PermissionsAndroid, Platform, Pressable, StyleSheet, Text, View,
} from "react-native";
import { WebView, type WebViewMessageEvent } from "react-native-webview";

import { ensureCameraPermission } from "../components/cameraPermission";
import { WEB_APP_URL } from "../config";
import { useAndroidBackTo } from "../hooks/useAndroidBack";
import { useT } from "../i18n";
import { publicDemoUrl, type PublicDemo } from "../publicDemos";
import { theme } from "../theme";

async function ensureMicrophonePermission(): Promise<void> {
  if (Platform.OS !== "android") return;
  try {
    const already = await PermissionsAndroid.check(PermissionsAndroid.PERMISSIONS.RECORD_AUDIO);
    if (already) return;
    await PermissionsAndroid.request(PermissionsAndroid.PERMISSIONS.RECORD_AUDIO, {
      title: "Microphone for the demo",
      message: "Salareen uses the microphone so the audio demo and listening games can hear you.",
      buttonPositive: "Allow",
      buttonNegative: "Not now",
    });
  } catch {
    /* The page still opens. The demo asks again if it needs the mic. */
  }
}

export default function DemoWebScreen({
  demo,
  onBack,
}: {
  demo: PublicDemo;
  onBack: () => void;
}) {
  const { t } = useT();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [plays, setPlays] = useState(0);
  const url = publicDemoUrl(WEB_APP_URL, demo.path);
  useAndroidBackTo(onBack);

  useEffect(() => {
    void ensureCameraPermission();
    void ensureMicrophonePermission();
  }, []);

  function onMessage(event: WebViewMessageEvent) {
    try {
      const message = JSON.parse(event.nativeEvent.data) as {
        type?: string;
        event?: { activity_id?: string; outcome?: string; fun_score?: number };
      };
      if (message.type !== "salareen-telemetry") return;
      setPlays((count) => count + 1);
    } catch {
      /* The page posts lesson and game stats. Anything else is ignored. */
    }
  }

  return (
    <View style={styles.root} testID="demo-web">
      <View style={styles.bar}>
        <Pressable onPress={onBack} testID="demo-web-back" hitSlop={8}>
          <Text style={styles.back}>{t("guest.back")}</Text>
        </Pressable>
        <Text style={styles.title} numberOfLines={1}>{demo.title}</Text>
        {plays > 0 ? <Text style={styles.plays} testID="demo-telemetry">{plays}</Text> : null}
      </View>
      {error ? (
        <View style={styles.errorWrap}>
          <Text style={styles.error}>{t("guest.webFailed")}</Text>
          <Text style={styles.errorDetail}>{error}</Text>
        </View>
      ) : (
        <WebView
          testID="demo-webview"
          source={{ uri: url }}
          style={styles.web}
          onLoadStart={() => { setError(""); setLoading(true); }}
          onLoadEnd={() => setLoading(false)}
          onError={(event) => {
            setLoading(false);
            setError(event.nativeEvent.description || "load failed");
          }}
          javaScriptEnabled
          domStorageEnabled
          allowsFullscreenVideo
          allowsInlineMediaPlayback
          mediaPlaybackRequiresUserAction={false}
          mediaCapturePermissionGrantType="grant"
          setSupportMultipleWindows={false}
          onMessage={onMessage}
        />
      )}
      {loading && !error ? (
        <View style={styles.loading} pointerEvents="none">
          <ActivityIndicator color={theme.colors.accent} />
          <Text style={styles.loadingText}>{t("guest.loading")}</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.colors.bg },
  bar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  back: { color: "#f4e9d8", fontSize: 16, fontWeight: "600" },
  title: { flex: 1, color: theme.colors.text, fontSize: 16, fontWeight: "700" },
  plays: { color: "#fde68a", fontSize: 13, fontWeight: "700" },
  web: { flex: 1, backgroundColor: theme.colors.bg },
  loading: {
    ...StyleSheet.absoluteFillObject,
    top: 48,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(11,16,32,0.72)",
    gap: 12,
  },
  loadingText: { color: theme.colors.text, fontSize: 15 },
  errorWrap: { flex: 1, padding: 24, justifyContent: "center" },
  error: { color: theme.colors.text, fontSize: 16, textAlign: "center" },
  errorDetail: { color: theme.colors.muted, fontSize: 13, textAlign: "center", marginTop: 8 },
});
