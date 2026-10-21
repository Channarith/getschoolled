/**
 * Plays the Meshy GLB (the same Mascot.glb the web setup assistant uses)
 * inside a WebView. React Native has no Three.js canvas here, and the
 * WebView is already in the native binary, so this does not add a native
 * module. The viewer, Draco decoder, and model are bundled assets — the
 * phone does not fetch them.
 */
import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Platform, StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import WebView from "react-native-webview";

import MascotActor, { type MascotScene } from "./MascotActor";

export const MASCOT_DECODER_FILE = "draco_decoder.js";
export const MASCOT_VIEWER_FILE = "viewer.js";
export const MASCOT_MODEL_FILE = "Mascot.glb";
const CACHE_DIR = "mascot-meshy-v2";

const VIEWER = require("../../assets/mascot3d/viewer.txt");
const DECODER = require("../../assets/mascot3d/draco_decoder.txt");
const MODEL = require("../../assets/mascot3d/Mascot.glb");

/** Clip baked into Mascot.glb. "idle" rotates the calm Meshy set. */
export function clipForMascotScene(scene: MascotScene): string {
  switch (scene.kind) {
    case "flyin-point":
      return "Big_Wave_Hello";
    case "dance":
      return "Boom_Dance";
    case "video":
      return "Indoor_Swing";
    case "teacher":
      return "Confident_Strut";
    case "presentation":
      return "Indoor_Swing";
    case "reading":
      return "Wave_for_Help_1";
    case "tutoring":
      return "Wave_for_Help_2";
    case "gaming":
      return "Jump_Rope";
    case "age-morph":
    case "idle":
      return "idle";
    default:
      return "idle";
  }
}

/**
 * three.js loads the GLB and the Draco decoder with fetch(). Android WebView
 * and WKWebView refuse fetch() for file:// URLs, so the viewer failed before
 * the first frame and the 2D fallback took its place. XMLHttpRequest can read
 * the same local files, so local URLs go through it.
 */
export const LOCAL_FETCH_SHIM = `(function () {
  var nativeFetch = window.fetch ? window.fetch.bind(window) : null;
  function isLocal(url) {
    return /^file:/i.test(url) || !/^[a-z][a-z0-9+.-]*:/i.test(url);
  }
  window.fetch = function (input, init) {
    var url = typeof input === "string" ? input : (input && input.url) || String(input);
    if (!isLocal(url) && nativeFetch) return nativeFetch(input, init);
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      xhr.open("GET", url, true);
      xhr.responseType = "arraybuffer";
      xhr.onload = function () {
        var ok = xhr.status === 0 || (xhr.status >= 200 && xhr.status < 300);
        if (!ok || !xhr.response) {
          reject(new TypeError("local file unreadable: " + url + " (" + xhr.status + ")"));
          return;
        }
        resolve(new Response(xhr.response, { status: 200 }));
      };
      xhr.onerror = function () {
        reject(new TypeError("local file unreadable: " + url));
      };
      xhr.send();
    });
  };
  window.addEventListener("error", function (event) {
    if (window.ReactNativeWebView) {
      window.ReactNativeWebView.postMessage("error:" + (event.message || "script error"));
    }
  });
})();`;

export function mascotViewerHtml(clip: string): string {
  const safe = clip.replace(/[^A-Za-z0-9_]/g, "") || "idle";
  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no" />
<style>
  html, body { margin: 0; height: 100%; background: transparent; overflow: hidden; }
  canvas { display: block; width: 100%; height: 100%; background: transparent; }
</style>
</head>
<body>
<script>${LOCAL_FETCH_SHIM}</script>
<script src="${MASCOT_VIEWER_FILE}"></script>
<script>MascotViewer.start({ modelUrl: "${MASCOT_MODEL_FILE}", clip: "${safe}" });</script>
</body>
</html>`;
}

/** One small HTML file per clip, next to the viewer, for iOS to open as a file. */
export function mascotPageFile(clip: string): string {
  const safe = clip.replace(/[^A-Za-z0-9_]/g, "") || "idle";
  return `mascot-${safe}.html`;
}

export type MascotSource = { html: string; baseUrl: string } | { uri: string };

/**
 * v0.94.2 switched this from opening a real file to inline markup, and the 3D
 * mascot stopped appearing on iPhone (it fell back to the flat picture). iOS
 * goes back to opening a page file with read access to its folder, which is
 * what worked before. Android keeps the inline markup that fixed it there.
 */
export function mascotSourceFor(os: string, dir: string, clip: string, attempt = 0): MascotSource {
  // The second attempt uses the other way of loading, in case the first is
  // refused on this device.
  const asFile = (os === "ios") !== (attempt > 0);
  if (asFile) return { uri: `${dir}${mascotPageFile(clip)}` };
  return { html: mascotViewerHtml(clip), baseUrl: dir };
}

let filesReady: Promise<string> | null = null;

async function copyAsset(moduleId: number, dest: string): Promise<void> {
  const { Asset } = require("expo-asset") as typeof import("expo-asset");
  const FileSystem = require("expo-file-system") as typeof import("expo-file-system");
  const asset = Asset.fromModule(moduleId);
  await asset.downloadAsync();
  const from = asset.localUri || asset.uri;
  if (!from) throw new Error("mascot asset missing");
  await FileSystem.deleteAsync(dest, { idempotent: true });
  await FileSystem.copyAsync({ from, to: dest });
}

function ensureViewerFiles(): Promise<string> {
  if (!filesReady) {
    filesReady = (async () => {
      const FileSystem = require("expo-file-system") as typeof import("expo-file-system");
      const root = FileSystem.cacheDirectory;
      if (!root) throw new Error("no cache directory");
      // A new directory prevents an Android WebView from retaining an older
      // file:// viewer after an app update. Android caches local scripts much
      // more aggressively than iOS does.
      const dir = `${root}${CACHE_DIR}/`;
      await FileSystem.makeDirectoryAsync(dir, { intermediates: true });
      await copyAsset(VIEWER, dir + MASCOT_VIEWER_FILE);
      await copyAsset(DECODER, dir + MASCOT_DECODER_FILE);
      await copyAsset(MODEL, dir + MASCOT_MODEL_FILE);
      return dir;
    })().catch((err) => {
      filesReady = null;
      throw err;
    });
  }
  return filesReady;
}

type Props = {
  scene: MascotScene;
  style?: StyleProp<ViewStyle>;
};

export default function MobileMascotMeshy({ scene, style }: Props) {
  const clip = clipForMascotScene(scene);
  const [page, setPage] = useState<string | null>(null);
  const [source, setSource] = useState<MascotSource | null>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [tried, setTried] = useState({ clip, attempt: 0 });
  const attempt = tried.clip === clip ? tried.attempt : 0;
  const readyRef = useRef(false);

  function fail() {
    if (attempt === 0) setTried({ clip, attempt: 1 });
    else setFailed(true);
  }

  useEffect(() => {
    let cancel = false;
    readyRef.current = false;
    setReady(false);
    setFailed(false);
    setSource(null);
    const timer = setTimeout(() => {
      if (!cancel && !readyRef.current) fail();
    }, attempt === 0 ? 9000 : 15000);
    void ensureViewerFiles()
      .then(async (dir) => {
        // Supplying the markup directly avoids Android WebView's inconsistent
        // handling of a file:// HTML document that then loads another local
        // JavaScript file. `baseUrl` retains the same local directory for the
        // viewer, Draco decoder, and GLB.
        const FileSystem = require("expo-file-system") as typeof import("expo-file-system");
        await FileSystem.writeAsStringAsync(`${dir}${mascotPageFile(clip)}`, mascotViewerHtml(clip));
        if (cancel) return;
        setSource(mascotSourceFor(Platform.OS, dir, clip, attempt));
        setPage(dir);
      })
      .catch(() => {
        if (!cancel) fail();
      });
    return () => {
      cancel = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clip, attempt]);

  if (failed) {
    return (
      <View style={[styles.fill, style]} testID="mobile-mascot-fallback">
        <MascotActor scene={scene} size={160} />
      </View>
    );
  }

  return (
    <View style={[styles.fill, style]} testID="mobile-mascot-meshy" pointerEvents="none">
      {page && source ? (
        <WebView
          key={`${clip}-${attempt}`}
          source={source}
          style={styles.web}
          originWhitelist={["*"]}
          allowingReadAccessToURL={page}
          allowFileAccess
          allowFileAccessFromFileURLs
          allowUniversalAccessFromFileURLs
          javaScriptEnabled
          domStorageEnabled
          cacheEnabled={false}
          scrollEnabled={false}
          bounces={false}
          androidLayerType="hardware"
          setSupportMultipleWindows={false}
          onError={(event) => {
            console.warn(`[mascot] webview: ${event.nativeEvent.description}`);
            fail();
          }}
          onHttpError={(event) => {
            console.warn(`[mascot] ${event.nativeEvent.statusCode} ${event.nativeEvent.url}`);
            fail();
          }}
          onMessage={(event) => {
            const data = event.nativeEvent.data || "";
            if (data === "ready") {
              readyRef.current = true;
              setReady(true);
            } else if (data.startsWith("error:")) {
              console.warn(`[mascot] ${data.slice(6)}`);
              fail();
            }
          }}
        />
      ) : null}
      {ready ? null : (
        <View style={styles.spinner} pointerEvents="none">
          <ActivityIndicator color="#0f9d8f" />
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  fill: { width: "100%", height: "100%", backgroundColor: "transparent" },
  web: { flex: 1, backgroundColor: "transparent" },
  spinner: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center",
    justifyContent: "center",
  },
});
