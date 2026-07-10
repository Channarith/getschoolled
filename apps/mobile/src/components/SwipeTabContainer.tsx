import { useRef } from "react";
import { Animated, Dimensions, PanResponder, type ViewProps } from "react-native";

import type { TabId } from "../types";

/** Tab order left → right; must match BottomTabs. */
export const TAB_ORDER: TabId[] = [
  "home", "drive", "mylist", "careers", "notifications", "settings",
];

const SWIPE_THRESHOLD = 72;
// Fling past this velocity commits the swipe even if under the distance threshold.
const VELOCITY_THRESHOLD = 0.35;
const SLIDE_OUT_MS = 170;
const SLIDE_IN_MS = 230;
// Resistance applied when dragging toward an edge with no tab to reveal.
const EDGE_RESISTANCE = 0.3;

type Props = ViewProps & {
  active: TabId;
  enabled: boolean;
  onChange: (id: TabId) => void;
  children: React.ReactNode;
};

/**
 * Horizontal swipe to change tabs with the whole pane sliding under the finger.
 * The active pane tracks the drag, then slides fully off-screen on commit while
 * the incoming pane slides in from the opposite edge. Only activates on a
 * deliberate sideways gesture so vertical ScrollViews keep priority.
 */
export default function SwipeTabContainer({
  active, enabled, onChange, children, style, ...rest
}: Props) {
  const activeRef = useRef(active);
  activeRef.current = active;

  const width = Dimensions.get("window").width;
  const translateX = useRef(new Animated.Value(0)).current;
  // Guards against starting a new gesture mid-transition (avoids pane flicker).
  const animatingRef = useRef(false);

  const canGo = (dir: -1 | 1) => {
    const idx = TAB_ORDER.indexOf(activeRef.current);
    if (idx < 0) return false;
    const next = idx + dir;
    return next >= 0 && next < TAB_ORDER.length;
  };

  const settleBack = () => {
    Animated.spring(translateX, {
      toValue: 0,
      useNativeDriver: true,
      bounciness: 0,
      speed: 18,
    }).start();
  };

  const commit = (target: TabId, outTo: number) => {
    animatingRef.current = true;
    Animated.timing(translateX, {
      toValue: outTo,
      duration: SLIDE_OUT_MS,
      useNativeDriver: true,
    }).start(() => {
      onChange(target);
      // Incoming pane starts just off the opposite edge, then slides to center.
      translateX.setValue(-outTo);
      Animated.timing(translateX, {
        toValue: 0,
        duration: SLIDE_IN_MS,
        useNativeDriver: true,
      }).start(() => {
        animatingRef.current = false;
      });
    });
  };

  const pan = useRef(
    PanResponder.create({
      onMoveShouldSetPanResponder: (_, g) =>
        enabled
        && !animatingRef.current
        && Math.abs(g.dx) > 18
        && Math.abs(g.dx) > Math.abs(g.dy) * 1.8,
      onPanResponderMove: (_, g) => {
        const dir: -1 | 1 = g.dx < 0 ? 1 : -1;
        const damp = canGo(dir) ? 1 : EDGE_RESISTANCE;
        translateX.setValue(g.dx * damp);
      },
      onPanResponderRelease: (_, g) => {
        if (!enabled) return;
        const idx = TAB_ORDER.indexOf(activeRef.current);
        if (idx < 0) return settleBack();

        const wantsNext =
          (g.dx < -SWIPE_THRESHOLD || g.vx < -VELOCITY_THRESHOLD)
          && g.dx < 0;
        const wantsPrev =
          (g.dx > SWIPE_THRESHOLD || g.vx > VELOCITY_THRESHOLD)
          && g.dx > 0;

        if (wantsNext && idx < TAB_ORDER.length - 1) {
          commit(TAB_ORDER[idx + 1], -width);
        } else if (wantsPrev && idx > 0) {
          commit(TAB_ORDER[idx - 1], width);
        } else {
          settleBack();
        }
      },
      onPanResponderTerminate: () => settleBack(),
    }),
  ).current;

  return (
    <Animated.View
      style={[{ flex: 1, transform: [{ translateX }] }, style]}
      {...(enabled ? pan.panHandlers : {})}
      {...rest}
    >
      {children}
    </Animated.View>
  );
}
