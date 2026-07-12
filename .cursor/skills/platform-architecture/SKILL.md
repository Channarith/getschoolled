---
name: platform-architecture
description: Orientation map for the Salareen / Agentic Online Education Platform monorepo — where things live, the service/port layout, the aoep_shared provider abstraction, and local vs cloud (deploy-mode) selection. Use when getting oriented, deciding which service/module owns a feature, wiring a new capability, or answering "where does X live / which service handles Y" for backend (FastAPI), web (Next.js), or mobile (Expo).
---

# Platform architecture (orientation)

Read this first when you don't yet know where something lives. It's an index —
follow the pointers to the focused skills for how-to detail.

## Shape of the repo
- **Monorepo.** Backend = Python/FastAPI microservices behind a provider
  abstraction; web = Next.js (`apps/web`); mobile = Expo React Native (`apps/mobile`).
- **Shared library:** `packages/shared/src/aoep_shared` (distribution `aoep-shared`,
  editable-installed). ALL cross-service logic lives here. If logic is used by more
  than one service, it belongs in `aoep_shared`, not in a service.
- **Services:** `services/<name>/src/<pkg>/main.py`. Package name == service name
  **except speech**, whose package is `speech_gw`.
- **Docs:** `docs/*.txt` (plain text — see the no-markdown convention in AGENTS.md).
  Key: `docs/architecture.txt`, `docs/api-reference.txt`, `docs/hosting.txt`.

## Services + local ports
| Service | Pkg | Port | Owns |
|---------|-----|------|------|
| orchestrator | `orchestrator` | 8000 | teaching brain: lessons, sessions, director, assessment, live rooms, group classes |
| speech | `speech_gw` | 8002 | TTS routing + `/tts`, translation, language learning |
| memory | `memory` | 8004 | telemetry, feature flags, surveys, mascots |
| curriculum | `curriculum` | 8005 | course catalog, audio courses, jobs, decks, ingest |
| identity | `identity` | 8008 | accounts, auth, students, rewards/points, games, enrollments |
| perception | `perception` | (8xxx) | face recognition / engagement (OpenCV YuNet+SFace) |
| billing | `billing` | (8xxx) | payments/subscriptions |
| integrations | `integrations` | (8xxx) | webhooks, payment/LMS/cloud connectors, Zoom/Teams/Meet bridges |

Web resolves service URLs from `NEXT_PUBLIC_*_URL` (see `apps/web/app/lib/api.ts`
`SERVICE_URLS`); mobile from `apps/mobile/src/config.ts` (cloud origin + path
prefixes like `/identity`, `/curriculum`, `/speech`, or per-service local ports).

## Provider abstraction (the core pattern)
`aoep_shared` exposes swappable providers (LLM, Speech, Vision, **Media/LiveKit**,
ObjectStore, Payment, Search, OCR, Embodiment, Jobs) selected by env — **no code
forks between local and cloud**. A FastAPI app gets them via
`app.state.factory.<provider>()` (see `aoep_shared/factory.py`, `providers/`).
`DEPLOY_MODE` (local | cloud | edge) plus per-component `<COMPONENT>_MODE` env
choose implementations; blank override means "inherit DEPLOY_MODE"
(`aoep_shared/config.py::load_config`, `AppConfig`).

## Offline-first behavior
Heavy providers (LLM/speech serving, LiveKit, ElevenLabs) target real endpoints;
without them the code **degrades gracefully** (RAG-grounded tutor fallback, device
TTS, in-memory stores) so the teaching loop works offline. Never hard-require a
GPU/key/network for a core path.

## Where to go next (focused skills)
- Run/test locally, CI gates → **run-and-test-locally**
- Add/modify a FastAPI service or provider → **backend-service**
- Accounts, points/rewards, admin, feature flags, "data lost on redeploy" → **identity-rewards-durability**
- Group-class video / Salareen LiveKit rooms → **live-rooms-video**
- Scraping/ingesting course content, lessons/slides → **harvester-content**
- Narration / natural voices / ElevenLabs → **speech-tts**
- Versioning, PRs/auto-merge, Vultr (VKE) deploy → **release-and-deploy**
