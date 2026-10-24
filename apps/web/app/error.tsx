"use client";

import { useEffect } from "react";
import FriendlyError from "./components/FriendlyError";
import { statusFromError } from "./lib/friendlyStatus";

// Catches a failed page or segment (a crashed render, or a data call that gave up with a 5xx).
export default function SegmentError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error("[segment error]", error);
  }, [error]);
  const status = statusFromError(error);
  return <FriendlyError status={status} onRetry={() => { reset(); return true; }} autoRetrySeconds={status && [502, 503, 504].includes(status) ? 15 : 0} />;
}
