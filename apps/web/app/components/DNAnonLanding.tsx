"use client";

import Link from "next/link";
import { useT } from "../lib/i18n";
import { useSecretLogoTaps } from "../lib/useSecretLogoTaps";
import MascotImage from "./MascotImage";

/**
 * DN "Dark Navy" ANONYMOUS landing — what everyone sees before signing in.
 *
 * Keeps the pre-DN layout (brand wordmark + big centered mascot above two
 * buttons: "Try the demo" and "Log in") but restyled in the DN palette so
 * it fits the rest of the site. The richer DN hero (orbital stage, feature
 * cards, "AI Precision. Human Warmth.") is reserved for signed-in users
 * and lives in DNLandingHero.
 *
 * Routes:
 *   [Try the demo] → /demo  (sales demo flow)
 *   [Log in]       → /login
 */
export default function DNAnonLanding() {
  const onLogoClick = useSecretLogoTaps();
  const { t } = useT();
  return (
    <main className="dn-anon-landing">
      <div className="dn-anon-content">
        <div className="dn-anon-brand" aria-hidden onClick={onLogoClick}>
          Salareen
        </div>
        <MascotImage
          width={220}
          alt="Salareen mascot"
          className="dn-anon-mascot"
        />
        <h1 className="dn-anon-title">
          AI Precision. Human <em>Warmth.</em>
        </h1>
        <p className="dn-anon-subtitle">
          A patient tutor for every learner, in every language.
        </p>
        <div className="dn-anon-cta-row" data-testid="landing-guest-cta">
          <Link href="/demo" className="btn-primary">
            {t("landing.tryDemo")}
          </Link>
          <Link href="/login" className="btn-outline">
            {t("landing.logIn")}
          </Link>
        </div>
      </div>
    </main>
  );
}
