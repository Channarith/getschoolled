import { useEffect, useLayoutEffect, useRef } from "react";
import {
  Animated, PanResponder, type StyleProp, type ViewStyle, useWindowDimensions,
} from "react-native";

const EDGE_PADDING = 14;

type Props = {
  accessibilityLabel: string;
  aboveTabs?: boolean;
  children: React.ReactNode;
  disabled?: boolean;
  height: number;
  initialSide?: "left" | "right";
  onPress: () => void;
  style?: StyleProp<ViewStyle>;
  testID?: string;
  width: number;
};

/** A tap target that can be dragged anywhere within the current screen. */
export default function DraggableFloatingButton({
  accessibilityLabel,
  aboveTabs = false,
  children,
  disabled = false,
  height,
  initialSide = "right",
  onPress,
  style,
  testID,
  width,
}: Props) {
  const { width: screenWidth, height: screenHeight } = useWindowDimensions();
  const bottomOffset = aboveTabs ? 82 : 16;
  const initialLeft = initialSide === "left"
    ? EDGE_PADDING
    : screenWidth - EDGE_PADDING - width;
  const initialTop = screenHeight - bottomOffset - height;

  const dimsRef = useRef({ width: screenWidth, height: screenHeight });
  const onPressRef = useRef(onPress);
  const disabledRef = useRef(disabled);
  const pos = useRef(new Animated.ValueXY({ x: initialLeft, y: initialTop })).current;
  const lastPos = useRef({ x: initialLeft, y: initialTop });
  const dragDistance = useRef(0);

  useLayoutEffect(() => {
    dimsRef.current = { width: screenWidth, height: screenHeight };
  }, [screenWidth, screenHeight]);
  useEffect(() => { onPressRef.current = onPress; }, [onPress]);
  useEffect(() => { disabledRef.current = disabled; }, [disabled]);

  useEffect(() => {
    const maxX = Math.max(0, screenWidth - width);
    const maxY = Math.max(0, screenHeight - height);
    const isAtDefaultEdge = initialSide === "left"
      ? lastPos.current.x <= EDGE_PADDING + 4
      : lastPos.current.x >= maxX - EDGE_PADDING - 4;
    const next = {
      x: isAtDefaultEdge
        ? (initialSide === "left" ? EDGE_PADDING : maxX - EDGE_PADDING)
        : Math.max(0, Math.min(lastPos.current.x, maxX)),
      y: isAtDefaultEdge
        ? Math.max(0, Math.min(screenHeight - bottomOffset - height, maxY))
        : Math.max(0, Math.min(lastPos.current.y, maxY)),
    };
    pos.setValue(next);
    lastPos.current = next;
  }, [aboveTabs, bottomOffset, height, initialSide, pos, screenHeight, screenWidth, width]);

  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: () => {
        dragDistance.current = 0;
        pos.stopAnimation();
        pos.setOffset(lastPos.current);
        pos.setValue({ x: 0, y: 0 });
      },
      onPanResponderMove: (_, gesture) => {
        dragDistance.current = Math.abs(gesture.dx) + Math.abs(gesture.dy);
        Animated.event([null, { dx: pos.x, dy: pos.y }], {
          useNativeDriver: false,
        })(_, gesture);
      },
      onPanResponderRelease: (_, gesture) => {
        pos.flattenOffset();
        const maxX = Math.max(0, dimsRef.current.width - width);
        const maxY = Math.max(0, dimsRef.current.height - height);
        const next = {
          x: Math.max(0, Math.min(lastPos.current.x + gesture.dx, maxX)),
          y: Math.max(0, Math.min(lastPos.current.y + gesture.dy, maxY)),
        };
        lastPos.current = next;
        pos.setValue(next);
        if (dragDistance.current < 8 && !disabledRef.current) {
          onPressRef.current();
        }
      },
      onPanResponderTerminate: () => {
        pos.flattenOffset();
        pos.setValue(lastPos.current);
      },
    }),
  ).current;

  return (
    <Animated.View
      {...panResponder.panHandlers}
      accessible
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityState={{ disabled }}
      testID={testID}
      style={[
        {
          position: "absolute",
          zIndex: 1000,
          elevation: 14,
          width,
          height,
          left: pos.x,
          top: pos.y,
        },
        style,
        disabled && { opacity: 0.4 },
      ]}
    >
      {children}
    </Animated.View>
  );
}
