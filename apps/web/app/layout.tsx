import "./globals.css";
import type { Metadata } from "next";
import localFont from "next/font/local";
import { APP_VERSION } from "./lib/version";
import DisclaimerGate from "./components/DisclaimerGate";
import OnboardingSurveyGate from "./components/OnboardingSurveyGate";
import IntroSequence from "./components/IntroSequence";
import BackgroundProvider from "./components/BackgroundProvider";
import LocalizedNav from "./components/LocalizedNav";
import SiteFooter from "./components/SiteFooter";
import MaintenanceBanner from "./components/MaintenanceBanner";
import FriendlyErrorHost from "./components/FriendlyErrorHost";
import ClientLogInit from "./components/ClientLogInit";
import FloatingBugReporter from "./components/FloatingBugReporter";
import { XaiVoiceDock } from "./components/XaiVoiceDock";
import FloatingSalesDemo from "./components/FloatingSalesDemo";
import PresenceHeartbeat from "./components/PresenceHeartbeat";
import { LocaleProvider } from "./lib/i18n";
import { FlagsProvider } from "./lib/flags";
import { STORAGE_SHIM_SCRIPT } from "./lib/storageShimScript.mjs";

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

/**
 * DN "Dark Navy" theme display serif. Loaded via next/font so the browser
 * downloads only the Latin subset and we get an auto-generated CSS variable
 * (`--font-display`) that globals.css applies to h1/h2/.display headlines.
 * Italic is enabled so copy like "Human *Warmth.*" renders in true italic
 * serif, matching the DN mockup. Regular body text keeps the system sans.
 */
// Self-hosted (latin subset, variable weight): a build must never depend on Google Fonts being reachable.
const displaySerif = localFont({
  src: [
    { path: "./fonts/fraunces-normal.woff2", weight: "400 700", style: "normal" },
    { path: "./fonts/fraunces-italic.woff2", weight: "400 700", style: "italic" },
  ],
  display: "swap",
  variable: "--font-display",
});

/**
 * Inline script that runs BEFORE React hydrates. It reads the user's saved
 * theme preference from localStorage (and falls back to the OS-level
 * `prefers-color-scheme`) and sets `data-theme="dark"` or `"light"` on
 * <html> so the correct DN palette paints on the very first frame — no
 * light-flash on dark-mode reloads. Kept tiny and self-contained; it is
 * dangerouslySetInnerHTML because Next inlines it as a server string.
 */
const themeInitScript = `
(function(){try{
  var saved = localStorage.getItem('aoep.theme');
  var mode = (saved === 'dark' || saved === 'light') ? saved
    : (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  document.documentElement.setAttribute('data-theme', mode);
  document.documentElement.style.colorScheme = mode;
}catch(e){document.documentElement.setAttribute('data-theme','light');}
})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={displaySerif.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: STORAGE_SHIM_SCRIPT }} />
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
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
            <XaiVoiceDock />
            <PresenceHeartbeat />
            <FriendlyErrorHost />
          </FlagsProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
