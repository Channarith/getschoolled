/** Shared web layout width classes (mirror mobile compact / medium / expanded). */
export const LAYOUT_WIDTH = {
  compactMax: 599,
  mediumMin: 600,
  mediumMax: 839,
  expandedMin: 840,
} as const;

export type LayoutWidthClass = "compact" | "medium" | "expanded";

export const EXPANDED_LAYOUT_MEDIA = `(min-width: ${LAYOUT_WIDTH.expandedMin}px)`;

export function layoutWidthClass(width: number): LayoutWidthClass {
  if (width <= LAYOUT_WIDTH.compactMax) return "compact";
  if (width <= LAYOUT_WIDTH.mediumMax) return "medium";
  return "expanded";
}

/** Learning-style onboarding cards: one per page until expanded desktop. */
export function learningModesPerPage(width: number): 1 | 2 {
  return layoutWidthClass(width) === "expanded" ? 2 : 1;
}

export function isImmersiveSetupPath(pathname: string): boolean {
  return pathname === "/onboarding" || pathname.startsWith("/onboarding/");
}
