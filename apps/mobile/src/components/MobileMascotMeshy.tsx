/**
 * Plays the Meshy GLB (the same Mascot.glb the web setup assistant uses)
 * inside a WebView. React Native has no Three.js canvas here, and the
 * WebView is already in the native binary, so this does not add a native
 * module. The viewer, Draco decoder, and model are bundled assets — the
 * phone does not fetch them.
 */
import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import WebView from "react-native-webview";

import MascotActor, { type MascotScene } from "./MascotActor";

export const MASCOT_DECODER_FILE = "draco_decoder.js";
export const MASCOT_VIEWER_FILE = "viewer.js";
export const MASCOT_MODEL_FILE = "Mascot.glb";

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
<script src="${MASCOT_VIEWER_FILE}"></script>
<script>MascotViewer.start({ modelUrl: "${MASCOT_MODEL_FILE}", clip: "${safe}" });</script>
</body>
</html>`;
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
      const dir = `${root}mascot-meshy/`;
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
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const readyRef = useRef(false);

  useEffect(() => {
    let cancel = false;
    readyRef.current = false;
    setReady(false);
    setFailed(false);
    const timer = setTimeout(() => {
      if (!cancel && !readyRef.current) setFailed(true);
    }, 20000);
    void ensureViewerFiles()
      .then(async (dir) => {
        const htmlPath = `${dir}index-${clip}.html`;
        const FileSystem = require("expo-file-system") as typeof import("expo-file-system");
        await FileSystem.writeAsStringAsync(htmlPath, mascotViewerHtml(clip));
        if (!cancel) setPage(htmlPath);
      })
      .catch(() => {
        if (!cancel) setFailed(true);
      });
    return () => {
      cancel = true;
      clearTimeout(timer);
    };
  }, [clip]);

  if (failed) {
    return (
      <View style={[styles.fill, style]} testID="mobile-mascot-fallback">
        <MascotActor scene={scene} size={160} />
      </View>
    );
  }

  const dir = page ? page.slice(0, page.lastIndexOf("/") + 1) : undefined;
  return (
    <View style={[styles.fill, style]} testID="mobile-mascot-meshy" pointerEvents="none">
      {page ? (
        <WebView
          key={clip}
          source={{ uri: page }}
          style={styles.web}
          originWhitelist={["*"]}
          allowingReadAccessToURL={dir}
          allowFileAccess
          allowFileAccessFromFileURLs
          scrollEnabled={false}
          bounces={false}
          androidLayerType="hardware"
          setSupportMultipleWindows={false}
          onError={() => setFailed(true)}
          onHttpError={() => setFailed(true)}
          onMessage={(event) => {
            const data = event.nativeEvent.data || "";
            if (data === "ready") {
              readyRef.current = true;
              setReady(true);
            } else if (data.startsWith("error:")) {
              setFailed(true);
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
