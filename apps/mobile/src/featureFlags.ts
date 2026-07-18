import { useEffect, useState } from "react";

import { getFlag } from "./api";

export function useFeatureFlag(key: string, fallback = false): boolean {
  const [enabled, setEnabled] = useState(fallback);

  useEffect(() => {
    let cancelled = false;
    getFlag(key)
      .then((value) => {
        if (!cancelled) setEnabled(Boolean(value));
      })
      .catch(() => {
        if (!cancelled) setEnabled(fallback);
      });
    return () => {
      cancelled = true;
    };
  }, [fallback, key]);

  return enabled;
}
