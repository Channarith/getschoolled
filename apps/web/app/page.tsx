"use client";

import { useEffect, useState } from "react";
import DNAnonLanding from "./components/DNAnonLanding";
import DNLandingHero from "./components/DNLandingHero";
import { AUTH_EVENT, getToken } from "./lib/api";
import { useT } from "./lib/i18n";

// Front door: signed-out visitors (fresh visit or after sign-out) get the simple two-button page
// (Try the demo / Log in); signed-in users get the orbital hero. Sign-in stays required for everything else.
export default function HomePage() {
  const { t } = useT();
  const [authResolved, setAuthResolved] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    const sync = () => {
      setLoggedIn(Boolean(getToken()));
      setAuthResolved(true);
    };
    sync();
    window.addEventListener(AUTH_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(AUTH_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  if (!authResolved) {
    return (
      <main className="landing-hero">
        <p className="muted" style={{ textAlign: "center", paddingTop: 80 }}>{t("home.loading")}</p>
      </main>
    );
  }
  return loggedIn ? <DNLandingHero /> : <DNAnonLanding />;
}
