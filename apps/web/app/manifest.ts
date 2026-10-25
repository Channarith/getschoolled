import type { MetadataRoute } from "next";

// Served at /manifest.webmanifest and linked from every page automatically. Gold for the browser chrome and cream behind the
// splash match the gold pass (globals.css --gold-line family); the icons are the two real files in /public.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Salareen",
    short_name: "Salareen",
    description: "A patient tutor for every learner, in every language.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "any",
    background_color: "#f6efe3",
    theme_color: "#d4af37",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon.png", sizes: "512x512", type: "image/png", purpose: "any" },
    ],
  };
}
