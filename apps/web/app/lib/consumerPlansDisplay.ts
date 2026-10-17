import type { ConsumerPlan } from "./api";

export const CONSUMER_TIER_ORDER = ["free", "basic", "pro", "premium"] as const;

export function formatMonthlyPrice(plan: ConsumerPlan): string {
  if (plan.price_usd <= 0) return "$0";
  const whole = Math.round(plan.price_usd * 100) % 100 === 0;
  return whole ? `$${Math.round(plan.price_usd)}/mo` : `$${plan.price_usd.toFixed(2)}/mo`;
}

export function orderedConsumerPlans(
  catalog: Record<string, ConsumerPlan>,
): ConsumerPlan[] {
  return CONSUMER_TIER_ORDER.map((tier) => catalog[tier]).filter(Boolean);
}
