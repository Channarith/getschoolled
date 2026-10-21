/**
 * Front-camera preview that stays on, like a video call.
 * Frames are small JPEGs grabbed from that live preview — the system camera
 * app never opens, and there is no shutter review step.
 */
import { CameraView } from "expo-camera";
import * as FileSystem from "expo-file-system";
import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";

export type LiveFrame = {
  base64: string;
  width: number;
  height: number;
  uri?: string;
};

export type LiveFaceCameraHandle = {
  grabFrame: (options?: { retainFile?: boolean; includeBase64?: boolean }) => Promise<LiveFrame | null>;
};

type Props = {
  facing?: "front" | "back";
  style?: StyleProp<ViewStyle>;
  onReady?: () => void;
  onError?: (message: string) => void;
};

/** Prefer a ~720px still so face reads stay fast without a multi-megapixel JPEG. */
export function pickLivePictureSize(sizes: string[]): string | null {
  const parsed = sizes.flatMap((s) => {
    const match = /^(\d+)x(\d+)$/.exec(s);
    if (!match) return [];
    const w = Number(match[1]);
    const h = Number(match[2]);
    if (!w || !h) return [];
    return [{ s, long: Math.max(w, h) }];
  });
  if (!parsed.length) return null;
  const usable = parsed.filter((item) => item.long >= 480);
  const pool = usable.length ? usable : parsed;
  pool.sort((a, b) => Math.abs(a.long - 720) - Math.abs(b.long - 720) || a.long - b.long);
  return pool[0].s;
}

const LiveFaceCamera = forwardRef<LiveFaceCameraHandle, Props>(function LiveFaceCamera(
  { facing = "front", style, onReady, onError },
  ref,
) {
  const cameraRef = useRef<CameraView>(null);
  const readyRef = useRef(false);
  const busyRef = useRef(false);
  const sizedRef = useRef(false);
  // Same live size as the vision lab: 1280×720 front camera, not a photo session.
  const [pictureSize, setPictureSize] = useState<string | undefined>("1280x720");

  useImperativeHandle(ref, () => ({
    async grabFrame(options) {
      if (!readyRef.current || busyRef.current || !cameraRef.current) return null;
      busyRef.current = true;
      try {
        const includeBase64 = options?.includeBase64 !== false;
        const photo = await cameraRef.current.takePictureAsync({
          quality: 0.32,
          base64: includeBase64,
          exif: false,
        });
        if (!photo) return null;
        if (includeBase64 && !photo.base64) return null;
        const keep = options?.retainFile && photo.uri && !photo.uri.startsWith("data:");
        if (!keep && photo.uri && !photo.uri.startsWith("data:")) {
          void FileSystem.deleteAsync(photo.uri, { idempotent: true }).catch(() => undefined);
        }
        return {
          base64: photo.base64 ?? "",
          width: photo.width,
          height: photo.height,
          uri: keep ? photo.uri : undefined,
        };
      } catch {
        return null;
      } finally {
        busyRef.current = false;
      }
    },
  }), []);

  return (
    <View style={[styles.fill, style]} collapsable={false}>
      <CameraView
        ref={cameraRef}
        style={StyleSheet.absoluteFill}
        facing={facing}
        mode="video"
        mute
        mirror
        animateShutter={false}
        flash="off"
        ratio="16:9"
        pictureSize={pictureSize}
        onMountError={({ message }) => onError?.(message || "The camera didn’t start.")}
        onCameraReady={() => {
          readyRef.current = true;
          onReady?.();
          if (sizedRef.current) return;
          sizedRef.current = true;
          void cameraRef.current?.getAvailablePictureSizesAsync?.().then((sizes) => {
            const picked = pickLivePictureSize(sizes ?? []);
            if (picked && picked !== pictureSize) setPictureSize(picked);
          }).catch(() => undefined);
        }}
      />
    </View>
  );
});

export default LiveFaceCamera;

const styles = StyleSheet.create({
  fill: { ...StyleSheet.absoluteFillObject, backgroundColor: "#000000" },
});
