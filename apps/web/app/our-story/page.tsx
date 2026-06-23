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

// Ecosystem tools shown on the Our Story page. Each renders as a hoverable
// card; hovering or focusing reveals a tooltip with the description + examples.
type EcosystemTool = {
  name: string;
  description: string;
  examples: string[];
};

const ECOSYSTEM_TOOLS: EcosystemTool[] = [
  {
    name: "Privately-trained tutor agent",
    description:
      "Our own education-tuned model teaches lessons and answers questions, grounded in a curated knowledge base so replies stay citable.",
    examples: [
      "“Explain photosynthesis like I’m 10, then quiz me.”",
      "Asks a follow-up question when you’re stuck instead of just handing over the answer.",
    ],
  },
  {
    name: "Homework grader",
    description:
      "Submit typed or handwritten work and get a grade with step-by-step rationale and citations back to the source material.",
    examples: [
      "Snap a photo of a math worksheet → per-question feedback.",
      "Flags the exact line where a proof goes wrong and why.",
    ],
  },
  {
    name: "Human-in-the-loop courses",
    description:
      "The AI teaches and drafts answers, but a human educator reviews and approves high-stakes or low-confidence responses before they ship.",
    examples: [
      "A medical-course answer is routed to a human for sign-off.",
      "An educator edits the AI’s explanation; the learner sees the approved version.",
    ],
  },
  {
    name: "Live group & private courses",
    description:
      "Scheduled multi-learner classes the AI presents live (via Zoom, Teams, Meet, or the built-in room), plus 1:1 private lessons on demand any time.",
    examples: [
      "Join “Evening Fractions” at 7pm with 30 classmates.",
      "Start a solo lesson at 2am and go at your own pace.",
    ],
  },
  {
    name: "Drive Mode",
    description:
      "Eyes-free, voice-only audio classes for commutes — the AI narrates lessons and answers spoken questions in natural, localized speech.",
    examples: [
      "“Continue my Spanish course” while driving.",
      "Say “repeat that last part” completely hands-free.",
    ],
  },
  {
    name: "Mobile apps (Android & iOS)",
    description:
      "Native apps with offline lessons, Drive Mode, rewards, and push notifications so learning travels with you.",
    examples: [
      "Download lessons before a flight and learn offline.",
      "Get a push notification when your live class is about to start.",
    ],
  },
  {
    name: "AI adaptive learning",
    description:
      "Per-learner profiles track mastery and adjust pace and difficulty, automatically re-teaching weak spots.",
    examples: [
      "Speeds through topics you’ve mastered, slows down on new ones.",
      "Re-asks a concept you missed two lessons later to check retention.",
    ],
  },
  {
    name: "Machine vision (on-device)",
    description:
      "Opt-in camera and face/voice recognition for attention and presence — detection runs on your device, so raw frames never leave it.",
    examples: [
      "Notices when a student looks away and gently re-engages them.",
      "Recognizes an enrolled learner to resume their profile.",
    ],
  },
  {
    name: "Mini-games arcade & rewards",
    description:
      "Quiz games, matching, and leaderboards plus a points and rewards system that keeps learning fun and motivating.",
    examples: [
      "Earn points for a quiz streak and redeem a reward.",
      "Climb the weekly class leaderboard with friends.",
    ],
  },
  {
    name: "Course scraper",
    description:
      "Builds fresh, structured courses from the open web, then validates and grounds them in the knowledge base.",
    examples: [
      "Turn a set of public articles into a 10-slide lesson.",
      "Refresh a course automatically when its source material changes.",
    ],
  },
  {
    name: "Knowledge base (RAG)",
    description:
      "A retrieval-augmented knowledge store so every answer is grounded in real passages and shows its citations.",
    examples: [
      "“Where did that fact come from?” → links the exact source slide.",
      "Flags an unverified claim as unsupported rather than guessing.",
    ],
  },
  {
    name: "Integrations",
    description:
      "Connects to LMS/SIS, finance and billing, and cloud collaboration tools, plus meeting bridges for live classes.",
    examples: [
      "Sync rosters and pass grades back to your LMS.",
      "Bridge a class into Zoom, Microsoft Teams, or Google Meet.",
    ],
  },
  {
    name: `${LANG_TOTAL} languages`,
    description:
      `Teaching across ${LANG_TOTAL} languages with localized voices and accents; the interface is fully localized in ${LANG_FULL}, with graceful English fallback for the rest while their UI localization rolls out.`,
    examples: [
      "Switch the entire app to Khmer or Vietnamese in one tap.",
      "Hear Drive Mode narrated with your language’s accent.",
    ],
  },
  {
    name: "Humanoid-robot ready",
    description:
      "The same teaching brain can drive an embodied tutor — a screen avatar today, a physical robot tomorrow — through one embodiment interface.",
    examples: [
      "Render a teaching beat as avatar gestures and speech.",
      "Send the same lesson actions to a physical robot.",
    ],
  },
];

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

      <p className="muted">
        Hover over (or tap/focus) any tool below to see what it does and a couple
        of concrete examples.
      </p>
      <ul className="tools">
        {ECOSYSTEM_TOOLS.map((tool) => (
          <li
            key={tool.name}
            className="tool"
            tabIndex={0}
            aria-label={`${tool.name}: ${tool.description}`}
          >
            <span className="tool-name">{tool.name}</span>
            <span className="tool-tip" role="tooltip">
              <p>{tool.description}</p>
              <span className="ex-label">Examples</span>
              <ul className="examples">
                {tool.examples.map((ex) => (
                  <li key={ex}>{ex}</li>
                ))}
              </ul>
            </span>
          </li>
        ))}
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
