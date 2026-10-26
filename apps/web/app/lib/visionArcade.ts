/** Same-origin children webcam lab, used by the public vision arcade. */

export const VISION_ARCADE_PATH = "/arcade#vision";

export function visionArcadeFrameSrc(opts: { demo?: boolean } = {}): string {
  const fromEnv = process.env.NEXT_PUBLIC_CHILDREN_LAB_URL?.trim().replace(/\/$/, "") || "";
  const base = fromEnv ? `${fromEnv}/lab` : "/children-lab";
  return opts.demo ? `${base}?demo=1` : base;
}
