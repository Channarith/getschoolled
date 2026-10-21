import { useRef } from "react";
import {
  Animated, Pressable, StyleSheet, type PressableProps, type StyleProp, type ViewStyle,
} from "react-native";

import { theme } from "../theme";

type Props = PressableProps & {
  style?: StyleProp<ViewStyle>;
  scaleTo?: number;
  children: React.ReactNode;
};

/** Netflix-style press feedback — subtle scale, not a flat button flash. */
export default function AnimatedPressable({
  children, style, scaleTo = theme.motion.pressScale, onPressIn, onPressOut, ...rest
}: Props) {
  const scale = useRef(new Animated.Value(1)).current;

  return (
    <Pressable
      {...rest}
      style={[styles.hit, style]}
      onPressIn={(e) => {
        Animated.spring(scale, {
          toValue: scaleTo,
          useNativeDriver: true,
          speed: 40,
          bounciness: 0,
        }).start();
        onPressIn?.(e);
      }}
      onPressOut={(e) => {
        Animated.spring(scale, {
          toValue: 1,
          useNativeDriver: true,
          speed: 28,
          bounciness: 4,
        }).start();
        onPressOut?.(e);
      }}
    >
      <Animated.View style={{ transform: [{ scale }] }} pointerEvents="none">
        {children}
      </Animated.View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  hit: { alignItems: "center", justifyContent: "center" },
});
