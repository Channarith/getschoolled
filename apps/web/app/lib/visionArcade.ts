/** Same-origin children webcam lab, used by the public vision arcade. */

export const VISION_ARCADE_PATH = "/arcade#vision";

export function visionArcadeFrameSrc(): string {
  const fromEnv = process.env.NEXT_PUBLIC_CHILDREN_LAB_URL?.trim().replace(/\/$/, "") || "";
  if (fromEnv) return `${fromEnv}/lab`;
  return "/children-lab";
}
