import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";
import { APP_VERSION } from "./lib/version";

export const metadata: Metadata = {
  title: "Agentic Online Education Platform",
  description: "A multi-agent AI instructor that teaches live online classes.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <nav className="nav">
          <span className="brand">AI Classroom</span>
          <Link href="/">Home</Link>
          <Link href="/class">Live Class</Link>
          <Link href="/homework">Homework</Link>
          <Link href="/console">Console</Link>
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/consent">Consent</Link>
          <Link href="/transparency">Transparency</Link>
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
      </body>
    </html>
  );
}
