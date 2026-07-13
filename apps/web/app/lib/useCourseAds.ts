"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getAdBreaks, type AdBreak, type AdPlan } from "./api";
import { useFlag } from "./flags";

/**
 * Dev/test override: append ?ads=1 (or ?ads=force) to any URL to force ads on
 * for the current page even on an ad-free (VIP/admin/pro) account. This is why
 * an admin test login normally sees nothing — it's VIP/ad-free — so testers can
 * flip ads on without changing accounts.
 */
export function adDevForce(): boolean {
  if (typeof window === "undefined") return false;
  const v = new URLSearchParams(window.location.search).get("ads");
  return v === "1" || v === "force" || v === "on";
}

/** The tier to request ads for, honoring the ?ads=force dev override. */
export function effectiveAdTier(tier: string): string {
  return adDevForce() ? "basic" : (tier || "free");
}

/**
 * Loads the tier-gated ad plan for a course and hands back the pre-roll plus a
 * puller for the next unplayed mid-roll, so slide/segment-based players (class,
 * Drive Mode) can insert ad breaks at natural boundaries.
 */
export function useCourseAds(courseId: string, tier: string) {
  const enabled = useFlag<boolean>("monetization.video_ads", true);
  const [plan, setPlan] = useState<AdPlan | null>(null);
  const played = useRef<Set<number>>(new Set());

  useEffect(() => {
    if (!enabled || !courseId) { setPlan(null); return; }
    let cancelled = false;
    getAdBreaks(courseId, effectiveAdTier(tier))
      .then((p) => { if (!cancelled) { setPlan(p); played.current = new Set(); } })
      .catch(() => { if (!cancelled) setPlan(null); });
    return () => { cancelled = true; };
  }, [courseId, tier, enabled]);

  const preroll = plan?.breaks.find((b) => b.position === "preroll") ?? null;
  const midrolls = (plan?.breaks ?? []).filter((b) => b.position === "midroll");

  /** Pop the next not-yet-played mid-roll (call at a natural break point). */
  const takeNextMidroll = useCallback((): AdBreak | null => {
    for (const b of midrolls) {
      if (!played.current.has(b.offset_s)) { played.current.add(b.offset_s); return b; }
    }
    return null;
  }, [midrolls]);

  return {
    enabled,
    plan,
    adFree: plan?.ad_free ?? true,
    preroll,
    midrolls,
    takeNextMidroll,
  };
}
