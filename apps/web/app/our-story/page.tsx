import type { Metadata } from "next";

import OurStoryContent from "./OurStoryContent";

export const metadata: Metadata = {
  title: "Our Story — Salareen",
  description:
    "Salareen's story: born of Khmer heritage and a belief that education is how people and nations rise. A single AI learning platform of adaptive agents — a patient teacher for everyone, in every language, at every age.",
};

export default function OurStoryPage() {
  return <OurStoryContent />;
}
