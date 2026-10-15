import { useEffect, useRef } from "react";
import {
  AccessibilityInfo, Animated, Easing, type ImageSourcePropType, type StyleProp, StyleSheet, type ImageStyle,
} from "react-native";

type Props = {
  source: ImageSourcePropType;
  style?: StyleProp<ImageStyle>;
  /** Seconds for one zoom pass; the motion reverses so it loops seamlessly. */
  duration?: number;
  opacity?: number;
};

/** Slow pan-and-zoom over a still photo; static when Reduce Motion is on. */
export default function KenBurnsImage({ source, style, duration = 22, opacity = 1 }: Props) {
  const progress = useRef(new Animated.Value(0)).current;
  const fade = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    let loop: Animated.CompositeAnimation | null = null;
    Animated.timing(fade, { toValue: opacity, duration: 700, useNativeDriver: true }).start();
    AccessibilityInfo.isReduceMotionEnabled().then((reduce) => {
      if (reduce) return;
      loop = Animated.loop(
        Animated.sequence([
          Animated.timing(progress, {
            toValue: 1, duration: duration * 1000, easing: Easing.inOut(Easing.quad), useNativeDriver: true,
          }),
          Animated.timing(progress, {
            toValue: 0, duration: duration * 1000, easing: Easing.inOut(Easing.quad), useNativeDriver: true,
          }),
        ]),
      );
      loop.start();
    }).catch(() => undefined);
    return () => loop?.stop();
  }, [duration, fade, opacity, progress, source]);

  const scale = progress.interpolate({ inputRange: [0, 1], outputRange: [1.05, 1.2] });
  const translateX = progress.interpolate({ inputRange: [0, 1], outputRange: [0, -14] });
  const translateY = progress.interpolate({ inputRange: [0, 1], outputRange: [0, -10] });

  return (
    <Animated.Image
      source={source}
      resizeMode="cover"
      style={[
        StyleSheet.absoluteFillObject,
        { width: "100%", height: "100%", opacity: fade, transform: [{ scale }, { translateX }, { translateY }] },
        style,
      ]}
    />
  );
}
