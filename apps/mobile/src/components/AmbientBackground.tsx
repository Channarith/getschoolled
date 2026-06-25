import { useEffect, useRef } from "react";
import { Animated, Image, StyleSheet, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { theme, wallpapers } from "../theme";

/** Full-bleed cinematic wallpaper with slow Ken Burns drift (matches web site-bg). */
export default function AmbientBackground() {
  const scale = useRef(new Animated.Value(1)).current;
  const translateX = useRef(new Animated.Value(0)).current;
  const translateY = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const half = theme.motion.kenBurnsMs / 2;
    const drift = Animated.loop(
      Animated.sequence([
        Animated.parallel([
          Animated.timing(scale, { toValue: 1.12, duration: half, useNativeDriver: true }),
          Animated.timing(translateX, { toValue: -12, duration: half, useNativeDriver: true }),
          Animated.timing(translateY, { toValue: -8, duration: half, useNativeDriver: true }),
        ]),
        Animated.parallel([
          Animated.timing(scale, { toValue: 1, duration: half, useNativeDriver: true }),
          Animated.timing(translateX, { toValue: 0, duration: half, useNativeDriver: true }),
          Animated.timing(translateY, { toValue: 0, duration: half, useNativeDriver: true }),
        ]),
      ]),
    );
    drift.start();
    return () => drift.stop();
  }, [scale, translateX, translateY]);

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
      <Animated.View
        style={[
          styles.layer,
          { transform: [{ scale }, { translateX }, { translateY }] },
        ]}
      >
        <Image source={wallpapers.hero} style={styles.image} resizeMode="cover" />
      </Animated.View>
      <LinearGradient
        colors={[
          "rgba(11,16,32,0.55)",
          "rgba(11,16,32,0.82)",
          "rgba(11,16,32,0.95)",
        ]}
        locations={[0, 0.45, 1]}
        style={StyleSheet.absoluteFill}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  layer: {
    position: "absolute",
    top: "-8%",
    left: "-8%",
    width: "116%",
    height: "116%",
  },
  image: { width: "100%", height: "100%" },
});
