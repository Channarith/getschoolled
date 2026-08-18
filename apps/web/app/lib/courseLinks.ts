/**
 * Watch (/watch) is gated by engagement.watch_window (default off).
 * Rewrite those deep links to Drive Mode, the working course-open path
 * used for audio catalog items elsewhere.
 */
export function resolveCourseDeepLink(href: string): string {
  if (!href) return href;
  const path = href.startsWith("http")
    ? (() => {
        try {
          return new URL(href).pathname + new URL(href).search;
        } catch {
          return href;
        }
      })()
    : href;
  if (!path.startsWith("/watch")) return href;
  const qIdx = path.indexOf("?");
  const params = new URLSearchParams(qIdx >= 0 ? path.slice(qIdx + 1) : "");
  const course = params.get("course");
  return course
    ? `/drive?course=${encodeURIComponent(course)}`
    : "/drive";
}

export function courseOpenHref(courseId: string, mediaOrFormat?: string): string {
  const fmt = (mediaOrFormat || "").toLowerCase();
  if (fmt === "audio") return `/drive?course=${encodeURIComponent(courseId)}`;
  if (fmt === "live_class") return `/class?lesson=${encodeURIComponent(courseId)}`;
  // Video / default: Drive until watch_window is enabled
  return `/drive?course=${encodeURIComponent(courseId)}`;
}
