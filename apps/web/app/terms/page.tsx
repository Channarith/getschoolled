import type { Metadata } from "next";
import LegalDocumentView from "../components/LegalDocumentView";
import { formatLegalBody, loadLegalDoc } from "../lib/legalDoc";

export const metadata: Metadata = {
  title: "Terms of Service · Salareen",
  description: "Salareen terms of service — AI disclosure, accounts, billing, and lawful use.",
};

export default function TermsPage() {
  const { title, paragraphs } = formatLegalBody(loadLegalDoc("TERMS.txt"));
  return (
    <LegalDocumentView
      title={title.replace(/^SALAREEN — /i, "")}
      paragraphs={paragraphs}
      related={[
        { href: "/privacy", label: "Privacy Policy" },
        { href: "/data-deletion", label: "Data deletion" },
        { href: "/legal", label: "Legal hub" },
      ]}
    />
  );
}
