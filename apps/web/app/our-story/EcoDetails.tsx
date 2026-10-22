"use client";

// Hover / focus / tap details for the Our Story feature cards: a longer
// description, three key points and a small flow diagram drawn in SVG (no
// external images, so it works under the site's strict CSP).
//
// English text lives here as the default. A translated string is used when a
// `story.eco.<id>Detail*` key exists in the locale files, so each language can
// be filled in later (the staff review lab is the intended source).

import type { ReactNode } from "react";

export type EcoDetail = {
  summary: string;
  points: [string, string, string];
  flow: string[];
  /** Optional illustrative bar chart, shown with an "Example" caption. */
  chart?: { title: string; bars: { label: string; value: number }[] };
};

export const ECO_DETAILS: Record<string, EcoDetail> = {
  homeworkGrader: {
    summary:
      "Take a photo of finished homework. Sala reads it, checks each step and explains where an answer went right or wrong, so you learn from the mistake and not only the score.",
    points: ["Checks step by step, not just right or wrong", "Explains mistakes in plain language", "Checks that the work is your own"],
    flow: ["Snap a photo", "Read the work", "Check each step", "Feedback and next step"],
  },
  tutorAgent: {
    summary:
      "A one-to-one tutor that answers from your course material, gives a hint before the answer, and adjusts its pace to how you learn.",
    points: ["Answers come from your course", "Says so when the material does not cover it", "Adapts to your learning profile"],
    flow: ["You ask", "Finds the lesson", "Hint, then answer", "Checks understanding"],
  },
  mobileApp: {
    summary: "Salareen on iPhone and Android, with a short voice-led setup and lessons you can take with you.",
    points: ["iPhone and Android", "Lessons available offline", "Camera and voice check is optional"],
    flow: ["Download", "Quick setup", "Pick a course", "Learn anywhere"],
  },
  driveMode: {
    summary:
      "Audio lessons you can follow hands-free. Tap Sala at any time to pause and ask a question; the lesson picks up where it left off.",
    points: ["Hands-free audio", "Pause and ask by voice", "Resumes where you left off"],
    flow: ["Start the lesson", "Listen", "Tap Sala to ask", "Back to the lesson"],
  },
  hitlCourses: {
    summary:
      "AI drafts each lesson, then a real teacher reviews and approves it before learners see it. Corrections flow back to improve later lessons.",
    points: ["Teacher sign-off before publishing", "Corrections improve the content", "Uncertain answers go to a person"],
    flow: ["AI drafts", "Teacher reviews", "Approved", "Published"],
  },
  liveGroup: {
    summary: "Scheduled classes with other learners in a built-in video room, led by a teacher.",
    points: ["Scheduled sessions", "Built-in video room", "Ask questions live"],
    flow: ["Book a class", "Join the room", "Learn together", "Ask questions"],
  },
  onDemand: {
    summary: "Name any topic and Sala builds a course for you, ready to start in minutes.",
    points: ["Any topic", "Sized to your time", "Shaped by your learning profile"],
    flow: ["Name a topic", "Course is built", "Review it", "Start learning"],
  },
  integrations: {
    summary: "Join classes on Zoom, Teams or Google Meet from one calendar.",
    points: ["Zoom, Teams and Google Meet", "One calendar for every class", "Join with one click"],
    flow: ["Book a class", "Added to your calendar", "Open your meeting tool", "Learn"],
  },
  arcade: {
    summary: "Short games that revisit what you just learned, with points and streaks to keep you going.",
    points: ["Quick rounds", "Reinforces the lesson", "Points and streaks"],
    flow: ["Finish a lesson", "Play a quick game", "Earn points", "Keep your streak"],
  },
  rewards: {
    summary: "Points for real progress that you can redeem for discounts, items or raffle entries.",
    points: ["Points for progress", "Discounts and items", "Raffle entries"],
    flow: ["Learn", "Earn points", "Redeem", "Discounts, items, raffles"],
  },
  scraper: {
    summary:
      "Turns PDFs, web pages and books into lesson-sized courses that a person reviews before they go live.",
    points: ["PDFs, websites and books", "Lesson-sized pieces", "Human review before use"],
    flow: ["Add a source", "Extract the text", "Split into lessons", "Review and publish"],
  },
  rag: {
    summary:
      "A search index of your course material. Answers are built from what it finds, and the tutor says so when the material does not cover a question.",
    points: ["Answers come from the course", "Sources are shown", "Says when it does not know"],
    flow: ["Your question", "Search the course", "Answer from what is found", "Cite sources or say not covered"],
  },
  adaptive: {
    summary:
      "Six ratings you set during setup (and can update any time) shape pacing, difficulty and the examples you see.",
    points: ["Set once, update any time", "Shapes pace and examples", "Used only to teach better"],
    flow: ["Rate how you learn", "Sala adapts the lesson", "You progress", "Profile updates"],
    chart: {
      title: "Example learner profile",
      bars: [
        { label: "Videos", value: 8 },
        { label: "Live teacher", value: 5 },
        { label: "Slides", value: 6 },
        { label: "Reading", value: 3 },
        { label: "1:1 tutor", value: 9 },
        { label: "Games", value: 7 },
      ],
    },
  },
  vision: {
    summary:
      "An optional camera and microphone let Sala see your work and talk with you. It is always opt-in and can run on your own device.",
    points: ["Always opt-in", "Can run on-device", "Never required to learn"],
    flow: ["You opt in", "Camera and mic on your device", "Sala sees and hears", "Talks back"],
  },
  robot: {
    summary: "The same lessons can stream to humanoid robot tutors when the hardware is available.",
    points: ["Same content as the app", "Robot-ready lesson packs", "When hardware is available"],
    flow: ["Course content", "Robot lesson pack", "Humanoid tutor", "Same lesson, in person"],
  },
  languages: {
    summary:
      "Interface, narration and courses in 26 languages and growing. Machine translations are checked by staff reviewers.",
    points: ["Full interface", "Narrated lessons", "Staff-reviewed translations"],
    flow: ["English source", "Machine translation", "Staff review", "Better for everyone"],
  },
};

type Tr = (key: string, fallback: string) => string;

function FlowDiagram({ steps }: { steps: string[] }): ReactNode {
  return (
    <ol className="os-pop-flow" aria-label={steps.join(" → ")}>
      {steps.map((label, i) => (
        <li key={i}>
          <span className="os-pop-num">{i + 1}</span>
          <span className="os-pop-steptxt">{label}</span>
          {i < steps.length - 1 && <svg className="os-pop-arrow" viewBox="0 0 12 12" aria-hidden="true"><path d="M2 6h8M7 3l3 3-3 3" /></svg>}
        </li>
      ))}
    </ol>
  );
}

function BarChart({ chart }: { chart: NonNullable<EcoDetail["chart"]> }): ReactNode {
  return (
    <div className="os-pop-chart" role="img" aria-label={chart.title}>
      <div className="os-pop-chart-title">{chart.title}</div>
      {chart.bars.map((b) => (
        <div className="os-pop-bar" key={b.label}>
          <span>{b.label}</span>
          <i style={{ width: `${b.value * 10}%` }} />
        </div>
      ))}
    </div>
  );
}

export function EcoPopover({
  id, label, popId, tr, at,
}: {
  id: string; label: string; popId: string; tr: Tr; at: string;
}): ReactNode {
  const d = ECO_DETAILS[id];
  if (!d) return null;
  const pre = `story.eco.${id}Detail`;
  const steps = d.flow.map((s, i) => tr(`${pre}Step${i + 1}`, s));
  return (
    <div className={`os-pop ${at}`} role="tooltip" id={popId}>
      <div className="os-pop-title">{label}</div>
      <p className="os-pop-sum">{tr(`${pre}`, d.summary)}</p>
      <FlowDiagram steps={steps} />
      <ul className="os-pop-points">
        {d.points.map((p, i) => <li key={i}>{tr(`${pre}Point${i + 1}`, p)}</li>)}
      </ul>
      {d.chart && <BarChart chart={d.chart} />}
    </div>
  );
}
