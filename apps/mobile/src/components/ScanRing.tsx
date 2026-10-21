/**
 * Ring that sweeps around the face circle while the camera is looking, and
 * fills green as each still is kept. Draws only; it never takes touches.
 */
import { useEffect, useRef } from "react";
import { Animated, Easing, StyleSheet, View } from "react-native";
import Svg, { Circle } from "react-native-svg";

type Props = { size: number; progress: number; found: boolean };

const RADIUS = 48;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export default function ScanRing({ size, progress, found }: Props) {
  const spin = useRef(new Animated.Value(0)).current;
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const sweep = Animated.loop(
      Animated.timing(spin, { toValue: 1, duration: 1800, easing: Easing.linear, useNativeDriver: true }),
    );
    const breathe = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 900, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: 900, easing: Easing.inOut(Easing.quad), useNativeDriver: true }),
      ]),
    );
    sweep.start();
    breathe.start();
    return () => {
      sweep.stop();
      breathe.stop();
    };
  }, [pulse, spin]);

  const rotate = spin.interpolate({ inputRange: [0, 1], outputRange: ["0deg", "360deg"] });
  const scale = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.035] });
  const opacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.55, 1] });
  const kept = Math.max(0, Math.min(1, progress));
  const color = found ? "#b6ffcf" : "#8fe3ff";

  return (
    <View style={[styles.box, { width: size, height: size }]} pointerEvents="none" testID="scan-ring">
      <Animated.View style={[StyleSheet.absoluteFill, { opacity, transform: [{ scale }] }]}>
        <Svg width="100%" height="100%" viewBox="0 0 100 100">
          <Circle cx="50" cy="50" r={RADIUS} stroke="rgba(255,255,255,0.18)" strokeWidth={2.5} fill="none" />
          {kept > 0 ? (
            <Circle
              cx="50"
              cy="50"
              r={RADIUS}
              stroke="#7ee0a1"
              strokeWidth={3.5}
              strokeLinecap="round"
              fill="none"
              strokeDasharray={`${kept * CIRCUMFERENCE} ${CIRCUMFERENCE}`}
              rotation={-90}
              origin="50, 50"
            />
          ) : null}
        </Svg>
      </Animated.View>
      <Animated.View style={[StyleSheet.absoluteFill, { transform: [{ rotate }] }]}>
        <Svg width="100%" height="100%" viewBox="0 0 100 100">
          <Circle
            cx="50"
            cy="50"
            r={RADIUS}
            stroke={color}
            strokeWidth={3.5}
            strokeLinecap="round"
            fill="none"
            strokeDasharray={`${CIRCUMFERENCE * 0.16} ${CIRCUMFERENCE}`}
          />
        </Svg>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  box: { alignItems: "center", justifyContent: "center" },
});
