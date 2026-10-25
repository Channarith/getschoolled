// Unified Legal hub. The user asked us to collapse Privacy Policy, Terms of
// Service, Data Deletion, and the Rewards & Sweepstakes rules into ONE page
// linked from the footer as "Legal". Each policy is still available at its own
// stable URL (/privacy, /terms, /data-deletion, /legal/sweepstakes-rules) for
// deep links, email templates, and app-store review submissions — this page is
// the "one stop" overview that renders every policy as a jump-link section so
// visitors never have to hunt through multiple footer links.
import type { Metadata } from "next";
import Link from "next/link";
import { formatLegalBody, loadLegalDoc } from "../lib/legalDoc";

export const metadata: Metadata = {
  title: "Legal · Salareen",
  description:
    "Salareen legal hub — Privacy Policy, Terms of Service, Data Deletion, and Rewards & Sweepstakes rules in one place.",
};

type Section = {
  id: string;
  label: string;
  href: string;
  filename: string;
};

const SECTIONS: Section[] = [
  { id: "privacy", label: "Privacy Policy", href: "/privacy", filename: "PRIVACY.txt" },
  { id: "terms", label: "Terms of Service", href: "/terms", filename: "TERMS.txt" },
  {
    id: "data-deletion",
    label: "Data Deletion",
    href: "/data-deletion",
    filename: "DATA_DELETION.txt",
  },
  { id: "terms-of-sale", label: "Terms of Sale", href: "/legal/terms-of-sale", filename: "TERMS_OF_SALE.txt" },
  { id: "refund-policy", label: "Refund Policy", href: "/legal/refund-policy", filename: "REFUND_POLICY.txt" },
  { id: "receipts-and-taxes", label: "Receipts & Taxes", href: "/legal/receipts-and-taxes", filename: "RECEIPTS_AND_TAXES.txt" },
  {
    id: "sweepstakes-rules",
    label: "Rewards & Sweepstakes Rules",
    href: "/legal/sweepstakes-rules",
    filename: "SWEEPSTAKES.txt",
  },
];

export default function LegalHubPage() {
  // Load each policy at request time; the Docker image ships the text files
  // under apps/web/content/legal/ so this works in both local dev and prod.
  const docs = SECTIONS.map((s) => {
    try {
      const { title, paragraphs } = formatLegalBody(loadLegalDoc(s.filename));
      return { ...s, title, paragraphs, missing: false as const };
    } catch {
      return { ...s, title: s.label, paragraphs: [] as string[], missing: true as const };
    }
  });

  return (
    <main className="container" style={{ maxWidth: 860 }}>
      <h1 style={{ marginBottom: 4 }}>Legal</h1>
      <p className="muted" style={{ marginTop: 0 }}>
        Everything in one place. Each policy below also has its own permalink.
      </p>

      <nav
        aria-label="Legal sections"
        className="card"
        style={{ display: "flex", gap: 10, flexWrap: "wrap", padding: "10px 14px" }}
      >
        {docs.map((d) => (
          <a
            key={d.id}
            href={`#${d.id}`}
            style={{
              padding: "4px 10px",
              borderRadius: 999,
              background: "rgba(110,168,254,0.12)",
              border: "1px solid rgba(110,168,254,0.3)",
              textDecoration: "none",
              fontSize: 13,
            }}
          >
            {d.label}
          </a>
        ))}
      </nav>

      {docs.map((d) => (
        <section key={d.id} id={d.id} className="card" style={{ scrollMarginTop: 90 }}>
          <div
            className="row"
            style={{ justifyContent: "space-between", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}
          >
            <h2 style={{ margin: 0 }}>{d.title.replace(/^SALAREEN — /i, "").replace(/^AOEP[^-]*-\s*/i, "")}</h2>
            <Link href={d.href} className="muted" style={{ fontSize: 13 }}>
              Permalink →
            </Link>
          </div>
          {d.missing ? (
            <p className="muted" style={{ fontStyle: "italic" }}>
              This policy text is being updated. Please contact{" "}
              <a href="mailto:legal@salareen.com">legal@salareen.com</a> for the current version.
            </p>
          ) : (
            <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.55 }}>
              {d.paragraphs.map((p, i) => (
                <p key={i} style={{ marginTop: i === 0 ? 0 : 12, marginBottom: 0 }}>
                  {p}
                </p>
              ))}
            </div>
          )}
        </section>
      ))}

      <p className="muted" style={{ fontSize: 12 }}>
        Templates. Counsel should finalize jurisdiction-specific wording. Questions:{" "}
        <a href="mailto:privacy@salareen.com">privacy@salareen.com</a>
        {" · "}
        <a href="mailto:legal@salareen.com">legal@salareen.com</a>
      </p>
    </main>
  );
}
