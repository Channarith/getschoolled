"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import AppBadges from "./components/AppBadges";
import AdSlot from "./components/AdSlot";
import { Rail, Tile } from "./components/CourseRail";
import MascotImage from "./components/MascotImage";
import { DemoOnlyLanding } from "./components/DemoOnly";
import DNLandingHero from "./components/DNLandingHero";
import DNAnonLanding from "./components/DNAnonLanding";
import { useFlag } from "./lib/flags";
import {
  AUTH_EVENT,
  getHomeFeed,
  getMe,
  getToken,
  type HomeRail,
} from "./lib/api";
import { friendlyError } from "./lib/errors";
import { useT } from "./lib/i18n";
import { useLearningPhrase } from "./lib/learningPhrases";

export default function HomePage() {
  const { t, locale } = useT();
  const learnPhrase = useLearningPhrase();
  const carousels = useFlag<boolean>("ux.netflix_carousels", true);
  const [rails, setRails] = useState<HomeRail[] | null>(null);
  const [error, setError] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);
  const [authResolved, setAuthResolved] = useState(false);
  const [tier, setTier] = useState("free");

  useEffect(() => {
    let alive = true;
    let feedController = new AbortController();
    const sync = () => {
      feedController.abort();
      feedController = new AbortController();
      const signal = feedController.signal;
      const authed = Boolean(getToken());
      setLoggedIn(authed);
      setAuthResolved(true);
      if (authed) {
        getHomeFeed(false, locale, signal)
          .then((r) => { if (!alive) return; setRails(r); })
          .catch((e) => { if (!alive || signal.aborted) return; setError(String(e)); });
        getMe()
          .then((m) => { if (!alive) return; setTier(m.tier || "free"); })
          .catch(() => { if (!alive) return; setTier("free"); });
      } else {
        setRails(null);
        setError("");
      }
    };
    sync();
    window.addEventListener(AUTH_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      alive = false;
      feedController.abort();
      window.removeEventListener(AUTH_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, [locale]);

  if (!authResolved) {
    return (
      <main className="landing-hero">
        <p className="muted" style={{ textAlign: "center", paddingTop: 80 }}>{t("home.loading")}</p>
      </main>
    );
  }

  // Front door split:
  //   - Signed-OUT visitors see <DNAnonLanding/>: the pre-DN simple landing
  //     (centered mascot above two buttons: "Try the demo" / "Log in"),
  //     restyled in the DN cream/navy palette.
  //   - Signed-IN users see the full <DNLandingHero/>: brand headline, the
  //     orbital mascot stage with the five nav tabs (Our Story, Vision Play
  //     Lab, On the Go, Live Class, Careers) as a visual launcher, and the
  //     "one tutor / learn by playing / live classes" feature cards.
  if (!loggedIn) return <DNAnonLanding />;
  return <DNLandingHero />;
}
