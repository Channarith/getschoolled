<p align="center">
  <img src="docs/images/hero.png" alt="AI Classroom - Agentic Online Education Platform" width="100%" />
</p>

<h1 align="center">AI Classroom &middot; Agentic Online Education Platform</h1>

<p align="center">
  A multi-agent AI instructor that teaches live online classes (group and 1:1),
  perceives the room over webcam, remembers every student across sessions, and
  adapts pedagogy in real time &mdash; built own-platform first, then bridged into
  Zoom / Teams / Meet.
</p>

<p align="center">
  <img src="docs/images/logo.png" alt="AI Classroom logo" width="120" />
</p>

---

> **Project conventions:** plain-text/code only (no markdown beyond this README and
> `AGENTS.md`), always `python3`, dual-mode via env (no code forks), pinned
> dependency versions, and `CHANGELOG.txt` updated on every meaningful change.
> See `docs/plan.txt` and `docs/cloud-agent-task.txt` for the full spec.

## Table of contents

- [What is this?](#what-is-this)
- [Screens &amp; scenarios by user type](#screens--scenarios-by-user-type)
- [Build status by phase](#build-status-by-phase)
- [Architecture &amp; design](#architecture--design)
- [Tech stack](#tech-stack)
- [Repository layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Quickstart](#quickstart)
- [Running the app](#running-the-app)
- [Testing &amp; linting](#testing--linting)
- [Configuration &amp; dual-mode](#configuration--dual-mode)
- [Full stack with Docker Compose](#full-stack-with-docker-compose)
- [The agents](#the-agents)
- [Compliance](#compliance)
- [Contributing](#contributing)

## What is this?

The platform pairs an **own agentic orchestration layer** with a base education
LLM (open-weight, RAG now, fine-tune later) on top of **LiveKit** (WebRTC) as the
real-time media backbone. The same codebase runs **fully local** (single
machine / docker compose) or **against a cloud backend**, switched purely by
configuration &mdash; there are no code forks. Every heavy capability (LLM, speech,
vision, media, object store, payments) sits behind a narrow interface with a
local and a cloud implementation, chosen at startup by a config-driven factory.

The current build runs the **live teaching loop end to end** in the web app
(start a class, the Teaching Director presents slides, ask the AI tutor questions
answered with RAG), plus working **face recognition**, **adaptive
pacing/difficulty**, **assessment** (quizzes/polls), a **curriculum CMS**,
**entitlements + multiple payment methods**, and **multilingual delivery
routing** &mdash; all testable offline. Real-time voice/video, GPU model serving,
and the external platform bridges (Zoom/Teams/Meet) are wired behind config and
need infra/credentials to run. See the status table below.

## Screens &amp; scenarios by user type

The platform serves several distinct customer types, each with its own layout and
journey. Below are recorded walkthroughs (animated GIFs) plus key screenshots.
Recordings live in `docs/demos/`, screenshots in `docs/screens/`.

### Backgrounds &amp; wallpapers (61+ designs, year-round)
A site-wide background system with **61+ designs** across holiday, seasonal,
social, economic, realistic, surreal, artistic, kids, anime and minimal styles.
Most are lightweight CSS/SVG (instant, no binary weight); five are rich image
wallpapers. The `/backgrounds` gallery lets anyone preview/apply a design, and
**Auto** mode rotates an appropriate design by date all year (New Year &rarr;
Valentine&rsquo;s &rarr; St. Patrick&rsquo;s &rarr; Earth Day &rarr; Pride &rarr;
&hellip; &rarr; Halloween &rarr; Thanksgiving &rarr; Christmas). Backed by
`apps/web/app/lib/backgrounds.ts` (`seasonalBackgroundId(date)`).

![Backgrounds gallery: 61+ themed wallpapers with seasonal auto-rotation](docs/demos/site_backgrounds_gallery_demo.gif)

| Gallery (categories + swatches) | Applied site-wide (Dreamscape) |
| --- | --- |
| <img src="docs/screens/backgrounds_gallery.webp" alt="Backgrounds gallery" /> | <img src="docs/screens/background_applied_home.webp" alt="Background applied on home" /> |

| Anime classroom | Surreal dreamscape | Kids space |
| --- | --- | --- |
| <img src="apps/web/public/wallpapers/anime_classroom.webp" alt="Anime classroom wallpaper" /> | <img src="apps/web/public/wallpapers/surreal_dreamscape.webp" alt="Surreal dreamscape wallpaper" /> | <img src="apps/web/public/wallpapers/kids_space.webp" alt="Kids space wallpaper" /> |

### Home / discover &mdash; Netflix-style catalog (on login)
When you open the home page (and right after sign-in) you land on a Netflix-style
feed: horizontal carousels for **Popular now**, **New releases**, **Free to
start**, **Hands-on labs**, **Just for kids**, and a row per **category**
(Science, Technology, History, &hellip;). Popularity is a real view signal; tiles
open the player. Backed by `GET /home` (curriculum).

![Home: Netflix-style catalog carousels](docs/demos/home_netflix_catalog_demo.gif)

<img src="docs/screens/home_netflix_feed.webp" alt="Netflix-style home feed carousels" />

### Children's platform &mdash; Kids mode
A dedicated, colorful **kids platform** at `/kids` that shows **only
kid-authored** content (mature/teen content is hidden &mdash; parental controls),
with big playful tiles and a simplified, safe experience.

![Kids mode: children's platform version](docs/demos/kids_mode_platform_demo.gif)

<img src="docs/screens/kids_mode.webp" alt="Kids mode children's platform" />

### Corporate training programs
Enterprise customers get curated **multi-course training programs** at
`/corporate` (e.g. New Hire Onboarding, Compliance &amp; Safety, Engineering
Upskilling), each adaptively sequenced by mastery. Backed by curriculum
`GET /programs?audience=corporate`.

![Corporate training programs](docs/demos/corporate_training_programs_demo.gif)

<img src="docs/screens/corporate_programs.webp" alt="Corporate training programs" />

### Sample demo class
Click **&ldquo;Try a sample class&rdquo;** on the home page to jump straight into a
live AI class: slide delivery + narration, then ask the AI teacher a question
answered with RAG **grounding, confidence and citations** (off-topic claims are
flagged by the hallucination guard).

![Sample demo class walkthrough](docs/demos/sample_demo_class_walkthrough.gif)

<img src="docs/screens/sample_class.webp" alt="Sample demo class" />

### 1. New / free learner &mdash; browse + ad-supported watch
Anonymous visitor explores the Netflix-style catalog (search + faceted filters)
and watches a course on the **free tier** with pre-roll / mid-roll video ads.

![Free learner: browse and ad-supported watch](docs/demos/persona_free_learner_browse_watch.gif)

| Catalog browse (search + filters) | Free-tier pre-roll ad |
| --- | --- |
| <img src="docs/screens/browse_catalog.webp" alt="Browse catalog filtered by Science" /> | <img src="docs/screens/watch_preroll_ad.webp" alt="Pre-roll video ad on free tier" /> |

### 2. Enrolled learner &mdash; live AI class
Start a session, the Teaching Director presents slides, ask the AI tutor a
question (answered with RAG + **grounding/citations + confidence**, unsupported
claims flagged), then a flag-gated **post-class survey** captures feedback.

![Learner: live AI class with grounded answers and post-class survey](docs/demos/persona_live_ai_class_student.gif)

<img src="docs/screens/live_class_grounded_answer.webp" alt="AI teacher answer with grounding, confidence and citations" />

### 3. Member / parent &mdash; account, personalization &amp; rewards
A paying subscriber signs in, manages membership tier and learner **sub-profiles**,
views Foresight **&ldquo;For You&rdquo;** recommendations for a child, and redeems
reward points for a prize.

![Member: account, recommendations and rewards](docs/demos/persona_member_account_rewards.gif)

| Member account portal | &ldquo;For You&rdquo; (Foresight) | Rewards redemption |
| --- | --- | --- |
| <img src="docs/screens/member_account.webp" alt="Member account portal" /> | <img src="docs/screens/foryou_recommendations.webp" alt="Foresight recommendations" /> | <img src="docs/screens/rewards_redeem.webp" alt="Rewards redemption" /> |

### 4. Educator / institution &mdash; Human-in-the-Loop console
With autonomy set to `suggest`, AI-drafted answers are routed to the educator
**review queue**; the teacher approves or edits before the answer reaches the
student. Separate lanes exist for co-teaching and co-grading.

![Educator: Human-in-the-Loop review console](docs/demos/persona_educator_hil_console.gif)

<img src="docs/screens/educator_hil_console.webp" alt="Educator HIL console with a pending AI-drafted answer" />

### 5. Platform admin / ops &mdash; feature flags, versions &amp; data mining
Secret-gated admin console: **System &amp; Versions** panel (per-service version /
git / mode, with drift detection), ~30 **feature flags** (toggles, rollouts,
tier targeting), and the multi-dimensional **survey data-mart**.

![Admin: feature flags, versions and survey insights](docs/demos/persona_admin_console.gif)

| System &amp; Versions panel | Feature-flag console |
| --- | --- |
| <img src="docs/screens/admin_system_versions.webp" alt="System and Versions panel" /> | <img src="docs/screens/admin_feature_flags.webp" alt="Feature flag console" /> |

> Higher-resolution `.mp4` versions of each recording are attached to the
> corresponding pull request.

## Build status by phase

The roadmap (`docs/plan.txt`) spans phase0 &rarr; phase10. This is the honest
current state of the repository:

Legend: ✅ implemented &amp; tested · ◑ partial (offline logic done; needs GPU/media/external infra) · ⬜ scaffolded behind interfaces/config.

| Phase | Scope | Status |
| --- | --- | --- |
| **phase0** | Foundations: monorepo, provider abstraction (local+cloud + factory), config contracts, db migrations, sample-curriculum RAG skeleton, vLLM serving config, local docker compose, per-service Dockerfiles, Makefile, CI | ✅ Implemented |
| **phase1** | Live AI teacher in the web app: Director + Lesson Delivery + Tutor; slide presentation + (text) narration; text-chat Q&amp;A via RAG | ◑ Text teaching loop works end to end; real-time LiveKit audio / agent-runtime room wiring still needs media infra |
| **phase2** | Multilingual + voice: language coverage (26 langs), per-student delivery routing (translate? pair supported? native XTTS vs cloud-TTS fallback) | ◑ Routing/coverage logic implemented &amp; tested; real streaming ASR / NLLB / XTTS need GPU model serving |
| **phase3** | Perception (consent-gated): face recognition + attention | ✅ Real self-hosted face recognition (OpenCV YuNet + SFace), consent-gated, enroll/identify, extensively tested |
| **phase4** | Memory &amp; adaptive learning: profiles, mastery, learning-behavior signals, pacing/difficulty policy (solo vs group) | ✅ Implemented &amp; tested (adaptive policy + behavior tracking) |
| **phase5** | Assessment: quizzes, definition checks, polls, mastery feedback loop | ✅ Implemented &amp; tested (MCQ generation, grading, polls) |
| **phase6** | Curriculum suite / CMS: author/import/manage decks | ✅ Implemented &amp; tested (deck CRUD + text import + presentation view) |
| **phase6b** | Monetization &amp; billing: entitlements API + payment methods (card, Apple/Google Pay, Cash App, PayPal, Venmo, Zelle); Stripe (cloud) / sandbox (local) | ✅ Implemented &amp; tested (sandbox simulates all methods offline) |
| **phase7** | Zoom bridge &rarr; LiveKit | ⬜ Scaffolded: `MediaBridge` interface + capability registry + credential checks; needs Zoom SDK + creds |
| **phase8** | Teams bridge (.NET Graph Communications) | ⬜ Scaffolded; needs Azure/Graph creds + a .NET media bot |
| **phase9** | Google Meet / Chat bridge | ⬜ Scaffolded; needs Google Workspace creds |
| **phase10** | Hardening &amp; scale: latency, GPU batching/pooling, observability, fine-tuning | ◑ Latency budget + recorder implemented &amp; tested; GPU/autoscale/observability stack needs infra |

> **In short:** phases 0, 3, 4, 5, 6, and 6b are implemented and tested; phases 1,
> 2, and 10 have their offline logic done but need GPU/media infra for the
> remaining pieces; phases 7&ndash;9 (platform bridges) are scaffolded behind a
> stable interface and need external SDKs/credentials to run. The whole backend
> suite is green (412 tests). Cloud k8s manifests under `infra/k8s` ship from the
> phase0 foundations; real model serving and platform bots require credentials/GPU.

## Trust, homework, HIL, edge, and integrations

A second initiative (19 phases, all merged) adding a trust/transparency layer (P1-P5), a homework subtool (P6-P9), human-in-the-loop collaboration (P10-P12), an edge/embodiment path toward a humanoid (P13-P15), and external API/webhook integrations (P16-P19). Legend: ✅ built &amp; merged (offline-tested).

| # | Phase | Status | PR |
| --- | --- | --- | --- |
| Trust 1 | AI disclosure: `aoep_shared/disclosure.py` + `GET /api/disclosure` + AI-instructed badge + `/transparency` page | ✅ | #44 |
| Trust 2 | Content credentials: `aoep_shared/provenance.py` (C2PA-style manifest, HMAC sign/verify) + `/provenance/sign`+`/verify` + public `/verify` page | ✅ | #45 |
| Trust 3 | User-facing citations + grounded/confidence chip + "verified against N sources" + unsupported-claim flags in class Q&A | ✅ | #46 |
| Trust 4 | Human-of-record on `Course` + `POST /report` dispute -> corrections review loop + web "Report / dispute" control | ✅ | #47 |
| Trust 5 | Opt-in `delivery_mode` (ai/human/hybrid) + `/catalog` filter + `training/model_card.py` + `GET /model-cards` + public `/model-cards` page | ✅ | #48 |

| Homework 6 | Homework generation: `aoep_shared/homework` (Assignment/Question) + `POST /homework/generate` from deck/course | ✅ | merged |
| Homework 7 | Scan/OCR (typed + handwritten): `OcrProvider` + `providers/ocr.py` + `factory.ocr()` + `homework/ingest.py` + `POST /homework/scan` | ✅ | #50 |
| Homework 8 | AI-vs-human authorship: `homework/authorship.py` (burstiness/lexical + handwriting signal) + `POST /homework/authorship` (probabilistic signal) | ✅ | #51 |
| Homework 9 | Autograder: `homework/grade.py` (objective + open-item corroboration vs catalog RAG + trusted domains like webmd/nih) + `POST /homework/grade` + public `/homework` page | ✅ | #52 |

| HIL 10 | Human-in-the-loop core: `aoep_shared/hil.py` (autonomy levels + ReviewQueue + escalation policy) | ✅ | #53 |
| HIL 11 | Co-teaching: orchestrator gates answers through the queue + `/api/hil/*` + web `/console` teacher review (`HIL_AUTONOMY`) | ✅ | #54 |
| HIL 12 | Co-grading: grades routed to a review queue + human override -> corrections back-prop + optimization ledger + console grading lane | ✅ | #55 |

| Edge 13 | Local-first `DEPLOY_MODE=edge` (all-local, offline) + `aoep_shared/edge.py` conformance (assert_offline) | ✅ | #56 |
| Embodiment 14 | `EmbodimentProvider` (say/gesture/perceive) + screen/robot impls + `factory.embodiment()` + `POST /api/embody` | ✅ | #57 |
| Embodiment 15 | On-device packaging (`apps/agent-runtime/edge/*`) + `docs/edge-robot-runbook.txt` + offline `edge_smoke` | ✅ | #58 |

| Accounts 1 | Identity service: signup/login (PBKDF2 + session tokens), membership tier, learner portfolio (enrolled/passed/failed) | ✅ | #69 |
| Accounts 2 | Course metadata (tags/audio/media_format/level/hands_on/preview/tier) + faceted `GET /courses/search` + `/courses/facets` | ✅ | #70 |
| Accounts 3 | Web: login/signup + Netflix-style `/browse` (search+filters, enroll) + `/account` member portal (tier, courses by status, security) | ✅ | #71 |
| Accounts 4 | Rewards/points: earn on course completion, redeem for class discounts or prize raffles (PS5/gold bar) + `/rewards` page + sweepstakes rules | ✅ | #72 |
| Foresight 1 | Portable "Foresight" prediction engine (`aoep_shared/foresight`): attention/router/pattern-grouping/multi-head + relational graph + LearnerForesight recommender; `docs/foresight.txt` (patent disclosure) | ✅ | #73 |
| Foresight 2 | Per-account student sub-profiles + `POST /recommend` (Foresight over the catalog) + web `/recommended` ("For You") + profile management | ✅ | #74 |
| Distribution 1 | Netflix-compatible catalog export: `GET /catalog/export?format=json\|mrss` (MRSS + JSON feed, HLS/DASH refs, maturity/audio/subtitle metadata) | ✅ | #75 |
| Monetization 1 | Video-ad monetization (IAB VAST/VMAP): `GET /courses/{id}/ad-breaks` tier-gated pre/mid-roll + web `/watch` player (skippable ads, ad-free for paid tiers) | ✅ | #76 |
| Admin 1 | Admin feature flags: `aoep_shared/flags.py` catalog + memory `GET /flags/evaluate`, admin-gated `PUT /admin/flags/{key}` (`X-Admin-Secret`) + web `/admin` console | ✅ | #77 |
| Engagement 1 | Post-class survey (flag-gated) + multi-dimensional data-mining insights: `aoep_shared/survey.py`, memory `/survey/post-class` + `/admin/survey/insights`, web survey modal on `/class` + insights on `/admin` | ✅ | #78 |
| Ops 1 | Version visibility + automation discovery: every service exposes `GET /version` + `GET /__meta` (route index); web `/admin` "System & Versions" panel aggregates service versions/health | ✅ | #79 |
| Ops 2 | Automation-testing APIs: gated deterministic `POST /admin/test/reset\|seed` hooks (`ENABLE_TEST_ENDPOINTS`) + `qa/stress.py` expanded to all 8 services & new endpoints | ✅ | #80 |
| Ops 3 | Observability/telemetry (local+cloud): per-service `GET /metrics` (Prometheus) + `/telemetry/summary\|errors\|logs`, request middleware, web `/admin` Observability panel (memory/perf/errors + RCA) | ✅ | #81 |
| Discovery 1 | Netflix-style home feed `GET /home` (popular/new/free/kids/category rails + view popularity), `/kids` children's platform, `/corporate` training programs, sample-class CTA | ✅ | #82 |
| Design 1 | Site backgrounds: 61+ themed designs (holiday/seasonal/social/economic/realistic/surreal/artistic/kids/anime) + seasonal auto-rotation + `/backgrounds` gallery picker + 5 image wallpapers | ✅ | #83 |
| Integrations 16 | Gateway + webhooks: `aoep_shared/webhooks.py` + `services/integrations` (subscriptions/emit, inbound verify, API clients) | ✅ | #59 |
| Integrations 17 | Finance/payment: `connectors/finance.py` + `/payments/webhook/{provider}` -> entitlements + `enrollment.paid` emit + payouts | ✅ | #60 |
| Integrations 18 | Education platforms: `connectors/lms.py` (LTI 1.3 / OneRoster / AGS / xAPI) + `/lms/launch`,`/lms/roster`,`/lms/grade-passback` | ✅ | #61 |
| Integrations 19 | Cloud/collab: `connectors/cloud.py` (Slack/Workspace notify, calendar scheduling, OIDC/SAML SSO) + `/notify`,`/calendar/schedule`,`/sso/oidc` | ✅ | #62 |

## Backend workstreams (validation, catalog, corrections, adaptivity, models, harvester)

Delivered phase-by-phase (each its own version release / PR). The
*Validation, Course Catalog, and Corrections Backend* plan grew into six
workstreams (23 phases); status below. Legend: ✅ built &amp; merged (offline-tested)
· ◑ code/config/runbook merged, heavy execution runs on a forked GPU/worker agent.

| # | Phase | Status | PR |
| --- | --- | --- | --- |
| 1.1 | `SearchProvider` + per-engine adapters (Bing/Google/Brave/Kagi/Baidu) + `factory.search_engines()` | ✅ | #19 |
| 1.2 | Validation engine (`validation.py`: extract/validate claims, cross-engine corroboration) | ✅ | #20 |
| 1.3 | Validation endpoints (`POST /validate/claim`, `POST /decks/{id}/validate`) | ✅ | #20 |
| 2.1 | Catalog model/store + `db/migrations/0003_catalog.sql` | ✅ | #21 |
| 2.2 | Catalog API + adaptive program plan (`/courses`, `/programs`, `/catalog`, `/programs/{id}/plan`) | ✅ | #22 |
| 3.1 | Corrections model + bulk parse (CSV/JSONL) + gold-example conversion | ✅ | #23 |
| 3.2 | Corrections review API (submit/bulk/list/approve/reject) | ✅ | #24 |
| 3.3 | Corrections apply (patch content / emit gold) + `training/export.py --corrections` back-prop | ✅ | #25 |
| 3.4 | Hallucination guard (`groundedness.py`) + Tutor abstain/ground + `/api/groundedness/check` | ✅ | #26 |
| 4.1 | Bayesian Knowledge Tracing + prerequisite `SkillGraph` (`knowledge.py`) | ✅ | #27 |
| 4.2 | Variational-inference Bayesian IRT ability model (`inference.py`) | ✅ | #28 |
| 4.3 | Thompson-sampling content bandit + BKT-driven mastery + model&rarr;policy wiring | ✅ | #29 |
| 4.4 | `OptimizationLedger` (per-stage accuracy, promote/revert) + `/api/optimization/*` | ✅ | #30 |
| 5.1 | Model bake-off / champion-challenger harness (`training/bakeoff.py`): per-category + fairness scoring, fairness gate, champion pointer (`training/champion.py`) + revert | ✅ | #31, #35 |
| 5.2 | `RoutedLLMProvider` multi-model routing + vLLM multi-LoRA serving config + per-domain adapter trainer + `routes.py` | ✅ | #31, #36 |
| 5.3 | Track A data pipeline code (clean/quality/MinHash-dedup/decontam/shard/tokenizer) + model-ladder configs | ✅ | #31, #37 |
| 5.3b | Track A.2 model sizing + 3D-parallelism validation + pretrain `--check` CPU smoke | ✅ | #38 |
| 5.3c | Track A.3 scaling-law fit + staged pretrain orchestration + runbook (full run on cluster) | ◑ | #39 |
| 5.3d | Track A.4 alignment: SFT/DPO builders + safety blocklist + fairness guardrail + config (run on cluster) | ◑ | #40 |
| 5.5 | P19 champion promotion: A-vs-B bake-off -> promote to served pointer + serving wiring + runbook | ✅ | #41 |
| 5.4 | Track B per-domain QLoRA adapter training (scripts/configs) | ✅ | #31, #36 |
| 6.1 | Harvest source spec + license gate (`harvest/sources.py`) | ✅ | #32 |
| 6.2 | Harvest dedup queue (`harvest/queue.py`) | ✅ | #32 |
| 6.3 | Harvest worker pipeline + stats (`harvest/worker.py`) | ✅ | #32 |
| 6.4 | Quality+license gate -> idempotent, batch-versioned catalog upsert + metrics (`harvest/pipeline.py`) | ✅ | #32, #42 |
| 6.5 | 24/7 at scale: checkpoint/resume loop + harvester service worker + compose/k8s + runbook | ✅ | #43 |

All ✅ rows run and are tested in this repo (full suite green &mdash; 292 tests). The ◑
rows (Track A.3/A.4 cluster pretraining/alignment) have their code/config/runbooks
merged; their compute-heavy execution runs on forked GPU agents once the secrets
in `docs/secrets.txt` are provided.

- Course validation - pluggable, key-gated `SearchProvider` (Bing/Google CSE/Brave/Kagi/Baidu + offline mock) to corroborate course content against the web. `factory.search_engines()` returns whichever engines have API keys configured. Endpoints: `POST /validate/claim` and `POST /decks/{id}/validate` (per-claim supported/unverified/contradicted + confidence + citations).

- Course catalog - persistent Programs -> Courses -> Modules (modules reference CMS decks/scenes) with dynamic-program adaptive rules (e.g. prerequisite mastery). `curriculum/catalog.py` (`CatalogStore`, JSON-persisted) + `db/migrations/0003_catalog.sql`. Endpoints: `/courses`, `/programs`, `GET /catalog`, and `POST /programs/{id}/plan` (mastery-gated course ordering with `next_course`).

- Corrections - standardized review/correction model (`aoep_shared/corrections.py`) for course content and the training model, with single + bulk (CSV/JSONL) entry and `correction_to_training_example` (gold, reward=+1) for back-propagation. Protected attributes are excluded from training context by design. Review API: `POST /corrections`, `POST /corrections/bulk`, `GET /corrections`, approve/reject, and `POST /corrections/{id}/apply` (patches deck/scene content or emits a gold training example; `training/export.py --corrections` merges those into training).

- Hallucination guard - `aoep_shared/groundedness.py` checks every answer's claims against its retrieved sources (groundedness + risk score); the Tutor abstains/grounds an ungrounded answer (never serves unsupported content) and reports `grounded`/`hallucination_risk`/`unsupported`. `POST /api/groundedness/check`; detected hallucinations route into the corrections back-prop loop.

- Adaptive learner modeling - Bayesian Knowledge Tracing + a prerequisite SkillGraph belief network (`aoep_shared/knowledge.py`), a variational-inference Bayesian IRT ability model (`aoep_shared/inference.py`), and a Thompson-sampling content bandit (`aoep_shared/bandit.py`). Memory mastery is BKT-driven and `adaptive.signals_from_models` feeds BKT/IRT signals into the pacing/difficulty policy. An `OptimizationLedger` (`aoep_shared/optimization.py`) tracks per-stage accuracy and promotes/reverts optimizer steps (endpoints under `/api/optimization/*`).
- 24/7 course harvester - `aoep_shared/harvest` (license gate + dedup queue + worker) ingests 100k+ permissively-licensed/OER materials on a separate worker agent; see `services/harvester/RUNBOOK.txt`. Two-track LLM training (open-weight multi-model + from-scratch) with a bake-off harness lives under `training/` (see `training/RUNBOOK.txt`).

## Architecture &amp; design

Full text source-of-truth: [`docs/architecture.txt`](docs/architecture.txt).
Diagrams below render on GitHub (mermaid); measured/illustrative charts are in
`docs/diagrams/`.

### Block diagram (services, providers, data)

```mermaid
flowchart TB
  subgraph Client
    WEB["Browser - apps/web (Next.js)<br/>per-persona UIs"]
  end
  WEB -->|JSON over HTTPS| ORCH["orchestrator :8000<br/>teaching loop, HIL, disclosure"]
  WEB --> MEM["memory :8004<br/>profiles, consent, flags, survey"]
  WEB --> CUR["curriculum :8005<br/>catalog, RAG, homework, ads, recommend"]
  WEB --> IDN["identity :8008<br/>accounts, tiers, students, rewards"]
  WEB --> INT["integrations :8007<br/>webhooks, LMS, finance, cloud"]
  ORCH --> SPC["speech :8002"]
  ORCH --> PER["perception :8003"]
  IDN --> BIL["billing :8006"]

  ORCH & MEM & CUR & IDN & INT & SPC & PER & BIL --> SHARED["packages/shared<br/>ProviderFactory (local | cloud | edge, by env)"]
  SHARED --> PROV{{"LLM · Speech · Vision · Media<br/>ObjectStore · Payment · OCR"}}
  SHARED --> DATA[("Postgres + pgvector · Redis · object store")]
  ORCH -.worker.-> ART["apps/agent-runtime<br/>(LiveKit Agents)"]
```

### Teaching-loop flow (ask the AI teacher)

```mermaid
flowchart LR
  A["Student asks a question"] --> B["RAG retrieve<br/>course passages"]
  B --> C["Tutor composes<br/>grounded answer"]
  C --> D["Groundedness guard<br/>confidence + flag unsupported"]
  D --> E{"HIL: should_escalate?<br/>(confidence, risk, autonomy)"}
  E -->|autonomous / high conf| F["Answer to student<br/>+ citations + confidence"]
  E -->|suggest / low conf| G["Educator review queue<br/>/console: approve or edit"]
  G --> F
```

### Ask sequence (RAG + grounding + optional human review)

```mermaid
sequenceDiagram
  participant U as Student (web)
  participant O as orchestrator
  participant R as RAG (curriculum)
  participant H as HIL ReviewQueue
  participant T as Educator (/console)
  U->>O: POST /api/sessions/{id}/ask
  O->>R: retrieve grounded passages
  R-->>O: passages + citations
  O->>O: compose answer + groundedness/confidence
  alt escalate (suggest mode / low confidence)
    O->>H: enqueue ReviewItem
    T->>H: approve / edit
    H-->>O: decided answer
  end
  O-->>U: answer + citations + confidence (+ pending_review?)
```

### Survey &rarr; multi-dimensional data mart (data mining)

```mermaid
flowchart LR
  ADM["Admin enables<br/>engagement.post_class_survey"] --> FL["memory FlagStore"]
  FL --> CLS["/class Finish -> survey modal (gated)"]
  CLS --> SUB["POST /survey/post-class"]
  SUB --> ST["SurveyStore"]
  ST --> MART["OLAP cube:<br/>course x class_type x rating"]
  ST --> MINE["suggestion-theme mining"]
  MART --> INS["/admin survey insights"]
  MINE --> INS
```

**Dual-mode** is the core idea: `DEPLOY_MODE=local|cloud|edge` sets the default
implementation family, and each capability can be overridden independently (for
example, keep biometrics local even in cloud for compliance) without forking code.

### Performance &amp; analytics charts

API latency is **measured** from the live QA stress harness (`qa/stress.py`);
mastery/engagement/funnel charts are **illustrative** models. Regenerate the
measured charts by re-running the stress smoke against a live stack.

| API latency profile (measured p95/service) | Latency vs concurrency (measured) |
| --- | --- |
| <img src="docs/diagrams/chart_api_latency.png" alt="Mean p95 latency per service" /> | <img src="docs/diagrams/chart_latency_vs_load.png" alt="Latency vs concurrency" /> |

| Mastery over sessions (BKT model) | Engagement &amp; rewards over time (illustrative) |
| --- | --- |
| <img src="docs/diagrams/chart_mastery_over_sessions.png" alt="Mastery over sessions" /> | <img src="docs/diagrams/chart_engagement_timeseries.png" alt="Engagement and rewards over time" /> |

<img src="docs/diagrams/chart_user_funnel.png" alt="User and customer-type funnel" width="560" />

## Tech stack

- **Frontend:** Next.js 14 + React 18 + TypeScript (LiveKit JS SDK to come).
- **Backend / agents:** Python, FastAPI, LiveKit Agents, LangGraph (Director).
- **LLM serving:** open-weight base model via vLLM; RAG now, fine-tune later.
- **Vision (implemented):** self-hosted OpenCV YuNet + SFace face recognition (CPU).
- **Speech (provider-wired):** Whisper large-v3 (ASR), NLLB-200 (translation),
  XTTS-v2 (TTS) behind the SpeechProvider; need GPU model serving to run.
- **Data:** Postgres (+pgvector), Redis, S3-compatible object storage (MinIO local).
- **Infra:** docker compose (local) / Kubernetes + GPU pool (cloud); GitHub Actions CI.

## Repository layout

```
apps/web                 Next.js app (live class, dashboards, consent)
apps/agent-runtime       Python LiveKit Agents worker (teaching brain)
services/orchestrator    Director + lesson/slide/RAG Q&A API (FastAPI)
services/memory          profiles, mastery, learning-behavior signals
services/speech          language coverage + delivery routing (ASR/MT/TTS behind provider)
services/perception      vision: face recognition + attention, consent-gated
services/curriculum      content/CMS API: deck authoring/import + RAG search
services/billing         plans, entitlements + payment methods (Stripe/sandbox)
packages/shared          provider interfaces + local/cloud impls + factory + schemas
config/                  per-mode env contracts (local.env, cloud.env)
db/migrations            SQL schema (consent/compliance + billing/entitlements)
models/serving           vLLM serving config (weights downloaded at runtime)
sample-curriculum/       sample lessons for the RAG skeleton
infra/compose            local docker compose (full stack)
docs/                    plan.txt, cloud-agent-task.txt, images
```

## Prerequisites

- **Python 3.11+** (the dev environment uses system Python 3.12; `.python-version`
  requests 3.11 &mdash; both work).
- **Node.js 20+** and **pnpm 10+** for the web app.
- **Docker** (optional) only for the full containerized stack.

## Quickstart

```bash
# 1. Backend: create the virtualenv and install dev deps (editable shared package)
make setup            # == python3 -m venv .venv && pip install -r requirements-dev.txt

# 2. Web: install dependencies
make setup-web        # == cd apps/web && pnpm install

# 3. Run the tests
make test             # all Python tests (shared + services + agent-runtime)
make test-web         # web typecheck + lint
```

> On a fresh Debian/Ubuntu machine you may first need the venv package:
> `sudo apt-get install -y python3.12-venv`.

## Running the app

Run the two dev processes in separate terminals (start the orchestrator first):

```bash
# Terminal 1 - Orchestrator API (http://localhost:8000)
. .venv/bin/activate
export DEPLOY_MODE=local CURRICULUM_DIR="$PWD/sample-curriculum"
cd services/orchestrator && uvicorn app.main:app --reload --port 8000
#   or: make dev-orchestrator

# Terminal 2 - Web app (http://localhost:3000)
make dev-web          # == cd apps/web && pnpm run dev
```

Then open **http://localhost:3000/class**, start the "Intro to Photosynthesis"
lesson, advance slides, and ask the AI teacher a question. The web app reads the
backend URL from `NEXT_PUBLIC_ORCHESTRATOR_URL` (default `http://localhost:8000`).

Quick API check:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/lessons
```

## Testing, QA &amp; stress

| Target | Command |
| --- | --- |
| All Python tests (412) | `make test` |
| Single package/service | `cd <path> && python -m pytest -q` |
| Coverage | `make coverage` (needs `pytest-cov`) |
| Ruff lint | `make lint` (needs `ruff`) |
| Web typecheck | `make web-typecheck` |
| Web production build | `make web-build` |
| Validate compose | `make compose-config` (requires Docker) |
| **API stress / perf** | `make stress` (start services first) |
| **Comprehensive gate** | `make qa` ( = `python3 qa/regression.py` ) |

The full backend suite (**412 tests**) is green across `packages/shared`, every
service, `training`, `scripts`, and the QA harness self-tests: provider
local-vs-cloud selection, the orchestrator teaching flow (start &rarr; advance &rarr;
ask), adaptive/assessment APIs, face-recognition accuracy, CMS deck CRUD/import,
homework generate/scan/authorship/grade, HIL review queues, edge/embodiment, and
the integrations gateway/connectors. Core `aoep_shared` line coverage is ~86%.

**Regression + stress system** (`qa/`, see `qa/RUNBOOK.txt`):

- `qa/regression.py` &mdash; one command that runs the backend matrix (+coverage),
  web typecheck/lint, and an API stress smoke, with a single pass/fail report.
- `qa/stress.py` &mdash; concurrency load test that probes each service's `/health`
  and reports **functional pass-rate (quality)**, **p50/p95/p99 latency (speed)**,
  and **RPS + error-rate (performance)** per endpoint, with tunable SLA gates
  (`--max-error-rate`, `--max-p95-ms`, `--min-functional`). Unreachable services
  are skipped, so it runs against local dev, compose, or a staging URL.

CI: `ci.yml` gates every PR (full pytest + web typecheck/build + compose/k8s);
`qa.yml` runs nightly with coverage + ruff lint.

## Configuration &amp; dual-mode

Configuration lives in `config/local.env` and `config/cloud.env`:

- `DEPLOY_MODE=local|cloud` selects the default implementation family.
- Per-component overrides (`LLM_MODE`, `SPEECH_MODE`, `VISION_MODE`,
  `MEDIA_MODE`, `OBJECT_STORE_MODE`, `PAYMENT_MODE`) override a single capability;
  **blank means "inherit `DEPLOY_MODE`"**.
- Endpoints/connection strings (`LLM_BASE_URL`, `LIVEKIT_URL`, `DATABASE_URL`,
  `REDIS_URL`, `OBJECT_STORE_ENDPOINT`, ...) are read by the cloud impls.

In **local** mode the heavy providers are deterministic, dependency-free stubs so
the teaching loop runs offline (no GPU/keys). In **cloud** mode they target
managed/GPU backends and raise `CloudProviderUnavailable` until real endpoints
and credentials are wired.

## Full stack with Docker Compose

`infra/compose/docker-compose.yml` defines the full local stack: `web`,
`orchestrator`, the supporting services, `agent-runtime`, `livekit`,
`postgres` (pgvector), `redis`, and `minio`.

```bash
docker compose -f infra/compose/docker-compose.yml config   # validate
docker compose -f infra/compose/docker-compose.yml up --build
```

## The agents

| Agent | Responsibility |
| --- | --- |
| Teaching Director | Lesson state machine; balances teach vs answer vs quiz vs re-engage |
| Lesson Delivery | Walks the deck, narrates slides via TTS, plays videos |
| Q&amp;A / Tutor | Chat + voice questions, RAG over curriculum, answers in the asker's language |
| Assessment | Pop quizzes, definition/key-point checks, polls, mastery |
| Perception | Consent-gated face recognition + attention/gaze scoring |
| Speech | Streaming multilingual ASR, language ID, translation, TTS |
| Memory / Profile | Long-term per-student profile, mastery graph, cross-class history |
| Consent / Compliance | Gates biometric features; enforces retention/deletion (FERPA/GDPR/BIPA) |

## Legal, licensing &amp; compliance

The platform is licensed under a proprietary `LICENSE` (use only in compliance
with all applicable laws/policies). User-facing legal notices live in `legal/`
and are surfaced in-app (the `/legal` page) with a recorded acceptance step:

- `LICENSE` &mdash; proprietary software license (sole, lawful usage model).
- `legal/TERMS.txt` &mdash; Terms of Use (AI disclosure, minors/school use, lawful use).
- `legal/PRIVACY.txt` &mdash; Privacy Notice (FERPA, COPPA 2025, GDPR, BIPA/CUBI).
- `legal/ACCEPTABLE_USE.txt` &mdash; Acceptable Use Policy (prohibited + region-restricted uses).
- `legal/DPA.txt` &mdash; Data Processing Addendum (school-official exception, residency).
- `SECURITY.txt` &mdash; vulnerability disclosure + user security-notification policy.
- `NOTICE.txt` &mdash; third-party / open-weight model / OER attributions.

Biometric features are **opt-in** and consent-gated, with a name-only fallback;
face embeddings are encrypted, deletable on request, and never leave the
configured boundary. A region-aware **Compliance policy** (`aoep_shared/compliance.py`)
encodes FERPA/COPPA/GDPR/BIPA and the **EU AI Act** (which **prohibits emotion
recognition in education**, so the platform disables expression/emotion inference
in the EU). Recording and data-retention disclosures are surfaced in-app.

The compliance policy is **enforced**, not just documented: set `REGION`
(`us`/`us_il`/`eu`/`other`) and the platform applies that region's rules. Users
record agreement to the required notices via the `/legal` page (memory service:
`GET /legal/notices`, `POST /legal/accept`, `GET /legal/acceptance/{user}`,
`GET /compliance/{region}`). Example enforcement: in the EU the vision provider
suppresses expression/emotion inference (EU AI Act prohibition). Data retention is
enforced (not just configured): `POST /retention/purge` (memory) deletes data past
its `retention_days` window; run it on a schedule via `scripts/retention_purge.py`
or the `retention-purge` k8s CronJob.

> These legal documents are engineering templates and **must be reviewed by
> qualified counsel** before any commercial/public release; they are not legal advice.

## Contributing

- Do **not** add new markdown files (this `README.md` and `AGENTS.md` aside) &mdash;
  use code, comments, and plain-text `.txt`.
- Always use `python3` (never `python`).
- Keep the dual-mode contract: no code forks; switch behavior via env only.
- Pin dependency versions; keep large model weights out of the repo.
- Update `CHANGELOG.txt` with every meaningful change.
- See `AGENTS.md` for environment/run caveats for automated agents.
