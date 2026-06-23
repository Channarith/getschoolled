import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import { LANGUAGE_LIST } from "../lib/i18n-strings";

// Keep advertised language counts in lockstep with the actual language list so
// the number can never drift from what the picker offers.
const LANG_TOTAL = LANGUAGE_LIST.length;
const LANG_FULL = LANGUAGE_LIST.filter((l) => l.tier === "full").length;

export const metadata: Metadata = {
  title: "Our Story — Salareen",
  description:
    "Why Salareen exists: world-class, AI-taught education that is accessible, affordable, adaptive, private, and respectful — in your language, on any device.",
};

// Static marketing/about page. Server component (no client interactivity).
export default function OurStoryPage() {
  return (
    <main className="container" style={{ maxWidth: 880 }}>
      <h1>Our Story</h1>
      <p className="muted" style={{ fontSize: 18 }}>
        Salareen exists to give everyone a patient, brilliant teacher — one that
        adapts to each learner, speaks their language, runs on the device in
        their pocket, and never gives up on them.
      </p>

      <div style={{ display: "flex", justifyContent: "center", margin: "20px 0" }}>
        <Image
          src="/salareen-mascot.webp"
          alt="The Salareen study buddy — a secular Bayon-inspired face forming an S, beside a bodhi-style leaf of knowledge"
          width={512}
          height={341}
          style={{ width: "min(320px, 70%)", height: "auto" }}
          priority
        />
      </div>

      <h2>What we believe</h2>
      <p>
        Great education is still rationed by geography, income, and language. We
        think a well-built AI teacher can change that — not by replacing human
        teachers, but by making expert, one-on-one instruction abundant and
        affordable for billions of learners who will never have access to it
        otherwise.
      </p>

      <h2>The name &amp; the buddy</h2>
      <p>
        <strong>Salareen</strong> comes from the Khmer <em>salaa rian</em> — “to
        go to school.” Our study buddy is a friendly, <strong>secular</strong>{" "}
        character: a calm, welcoming face in the spirit of classical Khmer
        craftsmanship, drawn as a modern mascot rather than a monument. Its
        silhouette forms an <strong>“S”</strong> for Salareen, and beside it
        grows a stylized <strong>leaf of knowledge</strong> — a heart-shaped
        bodhi-style leaf whose veins double as a learning network. It stands for
        curiosity, growth, and lifelong learning, not religion.
      </p>

      <h2>One platform, many ways to learn</h2>
      <p>
        Salareen is a single AI learning platform that meets learners wherever
        they are — on the web, on mobile, hands-free in the car, in scheduled
        live group classes, or in private on-demand lessons any time of day.
      </p>
      <div style={{ display: "flex", justifyContent: "center", margin: "16px 0" }}>
        <Image
          src="/salareen-ecosystem.webp"
          alt={`Salareen platform map: homework grader, private tutor agent, mobile apps, drive mode audio agent, human-in-the-loop and group and private courses, integrations, arcade, rewards, course scraper, knowledge base, adaptive learning, machine vision, humanoid-robot readiness, and ${LANG_TOTAL} languages`}
          width={1536}
          height={1024}
          style={{ width: "100%", height: "auto", borderRadius: 12 }}
        />
      </div>

      <ul style={{ lineHeight: 1.8 }}>
        <li><strong>Privately-trained tutor agent</strong> — our own education model, grounded in a curated knowledge base.</li>
        <li><strong>Homework grader</strong> — typed or handwritten, with rationale and citations.</li>
        <li><strong>Human-in-the-loop courses</strong> — AI teaches, a human reviews and approves where it matters.</li>
        <li><strong>Live group courses</strong> at scheduled times and <strong>private courses</strong> on demand.</li>
        <li><strong>Drive Mode</strong> — eyes-free audio classes with an AI agent for commutes.</li>
        <li><strong>Mobile apps</strong> for Android &amp; iOS.</li>
        <li><strong>AI adaptive learning</strong> with per-learner profiles and mastery tracking.</li>
        <li><strong>Machine vision</strong> — opt-in camera and voice recognition that runs <em>on your device</em>.</li>
        <li><strong>Mini-games arcade</strong> and a <strong>rewards &amp; points</strong> system to keep learning fun.</li>
        <li><strong>Course scraper</strong> that builds fresh courses from the open web.</li>
        <li><strong>Knowledge base (RAG)</strong> so answers stay grounded and citable.</li>
        <li><strong>Integrations</strong> with LMS, finance, and cloud tools.</li>
        <li><strong>{LANG_TOTAL} languages</strong> — the interface is fully localized in {LANG_FULL}, and the rest are supported through AI translation, speech, and content, with their UI localization rolling out.</li>
        <li><strong>Humanoid-robot ready</strong> — the same teaching brain can drive an embodied tutor.</li>
      </ul>

      <h2>How we build</h2>
      <ul style={{ lineHeight: 1.8 }}>
        <li><strong>Privacy &amp; consent first.</strong> Biometric features are opt-in; vision and audio can run on-device so raw camera frames never leave it.</li>
        <li><strong>Transparent AI.</strong> Every learner sees an AI-instruction disclosure; answers cite their sources.</li>
        <li><strong>Affordable to run.</strong> The architecture scales from a single laptop to millions of learners.</li>
        <li><strong>Respectful &amp; secular by design.</strong> Culturally inspired, never appropriative or devotional.</li>
      </ul>

      <p style={{ marginTop: 24 }}>
        <Link href="/browse" style={{ marginRight: 16 }}>Browse courses →</Link>
        <Link href="/transparency">How our AI works →</Link>
      </p>
    </main>
  );
}
