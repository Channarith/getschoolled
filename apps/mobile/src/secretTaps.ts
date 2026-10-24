// Hidden way into the On the Go demo: four quick taps on the Salareen logo, each within WINDOW_MS of the previous.
// Same rule as the web (apps/web/app/lib/secretTaps.ts). Pure logic so it is unit-tested with a fake clock.

export const SECRET_TAP_COUNT = 4;
export const SECRET_TAP_WINDOW_MS = 2500;

export type TapCounter = { tap: () => boolean; reset: () => void };

export function createTapCounter(
  options: { count?: number; windowMs?: number; now?: () => number } = {},
): TapCounter {
  const count = options.count ?? SECRET_TAP_COUNT;
  const windowMs = options.windowMs ?? SECRET_TAP_WINDOW_MS;
  const now = options.now ?? (() => Date.now());
  let taps = 0;
  let last = 0;
  return {
    tap() {
      const t = now();
      taps = taps > 0 && t - last <= windowMs ? taps + 1 : 1;
      last = t;
      if (taps >= count) {
        taps = 0;
        last = 0;
        return true;
      }
      return false;
    },
    reset() {
      taps = 0;
      last = 0;
    },
  };
}
