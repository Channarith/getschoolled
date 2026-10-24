"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import FriendlyError from "./FriendlyError";
import { FRIENDLY_ERROR_EVENT } from "../lib/friendlyStatus";

type Shown = { status: number | null; offline: boolean };

// Shows the mascot screen when the connection drops or an important call keeps failing.
// Quiet by design: one screen at a time, and it will not come back for 30 s after a dismissal.
export default function FriendlyErrorHost() {
  const [shown, setShown] = useState<Shown | null>(null);
  const quietUntil = useRef(0);

  const close = useCallback(() => {
    quietUntil.current = Date.now() + 30000;
    setShown(null);
  }, []);

  useEffect(() => {
    const onFailure = (event: Event) => {
      const status = Number((event as CustomEvent).detail?.status) || 0;
      if (Date.now() < quietUntil.current) return;
      setShown((current) => current || { status: status || null, offline: false });
    };
    const onOffline = () => setShown({ status: null, offline: true });
    const onOnline = () => setShown((current) => (current?.offline ? null : current));
    window.addEventListener(FRIENDLY_ERROR_EVENT, onFailure);
    window.addEventListener("offline", onOffline);
    window.addEventListener("online", onOnline);
    return () => {
      window.removeEventListener(FRIENDLY_ERROR_EVENT, onFailure);
      window.removeEventListener("offline", onOffline);
      window.removeEventListener("online", onOnline);
    };
  }, []);

  if (!shown) return null;
  const retry = async () => {
    try {
      const response = await fetch("/health", { cache: "no-store" });
      return response.ok;
    } catch {
      return false;
    }
  };
  return (
    <FriendlyError
      status={shown.status}
      kind={shown.offline ? "offline" : undefined}
      onRetry={retry}
      autoRetrySeconds={15}
      onClose={close}
    />
  );
}
