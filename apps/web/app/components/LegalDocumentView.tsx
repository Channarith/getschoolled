import Link from "next/link";

type Props = {
  title: string;
  paragraphs: string[];
  related: { href: string; label: string }[];
};

/** Shared chrome for Privacy / Terms / Data deletion pages. */
export default function LegalDocumentView({ title, paragraphs, related }: Props) {
  return (
    <main className="container" style={{ maxWidth: 820 }}>
      <h1 style={{ marginBottom: 8 }}>{title}</h1>
      <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
        Salareen · GetSchoolled &nbsp;·&nbsp;
        {related.map((r, i) => (
          <span key={r.href}>
            {i > 0 ? " · " : null}
            <Link href={r.href}>{r.label}</Link>
          </span>
        ))}
      </p>
      <div className="card" style={{ whiteSpace: "pre-wrap", lineHeight: 1.55 }}>
        {paragraphs.map((p, i) => (
          <p key={i} style={{ marginTop: i === 0 ? 0 : 12, marginBottom: 0 }}>
            {p}
          </p>
        ))}
      </div>
      <p className="muted" style={{ fontSize: 12, marginTop: 16 }}>
        Template notice — counsel should finalize jurisdiction-specific wording.
        Questions:{" "}
        <a href="mailto:privacy@salareen.com">privacy@salareen.com</a>
        {" · "}
        <a href="mailto:legal@salareen.com">legal@salareen.com</a>
      </p>
    </main>
  );
}
