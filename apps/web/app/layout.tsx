import "./globals.css";
import type { Metadata } from "next";
import { APP_VERSION } from "./lib/version";
import DisclaimerGate from "./components/DisclaimerGate";
import OnboardingSurveyGate from "./components/OnboardingSurveyGate";
import IntroSequence from "./components/IntroSequence";
import BackgroundProvider from "./components/BackgroundProvider";
import LocalizedNav from "./components/LocalizedNav";
import SiteFooter from "./components/SiteFooter";
import MaintenanceBanner from "./components/MaintenanceBanner";
import ClientLogInit from "./components/ClientLogInit";
import FloatingBugReporter from "./components/FloatingBugReporter";
import FloatingSalesDemo from "./components/FloatingSalesDemo";
import PresenceHeartbeat from "./components/PresenceHeartbeat";
import { LocaleProvider } from "./lib/i18n";
import { FlagsProvider } from "./lib/flags";

export const metadata: Metadata = {
  title: "Salareen — Agentic Online Education Platform",
  description: "A multi-agent AI instructor that teaches live online classes.",
  icons: {
    icon: [
      { url: "/favicon.ico" },
      { url: "/icon.png", type: "image/png", sizes: "512x512" },
    ],
    apple: "/logo.webp",
  },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <LocaleProvider>
          <FlagsProvider>
            <ClientLogInit />
            <MaintenanceBanner />
            <BackgroundProvider />
            <IntroSequence />
            <DisclaimerGate />
            <OnboardingSurveyGate />
            <LocalizedNav appVersion={APP_VERSION} />
            <div className="site-main">{children}</div>
            <SiteFooter />
            <FloatingSalesDemo />
            <FloatingBugReporter />
            <PresenceHeartbeat />
          </FlagsProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
