AOEP private webcam recognition lab
===================================

Purpose
-------
This private sub-repo package is for building and testing webcam-derived presence
signals before they are promoted into the production perception service.

Scope:
- Solo Theodore AI teaching
- Solo self-teaching
- Group classes / Salareen live rooms
- Face presence, attention, and too-many-faces handling
- Silhouette-only detection when a learner is partly visible or turned away
- User absence and grace-window hold decisions
- xAI-compatible Theodore voice-agent responses for natural communication

Privacy boundaries
------------------
Raw camera frames, videos, and local model artifacts must stay out of git. The
package consumes small observation records: face counts, attention scores,
silhouette boxes, movement scores, and timestamps. It does not require raw frame
storage to test the policy layer.

Integration shape
-----------------
The lab emits the same presence payload shape used by:

POST /api/live-rooms/{room_id}/presence-report

Payload fields:
- participant_id
- present
- face_count
- liveness_state
- liveness_score
- reason
- source
- observed_at

The production path can plug client-side webcam detectors or the perception
service into this package, then submit the resulting payload to the orchestrator.
For solo AI teaching and group classes, the decision can pause Theodore after the
configured absence grace window. For self-teaching, the default behavior is a
gentler nudge instead of an enforced pause.

xAI voice-agent notes
---------------------
The xAI adapter is OpenAI-compatible and uses:

XAI_API_KEY
XAI_BASE_URL, default https://api.x.ai/v1
XAI_VOICE_MODEL, default grok-4

When no key is configured, tests and local development use deterministic
Theodore-style fallback text. The speech gateway can turn the returned text into
audio through the existing TTS chain.

Local test command
------------------
From this directory:

python3 -m pytest -q
