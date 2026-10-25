import type { Metadata } from "next";
import LegalDocumentView from "../../components/LegalDocumentView";
import PolicyFacts from "../../components/PolicyFacts";
import { formatLegalBody, loadLegalDoc } from "../../lib/legalDoc";

export const metadata: Metadata = {
  title: "Receipts and Taxes · Salareen",
  description: "What is on a receipt, where to find it, and how sales tax is shown.",
};

export default function Page() {
  const { title, paragraphs } = formatLegalBody(loadLegalDoc("RECEIPTS_AND_TAXES.txt"));
  return (
    <>
      <LegalDocumentView
        title={title.replace(/^SALAREEN\s*-\s*/i, "")}
        paragraphs={paragraphs}
        related={[
          { href: "/legal", label: "Legal hub" },
          { href: "/legal/terms-of-sale", label: "Terms of Sale" },
          { href: "/legal/refund-policy", label: "Refund Policy" },
          { href: "/legal/receipts-and-taxes", label: "Receipts & Taxes" },
        ]}
      />
      <PolicyFacts kind="receipts" />
    </>
  );
}
