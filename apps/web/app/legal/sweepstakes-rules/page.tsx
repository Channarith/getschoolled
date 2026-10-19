import type { Metadata } from "next";
import LegalDocumentView from "../../components/LegalDocumentView";
import { formatLegalBody, loadLegalDoc } from "../../lib/legalDoc";

export const metadata: Metadata = {
  title: "Rewards & Sweepstakes Rules · Salareen",
  description:
    "Official rules for the Salareen Rewards & Sweepstakes program: how points are earned, redemption, prize drawings, no-purchase-necessary entry, eligibility, and taxes.",
};

export default function SweepstakesRulesPage() {
  const { title, paragraphs } = formatLegalBody(loadLegalDoc("SWEEPSTAKES.txt"));
  return (
    <LegalDocumentView
      title={title.replace(/^AOEP[^-]*-\s*/i, "").replace(/^SALAREEN[^-]*-\s*/i, "")}
      paragraphs={paragraphs}
      related={[
        { href: "/rewards", label: "Rewards hub" },
        { href: "/legal", label: "Legal hub" },
        { href: "/privacy", label: "Privacy Policy" },
      ]}
    />
  );
}
