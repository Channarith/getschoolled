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

/**
 * Learning-style onboarding cards: one per page on every viewport.
 *
 * The onboarding "How do you learn best?" step shows exactly one mode card
 * per page across phones, tablets, and desktops. That matches the mobile
 * experience (see v0.66.0 changelog) and gives the MascotActor in the left
 * art pane room to act out the focused mode without competing for width
 * with a second card on wider screens.
 *
 * The `width` argument is kept so this stays a stable, pure helper the
 * matchMedia hook and the companion unit test can call, even though every
 * viewport returns the same value today.
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function learningModesPerPage(_width: number): 1 {
  return 1;
}

export function isImmersiveSetupPath(pathname: string): boolean {
  return pathname === "/onboarding" || pathname.startsWith("/onboarding/");
}
