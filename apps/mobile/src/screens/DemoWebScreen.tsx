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
import { CAMERA_CHECK_PATH, diagBridgeScript, isCameraCheckPath, routeDiagMessage } from "../diag/webDiag";
import { armDiagForBugReport, diagLog, initDiag, isDebugMode, shareDiagReport } from "../diag/diagLog";
import { APP_VERSION } from "../version";
import { loadVoiceAgentChoice } from "../voiceAgentPref";
import AdaptiveContent from "../layout/AdaptiveContent";
import { useLayoutMetrics } from "../layout";
import { theme } from "../theme";

async function ensureMicrophonePermission(): Promise<string> {
  if (Platform.OS !== "android") return "ios-prompts-on-use";
  try {
    const already = await PermissionsAndroid.check(PermissionsAndroid.PERMISSIONS.RECORD_AUDIO);
    if (already) return "granted";
    return await PermissionsAndroid.request(PermissionsAndroid.PERMISSIONS.RECORD_AUDIO, {
      title: "Microphone for the demo",
      message: "Salareen uses the microphone so the audio demo and listening games can hear you.",
      buttonPositive: "Allow",
      buttonNegative: "Not now",
    });
  } catch (error) {
    /* The page still opens. The demo asks again if it needs the mic. */
    return `error: ${String((error as Error)?.message || error)}`;
  }
}

export default function DemoWebScreen({
  demo,
  onBack,
  onReportBug,
}: {
  demo: PublicDemo;
  onBack: () => void;
  /** Opens the Report a bug screen. Used by the camera check's "Send to Salareen" button. */
  onReportBug?: () => void;
}) {
  const { t, locale } = useT();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [plays, setPlays] = useState(0);
  const [voiceScript, setVoiceScript] = useState<string | null>(null);
  const webRef = useRef<WebView>(null);
  const basePath = demoPathWithLocale(demo.path, locale);
  const isVisionDemo = basePath.includes("/children-lab");
  // The camera check swaps this same WebView to the hosted diagnostics page and back, so the game keeps its place.
  const [checking, setChecking] = useState(isCameraCheckPath(demo.path));
  const path = checking ? CAMERA_CHECK_PATH : basePath;
  const url = publicDemoUrl(WEB_APP_URL, path);
  const canToggleCheck = isVisionDemo && !isCameraCheckPath(demo.path);
  const [debug, setDebug] = useState(isDebugMode());
  const loadStartedAt = useRef(0);
  function toggleCheck() {
    diagLog("camera-check", checking ? "back to the game" : "opened from the game");
    setError(""); setErrorStatus(null);
    setChecking((on) => !on);
  }
  const audioOnly = path.includes("presentation=audio");
  const studioCourse = path.includes("/studio");
  // Full course: the lesson fills the screen. Back/Exit live in the lesson's own movable panel.
  const cleanCourse = studioCourse && path.includes("access=full");
  const localeScript = path.includes("/children-lab") ? childrenLabLocaleScript(locale) : undefined;
  const touchScript = path.includes("/children-lab") ? childrenLabTouchScript() : undefined;
  const waveScript = audioOnly ? driverWaveScript() : undefined;
  const phoneAudio = liveAudioPhoneScript();
  const beforeLoad = [diagBridgeScript(), voiceScript, phoneAudio, waveScript, localeScript, touchScript].filter(Boolean).join("\n");
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
    void initDiag().then(() => setDebug(isDebugMode()));
    void ensureLoudSpeaker();
    void ensureCameraPermission().then((granted) => diagLog("perm", `Android/iOS CAMERA ${granted ? "granted" : "not granted"} (asked on screen open: ${demo.id})`));
    void ensureMicrophonePermission().then((result) => diagLog("perm", `RECORD_AUDIO ${result}`));
  }, [demo.id]);

  useEffect(() => {
    const sub = AppState.addEventListener("change", (state) => {
      webRef.current?.injectJavaScript(appStateScript(state));
    });
    return () => sub.remove();
  }, []);

  function onMessage(event: WebViewMessageEvent) {
    const routed = routeDiagMessage(event.nativeEvent.data);
    if (routed.handled) {
      if (routed.shareText) void shareDiagReport();
      return;
    }
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
        {canToggleCheck ? (
          <Pressable
            onPress={toggleCheck}
            testID="demo-camera-check-toggle"
            hitSlop={12}
            style={styles.checkHit}
          >
            <Text style={styles.checkText}>{checking ? "Back to game" : "Camera check"}</Text>
          </Pressable>
        ) : null}
      </View>}
      {checking ? (
        <View style={styles.checkRow}>
          <Pressable onPress={() => void shareDiagReport()} testID="camera-check-share" style={styles.checkButton}>
            <Text style={styles.checkButtonText}>Share report</Text>
          </Pressable>
          {onReportBug ? (
            <Pressable onPress={() => { armDiagForBugReport(); onReportBug(); }} testID="camera-check-send" style={styles.checkButton}>
              <Text style={styles.checkButtonText}>Send to Salareen</Text>
            </Pressable>
          ) : null}
        </View>
      ) : null}
      {error ? (
        <View style={styles.errorWrapper}>
          <FriendlyErrorView
            status={errorStatus}
            kind={friendlyKindFor(errorStatus, error)}
            details={error}
            autoRetrySeconds={15}
            onRetry={() => { setError(""); setErrorStatus(null); return true; }}
            onBack={onBack}
          />
          {canToggleCheck && !checking ? (
            <Pressable onPress={toggleCheck} testID="demo-error-camera-check" style={styles.errorCheck}>
              <Text style={styles.checkText}>Run the camera check</Text>
            </Pressable>
          ) : null}
        </View>
      ) : voiceScript === null ? null : (
        <WebView
          ref={webRef}
          testID="demo-webview"
          source={{ uri: url }}
          style={styles.web}
          key={path}
          onLoadStart={() => { loadStartedAt.current = Date.now(); setError(""); setErrorStatus(null); setLoading(true); }}
          onLoadEnd={() => {
            setLoading(false);
            diagLog("webview", `loaded ${path.split("?")[0]} in ${Date.now() - loadStartedAt.current} ms`);
          }}
          onError={(event) => {
            setLoading(false);
            setErrorStatus(null);
            diagLog("error", `WebView load error ${event.nativeEvent.code ?? ""} ${event.nativeEvent.description || "load failed"} (${path.split("?")[0]})`);
            setError(event.nativeEvent.description || "load failed");
          }}
          onRenderProcessGone={(event) => {
            // Android: the page's renderer was killed, most often because the phone ran out of memory.
            setLoading(false);
            diagLog("error", `WebView render process gone didCrash=${String(event.nativeEvent.didCrash)} (memory pressure is the usual cause)`);
            setErrorStatus(null);
            setError("The page ran out of memory and closed. Close other apps and try again.");
          }}
          onContentProcessDidTerminate={() => {
            // iOS: WKWebView's web process was killed. Reload the page instead of leaving a blank screen.
            diagLog("error", "WebView content process terminated; reloading");
            webRef.current?.reload();
          }}
          webviewDebuggingEnabled={debug || __DEV__}
          applicationNameForUserAgent={`SalareenApp/${APP_VERSION}`}
          onHttpError={(event) => {
            diagLog("webview", `HTTP ${event.nativeEvent.statusCode} ${String(event.nativeEvent.url || "").split("?")[0]}`);
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
  errorWrapper: { flex: 1 },
  errorCheck: { alignSelf: "center", minHeight: 44, justifyContent: "center", paddingHorizontal: 16, paddingBottom: 12 },
  checkHit: { minHeight: 44, justifyContent: "center", paddingHorizontal: 4, flexShrink: 0 },
  checkText: { color: "#d4af37", fontSize: 13, fontWeight: "700" },
  checkRow: { flexDirection: "row", gap: 10, paddingHorizontal: 12, paddingBottom: 6, backgroundColor: theme.colors.bg },
  checkButton: { minHeight: 40, paddingHorizontal: 14, borderRadius: 10, borderWidth: 1, borderColor: "#d4af37", justifyContent: "center" },
  checkButtonText: { color: "#f4e9d8", fontSize: 14, fontWeight: "600" },
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
