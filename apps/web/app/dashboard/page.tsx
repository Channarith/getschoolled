const AGENTS = [
  ["Teaching Director", "Lesson state machine; balances teach vs answer vs quiz."],
  ["Lesson Delivery", "Walks the deck and narrates slides via TTS."],
  ["Q&A / Tutor", "Answers chat/voice questions with RAG in the asker's language."],
  ["Assessment", "Pop quizzes, definition checks, polls, mastery tracking."],
  ["Perception", "Consent-gated face recognition + attention scoring."],
  ["Speech", "Streaming multilingual ASR, language ID, translation, TTS."],
  ["Memory / Profile", "Long-term per-student profile and mastery graph."],
  ["Consent / Compliance", "Gates biometrics; enforces retention (FERPA/GDPR/BIPA)."],
  ["Situational Awareness", "Perceive → comprehend → project; scores cue recall in drills."],
  ["Forecasting", "Pre-mortem: anticipates failure modes before they happen."],
  ["Rapid Decision", "OODA-loop scoring of split-second decisions under the clock."],
  ["Critical Thinking", "Critiques reasoning, flags biases/fallacies, probes Socratically."],
  ["Learning Behavior", "Adapts pacing/difficulty/tone; sensitive to overload and frustration."],
];

export default function DashboardPage() {
  return (
    <main className="container">
      <h1>Teacher Dashboard</h1>
      <p className="muted">The agent roster powering each live class.</p>
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
