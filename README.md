# Salareen - Agentic Online Education Platform

<p align="center">
  <img src="docs/brand/salareen_bayon_buddy_mascot.png" alt="Salareen study buddy — a secular Bayon-inspired face forming an S, beside a bodhi-style leaf of knowledge" width="200" />
  <img src="apps/web/public/bayon-mark.webp" alt="Salareen Bayon Buddy mascot holding the Bodhi-leaf S mark" width="180" />
</p>

Salareen (referred to as AI Classroom across parts of the codebase) is a
multi-service education platform for live AI-taught classes, mobile Drive Mode
audio lessons, adaptive learning, language learning, rewards, careers-to-skills
matching, compliance controls, and third-party integrations. The same codebase
runs local, cloud, or edge by environment configuration only.

## Our Story

**Salareen** comes from the Khmer *salaa rian* — "to go to school." Our mission
is to make world-class, AI-taught education accessible, affordable, and adaptive
for everyone — in their language, on any device — without replacing human
teachers, but by making expert, one-on-one instruction abundant.

The Salareen study buddy is a friendly, **secular** mascot: a calm, welcoming
face in the spirit of classical Khmer craftsmanship (drawn as a modern
character, not a monument), whose silhouette forms an **"S"** for Salareen,
paired with a stylized **leaf of knowledge** — a heart-shaped, bodhi-style leaf
whose veins double as a learning network. It stands for curiosity, growth, and
lifelong learning, not religion. The full story lives in the web app at
`/our-story` (`apps/web/app/our-story`).

## The platform at a glance

One AI learning platform, many ways to learn:

![Salareen platform ecosystem: homework grader, private tutor agent, mobile apps, drive-mode audio agent, human-in-the-loop / group / private courses, integrations, arcade, rewards, course scraper, knowledge base, adaptive learning, machine vision, humanoid-robot readiness, and 27 languages](docs/brand/salareen_platform_ecosystem.png)

| Sub-app | What it does |
| --- | --- |
| Privately-trained tutor agent | Our own education model, grounded in a curated knowledge base |
| Homework grader | Grades typed or handwritten work with rationale + citations |
| Human-in-the-loop courses | AI teaches; a human reviews/approves where it matters |
| Live group courses | Scheduled, synchronous classes |
| Private on-demand courses | Self-paced lessons any time |
| Drive Mode (audio agent) | Eyes-free audio classes for commutes |
| Mobile apps | Android & iOS (Expo) |
| AI adaptive learning + profiles | Per-learner mastery tracking and sequencing |
| Machine vision (camera & voice) | Opt-in recognition that can run on-device |
| Mini-games arcade | Subject mini-games and leaderboards |
| Rewards & points | Points, prizes, and redemptions |
| Course scraper / harvester | Builds fresh courses from the open web |
| Knowledge base (RAG) | Keeps answers grounded and citable |
| Integrations | LMS, finance, and cloud connectors |
| 27 languages | Multilingual delivery and language learning (UI fully localized in 14; all 27 supported via ASR + translation + speech, with more UI localization rolling out) |
| Humanoid-robot ready | The same teaching brain can drive an embodied tutor |

## Brand

Salareen has two complementary marks: the **Salareen study buddy** (a secular,
Bayon-inspired character with an "S" monogram and a bodhi-style leaf of
knowledge) used as the friendly product mascot, and a **minimalist graduation
monogram** used as the lightweight app/browser icon. Source vectors and raster
assets live in `docs/brand/` and `apps/web/public/`. Usage rules are in

## Brand

The Salareen brand pairs the friendly **Bayon Buddy** mascot (a secular,
Bayon-inspired character cradling a gold "S" medallion crowned with a Bodhi-leaf
"leaf of knowledge") with a minimalist circular **"S" badge** used as the
app/browser icon. The "S" and the leaf stand for school, curiosity, and growth -
it is a cultural character, not a religious symbol. Web delivery assets live in
`apps/web/public/`; mobile assets in `apps/mobile/assets/`; usage rules in
`docs/brand/branding.txt`.

| Asset | Path | Purpose |
| --- | --- | --- |
| Study buddy mascot | `docs/brand/salareen_bayon_buddy_mascot.png` | Friendly product mascot (hero, about, app store) |
| Mascot (web) | `apps/web/public/salareen-mascot.webp` | Web-optimized mascot |
| Platform ecosystem poster | `docs/brand/salareen_platform_ecosystem.png` | One-glance map of every sub-app |
| Ecosystem (web) | `apps/web/public/salareen-ecosystem.webp` | Web-optimized ecosystem poster |
| Mark SVG | `apps/web/public/logo-mark.svg` | Browser/app icon and lightweight web mark |
| Mark source | `docs/brand/aiclassroom_mark.svg` | Single source of truth for the icon |
| Wordmark source | `docs/brand/aiclassroom_wordmark.svg` | Horizontal lockup |
| Favicon | `apps/web/public/favicon.ico` | Browser favicon |

Design guardrail: brand and theme art stays **secular**. The Salareen buddy is a
culturally-inspired *character*, presented as a friendly study companion — not a
temple, monument, or devotional object — and the leaf is framed as a symbol of
knowledge and growth, not faith. Keep it respectful, never appropriative.
| Bayon Buddy mascot | `apps/web/public/bayon-mark.webp` | Hero / marketing mascot |
| Logo mark (web) | `apps/web/public/logo-mark.webp` | Nav + browser/app "S" badge |
| Logo mark (SVG) | `apps/web/public/logo-mark.svg` | Themable vector "S" badge |
| Kids logo variant | `apps/web/public/logo-cartoon-mark.webp` | Cartoon "S" badge on /kids |
| App icon (mobile) | `apps/mobile/assets/salareen_icon_1024.png` | iOS/Android app icon + splash |
| Favicon | `apps/web/public/favicon.ico` | Browser favicon |

Design guardrail: brand and theme art stays **secular**. The Bayon Buddy is a
culturally-inspired character presented as a friendly study companion - never a
temple, monument, or devotional object - and the leaf is a symbol of knowledge
and growth, not faith. Keep it respectful and never appropriative.

## Screens and videos

<video src="docs/demos/platform_walkthrough.mp4" controls></video>

Mobile preview walkthrough: <video src="docs/demos/mobile_preview_walkthrough.mp4" controls></video>

| Web home | Live class answer | Mobile preview | Themes |
| --- | --- | --- | --- |
| <img src="docs/screens/homepage.webp" alt="Web homepage" /> | <img src="docs/screens/live_class_answer.webp" alt="Live class AI answer with grounding" /> | <img src="docs/screens/mobile_preview.webp" alt="Mobile web preview" /> | <img src="docs/screens/backgrounds_gallery.webp" alt="Neutral backgrounds gallery" /> |

Additional walkthroughs checked into `docs/demos/` include Drive Mode, language
learning, arcade, careers, kids mode, corporate training, admin, educator HIL,
and member rewards flows. Additional screenshots live in `docs/screens/`.

## What is implemented

| Area | Status | Key surfaces |
| --- | --- | --- |
| Live class | Session start, slide advance, RAG Q&A, grounding, confidence, dispute reporting, HIL queue | `apps/web/app/class`, `services/orchestrator` |
| Curriculum | Catalog, search/facets, decks, scenes, RAG, validation, corrections, homework, audio courses | `services/curriculum` |
| Mobile | Expo app, Drive Mode, Netflix-style rails, My List, progress, notifications, i18n, EAS profiles | `apps/mobile` |
| Language learning | 27 supported language codes including Turkish and Khmer; rich/starter tiers; exercises/pronunciation hooks | `aoep_shared/language_learning.py`, `services/speech` |
| Careers | Job board, skill coverage, JD parsing, certification class matching | `/jobs`, curriculum jobs APIs |
| Accounts | Signup/login, session tokens, students, portfolio, profile context sharing, rewards | `services/identity` |
| Payments | 44 payment methods across 12 processors; sandbox/local and provider-routed cloud paths | `docs/payments.txt`, `services/billing` |
| Integrations | Signed webhooks, LMS/LTI/OneRoster/AGS, finance webhooks, cloud notify/calendar/SSO, API clients | `services/integrations` |
| Ops | `/version`, `/__meta`, telemetry, metrics, flags, testsupport, rate limits, ETags, load tests | shared service middleware + `qa/` |
| Compliance | Legal notices, disclaimer gate, privacy/DPA, consent, retention, regional policy, internal auth gates | `legal/`, `services/memory` |
| Scale/hosting | Docker compose, k8s manifests, HPAs/PDBs/Ingress/Redis, Terraform skeletons, hosting plan | `infra/`, `docs/hosting.txt`, `docs/scalability.txt` |
| Vultr VKE | Provider overlay for Vultr Container Registry, VKE ingress hosts, Vultr Object Storage, and VKE block-storage constraints | `infra/k8s-vke` |

Known live-class gap: the current web example is interactive but not yet fully
autonomous per-student live orchestration. The Director, TeachingBrain, Memory
signals, HIL, and adaptive policy exist; the next implementation step is wiring
those into a tick-by-tick live agent loop that changes pacing, reteaches, quizzes,
and feedback per student during the same course.

## Architecture

```mermaid
flowchart TB
  WEB[apps/web - Next.js]
  MOBILE[apps/mobile - Expo]
  ORCH[orchestrator :8000 - class sessions, tutor, HIL, adaptive plan]
  SPEECH[speech :8002 - languages, TTS routing, translation, learning APIs]
  PER[perception :8003 - consent-gated face/attention]
  MEM[memory :8004 - consent, mastery, behavior, flags, surveys]
  CUR[curriculum :8005 - catalog, RAG, homework, audio, jobs, notifications]
  BILL[billing :8006 - plans, entitlements, checkout]
  INT[integrations :8007 - webhooks, LMS, finance, notify, SSO]
  ID[identity :8008 - auth, students, rewards, profile sharing]
  SHARED[packages/shared - providers, schemas, policy engines]
  DATA[(Postgres/pgvector, Redis, object store, local stores)]

  WEB --> ORCH
  WEB --> CUR
  WEB --> ID
  WEB --> MEM
  WEB --> INT
  MOBILE --> CUR
  MOBILE --> ID
  ORCH --> SPEECH
  ORCH --> PER
  ID --> BILL
  ORCH & SPEECH & PER & MEM & CUR & BILL & INT & ID --> SHARED
  SHARED --> DATA
```

The `:800x` ports above are the **local-dev** ports (docker compose / `uvicorn`). In
the Kubernetes cluster every service listens on **`:8000`** and is reached by its
Service name (e.g. `http://curriculum:8000`); the browser reaches them through the
Ingress (see below).

### Kubernetes deployment (Vultr VKE)

Manifests: `infra/k8s` (base, kustomize) + `infra/k8s-vke` (Vultr overlay: image
registry rewrite, `salareen.com` hosts, cert-manager TLS, object storage). Images
are built and rolled by `.github/workflows/deploy.yml`.

```mermaid
flowchart TB
  DNS[Cloudflare DNS + TLS → salareen.com / api.salareen.com]
  subgraph cluster["VKE cluster — namespace aoep"]
    ING["nginx Ingress<br/>host + path routing · cookie session affinity · cert-manager TLS"]
    WEBD["web Deployment ×3<br/>(HPA 3→30, PDB)"]
    subgraph api["API tier — each Deployment ×3 · HPA · PDB · zone anti-affinity · :8000"]
      ORCH2[orchestrator]
      CUR2[curriculum]
      ID2[identity]
      MEM2[memory]
      SP2[speech]
      PER2[perception]
      BILL2[billing]
      INT2[integrations]
    end
    LLM2["vLLM / LLM (GPU pool)"]
    REDIS[("Redis — rate-limit, cache, sessions")]
  end
  PG[("Postgres + pgvector")]
  OBJ[("Vultr Object Storage")]
  REG[("Vultr Container Registry<br/>sjc.vultrcr.com/salareen")]
  CD["GitHub Actions deploy.yml<br/>build + push images, kubectl rollout"]

  DNS --> ING
  ING -->|"/"| WEBD
  ING -->|"/api/"| ORCH2
  ING -->|"/curriculum /identity /integrations /memory /speech /billing /perception"| api
  api --> REDIS
  api --> PG
  api --> OBJ
  ORCH2 --> LLM2
  CD -->|push| REG
  REG -. pull .-> cluster
  CD -->|set image + rollout| cluster
```

### Live-class request flow (in cluster)

The orchestrator keeps class sessions in-memory, so the Ingress uses a **cookie
session affinity** to pin each learner to the replica that created their session
(otherwise `…/advance|ask` would round-robin to a pod that never saw the session
and 404). A Redis-backed session store is the durable follow-up.

```mermaid
sequenceDiagram
  participant B as Browser (web)
  participant I as nginx Ingress (sticky)
  participant O as orchestrator (pinned replica)
  participant C as curriculum (RAG)
  participant L as LLM (vLLM or grounded fallback)
  B->>I: POST /api/sessions (start class)
  I->>O: route + set affinity cookie (B↔O)
  O-->>B: session + first slide
  B->>I: POST /api/sessions/{id}/ask
  I->>O: same pinned replica (no 404)
  O->>C: retrieve RAG passages
  C-->>O: citations + passages
  O->>L: compose grounded answer (deterministic fallback if no LLM)
  O-->>B: answer + confidence + citations
```

## Repository layout

| Path | Purpose |
| --- | --- |
| `apps/web` | Next.js web app and admin/user surfaces |
| `apps/mobile` | Expo React Native mobile app |
| `apps/agent-runtime` | LiveKit agent runtime and edge packaging |
| `packages/shared` | Provider interfaces, settings, schemas, adaptive/assessment/compliance engines |
| `services/orchestrator` | Teaching Director, sessions, Tutor Q&A, HIL, assessment |
| `services/curriculum` | Catalog, RAG, decks, jobs, homework, audio courses, notifications |
| `services/identity` | Auth, students, rewards, profile sharing |
| `services/memory` | Consent, mastery, behavior signals, flags, surveys, telemetry state |
| `services/integrations` | Webhooks, LMS, finance, cloud connectors, API clients |
| `services/billing` | Plans, entitlements, payment methods, checkout |
| `services/speech` | Language coverage, TTS routing, translation, learning APIs |
| `services/perception` | Face recognition and attention/engagement |
| `infra/compose` | Local Docker compose stack and scaling overlay |
| `infra/k8s` | Kubernetes base manifests (kustomize): Deployments/Services, HPA/PDB, Ingress (+ per-service API routes), Redis, configmap |
| `infra/k8s-vke` | Vultr VKE overlay: registry rewrite, salareen.com hosts, cert-manager TLS, object storage, runbook |
| `.github/workflows` | CI (tests/lint), QA, and `deploy.yml` (build+push images → roll the cluster) |
| `infra/terraform` | AWS and Cloudflare skeletons |
| `db/migrations` | SQL schema-of-record |
| `docs` | Architecture, brand, hosting, scalability, payments, screenshots, demos |
| `legal` | Terms, privacy, DPA, disclaimer, acceptable use, sweepstakes |

## Setup

Backend:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements-dev.txt
make install
```

Web:

```bash
cd apps/web
pnpm install
pnpm run typecheck
pnpm run build
```

Mobile:

```bash
cd apps/mobile
pnpm install
pnpm run typecheck
pnpm run export
```

Android native build prerequisites:

```bash
export ANDROID_HOME=/usr/lib/android-sdk
export ANDROID_SDK_ROOT=/usr/lib/android-sdk
export PATH=$ANDROID_HOME/platform-tools:$ANDROID_HOME/build-tools/34.0.0:$ANDROID_HOME/cmdline-tools/13.0/bin:$PATH
cd apps/mobile
pnpm run native:prebuild:android
pnpm run native:build:android
```

`native:build:android` still requires network access to Maven/Gradle plugin
repositories for Kotlin and Android Gradle plugin artifacts.

## Run commands

Core local teaching loop:

```bash
# Terminal 1 - orchestrator, live class API
cd services/orchestrator
DEPLOY_MODE=local CURRICULUM_DIR=/workspace/sample-curriculum \
  PYTHONPATH=src uvicorn orchestrator.main:app --port 8000

# Terminal 2 - curriculum, catalog/audio/jobs/home APIs
cd services/curriculum
DEPLOY_MODE=local PYTHONPATH=src uvicorn curriculum.main:app --port 8005

# Terminal 3 - web app
cd apps/web
pnpm run dev
```

Then open `http://localhost:3000`, `http://localhost:3000/class`,
`http://localhost:3000/drive`, `http://localhost:3000/jobs`, or
`http://localhost:3000/backgrounds`.

Full compose stack:

```bash
docker compose -f infra/compose/docker-compose.yml config
docker compose -f infra/compose/docker-compose.yml up --build
```

Vultr Kubernetes Engine:

```bash
kustomize build infra/k8s-vke
kubectl apply -k infra/k8s-vke
```

See `infra/k8s-vke/RUNBOOK.txt` for VKE cluster creation, ingress-nginx,
cert-manager, DNS, secrets, image push, and verification steps.

Multi-replica local overlay:

```bash
make scale-up
make loadtest URL=http://localhost:18500/audio/categories RPS=500 DURATION=30
make scale-down
```

Mobile preview:

```bash
cd apps/mobile
pnpm run export
cd dist
python3 -m http.server 3001
```

## Tests, regressions, and QA

| Check | Command |
| --- | --- |
| All backend tests | `make test` |
| Python lint | `make lint` |
| Coverage | `make coverage` |
| Web typecheck | `make web-typecheck` |
| Web build | `make web-build` |
| Mobile install | `make mobile-install` |
| Mobile typecheck | `make mobile-typecheck` |
| Mobile export build | `make mobile-build` |
| Compose config | `make compose-config` |
| Regression gate | `make qa` |
| API stress | `make stress` |
| Sustained load test | `make loadtest URL=http://localhost:8005/audio/categories RPS=200 DURATION=15` |

Focused tests added by recent branches cover catalog i18n, homework i18n, Khmer
support, notifications, payments, rate limiting, HTTP cache/ETag behavior,
service scaling, internal-auth gates, profile context sharing, and mobile builds.

## API map

| Service | Important endpoints |
| --- | --- |
| orchestrator | `GET /api/lessons`, `POST /api/sessions`, `POST /api/sessions/{id}/advance`, `POST /api/sessions/{id}/ask`, `/director/plan`, `/assessment/quiz`, `/api/hil/*` |
| curriculum | `/courses/search`, `/home`, `/audio/courses`, `/jobs`, `/jobs/parse`, `/recommend`, `/homework/*`, `/catalog/export`, `/notifications/feed`, `/validate/*`, `/scenes/*` |
| identity | `/auth/signup`, `/auth/login`, `/students`, `/profile-shares/context`, `/portfolio`, `/rewards`, `/games/*`, `/language/practice` |
| memory | `/consent`, `/legal/notices`, `/legal/accept`, `/compliance/{region}`, `/retention/purge`, `/flags/*`, `/survey/*`, `/mastery`, `/behavior`, `/learner/{student}/{topic}` |
| integrations | `/webhooks/subscriptions`, `/webhooks/emit`, `/webhooks/inbound/{provider}`, `/payments/webhook/{provider}`, `/lms/*`, `/notify`, `/calendar/schedule`, `/sso/oidc`, `/clients` |
| billing | `/plans`, `/payment-methods`, `/payment-methods/by-country`, `/entitlements/can-start`, `/checkout` |
| speech | `/languages`, `/tts/engine`, `/delivery/plan`, `/translate`, `/learn/*` |
| perception | `/enroll/{student_id}`, `/identify`, `/analyze/consent-check`, `/gallery` |

Every service created through `create_service()` also exposes `/health`,
`/version`, `/__meta`, `/metrics`, `/telemetry/summary`, `/telemetry/errors`,
and `/telemetry/logs`.

## Webhooks and third-party connections

`services/integrations` is the hub for outbound/inbound connectivity:

- Signed outbound webhooks with subscription storage and emit/retry plumbing.
- Inbound provider webhooks at `/webhooks/inbound/{provider}`.
- Payment webhooks at `/payments/webhook/{provider}`.
- LMS/LTI launch, roster sync, and grade passback.
- Finance payout and entitlement hooks.
- Cloud notification, calendar scheduling, OIDC/SSO endpoints.
- API client registry gated by internal auth.

Third-party/provider paths are environment-driven: Stripe/sandbox, PayPal,
Square, Razorpay, Paytm, Mercado Pago, VNPay, MoMo, ZaloPay, ABA/Wing/KHQR,
LTI/OneRoster/AGS, Slack/Workspace-style notify, calendar, OIDC/SAML, LiveKit,
S3/MinIO, Redis, Postgres/pgvector, vLLM/Ollama, Whisper/NLLB/XTTS, YuNet/SFace,
and OCR providers.

## Configuration

Configuration lives in `config/local.env` and `config/cloud.env`.

- `DEPLOY_MODE=local|cloud|edge` chooses provider defaults.
- Blank per-component overrides inherit `DEPLOY_MODE`.
- Component overrides include `LLM_MODE`, `SPEECH_MODE`, `VISION_MODE`,
  `MEDIA_MODE`, `OBJECT_STORE_MODE`, `PAYMENT_MODE`, `OCR_MODE`, and related
  URLs/secrets.
- Internal/admin controls use `ADMIN_SECRET`, `INTERNAL_TOKEN`,
  `INTERNAL_TOKEN_KEY`, and service-specific webhook/payment keys.

## Security, restrictions, and regulatory information

License: proprietary. See `LICENSE`. Use is limited to authorized educational
purposes and must comply with applicable laws, institution policies, and product
notices.

Legal and policy files:

| File | Purpose |
| --- | --- |
| `legal/TERMS.txt` | Terms of use and AI-specific terms |
| `legal/PRIVACY.txt` | Privacy notice for student/personal data |
| `legal/DPA.txt` | Data Processing Addendum |
| `legal/DISCLAIMER.txt` | Required AI/disclaimer notice |
| `legal/ACCEPTABLE_USE.txt` | Prohibited and restricted usage |
| `legal/SWEEPSTAKES.txt` | Rewards/prize rules |
| `SECURITY.txt` | Vulnerability disclosure and notification policy |
| `NOTICE.txt` | Third-party and open-weight/OER notices |

Compliance controls in code:

- AI disclosure endpoint and one-time disclaimer gate.
- Consent-gated biometric features and name-only fallback.
- Region policy via `aoep_shared.compliance`.
- Retention purge endpoint and scheduled purge script.
- Internal-auth gates on sensitive admin, correction, export, provenance, HIL,
  optimization, retention, enrollment, webhook/client, and payout endpoints.
- Webhook signing fails closed in cloud mode when required signing keys are unset.
- Profile sharing uses explicit owner grants, scopes, expiry, and bearer tokens.
- Rate limiting, ETags, telemetry, request IDs, and Prometheus metrics.

These legal files are engineering templates and must be reviewed by qualified
counsel before public/commercial release.

## Mobile platform

The Expo app supports Android and iOS with:

- Drive Mode audio classes using `expo-speech`.
- Netflix-style home rails and category cards.
- Continue Listening, My List, local progress, streaks, and saved settings.
- Local notifications and alerts inbox.
- Locale picker with 13 translated UI locales plus supported-language fallback.
- EAS build profiles for development, preview APK, and production app bundle/IPA.

Build locally with `pnpm run export`; build native binaries through EAS or with
`native:build:android` when Android SDK and Maven/Gradle repository access are
available.

## Hosting and scale

- `docs/hosting.txt` recommends AWS for compute/state/GPU and Cloudflare for DNS,
  CDN, WAF, DDoS, and edge storage.
- `docs/scalability.txt` documents rate limiting, ETags/cache, multi-replica
  compose, k8s HPA/PDB/anti-affinity/Ingress/Redis, load testing, and capacity
  math.
- `infra/k8s-vke/` contains the Vultr Kubernetes Engine overlay and runbook.
- `infra/terraform/` contains AWS and Cloudflare skeletons.
- `infra/k8s/` contains service, autoscaling, ingress, Redis, and kustomize files.

## Project conventions

- Use `python3`, never `python`.
- Keep local/cloud/edge behavior selected by env, not code forks.
- Pin dependency versions.
- Keep model weights and generated build outputs out of the repo.
- Update `CHANGELOG.txt` for meaningful changes.
- Do not add new markdown files unless explicitly requested.
