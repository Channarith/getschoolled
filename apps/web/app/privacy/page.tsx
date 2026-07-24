import type { Metadata } from "next";
import LegalDocumentView from "../components/LegalDocumentView";
import { formatLegalBody, loadLegalDoc } from "../lib/legalDoc";

export const metadata: Metadata = {
  title: "Privacy Policy · Salareen",
  description: "Salareen privacy policy — how we process learning data, biometrics, and your rights.",
};

export default function PrivacyPage() {
  const { title, paragraphs } = formatLegalBody(loadLegalDoc("PRIVACY.txt"));
  return (
    <LegalDocumentView
      title={title.replace(/^SALAREEN — /i, "")}
      paragraphs={paragraphs}
      related={[
        { href: "/terms", label: "Terms of Service" },
        { href: "/data-deletion", label: "Data deletion" },
        { href: "/legal", label: "Legal hub" },
      ]}
    />
  );
}
