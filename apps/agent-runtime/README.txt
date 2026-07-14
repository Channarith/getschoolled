apps/agent-runtime — LiveKit teaching-agent runtime (AOEP / Salareen)
====================================================================

Purpose
  The worker shell that runs the teaching brain as a real-time LiveKit Agent —
  it wires TeachingBrain (agent_runtime/brain.py) into a live room so the AI can
  present, listen, and respond in the media plane. Also holds the edge packaging
  (apps/agent-runtime/edge/) for embodied/robot deployments.

Distribution
  aoep-agent-runtime  (installs the [livekit] extra for the media worker)
Entrypoint
  python3 -m agent_runtime.worker
  (apps/agent-runtime/src/agent_runtime/worker.py — connects to a LiveKit
  server/room; without LiveKit config it prints connect instructions and exits.)

Compose / deploy
  Runs as the `agent-runtime` service in infra/compose (no host port; depends on
  the livekit + orchestrator services).

Test
  apps/agent-runtime/tests/   (run via `make test`)

Notes
  - Salareen's group/solo live rooms are minted + tracked by the orchestrator;
    this runtime is the media-plane agent that can join them. See the
    live-rooms-video skill for the room/token flow.

See also: .cursor/skills/live-rooms-video, docs/edge-robot-runbook.txt.
