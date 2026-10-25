import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator, AppState, Image, PermissionsAndroid, Platform, Pressable, StyleSheet, Text, View,
} from "react-native";
import FriendlyErrorView, { friendlyKindFor } from "../components/FriendlyErrorView";
import { WebView, type WebViewMessageEvent } from "react-native-webview";

import { ensureCameraPermission } from "../components/cameraPermission";
import { WEB_APP_URL } from "../config";
import { useAndroidBackTo } from "../hooks/useAndroidBack";
import { useT } from "../i18n";
import { driverWaveScript } from "../driverWave";
import { liveAudioPhoneScript } from "../liveAudioPhone";
import { appStateScript, demoVoiceHandoffScript, isPageHttpError, publicDemoUrl, childrenLabLocaleScript, childrenLabTouchScript, demoPathWithLocale, type PublicDemo } from "../publicDemos";
import { SERENITY_HERO, SERENITY_NAME } from "../serenity";
import { ensureLoudSpeaker } from "../tts";
import { getSelectedVoice } from "../cloneVoice";
import { getSettings } from "../storage";
import { loadVoiceAgentChoice } from "../voiceAgentPref";
import AdaptiveContent from "../layout/AdaptiveContent";
import { useLayoutMetrics } from "../layout";
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
  const { t, locale } = useT();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [plays, setPlays] = useState(0);
  const [voiceScript, setVoiceScript] = useState<string | null>(null);
  const webRef = useRef<WebView>(null);
  const path = demoPathWithLocale(demo.path, locale);
  const url = publicDemoUrl(WEB_APP_URL, path);
  const audioOnly = path.includes("presentation=audio");
  const studioCourse = path.includes("/studio");
  // Full course: the lesson fills the screen. Back/Exit live in the lesson's own movable panel.
  const cleanCourse = studioCourse && path.includes("access=full");
  const localeScript = path.includes("/children-lab") ? childrenLabLocaleScript(locale) : undefined;
  const touchScript = path.includes("/children-lab") ? childrenLabTouchScript() : undefined;
  const waveScript = audioOnly ? driverWaveScript() : undefined;
  const phoneAudio = liveAudioPhoneScript();
  const beforeLoad = [voiceScript, phoneAudio, waveScript, localeScript, touchScript].filter(Boolean).join("\n");
  const { overlayBottomPad } = useLayoutMetrics();
  useAndroidBackTo(onBack);

  useEffect(() => {
    let alive = true;
    void Promise.all([getSelectedVoice(), getSettings(), loadVoiceAgentChoice()])
      .then(([cloneVoice, settings, agent]) => {
        if (alive) setVoiceScript(demoVoiceHandoffScript({ cloneVoice, voiceId: settings.voiceId, agent }));
      })
      .catch(() => { if (alive) setVoiceScript(demoVoiceHandoffScript({})); });   // storage unavailable: the page uses its own defaults
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    void ensureLoudSpeaker();
    void ensureCameraPermission();
    void ensureMicrophonePermission();
  }, []);

  useEffect(() => {
    const sub = AppState.addEventListener("change", (state) => {
      webRef.current?.injectJavaScript(appStateScript(state));
    });
    return () => sub.remove();
  }, []);

  function onMessage(event: WebViewMessageEvent) {
    try {
      const message = JSON.parse(event.nativeEvent.data) as {
        type?: string;
        event?: {
          activity_id?: string;
          outcome?: string;
          fun_score?: number;
          sensors?: { touch_mode?: string; hand?: boolean; finger?: boolean; face?: boolean; screen_touch?: boolean };
        };
      };
      if (message.type === "salareen-exit") { onBack(); return; }
      if (message.type !== "salareen-telemetry") return;
      setPlays((count) => count + 1);
    } catch {
      /* The page posts lesson and game stats. Anything else is ignored. */
    }
  }

  return (
    <AdaptiveContent style={[styles.root, { paddingBottom: overlayBottomPad }]} testID="demo-web">
      {cleanCourse && !error ? null : <View style={styles.bar} collapsable={false}>
        <Pressable
          onPress={onBack}
          testID="demo-web-back"
          hitSlop={16}
          style={styles.backHit}
        >
          <Text style={styles.back}>{t("guest.back")}</Text>
        </Pressable>
        {studioCourse ? (
          <Image
            source={SERENITY_HERO}
            accessibilityLabel={SERENITY_NAME}
            style={styles.serenity}
          />
        ) : null}
        <Text style={styles.title} numberOfLines={2}>{demo.title}</Text>
        {plays > 0 ? <Text style={styles.plays} testID="demo-telemetry">{plays}</Text> : null}
      </View>}
      {error ? (
        <FriendlyErrorView
          status={errorStatus}
          kind={friendlyKindFor(errorStatus, error)}
          details={error}
          autoRetrySeconds={15}
          onRetry={() => { setError(""); setErrorStatus(null); return true; }}
          onBack={onBack}
        />
      ) : voiceScript === null ? null : (
        <WebView
          ref={webRef}
          testID="demo-webview"
          source={{ uri: url }}
          style={styles.web}
          onLoadStart={() => { setError(""); setErrorStatus(null); setLoading(true); }}
          onLoadEnd={() => setLoading(false)}
          onError={(event) => {
            setLoading(false);
            setErrorStatus(null);
            setError(event.nativeEvent.description || "load failed");
          }}
          onHttpError={(event) => {
            if (!isPageHttpError(event.nativeEvent.url, url)) return;
            setLoading(false);
            setErrorStatus(event.nativeEvent.statusCode);
            setError(`HTTP ${event.nativeEvent.statusCode} ${event.nativeEvent.url || ""}`.trim());
          }}
          injectedJavaScriptBeforeContentLoaded={beforeLoad}
          injectedJavaScript={[phoneAudio, waveScript, touchScript].filter(Boolean).join("\n")}
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
        <View style={[styles.loading, cleanCourse ? { top: 0 } : null]} pointerEvents="none">
          <ActivityIndicator color={theme.colors.accent} />
          <Text style={styles.loadingText}>{t("guest.loading")}</Text>
        </View>
      ) : null}
    </AdaptiveContent>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.colors.bg, overflow: "hidden", width: "100%" },
  bar: {
    zIndex: 1100,
    elevation: 24,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 12,
    paddingVertical: 6,
    backgroundColor: theme.colors.bg,
  },
  backHit: { minHeight: 44, minWidth: 72, justifyContent: "center", paddingHorizontal: 4 },
  back: { color: "#f4e9d8", fontSize: 16, fontWeight: "600", flexShrink: 0 },
  serenity: {
    width: 36,
    height: 48,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "rgba(94,234,212,0.55)",
    backgroundColor: "#0a1624",
    flexShrink: 0,
  },
  title: { flex: 1, minWidth: 0, color: theme.colors.text, fontSize: 16, fontWeight: "700", lineHeight: 20 },
  plays: { color: "#fde68a", fontSize: 13, fontWeight: "700", flexShrink: 0 },
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
