/**
 * Guards the native setup the camera games depend on. A WebView that lacks one of these settings does not fail
 * loudly: getUserMedia is simply refused, and the game quietly falls back to the pointer demo. These checks read the
 * source and the app config, because the real behaviour only shows on a device.
 */
import fs from "fs";
import path from "path";

const root = path.resolve(__dirname, "..", "..");
const read = (rel: string) => fs.readFileSync(path.join(root, rel), "utf8");
const screen = read("src/screens/DemoWebScreen.tsx");
const appJson = JSON.parse(read("app.json")).expo;
const pkg = JSON.parse(read("package.json"));

describe("WebView props for camera and microphone pages", () => {
  const required = [
    "javaScriptEnabled",
    "domStorageEnabled",
    "allowsInlineMediaPlayback",        // iOS: camera video plays inline instead of going full screen
    "mediaPlaybackRequiresUserAction={false}",
    'mediaCapturePermissionGrantType="grant"',   // iOS 15+: the page's getUserMedia is answered without a second prompt
    "onRenderProcessGone",             // Android: renderer killed (usually out of memory)
    "onContentProcessDidTerminate",    // iOS: web process killed
    "webviewDebuggingEnabled",         // chrome://inspect on Android when the debug switch is on
  ];
  it.each(required)("sets %s", (prop) => {
    expect(screen).toContain(prop);
  });

  it("asks for the camera and microphone at runtime on Android and logs the answer", () => {
    expect(screen).toContain("ensureCameraPermission");
    expect(screen).toContain("PermissionsAndroid.PERMISSIONS.RECORD_AUDIO");
    expect(screen).toMatch(/diagLog\("perm"/);
  });

  it("forwards page diagnostics and reloads a crashed iOS web process", () => {
    expect(screen).toContain("routeDiagMessage");
    expect(screen).toContain("diagBridgeScript");
    expect(screen).toMatch(/onContentProcessDidTerminate[\s\S]{0,400}reload\(\)/);
  });

  it("offers the camera check from the game and from the error screen", () => {
    expect(screen).toContain('testID="demo-camera-check-toggle"');
    expect(screen).toContain('testID="demo-error-camera-check"');
  });
});

describe("native permissions", () => {
  it("declares the iOS camera and microphone purposes and mentions the camera games", () => {
    const plist = appJson.ios.infoPlist;
    expect(plist.NSCameraUsageDescription).toMatch(/camera games|hands and body/i);
    expect(plist.NSMicrophoneUsageDescription).toBeTruthy();
  });

  it("declares CAMERA and RECORD_AUDIO on Android", () => {
    expect(appJson.android.permissions).toEqual(expect.arrayContaining(["CAMERA", "RECORD_AUDIO"]));
  });

  it("does not describe the camera prompt as live-class only", () => {
    const camera = read("src/components/cameraPermission.ts");
    expect(camera).toMatch(/camera games|hands and body/i);
    expect(camera).not.toContain("classmates can see you in the live room");
  });
});

describe("react-native-webview matches the Expo SDK", () => {
  it("uses the exact version the SDK bundles", () => {
    const bundled = JSON.parse(read("node_modules/expo/bundledNativeModules.json"));
    expect(pkg.dependencies["react-native-webview"]).toBe(bundled["react-native-webview"]);
  });
});
