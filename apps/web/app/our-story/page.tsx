import type { Metadata } from "next";

import OurStoryContent from "./OurStoryContent";

export const metadata: Metadata = {
  title: "Our Story — Salareen",
  description:
    "Why Salareen exists: world-class, AI-taught education that is accessible, affordable, adaptive, private, and respectful — in your language, on any device.",
};

export default function OurStoryPage() {
  return <OurStoryContent />;
}
