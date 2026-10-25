import type { Metadata } from "next";
import LegalDocumentView from "../../components/LegalDocumentView";
import PolicyFacts from "../../components/PolicyFacts";
import { formatLegalBody, loadLegalDoc } from "../../lib/legalDoc";

export const metadata: Metadata = {
  title: "Terms of Sale · Salareen",
  description: "The terms for buying a course: what you get, price, tax, receipts, refunds and what a course is not.",
};

export default function Page() {
  const { title, paragraphs } = formatLegalBody(loadLegalDoc("TERMS_OF_SALE.txt"));
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
      <PolicyFacts kind="sale" />
    </>
  );
}
