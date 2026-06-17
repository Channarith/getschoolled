import Link from "next/link";

export default function HomePage() {
  return (
    <main className="container">
      <h1>Agentic Online Education Platform</h1>
      <p className="muted">
        A multi-agent AI instructor that teaches live classes, adapts to each
        student, and remembers them across sessions. This dev build runs the
        Phase&nbsp;1 teaching loop end to end against the orchestrator.
      </p>

      <div className="grid">
        <div className="card">
          <h3>Join a Live Class</h3>
          <p className="muted">
            Start a session, watch the AI teacher present slides, and ask
            questions answered from the lesson via RAG.
          </p>
          <Link href="/class">
            <button>Enter classroom</button>
          </Link>
        </div>
        <div className="card">
          <h3>Teacher Dashboard</h3>
          <p className="muted">Overview of agents and platform capabilities.</p>
          <Link href="/dashboard">
            <button className="secondary">Open dashboard</button>
          </Link>
        </div>
        <div className="card">
          <h3>Biometric Consent</h3>
          <p className="muted">
            Vision features are opt-in and consent-gated (FERPA/GDPR/BIPA).
          </p>
          <Link href="/consent">
            <button className="secondary">Manage consent</button>
          </Link>
        </div>
      </div>
    </main>
  );
}
