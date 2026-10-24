"use client";

import FriendlyError from "./components/FriendlyError";
import { statusFromError } from "./lib/friendlyStatus";

// Last resort: the root layout itself failed, so there is no locale provider or nav here.
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const status = statusFromError(error);
  const device = typeof navigator !== "undefined" ? (navigator.language || "en") : "en";
  return (
    <html lang={device.split("-")[0]}>
      <body style={{ margin: 0, background: "#0b1020" }}>
        <FriendlyError status={status} locale={device} onRetry={() => { reset(); return true; }} />
      </body>
    </html>
  );
}
