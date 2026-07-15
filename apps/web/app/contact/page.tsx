"use client";

import Link from "next/link";

// Simple contact hub: how to reach Salareen for support, business/partnerships,
// jobs, and custom (bespoke) courses. Plain mailto links so it works without any
// backend/contact-form wiring.
type ContactCard = {
  icon: string;
  title: string;
  blurb: string;
  email: string;
  subject: string;
  accent: string;
};

const CARDS: ContactCard[] = [
  {
    icon: "🛟",
    title: "Support",
    blurb: "Trouble with your account, a class, billing, or the app? We're here to help.",
    email: "support@salareen.com",
    subject: "Support request",
    accent: "#0ea5e9",
  },
  {
    icon: "🤝",
    title: "Work with us / Business",
    blurb: "Partnerships, enterprise plans, press, or any other business inquiry.",
    email: "business@salareen.com",
    subject: "Business inquiry",
    accent: "#16a34a",
  },
  {
    icon: "💼",
    title: "Careers / Jobs",
    blurb: "Want to join the team? Send your résumé and what you'd love to build with us.",
    email: "jobs@salareen.com",
    subject: "Careers — I'd like to join Salareen",
    accent: "#7c3aed",
  },
  {
    icon: "🎓",
    title: "Custom courses",
    blurb: "Bespoke Agentic courses and materials tailored to your company — hosted privately or downloadable.",
    email: "courses@salareen.com",
    subject: "Custom Agentic course for our business",
    accent: "#f59e0b",
  },
];

export default function ContactPage() {
  return (
    <main className="container" style={{ maxWidth: 900 }}>
      <h1>Contact Salareen</h1>
      <p className="muted">
        Reach the right team directly. We read every message and aim to reply quickly.
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: 12,
          marginTop: 12,
        }}
      >
        {CARDS.map((c) => (
          <div
            key={c.email}
            className="card"
            style={{ borderColor: c.accent, display: "flex", flexDirection: "column", gap: 8 }}
          >
            <h3 style={{ margin: 0 }}>
              <span aria-hidden style={{ marginRight: 8 }}>{c.icon}</span>
              {c.title}
            </h3>
            <p className="muted" style={{ margin: 0, flex: 1 }}>{c.blurb}</p>
            <a href={`mailto:${c.email}?subject=${encodeURIComponent(c.subject)}`}>
              <button style={{ width: "100%", background: c.accent, color: "#fff" }}>
                ✉️ {c.email}
              </button>
            </a>
          </div>
        ))}
      </div>

      <p className="muted" style={{ marginTop: 16, fontSize: 13 }}>
        Looking for a custom course for your company? See{" "}
        <Link href="/corporate">Corporate training</Link>. Exploring roles you can train for? Browse{" "}
        <Link href="/jobs">Careers</Link>.
      </p>
    </main>
  );
}
