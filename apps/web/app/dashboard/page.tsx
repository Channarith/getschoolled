const AGENTS = [
  ["Teaching Director", "Lesson state machine; balances teach vs answer vs quiz."],
  ["Lesson Delivery", "Walks the deck and narrates slides via TTS."],
  ["Q&A / Tutor", "Answers chat/voice questions with RAG in the asker's language."],
  ["Assessment", "Pop quizzes, definition checks, polls, mastery tracking."],
  ["Perception", "Consent-gated face recognition + attention scoring."],
  ["Speech", "Streaming multilingual ASR, language ID, translation, TTS."],
  ["Memory / Profile", "Long-term per-student profile and mastery graph."],
  ["Consent / Compliance", "Gates biometrics; enforces retention (FERPA/GDPR/BIPA)."],
  ["Harvester", "24/7 crawl, generate, and critique courses for the catalog."],
  ["AI Presenter", "Narrates slides and drives live meeting presentation."],
  ["AI Chatbot", "Meeting chat tutor with grounded answers."],
  ["Learning Behavior Coach", "Adapts pace and tone; sensitive to frustration and wellness."],
  ["Critical Thinking Coach", "Socratic probes that build reasoning, not just answers."],
  ["Situational Analysis Coach", "Progressive cue reveal and priority training."],
  ["Quick Decision Coach", "Split-minute drills under time pressure."],
  ["Foresight / Mental Prep Coach", "Forecasting and rehearsal before events unfold."],
  ["Emergency Scenario Coach", "Emergency procedures (e.g. sim engine-out landing)."],
];

export default function DashboardPage() {
  return (
    <main className="container">
      <h1>Teacher Dashboard</h1>
      <p className="muted">The agent roster powering each live class and training drill.</p>
      <div className="grid">
        {AGENTS.map(([name, desc]) => (
          <div className="card" key={name}>
            <h3>{name}</h3>
            <p className="muted">{desc}</p>
          </div>
        ))}
      </div>
    </main>
  );
}
