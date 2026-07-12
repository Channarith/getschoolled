---
name: live-rooms-video
description: How the built-in "Salareen" group-class video rooms work — the orchestrator live-room hub, LiveKit WebRTC token minting, group-class scheduling/start flow, and the web/mobile live-room UIs. Use for group classes, multi-user video rooms, LiveKit, "404 joining a room", Q&A queue / moderation / gifts, or connecting real videochat. Salareen rooms are LiveKit-backed and self-hosted; Zoom/Teams/Meet are separate bridges in the integrations service.
---

# Live rooms & videochat (Salareen / LiveKit)

## Pieces
- Orchestrator (`services/orchestrator`, :8000): `live_room_hub.py` (WS hub),
  `aoep_shared/live_room*.py` (`LiveRoomStore`, discovery, social, ws, rewards).
  Routes: `GET/POST /api/live-rooms`, `/api/live-rooms/{id}`, `.../join|leave|chat|
  raise-hand|queue/*|mute|reaction|gift|record*|ban|report|follow`.
- Group classes: `/api/group-classes` (+ `/{id}/register|start|calendar.ics`),
  model in `aoep_shared/group_classes.py`.
- Media/LiveKit token: `aoep_shared/providers/media.py::issue_token` mints a REAL
  LiveKit access token (HS256 JWT, `video` grant: roomJoin/canPublish/canSubscribe)
  for `LIVEKIT_URL` — works against a local container or a cluster.
- Web: `apps/web/app/group-classes/page.tsx` (platform `salareen`), the room UI at
  `apps/web/app/live-room/[roomId]/page.tsx` + `components/LiveKitRoomGrid.tsx`
  (`livekit-client`) + `lib/liveRoomSocket.ts`. Mobile: `screens/LiveRoomScreen.tsx`.

## Room lifecycle (and the 404 rule)
Rooms live in an in-memory `LiveRoomStore`. They are created by `open_room` on
group-class **start** or by `POST /api/live-rooms` (instant room). `GET`/`join`
on a missing room 404s. To avoid the 404 when a learner selects a scheduled (not
yet started) Salareen class, or after a restart drops the room, the orchestrator
**lazily opens** the room from the group-class record in `_ensure_group_class_room`
(roomId `class-<classId>` → look up class → start session if needed → idempotent
`open_room`). `open_room` returns the existing room if present, so lazy-open and
`/start` coexist safely. Genuinely unknown / non-Salareen room ids still 404.

## Making video actually connect (config, not code)
Token minting + `livekit-client` are already wired. Real WebRTC needs a running
LiveKit server (`infra/k8s/livekit.yaml`, VKE `LIVEKIT_URL=wss://livekit.salareen.com`)
and `LIVEKIT_API_KEY`/`LIVEKIT_API_SECRET` that **match the server** (they are
`__INJECT__` placeholders in the configmap → set as secrets). With no reachable
LiveKit, the UI degrades to local camera tiles (`livekitAvailable=false`) — not an
error, just no remote video.

## Testing
`services/orchestrator/tests/test_live_room_api.py` + `test_group_classes_api.py`.
For lazy-open coverage: schedule a Salareen class WITHOUT starting it, then GET/join
`/api/live-rooms/class-<id>` and assert 200 + a 3-segment JWT in `media.token`.
Quick live check: run orchestrator on :8000 and curl the schedule→get→join flow.
