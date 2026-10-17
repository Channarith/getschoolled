import { useMemo } from "react";
import { useWindowDimensions } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import {
  CONTENT_MAX_WIDTH,
  gridColumnsFor,
  widthClassFor,
} from "./breakpoints";

/** Matches BottomTabs min bar height (paddingTop + tab minHeight). */
const TAB_BAR_CONTENT_HEIGHT = 66;

export function useLayoutMetrics() {
  const { width, height, fontScale } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const widthClass = widthClassFor(width);

  return useMemo(() => {
    const isCompact = widthClass === "compact";
    const isMedium = widthClass === "medium";
    const isExpanded = widthClass === "expanded";
    const horizontalPadding = isCompact ? 16 : isMedium ? 20 : 24;
    const usableWidth = width - insets.left - insets.right;
    const cap = CONTENT_MAX_WIDTH[widthClass];
    const contentMaxWidth = cap ? Math.min(usableWidth, cap) : usableWidth;
    const tabBarBottomPad = Math.max(insets.bottom, 8);
    const tabBarClearance = TAB_BAR_CONTENT_HEIGHT + tabBarBottomPad;
    const floatingBottomOffset = tabBarClearance + 8;
    const largeText = fontScale >= 1.3;
    const gridColumns = gridColumnsFor(widthClass);
    const overlayTopPad = Math.max(insets.top, 8) + 8;
    const overlayBottomPad = Math.max(insets.bottom, 12);

    return {
      width,
      height,
      fontScale,
      insets,
      widthClass,
      isCompact,
      isMedium,
      isExpanded,
      horizontalPadding,
      contentMaxWidth,
      tabBarBottomPad,
      tabBarClearance,
      floatingBottomOffset,
      largeText,
      gridColumns,
      overlayTopPad,
      overlayBottomPad,
    };
  }, [width, height, fontScale, insets, widthClass]);
}
