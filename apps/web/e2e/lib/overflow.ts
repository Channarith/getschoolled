import { expect, type Page } from "@playwright/test";

/**
 * Viewport-wide overflow/clipping sweep (V&V master plan WV-21).
 *
 * The single highest-ROI responsive check for this app: `globals.css` has zero
 * CSS breakpoints (master plan risk R14), so a layout that fits a desktop can
 * silently clip or trigger a horizontal scrollbar on a phone. This helper is
 * pure assertions — no pixel baselines — so it is immune to per-OS font metrics
 * and never flakes on rendering differences between CI and a laptop.
 */

export type Viewport = { name: string; width: number; height: number };

/**
 * Viewport *samples* (not breakpoint boundaries) from master plan §3.4:
 *   V1 small Android phone, V4 laptop, V5 desktop.
 * Exercises narrow/medium/wide widths against the one breakpoint-free layout.
 */
export const SWEEP_VIEWPORTS: Viewport[] = [
  { name: "V1 small-phone", width: 360, height: 780 },
  { name: "V4 laptop", width: 1280, height: 800 },
  { name: "V5 desktop", width: 1920, height: 1080 },
];

// Horizontal-overflow tolerance in CSS px. Sub-pixel rounding and a 1px
// scrollbar gutter are not real defects; anything wider is content escaping
// the viewport.
const OVERFLOW_TOLERANCE_PX = 1;

/**
 * Assert the document does not overflow its viewport horizontally at the
 * current viewport size.
 */
export async function expectNoHorizontalOverflow(page: Page, label = "page"): Promise<void> {
  const overflow = await page.evaluate(() => {
    // Content can escape via either the root or <body> (a wide table or an
    // unwrapped long string often overflows body while <html> stays clamped),
    // so take the wider of the two against the viewport width.
    const widest = Math.max(
      document.documentElement.scrollWidth,
      document.body ? document.body.scrollWidth : 0,
    );
    return widest - document.documentElement.clientWidth;
  });
  expect(overflow, `${label} overflows horizontally by ${overflow}px`).toBeLessThanOrEqual(
    OVERFLOW_TOLERANCE_PX,
  );
}

/**
 * Load `path`, wait for a stable render signal, and assert no horizontal
 * overflow at each sweep viewport. Restores the desktop viewport afterward so a
 * subsequent assertion in the same test sees a normal window.
 *
 * @param waitFor CSS selector proving the route rendered (defaults to the page
 *   heading). Content-loading routes should pass a route-specific selector.
 */
export async function sweepRouteOverflow(
  page: Page,
  path: string,
  opts: { viewports?: Viewport[]; waitFor?: string } = {},
): Promise<void> {
  const viewports = opts.viewports ?? SWEEP_VIEWPORTS;
  const waitFor = opts.waitFor ?? "h1, h2";
  for (const vp of viewports) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto(path);
    await page.locator(waitFor).first().waitFor({ state: "visible", timeout: 15_000 });
    await expectNoHorizontalOverflow(page, `${path} @ ${vp.name} (${vp.width}px)`);
  }
  // Leave the page at the desktop representative for any follow-on assertions.
  await page.setViewportSize({ width: 1280, height: 800 });
}
