"use client";

import { useRouter } from "next/navigation";
import type { MouseEvent } from "react";
import { useCallback } from "react";

import { createTapCounter, isPlainPointerClick, SECRET_PATH } from "./secretTaps";

// One counter for every Salareen logo on the page (header, landing, demo shells), so the taps add up wherever they land.
const counter = createTapCounter();

/** onClick for a Salareen logo. Clicks 1-3 behave exactly as before; the 4th goes to the hidden page. */
export function useSecretLogoTaps() {
  const router = useRouter();
  return useCallback(
    (event: MouseEvent) => {
      if (!isPlainPointerClick(event)) return;
      if (counter.tap()) {
        event.preventDefault();
        router.push(SECRET_PATH);
      }
    },
    [router],
  );
}
