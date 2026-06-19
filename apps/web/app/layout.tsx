import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";
import { APP_VERSION } from "./lib/version";
import DisclaimerGate from "./components/DisclaimerGate";
import BackgroundProvider from "./components/BackgroundProvider";

export const metadata: Metadata = {
  title: "AI Classroom — Agentic Online Education Platform",
  description: "A multi-agent AI instructor that teaches live online classes.",
  icons: { icon: "/favicon.ico" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <BackgroundProvider />
        <DisclaimerGate />
        <nav className="nav">
          <Link href="/" className="brand" style={{ display: "inline-flex", alignItems: "center", gap: 8, textDecoration: "none", color: "inherit" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/logo-mark.webp" alt="AI Classroom logo" height={30}
              style={{ height: 30, width: "auto", borderRadius: 6 }} />
            AI Classroom
          </Link>
          <Link href="/">Home</Link>
          <Link href="/browse">Browse</Link>
          <Link href="/kids">Kids</Link>
          <Link href="/corporate">Corporate</Link>
          <Link href="/recommended">For You</Link>
          <Link href="/languages">Languages</Link>
          <Link href="/arcade">Arcade</Link>
          <Link href="/watch">Watch</Link>
          <Link href="/class">Live Class</Link>
          <Link href="/homework">Homework</Link>
          <Link href="/rewards">Rewards</Link>
          <Link href="/account">Account</Link>
          <Link href="/console">Console</Link>
          <Link href="/admin">Admin</Link>
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/consent">Consent</Link>
          <Link href="/backgrounds">Themes</Link>
          <Link href="/transparency">Transparency</Link>
          <Link href="/legal">Legal</Link>
          <span
            title="This platform is AI-instructed; see the Transparency page."
            style={{ marginLeft: "auto", fontSize: 12, padding: "2px 8px", borderRadius: 999, border: "1px solid currentColor", opacity: 0.85 }}
          >
            AI-instructed
          </span>
          <span className="version" title="App version" style={{ opacity: 0.7, fontSize: 12 }}>
            v{APP_VERSION}
          </span>
        </nav>
        {children}
        <footer style={{ marginTop: 40, padding: "16px 24px", borderTop: "1px solid #333", fontSize: 12, opacity: 0.75 }}>
          <span>© 2026 AOEP · </span>
          <Link href="/legal">Legal &amp; Compliance</Link>
          <span> · AI-assisted instruction. Use only in compliance with applicable laws. </span>
          <Link href="/transparency">Transparency</Link>
        </footer>
      </body>
    </html>
  );
}
