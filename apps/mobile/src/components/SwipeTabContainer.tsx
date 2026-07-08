import { useRef } from "react";
import { PanResponder, View, type ViewProps } from "react-native";

import type { TabId } from "../types";

/** Tab order left → right; must match BottomTabs. */
export const TAB_ORDER: TabId[] = [
  "home", "drive", "mylist", "careers", "notifications", "settings",
];

const SWIPE_THRESHOLD = 72;

type Props = ViewProps & {
  active: TabId;
  enabled: boolean;
  onChange: (id: TabId) => void;
  children: React.ReactNode;
};

/**
 * Horizontal swipe to change tabs. Only activates on a deliberate sideways
 * gesture so vertical ScrollViews keep priority.
 */
export default function SwipeTabContainer({
  active, enabled, onChange, children, style, ...rest
}: Props) {
  const activeRef = useRef(active);
  activeRef.current = active;

  const pan = useRef(
    PanResponder.create({
      onMoveShouldSetPanResponder: (_, g) =>
        enabled
        && Math.abs(g.dx) > 20
        && Math.abs(g.dx) > Math.abs(g.dy) * 1.8,
      onPanResponderRelease: (_, g) => {
        if (!enabled) return;
        const idx = TAB_ORDER.indexOf(activeRef.current);
        if (idx < 0) return;
        if (g.dx < -SWIPE_THRESHOLD && idx < TAB_ORDER.length - 1) {
          onChange(TAB_ORDER[idx + 1]);
        } else if (g.dx > SWIPE_THRESHOLD && idx > 0) {
          onChange(TAB_ORDER[idx - 1]);
        }
      },
    }),
  ).current;

  return (
    <View
      style={[{ flex: 1 }, style]}
      {...(enabled ? pan.panHandlers : {})}
      {...rest}
    >
      {children}
    </View>
  );
}
