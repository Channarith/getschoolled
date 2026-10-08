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

function DemoOnlyShell({ children, kicker = true }: { children: React.ReactNode; kicker?: boolean }) {
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
      <div className="landing-inner">
        <MascotImage width={140} className="landing-mascot" alt="Salareen mascot" />
        {kicker && <span className="theme-badge">{t("hero.kicker")}</span>}
        {children}
      </div>
    </main>
  );
}

const squareButton: React.CSSProperties = {
  width: "min(190px, 40vw)",
  aspectRatio: "1 / 1",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  gap: 10,
  borderRadius: 22,
  border: "1px solid rgba(255,255,255,0.25)",
  color: "#fff",
  fontSize: 24,
  fontWeight: 800,
  textDecoration: "none",
  boxShadow: "0 14px 34px rgba(2,6,23,.45)",
};

export function DemoOnlyLanding() {
  return (
    <DemoOnlyShell>
      <div style={{ display: "flex", gap: 20, justifyContent: "center", marginTop: 34 }}>
        <Link href="/demo" style={{ ...squareButton, background: "linear-gradient(145deg, #6366f1, #8b5cf6)" }}>
          <span aria-hidden style={{ fontSize: 44 }}>✨</span>
          Demo
        </Link>
        <Link href="/login" style={{ ...squareButton, background: "rgba(15,23,42,0.78)" }}>
          <span aria-hidden style={{ fontSize: 44 }}>🔑</span>
          Log in
        </Link>
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
