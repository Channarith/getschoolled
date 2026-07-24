import type { Metadata } from "next";
import LegalDocumentView from "../components/LegalDocumentView";
import { formatLegalBody, loadLegalDoc } from "../lib/legalDoc";

export const metadata: Metadata = {
  title: "Data Deletion · Salareen",
  description: "Request deletion of your Salareen account and personal data.",
};

export default function DataDeletionPage() {
  const { title, paragraphs } = formatLegalBody(loadLegalDoc("DATA_DELETION.txt"));
  return (
    <LegalDocumentView
      title={title.replace(/^SALAREEN — /i, "")}
      paragraphs={paragraphs}
      related={[
        { href: "/privacy", label: "Privacy Policy" },
        { href: "/terms", label: "Terms of Service" },
        { href: "/legal", label: "Legal hub" },
        { href: "/contact", label: "Contact" },
      ]}
    />
  );
}
