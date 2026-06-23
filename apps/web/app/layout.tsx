import "./globals.css";
import type { Metadata } from "next";
import { APP_VERSION } from "./lib/version";
import DisclaimerGate from "./components/DisclaimerGate";
import BackgroundProvider from "./components/BackgroundProvider";
import LocalizedNav from "./components/LocalizedNav";
import SiteFooter from "./components/SiteFooter";
import { LocaleProvider } from "./lib/i18n";

export const metadata: Metadata = {
  title: "Salareen — Agentic Online Education Platform",
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
          <SiteFooter />
        </LocaleProvider>
      </body>
    </html>
  );
}
