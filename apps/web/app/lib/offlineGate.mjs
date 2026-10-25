// Pure decision for "should this link click be intercepted because the browser is offline?" (testable without a DOM).
export function shouldBlockOfflineNavigation(nav) {
  if (!nav || typeof nav.onLine !== "boolean") return false; // unknown: let the browser try
  return nav.onLine === false;
}
