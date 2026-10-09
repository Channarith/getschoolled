"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import LandingAuthPanel from "./LandingAuthPanel";
import MascotImage from "./MascotImage";
import { useFlag, useFlags } from "../lib/flags";
import { useT } from "../lib/i18n";
import { DEMO_ONLY_FEATURE_IDS, SALES_DEMO_FEATURES, SALES_DEMO_FLAGS } from "../lib/salesDemo";

// Screens for demo-only mode (sales_demo.exclusive): a minimal landing with just the
// mascot and two choices, and a sign-in page that is only the landing's sign-in box.

function DemoOnlyShell({
  children,
  kicker = true,
  brand = false,
}: {
  children: React.ReactNode;
  kicker?: boolean;
  brand?: boolean;
}) {
  const { t } = useT();
  return (
    <main className="landing-hero">
      <div
        className="landing-hero-bg site-bg-layer site-bg-kenburns site-bg-motion-2"
        style={{
          backgroundImage:
            "linear-gradient(0deg, rgba(11,16,32,.94) 0%, rgba(11,16,32,.35) 45%, rgba(11,16,32,.85) 100%), url(/wallpapers/wisdom_bodhi.webp)",
          backgroundSize: "cover", backgroundPosition: "center",
        }}
        aria-hidden
      />
      <div className="landing-inner" style={{ textAlign: "center" }}>
        {brand && (
          <div
            style={{
              color: "#fff",
              fontSize: 32,
              fontWeight: 700,
              letterSpacing: 4,
              textTransform: "uppercase",
              opacity: 0.92,
              marginBottom: 28,
            }}
          >
            Salareen
          </div>
        )}
        <MascotImage width={140} className="landing-mascot" alt="Salareen mascot" />
        {kicker && <span className="theme-badge">{t("hero.kicker")}</span>}
        {children}
      </div>
    </main>
  );
}

// Buttons use the site's cream body color (--bg = #f4e9d8) so the landing
// matches the rest of the website instead of a loud brand purple.
const ctaBase: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "16px 42px",
  minWidth: 184,
  borderRadius: 12,
  fontSize: 16,
  fontWeight: 600,
  letterSpacing: 0.3,
  textDecoration: "none",
  lineHeight: 1,
  transition: "transform 120ms ease, box-shadow 120ms ease, background 120ms ease",
};

const primaryCta: React.CSSProperties = {
  ...ctaBase,
  background: "#f4e9d8",
  color: "#0b1020",
  border: "1px solid #f4e9d8",
  boxShadow: "0 14px 30px rgba(0,0,0,.35)",
};

const secondaryCta: React.CSSProperties = {
  ...ctaBase,
  background: "transparent",
  color: "#f4e9d8",
  border: "1.5px solid rgba(244,233,216,0.75)",
};

export function DemoOnlyLanding() {
  const { t } = useT();
  return (
    <DemoOnlyShell kicker={false} brand>
      <h1
        style={{
          color: "#fff",
          fontSize: 15,
          lineHeight: 1.2,
          fontWeight: 600,
          letterSpacing: 0.3,
          margin: "18px auto 34px",
          textShadow: "0 2px 12px rgba(0,0,0,.45)",
        }}
      >
        {t("hero.kicker")}
      </h1>
      <div
        style={{
          display: "flex",
          gap: 16,
          justifyContent: "center",
          flexWrap: "wrap",
        }}
      >
        <Link href="/demo" style={primaryCta}>Try the demo</Link>
        <Link href="/login" style={secondaryCta}>Log in</Link>
      </div>
    </DemoOnlyShell>
  );
}

export function DemoOnlyShowcase() {
  const { flags } = useFlags();
  const features = SALES_DEMO_FEATURES.filter(
    (f) => (DEMO_ONLY_FEATURE_IDS as readonly string[]).includes(f.id) && flags[f.flagKey] !== false,
  );
  return (
    <DemoOnlyShell>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 16,
          width: "min(760px, 92vw)",
          margin: "34px auto 0",
        }}
      >
        {features.map((f) => (
          <Link
            key={f.id}
            href={f.href}
            className="card"
            style={{ padding: 22, textAlign: "left", color: "#fff", textDecoration: "none", background: "rgba(15,23,42,0.78)" }}
          >
            <div aria-hidden style={{ fontSize: 40 }}>{f.emoji}</div>
            <h3 style={{ margin: "8px 0 2px" }}>{f.title}</h3>
            <strong style={{ color: "#a5b4fc", fontSize: 13 }}>{f.subtitle}</strong>
            <p className="muted" style={{ marginBottom: 0 }}>{f.description}</p>
          </Link>
        ))}
      </div>
      <Link href="/" style={{ display: "inline-block", marginTop: 26, color: "rgba(255,255,255,0.7)", fontSize: 14 }}>
        ← Back
      </Link>
    </DemoOnlyShell>
  );
}

export function VisionArcadeLinks() {
  const demoOnly = useFlag<boolean>(SALES_DEMO_FLAGS.exclusive, false);
  if (demoOnly) return <Link href="/demo">← Back to demo</Link>;
  return (
    <>
      <Link href="/">← Back to Salareen</Link>
      {" · "}
      <Link href="/arcade">More arcade games</Link>
    </>
  );
}

export function DemoOnlyLogin() {
  const router = useRouter();
  return (
    <DemoOnlyShell kicker={false}>
      <LandingAuthPanel onSignedIn={() => router.push("/")} />
    </DemoOnlyShell>
  );
}
