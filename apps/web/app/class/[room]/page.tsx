"use client";

import { useState } from "react";
import { fetchJoinToken, type JoinInfo } from "@/lib/api";

export default function ClassRoom({
  params,
}: {
  params: { room: string };
}) {
  const [identity, setIdentity] = useState("student-1");
  const [join, setJoin] = useState<JoinInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleJoin() {
    setLoading(true);
    setError(null);
    try {
      // Phase0 wires the join handshake; phase1 connects the LiveKit JS SDK
      // using this token + url to render the live AI teacher.
      const info = await fetchJoinToken(params.room, identity);
      setJoin(info);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <div className="card">
        <span className="badge">room: {params.room}</span>
        <h2>Join the live class</h2>
        <p className="muted">
          Request a LiveKit join token from the orchestrator. The realtime media
          connection is rendered here in phase1.
        </p>
        <label>
          Your name&nbsp;
          <input
            value={identity}
            onChange={(e) => setIdentity(e.target.value)}
            style={{ padding: "0.4rem", borderRadius: 8 }}
          />
        </label>
        &nbsp;
        <button onClick={handleJoin} disabled={loading}>
          {loading ? "Joining…" : "Join class"}
        </button>
      </div>

      {error && (
        <div className="card" style={{ borderColor: "#ff6b6b" }}>
          <strong>Could not reach the orchestrator</strong>
          <p className="muted">{error}</p>
        </div>
      )}

      {join && (
        <div className="card">
          <strong>Token issued</strong>
          <p className="muted">Media URL: {join.url}</p>
          <p className="muted" style={{ wordBreak: "break-all" }}>
            JWT: {join.token.slice(0, 48)}…
          </p>
        </div>
      )}
    </main>
  );
}
