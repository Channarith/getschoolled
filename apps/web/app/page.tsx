import Link from "next/link";

const AGENTS = [
  ["Teaching Director", "Balances teach / answer / quiz / re-engage."],
  ["Lesson Delivery", "Walks the deck, narrates slides via TTS."],
  ["Q&A / Tutor", "RAG over the curriculum, answers in your language."],
  ["Assessment", "Pop quizzes, key-point checks, polls, mastery."],
  ["Perception", "Face recognition + attention (consent-gated)."],
  ["Speech", "Streaming ASR, language ID, translation, TTS."],
  ["Memory / Profile", "Long-term per-student profile + mastery graph."],
  ["Consent / Compliance", "Gates biometrics; FERPA / GDPR / BIPA."],
];

export default function Home() {
  return (
    <main>
      <section className="card">
        <h2>Live classes, taught by a team of AI agents</h2>
        <p className="muted">
          Group and 1:1 instruction over WebRTC. The same codebase runs fully
          local or against a cloud backend, switched by config only.
        </p>
        <p>
          <Link href="/class/demo-room">Enter the demo classroom</Link> &nbsp;·&nbsp;
          <Link href="/consent">Manage consent</Link>
        </p>
      </section>

      <h3>The teaching agents</h3>
      <div className="grid">
        {AGENTS.map(([name, desc]) => (
          <div className="card" key={name}>
            <strong>{name}</strong>
            <p className="muted" style={{ marginBottom: 0 }}>
              {desc}
            </p>
          </div>
        ))}
      </div>
    </main>
  );
}
