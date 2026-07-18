import { useEffect, useRef } from "react";
import { BackHandler, Platform } from "react-native";

/**
 * Wire the Android hardware / gesture back button to in-app navigation.
 * Return true from `handler` to consume the event (stay in the app);
 * return false to allow the default (usually exit the activity).
 *
 * No-op on iOS. Safe to call unconditionally from shared screens.
 */
export function useAndroidBack(
  handler: (() => boolean) | undefined,
  enabled = true,
): void {
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => {
    if (Platform.OS !== "android" || !enabled) return;
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      return handlerRef.current?.() ?? false;
    });
    return () => sub.remove();
  }, [enabled]);
}

/** Convenience: call the same `onBack` the UI back button uses, and consume the event. */
export function useAndroidBackTo(onBack: (() => void) | undefined, enabled = true): void {
  useAndroidBack(
    onBack
      ? () => {
        onBack();
        return true;
      }
      : undefined,
    enabled,
  );
}
