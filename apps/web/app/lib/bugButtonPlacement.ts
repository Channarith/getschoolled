// Where the floating bug-report button may sit. Phone layouts put their own controls
// (the Sala ask pill, the On the Go mascot stack) in the bottom-right corner.

const IMMERSIVE = ["/demo/on-the-go", "/drive"];
const OWN_BOTTOM_RIGHT = ["/learn", "/demo", "/class", "/live-room"];

export function bugButtonHidden(pathname: string): boolean {
  return pathname === "/report-bug" || IMMERSIVE.some((p) => pathname === p || pathname.startsWith(p + "/"));
}

export function defaultBugPosition(pathname: string, viewportW: number, viewportH: number, size: number): { x: number; y: number } {
  const phone = viewportW <= 700 || viewportH <= 500;
  const crowded = phone && OWN_BOTTOM_RIGHT.some((p) => pathname === p || pathname.startsWith(p + "/"));
  return { x: viewportW - size - 14, y: viewportH - size - 18 - (crowded ? 64 : 0) };
}
