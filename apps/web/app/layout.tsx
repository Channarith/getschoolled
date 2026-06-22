import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";
import { APP_VERSION } from "./lib/version";
import DisclaimerGate from "./components/DisclaimerGate";
import BackgroundProvider from "./components/BackgroundProvider";
import LanguagePicker from "./components/LanguagePicker";
import LocalizedNav from "./components/LocalizedNav";
import { LocaleProvider } from "./lib/i18n";

export const metadata: Metadata = {
  title: "AI Classroom — Agentic Online Education Platform",
  description: "A multi-agent AI instructor that teaches live online classes.",
  icons: {
    icon: [
      { url: "/favicon.ico" },
      { url: "/logo-mark.svg", type: "image/svg+xml" },
    ],
    apple: "/logo.webp",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <LocaleProvider>
          <BackgroundProvider />
          <DisclaimerGate />
          <LocalizedNav appVersion={APP_VERSION} />
          {children}
          <footer style={{ marginTop: 40, padding: "16px 24px", borderTop: "1px solid #333", fontSize: 12, opacity: 0.75, display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
            <span>© 2026 AOEP · </span>
            <Link href="/legal">Legal &amp; Compliance</Link>
            <span> · AI-assisted instruction. Use only in compliance with applicable laws. </span>
            <Link href="/transparency">Transparency</Link>
            <span style={{ marginLeft: "auto" }}><LanguagePicker /></span>
          </footer>
        </LocaleProvider>
      </body>
    </html>
  );
}
