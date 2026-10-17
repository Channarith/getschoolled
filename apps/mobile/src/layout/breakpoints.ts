/** Logical-width breakpoints — width is the source of truth (not device model). */
export const WIDTH_MEDIUM_MIN = 600;
export const WIDTH_EXPANDED_MIN = 840;

export type WidthClass = "compact" | "medium" | "expanded";

export const CONTENT_MAX_WIDTH: Record<WidthClass, number | undefined> = {
  compact: undefined,
  medium: undefined,
  expanded: 920,
};

export function widthClassFor(logicalWidth: number): WidthClass {
  if (logicalWidth < WIDTH_MEDIUM_MIN) return "compact";
  if (logicalWidth < WIDTH_EXPANDED_MIN) return "medium";
  return "expanded";
}

export function gridColumnsFor(widthClass: WidthClass): 1 | 2 | 3 {
  if (widthClass === "compact") return 1;
  if (widthClass === "medium") return 2;
  return 3;
}

export function railCardWidth(widthClass: WidthClass): number {
  if (widthClass === "compact") return 168;
  if (widthClass === "medium") return 192;
  return 208;
}

export function railTileWidth(widthClass: WidthClass): number {
  if (widthClass === "compact") return 148;
  if (widthClass === "medium") return 168;
  return 180;
}

export function liveRoomSeatSize(widthClass: WidthClass): { width: number; height: number } {
  if (widthClass === "compact") return { width: 120, height: 142 };
  if (widthClass === "medium") return { width: 132, height: 154 };
  return { width: 144, height: 166 };
}

export function cameraPreviewHeight(widthClass: WidthClass): number {
  if (widthClass === "compact") return 220;
  if (widthClass === "medium") return 280;
  return 340;
}

export function storyboardHeight(widthClass: WidthClass, fullscreen: boolean): number {
  if (fullscreen) {
    if (widthClass === "expanded") return 560;
    if (widthClass === "medium") return 480;
    return 400;
  }
  if (widthClass === "expanded") return 380;
  if (widthClass === "medium") return 360;
  return 330;
}
