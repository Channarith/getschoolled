"use client";
import { useEffect } from "react";
import { presencePing } from "../lib/api";
import { flushPendingLearnerCheck } from "../lib/pendingBiometrics";
import { flushPendingOnboardingSync } from "../lib/onboardingSync";

/**
 * Invisible component that pings /presence/ping every 60 seconds
 * while the user is signed in. Mounted once in the root layout.
 */
export default function PresenceHeartbeat() {
  useEffect(() => {
    const getActivity = (path: string): string => {
      if (path.startsWith("/live-room") || path.startsWith("/class")) return "live-class";
      if (path.startsWith("/arcade") || path.startsWith("/worlds")) return "game";
      if (path.startsWith("/languages")) return "language";
      if (path.startsWith("/drive")) return "drive-mode";
      if (path.startsWith("/group-class")) return "group-class";
      if (path.startsWith("/kids")) return "kids";
      if (path.startsWith("/corporate")) return "corporate";
      return "browsing";
    };

    const ping = () => {
      const path = window.location.pathname;
      void presencePing({ platform: "web", page: path, activity: getActivity(path) });
    };

    ping(); // immediate ping on mount
    void flushPendingLearnerCheck();
    void flushPendingOnboardingSync();
    const interval = setInterval(() => {
      ping();
      void flushPendingLearnerCheck();
      void flushPendingOnboardingSync();
    }, 60_000);
    const sendHeld = () => {
      void flushPendingLearnerCheck(true);
      void flushPendingOnboardingSync(true);
    };
    window.addEventListener("online", sendHeld);
    return () => {
      clearInterval(interval);
      window.removeEventListener("online", sendHeld);
    };
  }, []);

  return null;
}
