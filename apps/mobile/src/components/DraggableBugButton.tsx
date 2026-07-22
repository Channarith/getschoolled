import { useEffect, useLayoutEffect, useRef } from "react";
import {
  Animated, PanResponder, StyleSheet, Text, useWindowDimensions,
} from "react-native";

const BUTTON_SIZE = 42;
const EDGE_PADDING = 14;

interface Props {
  onPress: () => void;
  disabled?: boolean;
  aboveTabs?: boolean;
}

export default function DraggableBugButton({ onPress, disabled, aboveTabs }: Props) {
  const { width: screenWidth, height: screenHeight } = useWindowDimensions();

  // Keep refs current so the frozen PanResponder closure always reads fresh values.
  const dimsRef = useRef({ width: screenWidth, height: screenHeight });
  const onPressRef = useRef(onPress);
  const disabledRef = useRef(disabled);
  useLayoutEffect(() => { dimsRef.current = { width: screenWidth, height: screenHeight }; }, [screenWidth, screenHeight]);
  useEffect(() => { onPressRef.current = onPress; }, [onPress]);
  useEffect(() => { disabledRef.current = disabled; }, [disabled]);

  const bottomOffset = aboveTabs ? 82 : 16;
  const initLeft = screenWidth - EDGE_PADDING - BUTTON_SIZE;
  const initTop = screenHeight - bottomOffset - BUTTON_SIZE;

  const pos = useRef(new Animated.ValueXY({ x: initLeft, y: initTop })).current;
  const lastPos = useRef({ x: initLeft, y: initTop });
  const dragDist = useRef(0);

  // When aboveTabs changes, reposition to new default bottom (only if the button
  // is still parked near the right edge and hasn't been dragged away).
  useEffect(() => {
    const { width: w, height: h } = dimsRef.current;
    const newTop = h - (aboveTabs ? 82 : 16) - BUTTON_SIZE;
    const currentLeft = lastPos.current.x;
    if (currentLeft >= w - EDGE_PADDING - BUTTON_SIZE - 4) {
      const next = { x: currentLeft, y: newTop };
      pos.setValue(next);
      lastPos.current = next;
    }
  }, [aboveTabs, pos]);

  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: () => {
        dragDist.current = 0;
        pos.stopAnimation();
        pos.setOffset({ x: lastPos.current.x, y: lastPos.current.y });
        pos.setValue({ x: 0, y: 0 });
      },
      onPanResponderMove: (_, gesture) => {
        dragDist.current = Math.abs(gesture.dx) + Math.abs(gesture.dy);
        Animated.event([null, { dx: pos.x, dy: pos.y }], {
          useNativeDriver: false,
        })(_, gesture);
      },
      onPanResponderRelease: (_, gesture) => {
        // flattenOffset collapses setOffset(lastPos)+setValue({dx,dy}) → plain value,
        // then setValue below sets the final clamped position with offset cleared.
        pos.flattenOffset();
        const { width: sw, height: sh } = dimsRef.current;
        const rawX = lastPos.current.x + gesture.dx;
        const rawY = lastPos.current.y + gesture.dy;
        const clampedX = Math.max(0, Math.min(rawX, sw - BUTTON_SIZE));
        const clampedY = Math.max(0, Math.min(rawY, sh - BUTTON_SIZE));
        lastPos.current = { x: clampedX, y: clampedY };
        pos.setValue({ x: clampedX, y: clampedY });

        if (dragDist.current < 8 && !disabledRef.current) {
          onPressRef.current();
        }
      },
    })
  ).current;

  return (
    <Animated.View
      {...panResponder.panHandlers}
      accessible
      accessibilityRole="button"
      accessibilityLabel="Report a bug"
      style={[
        styles.container,
        { left: pos.x, top: pos.y },
        disabled && styles.disabled,
      ]}
    >
      <Text style={styles.icon}>🐛</Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: "absolute",
    zIndex: 1000,
    elevation: 14,
    width: BUTTON_SIZE,
    height: BUTTON_SIZE,
    borderRadius: BUTTON_SIZE / 2,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(30,27,75,0.82)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.3)",
    shadowColor: "#000",
    shadowOpacity: 0.28,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    opacity: 0.82,
  },
  disabled: { opacity: 0.4 },
  icon: { fontSize: 19 },
});
