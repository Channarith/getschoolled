/**
 * Quiet, fast stills from expo-camera for the Learner Check face check.
 *
 * The face check reads several small stills from the live preview. expo-camera
 * 15 plays a shutter click for every one (Android MediaActionSound, iOS system
 * sound) and asks iOS for balanced-quality processing, which is slow. This
 * keeps the click only where the OS says it is required (for example Japan and
 * Korea), asks iOS for speed, and asks Android CameraX for minimum latency.
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const QUIET = "salareen-quiet-capture";
const FAST = "salareen-fast-capture";
const CAMERA = path.join(ROOT, "node_modules", "expo-camera");

function patch(file, mark, edits) {
  const full = path.join(CAMERA, file);
  if (!fs.existsSync(full)) {
    console.warn(`patch-expo-camera-quiet-capture: ${file} not found`);
    return;
  }
  let text = fs.readFileSync(full, "utf8");
  if (text.includes(mark)) return;
  for (const [before, after] of edits) {
    if (!text.includes(before)) {
      console.warn(`patch-expo-camera-quiet-capture: ${file} changed upstream; ${mark} left as is`);
      return;
    }
    text = text.replace(before, after);
  }
  fs.writeFileSync(full, text);
  console.log(`patch-expo-camera-quiet-capture: ${mark} patched ${file}`);
}

const ANDROID_VIEW = "android/src/main/java/expo/modules/camera/ExpoCameraView.kt";

patch(ANDROID_VIEW, QUIET, [[
  "          if (volume != 0) {\n            MediaActionSound().play(MediaActionSound.SHUTTER_CLICK)\n          }",
  `          // ${QUIET}: click only where the region requires it.\n`
  + "          if (volume != 0 && android.os.Build.VERSION.SDK_INT >= 33 && MediaActionSound.mustPlayShutterSound()) {\n"
  + "            MediaActionSound().play(MediaActionSound.SHUTTER_CLICK)\n"
  + "          }",
]]);

patch(ANDROID_VIEW, FAST, [[
  "        imageCaptureUseCase = ImageCapture.Builder()\n          .setResolutionSelector(resolutionSelector)\n          .build()",
  "        imageCaptureUseCase = ImageCapture.Builder()\n"
  + "          .setResolutionSelector(resolutionSelector)\n"
  + `          // ${FAST}: skip the slow quality pipeline between stills.\n`
  + "          .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)\n"
  + "          .build()",
]]);

patch("ios/Current/CameraView.swift", QUIET, [
  ["import CoreMotion\n", `import CoreMotion\nimport AudioToolbox // ${QUIET}\n`],
  ["      photoSettings.photoQualityPrioritization = .balanced\n", "      photoSettings.photoQualityPrioritization = .speed\n"],
  [
    "  public func photoOutput(_ output: AVCapturePhotoOutput, willCapturePhotoFor resolvedSettings: AVCaptureResolvedPhotoSettings) {\n",
    "  public func photoOutput(_ output: AVCapturePhotoOutput, willCapturePhotoFor resolvedSettings: AVCaptureResolvedPhotoSettings) {\n"
    + "    // Regions that require the shutter sound still play it.\n"
    + "    AudioServicesDisposeSystemSoundID(1108)\n",
  ],
]);
