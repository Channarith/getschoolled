# Salareen - Agentic Online Education Platform

<p align="center">
  <img src="apps/web/public/bayon-mark.webp" alt="Salareen Bayon Buddy — a secular Khmer-inspired study buddy holding the golden S medallion with a bodhi leaf" width="200" />
</p>

Salareen is a multi-service AI education platform with **600+ courses** spanning
live AI-taught classes, Drive Mode audio lessons, 27-language learning, adaptive
learning, an educational arcade, careers matching, and more. Courses cover
mathematics (Arithmetic through Differential Equations), economics, professional
skills (Power BI, SAP, DevOps, Excel, UX Design, Cybersecurity), arts, film,
music, business, finance, technology, and every core academic subject. The same
codebase runs local, cloud, or edge by environment configuration only.

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
| Live group courses | Scheduled, synchronous classes with real-time Q&A floor control and voice confirmation loop |
| Solo (1:1) classes | Self-paced lessons with Theodore — same Salareen live room, scaled to one learner; Pause/Resume for breaks |
| Drive Mode (audio agent) | Eyes-free audio courses for commutes — 500+ topics across 39 categories, all >30 min |
| My List | Bookmark any course for later — synced across web and mobile |
| Netflix-style search | Magnifying-glass search in the nav finds courses, games, and settings instantly |
| Educational arcade | 20+ games: Jeopardy, Kart Race, Creature Catch, Card Match, Uno Quiz, geometry/stocks canvases, Challenge the AI duels, Connect Four, Number Duel, and more |
| Kids Academy | Age-gated section with cartoon artwork, subject filtering (no adult/professional content), and kid-safe courses |
| Careers & Jobs | Job board (LinkedIn, Indeed, USAJobs, WeWorkRemotely, Jobspresso + free RSS sources), JD parsing, skill-gap analysis |
| Bug reports | In-app floating bug reporter with screenshot capture; reports create GitHub Issues automatically |
| Mobile apps | Android & iOS (Expo) — Drive Mode, My List, Search, live rooms, arcade, language learning |
| AI adaptive learning + profiles | Per-learner mastery tracking, readiness scoring, and adaptive sequencing |
| Machine vision (camera & voice) | Opt-in attention tracking, obscene content detection, tiredness detection |
| Rewards & points | Points, prizes, and redemptions tied to course completions and arcade performance |
| Course scraper / harvester | Builds fresh courses from the open web; Google Scholar integration for academic content |
| Knowledge base (RAG) | Keeps answers grounded and citable |
| Integrations | LMS, finance, cloud connectors, Google Scholar, RapidAPI |
| 27 languages | Multilingual delivery and language learning (UI fully localized in 14; all 27 supported via ASR + translation + speech) |
| Humanoid-robot ready | The same teaching brain can drive an embodied tutor |

## Course catalog

Salareen ships **600+ courses** across live-class lessons, Drive Mode audio, arcade games, and language learning:

### Live-class lessons (87 courses, 25-30 slides each)

| Track | Courses |
| --- | --- |
| **Mathematics** | Arithmetic, Algebra I & II, Geometry, Trigonometry, Calculus I & II, Linear Algebra, Differential Equations, Problem-Solving Math, Math Olympiad, Statistics |
| **Economics** | Introduction to Economics, Microeconomics, Macroeconomics |
| **Professional skills** | Microsoft Power BI, Project Management, SAP Fundamentals, DevOps Engineering, Digital Marketing, UX Design, Cybersecurity, IT Fundamentals |
| **Microsoft Office** | Excel Tips & Tricks, Microsoft Word, Microsoft PowerPoint |
| **Health & Growth** | Personal Well-being |
| **Programming** | Python 01–12 (intro through OOP), Intro to Science |
| **Corporate / AI** | AI Fluency Essentials, AI-Powered Productivity, AI Solutions Builder, AI Product Engineering, AI Transformation Architect, AI & ML Fellowship, Java Software Engineering, DevOps Engineering Upskiller, Applied Data Engineering, Data Fellowship, Data Insights & Business Decisions |
| **Safety & Skills** | Aviation Emergency Basics, IFR Emergency Procedures, Nursing Judgment, First Responder Essentials, Emergency & Critical Thinking, Cyber Incident Response, Rapid Decision Making, Situational Awareness |
| **Science** | Intro to Photosynthesis, Intro to Physics |
| **Math** | Intro to Fractions |

### Drive Mode audio courses (500+ topics, 39 categories, all >30 min)

History · Science & Nature · Business & Career · Personal Finance · Health & Wellness · Technology · Focus & Philosophy · Arts & Culture · Productivity & Study · True Stories & Biographies · Geography & World · World Cultures · Cooking & Food · Civics & Law · Sports & Games · Arts & Film · Music & Instruments · Business & Finance · TED Talks · Programming & Software · Data Science & AI · Psychology · Law & Legal Studies · Healthcare & Medicine · Engineering Fundamentals · Writing & Communication · Environment & Sustainability · Social Sciences · Space & Astronomy · Mathematics Advanced · Parenting & Child Development · Finance & Investing · Entrepreneurship · Language & Linguistics · Architecture & Design · Nutrition & Food Science · Film & Media Studies · Music Theory & History · Personal Development

### Language learning (81 courses)
27 languages × 3 lesson types (Essential Phrases, Everyday Conversation, Travel Survival)

### Educational arcade games (20+ games)
Jeopardy! · Kart Race · Creature Catch · Card Match · Uno Quiz · Cosmic Catch · Solar Quiz 3D · Potion Lab · Geo Blocks · Geometry Blocks · Geometry Tetris · Shape Stack · Shape Drop · Stock Rush · Stock Trader · Market Catch · Market Moves · Market Mogul · Challenge the AI Hub (Quiz Duel · Tic-Tac-Toe · Connect Four · Number Duel · Grid Master · AI Duel)

## Brand

Salareen pairs the friendly **Bayon Buddy** mascot (a secular, Bayon-inspired
character cradling a gold "S" medallion crowned with a bodhi-style "leaf of
knowledge") with a minimalist circular **"S" badge** used as the app/browser
icon. The "S" and the leaf stand for school, curiosity, and growth — it is a
cultural character, not a religious symbol. Source assets live in `docs/brand/`
and `apps/web/public/`; mobile assets in `apps/mobile/assets/`; usage rules in
`docs/brand/branding.txt`.

Each of the 27 languages gets its own mascot that differs in **both colour and
physique**: a per-locale stone tint plus a slightly different build and arm/leg
placement (e.g. a sturdier grounded kneel for `sw`, a lean upright kneel for
`ja`, a cross-legged seat for `hi`), while every variant keeps the same serene
face, lotus crown, and S-with-bodhi-leaf medallion. Regenerate with
`python3 scripts/build_mascot_bases.py` (reference-guided base carvings ->
transparent `apps/web/public/mascots/base/{locale}.webp`) then
`python3 scripts/generate_locale_mascots.py` (layers each locale's colour tint
and writes the web + mobile `{locale}.webp` and the mobile asset manifest).

| Asset | Path | Purpose |
| --- | --- | --- |
| Bayon Buddy brand mark | `apps/web/public/bayon-mark.webp` | Canonical brand/logo/icon master: the buddy holding the golden "S" medallion. Also hero mascot + `km` base |
| Web brand icons | `apps/web/public/{favicon.ico, logo-mark.webp, logo.webp, icon.png}` | Favicon, nav/profile badge, apple-touch/app icon, hero/OG — buddy on navy; regenerate via `python3 scripts/build_bayon_icons.py` |
| Locale mascots (27) | `apps/web/public/mascots/{locale}.webp` (+ `base/` carvings, mobile copies) | Per-language mascot: distinct colour + build/pose. Contact sheet: `docs/screens/mascots_locale_variants.webp` |
| Kids logo variant | `apps/web/public/logo-cartoon-mark.webp` | Cartoon "S" badge on /kids |
| Mobile app icon | `apps/mobile/assets/salareen_icon_1024.png` (+ `salareen_adaptive_fg_1024.png` for Android) | Buddy + full golden S + bodhi leaf; regenerate via `python3 scripts/generate_salareen_mobile_icon.py` then rebuild native app |
| Legacy "S" monogram | `apps/web/public/logo-mark.svg` + `docs/brand/aiclassroom_mark.svg` | Wordmark / 1-color print only (no longer the favicon/app icon) |
| Platform diagrams | `docs/brand/salareen_platform_ecosystem.png`, `salareen_workstreams_diagram.png` | Ecosystem poster + workstream map |

Design guardrail: brand and theme art stays **secular**. The Bayon Buddy is a
culturally-inspired character presented as a friendly study companion — never a
temple, monument, or devotional object — and the leaf is a symbol of knowledge
and growth, not faith. Keep it respectful and never appropriative.

## Screens and videos

### Video walkthroughs

Recorded screen walkthroughs play inline below (animated previews). GitHub does
not embed repo-relative `.mp4` files, so the full-quality recordings (with
audio) are linked underneath each preview - click to open/play them.

Netflix-style UI tour (signed-out landing, Preview, profile dropdown, instant
language switching): [docs/demos/netflix_ui_walkthrough.mp4](docs/demos/netflix_ui_walkthrough.mp4)

Full platform tour:

![Platform walkthrough](docs/demos/platform_walkthrough.gif)

Full-quality video (with audio): [docs/demos/platform_walkthrough.mp4](docs/demos/platform_walkthrough.mp4)

Mobile preview tour:

![Mobile preview walkthrough](docs/demos/mobile_preview_walkthrough.gif)

Full-quality video (with audio): [docs/demos/mobile_preview_walkthrough.mp4](docs/demos/mobile_preview_walkthrough.mp4)

Theodore webcam live monitor (per-student quality metrics and detection charts,
plus the escaped-injection security check):

![Theodore webcam live monitor walkthrough](docs/demos/theodore_webcam_live_monitor_demo.gif)

Full-quality video: [docs/demos/theodore_webcam_live_monitor_demo.mp4](docs/demos/theodore_webcam_live_monitor_demo.mp4)

### More recorded flows (animated)

| Live AI class | Drive Mode audio | Netflix catalog | Learning arcade |
| --- | --- | --- | --- |
| ![Live AI class walkthrough](docs/demos/persona_live_ai_class_student.gif) | ![Drive Mode audio courses](docs/demos/drive_mode_audio_courses_demo.gif) | ![Netflix-style catalog](docs/demos/home_netflix_catalog_demo.gif) | ![Learning arcade games](docs/demos/learning_arcade_games_demo.gif) |
| Language learning | Careers / JD parsing | Kids mode | Member rewards |
| ![Language learning](docs/demos/language_learning_demo.gif) | ![Careers and job matching](docs/demos/careers_jobs_matching_demo.gif) | ![Kids mode](docs/demos/kids_mode_platform_demo.gif) | ![Member account and rewards](docs/demos/persona_member_account_rewards.gif) |

All recorded walkthroughs live in `docs/demos/` (animated `.gif` previews render
inline; matching `.mp4` files hold the full-quality recordings).

### Screenshots

| Signed-out landing | Profile dropdown | Live class answer | Solo (1:1) live room | Themes |
| --- | --- | --- | --- | --- |
| <img src="docs/screens/landing.webp" alt="Netflix-style signed-out landing" /> | <img src="docs/screens/profile_menu.webp" alt="Profile dropdown menu" /> | <img src="docs/screens/live_class_answer.webp" alt="Live class AI answer with grounding" /> | <img src="docs/screens/solo_live_room.webp" alt="Solo 1:1 Salareen live room — AI host slide tile plus one learner, chat and Q&A" /> | <img src="docs/screens/backgrounds_gallery.webp" alt="Theme wallpapers" /> |

Multimodal course storyboards cover all 115 corporate + solo lessons (6,440
parsed teaching slides) on web and mobile. Every slide has an animated scene,
domain background, characters/objects, examples, an activity, captions, and
neural/device narration; overlays route through the 27-language translation
stack and adapt for visual, auditory, reading, hands-on, or mixed profiles.
Hand-authored DMV/food scenes remain the curated tier; the semantic builder
covers the rest. **Exception:** audio courses and Drive Mode (while-driving)
courses stay audio-only — no pictures or animations — since they are consumed
hands-free and eyes-free. This is about consumption mode, not subject: seated
driver's-ed *study* courses keep their full animated scenes.

| Corporate AI | Solo algebra | DMV school bus | Food handwashing |
| --- | --- | --- | --- |
| <img src="docs/screens/storyboard_corporate_ai.png" alt="Animated corporate AI prompt-design storyboard with office background, characters, laptop, and charts" /> | <img src="docs/screens/storyboard_solo_algebra.png" alt="Animated solo algebra storyboard with classroom background, characters, chart, and document" /> | <img src="docs/screens/storyboard_dmv_school_bus.png" alt="Animated storyboard: California school bus stop law with bus, car, pedestrian, and school-zone sign" /> | <img src="docs/screens/storyboard_food_handwash.png" alt="Animated storyboard: food-handler handwashing at a prep station with sink, soap, and raw vs ready-to-eat zones" /> |

| Salareen mobile — Android home | Drive Mode (mockup) |
| --- | --- |
| <img src="docs/screens/mobile_android_home.webp" alt="Salareen mobile app home on Android — bodhi-tree hero, Careers CTA, Netflix-style course rails, bottom tabs" width="320" /> | <img src="docs/screens/mobile_app_mockup.webp" alt="Salareen mobile Drive Mode audio player" width="320" /> |

Theodore webcam live monitor — always-on per-student metrics (distance, light,
image quality, behaviour, mic quality, noise filtering) with live detection
charts and lesson alerts. The right-hand screenshot shows a deliberate
`<img src=x onerror=alert(1)>` session id rendered as inert escaped text:

| Live monitor (2 student windows) | Injected session id stays escaped |
| --- | --- |
| <img src="docs/screens/theodore_webcam_live_monitor.webp" alt="Theodore webcam live monitor with summary metric cards, lesson alerts, and two student windows each showing quality bars and a live detection chart" /> | <img src="docs/screens/theodore_webcam_monitor_xss_escaped.webp" alt="Live monitor heading showing an injection payload rendered as literal escaped text with no alert dialog" /> |

Recognition accuracy is tunable live - lighting/exposure limits, Sobel sharpness
thresholds, distance calibration, detection thresholds and audio noise gates are
all named knobs with room presets, adjustable while watching the failed-gate list
respond:

<img src="docs/screens/theodore_vision_tuning_panel.webp" alt="Recognition Tuning panel with preset selector and live sliders for lighting, Sobel sharpness, distance and audio knobs, beside the failed quality-gate list" />

How to run and test this yourself: **[`subrepos/theodore_webcam_lab/README.md`](subrepos/theodore_webcam_lab/README.md)**
— an illustrated five-step walkthrough with a one-command health check that
names any broken piece. Full knob and endpoint reference lives beside it in
`README.txt`.

### Theodore experiment labs (all seven)

Documentation screenshots for every Theodore subrepo (regenerate with
`python3 scripts/render_lab_docs_screenshots.py`):

| Drive Mode fine-tune | Homework (75 methodologies) | Music (featured player) |
| --- | --- | --- |
| <img src="docs/screens/theodore_drive_lab.webp" alt="Theodore Drive Lab wake echo TTS knobs and eval console" /> | <img src="docs/screens/theodore_homework_lab.webp" alt="Theodore Homework Lab 75-methodology roster and generate grade console" /> | <img src="docs/screens/theodore_music_lab.webp" alt="Theodore Music Lab featured MP3 player with lyric sync and meaning glosses" /> |

| Course Studio | Audio Translation |
| --- | --- |
| <img src="docs/screens/theodore_course_studio.webp" alt="Theodore Course Studio Make and teach with multimodal cert kits examples quiz and games" /> | <img src="docs/screens/theodore_audio_translation_lab.webp" alt="Theodore Audio Translation Lab capture panel and live multilingual feed with Theodore replies" /> |

| Webcam overview (owner lock) | RAG auto-tune |
| --- | --- |
| <img src="docs/screens/theodore_webcam_lab_overview.webp" alt="Theodore Webcam Lab overview with owner face lock multi-face and integrity metrics" /> | <img src="docs/screens/theodore_rag_lab.webp" alt="Theodore RAG Lab live tuning knobs and bakeoff console" /> |

Each lab keeps a copy under `subrepos/<lab>/docs/screens/` and a numbered
**STEP BY STEP** walkthrough in its `README.txt` (webcam also has the
illustrated `README.md`). Every lab serves a browser qualification UI at `/`
(or `/lab` / `/studio`): webcam `:8015`, course studio `:8040`, audio
translation `:8041`, RAG `:8095`, Drive `:8096`, music `:8097`, homework
`:8098`. Regenerate screens with
`python3 scripts/render_lab_docs_screenshots.py`.

Per-language Bayon Buddy mascots (distinct colour + physique/pose, same face,
crown, and S-with-bodhi-leaf medallion):

<img src="docs/screens/mascots_locale_variants.webp" alt="Contact sheet of all 27 locale Bayon Buddy mascots, each with a different stone colour, build, and arm/leg placement" width="760" />

Additional screenshots live in `docs/screens/`.

> Per AGENTS.md, refresh these screenshots/videos whenever the UI changes.

## What is implemented

| Area | Status | Key surfaces |
| --- | --- | --- |
| Live class (solo & group) | Session start, slide advance, RAG Q&A with floor-request voice loop (Theodore speaks learner's name → mic opens → confirmation loop → slides resume); Pause/Resume for solo; "Say it out loud" / "Repeat after me" auto-opens mic; chat auto-reply from Theodore | `apps/web/app/class`, `apps/web/app/live-room`, `services/orchestrator` |
| Live rooms & group classes | Salareen LiveKit rooms (participant grid, single-speaker Q&A mutex, gifts/reactions, moderation), scheduled group classes, auto start/advance/end | `services/orchestrator`, `apps/web/app/live-room`, `aoep_shared/live_room.py` |
| Assessment & retention | Server-authoritative checkpoints (formative, summative, retention); accessibility format selection (audio/video/game/text); verified pass tokens; spaced-retrieval schedule; drive-mode caption overrides | `packages/shared/src/aoep_shared/assessment_policy.py`, `services/orchestrator` |
| Course catalog (600+) | 87 live-class lessons, 500+ Drive Mode audio topics (39 categories), 81 language courses, 20+ arcade games; all courses >30 min / >30 segments | `sample-curriculum/`, `aoep_shared/audio_courses.py`, `aoep_shared/audio_topic_data.py` |
| My List | Bookmark courses for later (web + mobile); synced to identity service; ＋/✓ button on every course card; `/my-list` page | `apps/web/app/my-list`, `apps/web/app/components/BookmarkButton.tsx` |
| Search | Netflix-style magnifying-glass search in nav (courses, games, settings); mobile SearchScreen; debounced 300ms, grouped results | `apps/web/app/components/NavSearchBox.tsx`, `apps/mobile/src/screens/SearchScreen.tsx` |
| Kids Academy | Age-gated `/kids` with subject-based content filter (blocks AI/professional courses); cartoon SVG gradient artwork; per-subject emoji badges | `packages/shared/src/aoep_shared/learnable/index.py`, `apps/web/app/kids` |
| Course artwork | Subject-aware poster system: arcade/kids → inline SVG cartoon gradients (offline, accurate); 50+ subject-specific Unsplash photos for all other courses | `apps/web/app/lib/courseArtwork.ts` |
| Arcade (20+ games) | Jeopardy!, Kart Race, Creature Catch, Card Match, Uno Quiz plus geometry/stocks canvases, Challenge the AI duels, Connect Four, Number Duel, Grid Master, AI Duel, Cosmic Catch, Solar Quiz 3D, Potion Lab, and more; age group selector fixed | `apps/web/app/arcade/` |
| Bug reports → GitHub Issues | Floating 🐛 reporter with screenshot capture; auto-creates private (full) + public (redacted) GitHub Issues; screenshots stored and linked inline | `packages/shared/src/aoep_shared/bug_reports.py`, `services/memory` |
| Careers & Jobs | 8 job sources: LinkedIn (RapidAPI, rate-limited), Indeed Scraper API, Indeed RSS, USAJobs, WeWorkRemotely, Jobspresso, RemoteOK, Remotive, Arbeitnow; "Also search on" deep-links to LinkedIn/Indeed/ZipRecruiter/Glassdoor | `packages/shared/src/aoep_shared/jobs.py`, `apps/web/app/jobs` |
| Google Scholar | Academic publication search via RapidAPI; `/scholar/search` endpoint in curriculum service; 1-hour cache | `packages/shared/src/aoep_shared/scholar.py` |
| Mobile | Expo app, Drive Mode (voice profiles, Hey Sala, driving detection), Netflix-style rails, My List (server-synced), Search screen, progress, notifications, i18n, live rooms | `apps/mobile` |
| Onboarding & billing | Netflix-style first-time wizard (plan, payment, profile); standard vs VIP membership; sign-in audit | `apps/web/app/onboarding`, `apps/web/app/billing`, `services/identity` |
| Ads | Tier-gated web ad slots; house inventory locally; Google AdSense / Ad Manager / Meta via `AD_NETWORK` env | `aoep_shared/ad_networks.py`, `services/billing` |
| Language learning | 27 supported language codes; rich/starter tiers; exercises/pronunciation hooks | `aoep_shared/language_learning.py`, `services/speech` |
| Language delivery | Preferred language stored per account, follows learner across web + mobile; AI teacher answers in learner's language | `services/identity`, `services/orchestrator` |
| Accounts | Signup/login (email validation hardened), session tokens, students, portfolio, profile context sharing, rewards, My List | `services/identity` |
| Payments | 50 payment methods across 13 processors; sandbox/local and provider-routed cloud paths | `docs/payments.txt`, `services/billing` |
| Integrations | Signed webhooks, LMS/LTI/OneRoster/AGS, finance webhooks, cloud notify/calendar/SSO, RapidAPI (LinkedIn jobs, Indeed, Google Scholar), API clients | `services/integrations` |
| Ops | `/version`, `/__meta`, telemetry, metrics, flags, rate limits, ETags, load tests; auto-minor version bump threshold 120 | shared service middleware + `qa/` |
| Compliance | Legal notices, disclaimer gate, privacy/DPA, consent, retention, regional policy, internal auth gates | `legal/`, `services/memory` |
| Scale/hosting | Docker compose, k8s manifests, HPAs/PDBs/Ingress/Redis, Terraform skeletons, hosting plan | `infra/`, `docs/hosting.txt`, `docs/scalability.txt` |
| Vultr VKE | Provider overlay for Vultr Container Registry, VKE ingress, Vultr Object Storage, bug-report GitHub token, RapidAPI key in secrets | `infra/k8s-vke` |

Known live-class frontier: Salareen live rooms (LiveKit grid, Q&A mutex, gifts,
auto start/advance/end), group-class scheduling, the Director, TeachingBrain,
Memory signals, HIL, adaptive policy, and the `apps/agent-runtime` LiveKit-agent
scaffold all exist. The remaining step is wiring these into a fully autonomous,
tick-by-tick per-student live loop that changes pacing, reteaches, quizzes, and
gives feedback to each learner during the same course.

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

For a compiled visual reference — frontend, backend, accounts, data flow, network
traffic, live classes, and deployment — see **`docs/architecture.pdf`** (generated
from code by `scripts/build_architecture_pdf.py`; source diagrams in
`docs/diagrams/architecture/`). The canonical text is `docs/architecture.txt`.

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

## Course Composition Score (PCS) — our scoring algorithm

Salareen represents every course as a **quantifiable composition** and reduces
it to a single deterministic number — the **Pedagogical Composition Score
(PCS)** — so two ways of teaching the same subject can be compared with a metric
instead of an opinion. This is a **custom, proprietary algorithm (patent
pending)** unique to Salareen; the reference implementation lives in
`packages/shared/src/aoep_shared/harvest/composition.py` and is exercised by the
harvester (`services/harvester`).

### What it represents

A class is built from **nodes**. Each node has a **category** — a fixed
pedagogical type (`introduction`, `history`, `concept`, `example`, `video`,
`quiz`, `qanda`, `summary`, …; 18 in total, see `NODE_CATEGORIES`) — and an
optional **sub-node** label, a subtopic *within* that category (e.g. `"music"`
under `history`, or `example 1` / `example 2`). The whole class is stored as a
NumPy matrix `M` of shape `(C, S)` where `C` = number of categories, `S` = max
sub-node slots, and `M[i, j]` is the weight of the j-th sub-node in category `i`.

### The formula

Given the matrix `M`, the PCS is computed in five fixed steps:

$$
Q_{i,j} = \operatorname{round}(\rho \cdot M_{i,j})
\qquad
a_i = \sum_{j=0}^{S-1} (j+1)\, Q_{i,j}
$$

$$
R = \sum_{i=0}^{C-1} p_i \, a_i
\qquad
R' = R + \alpha N + \beta K
\qquad
\boxed{\;\mathrm{PCS} = R' \bmod \mu\;}
$$

| Symbol | Meaning | Value (fixed) | Constant in code |
| --- | --- | --- | --- |
| $\rho$ | weight quantization resolution (1/4 steps) | `4` | `QUANT_RESOLUTION` |
| $p_i$ | per-category coefficient = the i-th prime | `2, 3, 5, 7, …` | `_PRIMES` |
| $(j+1)$ | positional weight of sub-node slot `j` | — | `slot_weights` |
| $N$ | total nodes $=\sum_{i,j}\operatorname{round}(M_{i,j})$ | — | `total_nodes()` |
| $K$ | breadth = number of present categories | — | `present_categories()` |
| $\alpha$ | structural coefficient on $N$ | `101` | `STRUCT_NODE_COEFF` |
| $\beta$ | structural coefficient on $K$ | `103` | `STRUCT_CATEGORY_COEFF` |
| $\mu$ | readable code space (default 0–999) | `1000` | `DEFAULT_SCORE_MODULUS` |

In words: **quantize** the weights, apply a **positional weighting** to each
sub-node slot, **mix categories by distinct primes** (this is what makes the
result a near-injective fingerprint of the recipe), add **structural terms** for
size and breadth to suppress cross-shape collisions, then **fold** into a
readable 0–999 code. Setting $\mu \le 0$ returns the full uncompressed $R'$; for
exact, collision-free identity use `composition_signature()` (a SHA-256 of the
quantized matrix).

**Worked example.** A 3-node recipe `{introduction×1, example×2}`:

```
intro    (i=0, p=2):  a₀ = 1·round(4·1) = 4        → 2·4   = 8
example  (i=4, p=11): a₄ = 1·round(4·1) + 2·round(4·1)
                         = 4 + 8 = 12               → 11·12 = 132
R  = 8 + 132 = 140
R' = R + 101·N + 103·K = 140 + 101·3 + 103·2 = 649
PCS = 649 mod 1000 = 649
```

### Why it is novel / patentable

1. **Course-as-matrix representation** — pedagogy encoded as a NumPy
   node × sub-node weight matrix over a fixed category taxonomy.
2. **Prime-positional fingerprinting** — distinct-prime category mixing combined
   with positional sub-node weighting yields a compact, near-injective integer
   "recipe fingerprint" that *equates to* the exact content mix used.
3. **Tri-layer separation of identity, prior, and outcome** — the PCS (identity)
   is kept separate from `quality_index()` (a heuristic prior over
   coverage/balance/depth/interactivity) and from the *measured* survey outcome.
4. **Outcome-keyed recipe optimization** — `CompositionOutcomeLedger` correlates
   each PCS with real learner happiness, enabling direct A/B questions such as
   *"does Chemistry 101 make learners happier taught as recipe 247 or 148?"*.

### Data flow

```mermaid
flowchart LR
  SRC["Sources<br/>text · html · url · pdf · pptx · docx · database"]
  EXT["extractors.py<br/>→ ExtractedDoc (title + sections)"]
  CLS["classify_section()<br/>section → node category + sub-node label"]
  MAT["CourseComposition<br/>NumPy node × sub-node matrix M"]
  PCS["composition_score() = PCS<br/>(recipe fingerprint, e.g. 247)"]
  QUAL["quality_index() / quality_metrics()<br/>coverage · balance · depth · interactivity"]
  TAG["CourseTags (JSON/meta)<br/>free/expensive · LinkedIn job · career · core"]
  REV["GeneratedCourse → JSON<br/>(human review)"]
  CAT[("Curriculum catalog<br/>Course + meta_composition_score")]
  SURV["Post-class survey<br/>(happiness 1–5)"]
  LED["CompositionOutcomeLedger<br/>PCS → avg happiness · compare(a,b)"]

  SRC --> EXT --> CLS --> MAT
  MAT --> PCS
  MAT --> QUAL
  PCS --> REV
  QUAL --> REV
  TAG --> REV
  REV --> CAT
  CAT --> SURV --> LED
  PCS --> LED
  LED -->|"best recipes feed authoring"| MAT
```

### Design (modules)

```mermaid
flowchart TB
  subgraph harvest["aoep_shared.harvest"]
    EXTRACT["extractors<br/>ExtractedDoc"]
    COMP["composition<br/>CourseComposition · PCS · OutcomeLedger"]
    TAGS["tagging<br/>CourseTags"]
    GEN["generate<br/>generate_course() → GeneratedCourse"]
    CRIT["critique<br/>HarvestCritic · optimize_with_ledger"]
    PIPE["queue · worker · pipeline · runner<br/>(24/7 license-gated crawl)"]
  end
  RUN["services/harvester/run.py<br/>--generate · --critique · --instructions · crawl"]
  OPT["aoep_shared.optimization<br/>OptimizationLedger (revertible)"]

  EXTRACT --> GEN
  COMP --> GEN
  TAGS --> GEN
  GEN --> CRIT
  COMP --> CRIT
  CRIT --> OPT
  RUN --> GEN
  RUN --> CRIT
  RUN --> PIPE
  PIPE --> COMP
```

The harvester operational guide (local runs, source types, critique loop) is in
`services/harvester/RUNBOOK.txt`; print the live generation recipe with
`python3 services/harvester/src/harvester/run.py --instructions`.

## Teaching flow: harvest → teach → present

A generated course flows through three composable parts into a live, AI-taught
class. Each part has an **offline path** (deterministic lesson + mock meeting) so
the whole chain runs in CI without keys, network, or ffmpeg.

| Part | Module | Input → Output |
| --- | --- | --- |
| 1 — Harvest | `aoep_shared.harvest` | sources → scored, tagged `GeneratedCourse` → exported `.pptx` + `.course.json` |
| 2 — Teach | `aoep_shared.teaching` | course → `LessonPlan` (deterministic offline builder, or an LLM-scripted lesson when an LLM provider is configured) |
| 3 — Present | `aoep_shared.meeting` | lesson → live meeting (Google Meet / Zoom / Teams, or an offline mock) presenting slide → speak → advance |

The Part 1 → Part 2 hand-off is a real `.pptx` (the harvester narration rides in
the slide speaker notes), so any slide reader consumes it with zero changes; the
richer `.course.json` (composition matrix + PCS + tags) feeds the meeting layer.

```mermaid
flowchart LR
  subgraph P1["Part 1 · harvest"]
    GEN["generate_course()<br/>scored + tagged course"]
    EXP["export_course_package()<br/>.pptx + .course.json"]
  end
  subgraph P2["Part 2 · teach"]
    TEACH["teach_course()<br/>LessonPlan"]
    PPT["LLM-scripted lesson<br/>(script · TTS · video, optional)"]
  end
  subgraph P3["Part 3 · present"]
    PLAN["build_presentation_plan()<br/>timed slide plan"]
    PROV["MeetingProvider<br/>Google Meet · Zoom · Teams · mock"]
    LIVE["live class<br/>slide → speak → advance"]
  end
  GEN --> EXP --> TEACH
  EXP -. ".pptx" .-> PPT -.-> TEACH
  TEACH --> PLAN --> PROV --> LIVE
```

End-to-end (offline by default; falls back to the mock meeting when a real
provider has no credentials):

```bash
# One command: harvest a course, teach it, present it in a meeting.
python3 scripts/teach_and_present.py --source notes.pptx --subject chemistry \
  --meeting-provider zoom --teach-engine fallback

# Prove the whole chain is wired correctly (13 checks, no keys/network/ffmpeg):
python3 scripts/validate_pipeline.py
```

Real meeting providers activate by environment only: `MEETING_PROVIDER` plus
`GOOGLE_ACCESS_TOKEN` (Calendar scope), `ZOOM_ACCOUNT_ID`/`ZOOM_CLIENT_ID`/
`ZOOM_CLIENT_SECRET`, or `TEAMS_ACCESS_TOKEN` (Graph). Streaming the AI's
audio+slides into a live meeting is the per-provider media-transport step
(`MeetingProvider._deliver_step`); the scheduling, lesson, timed plan, and
transcript all run without it.

## Repository layout

| Path | Purpose |
| --- | --- |
| `apps/web` | Next.js web app and admin/user surfaces |
| `apps/mobile` | Expo React Native mobile app |
| `apps/agent-runtime` | LiveKit agent runtime and edge packaging |
| `subrepos/theodore_webcam_lab` | Private webcam recognition + voice lab (owner face lock; UI `:8015/`) |
| `subrepos/theodore_course_studio` | Early-learning / certification course studio (UI `:8040/studio`) |
| `subrepos/theodore_audio_translation_lab` | Realtime mic translation across 27 languages (UI `:8041/lab`) |
| `subrepos/theodore_rag_lab` | Private RAG auto-tune / bakeoff (browser console `:8095/`) |
| `subrepos/theodore_drive_lab` | Private Drive Mode fine-tune (browser console `:8096/`) |
| `subrepos/theodore_homework_lab` | Private homework lab, 75 methodologies (browser UI `:8098/`) |
| `subrepos/theodore_music_lab` | Learn-through-music lab (featured player `:8097/`) |
| `packages/shared` | Provider interfaces, settings, schemas, adaptive/assessment/compliance engines |
| `packages/sdk` | Installable Python SDK for safely extending AOEP (`AOEPClient.local()`, in-process APIs) |
| `services/orchestrator` | Teaching Director, sessions, Tutor Q&A, HIL, assessment |
| `services/curriculum` | Catalog, RAG, decks, jobs, homework, audio courses, notifications |
| `services/identity` | Auth, students, rewards, profile sharing |
| `services/memory` | Consent, mastery, behavior signals, flags, surveys, telemetry state |
| `services/integrations` | Webhooks, LMS, finance, cloud connectors, API clients |
| `services/billing` | Plans, entitlements, payment methods, checkout |
| `services/speech` | Language coverage, TTS routing, translation, learning APIs |
| `services/perception` | Face recognition and attention/engagement |
| `services/harvester` | 24/7 crawl/generate/export CLI worker (no HTTP app); posts decks to curriculum |
| `services/homework` | Offline homework generate / OCR scan / authorship / autograde CLI (HTTP mirror lives in curriculum `/homework/*`) |
| `services/cosyvoice` | GPU CosyVoice 2 TTS sidecar (`POST /tts`, :9880) for cloud/self-hosted clone narration |
| `training` | Education-LLM fine-tuning scaffold (dataset export, QLoRA config, promote/runbooks) — not an HTTP service |
| `voices` | Registered clone-voice reference assets used by the presenter (`--tts-engine clone`) |
| `scripts` | Dev/ops helpers (run local services, deploy, present/harvest, pipeline validation, voice tools) |
| `sample-curriculum` | 87 live-class lessons: full math track (Algebra through Differential Equations), economics, professional skills (Power BI, SAP, DevOps, Digital Marketing, UX, Cybersecurity, Excel/Word/PowerPoint), corporate/AI tracks, safety training, and more |
| `qa` | Regression gate, stress, and load-test harnesses (`make qa`, `make stress`) |
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

Other services load `config/local.env` (admin seed, QA accounts) via the helper
script — `./scripts/run_local_service.sh <name>` (or `make run-identity` :8008,
`make run-memory` :8004, `make run-orchestrator` :8000). For live-room WebRTC,
run a local LiveKit server with `make run-livekit` (:7880); without it the
teaching loop still works and rooms fall back gracefully. If the browser reports
`WebSocket is closed before the connection is established`, LiveKit rejected the
token — hit `GET /api/live-rooms/livekit-status` (add `?probe=1` for a live
server-side check) for a verified/rejected/unreachable verdict instead of a
mystery. See `docs/run-local.txt` for the full local-dev guide and each service's
`README.txt`.

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

Mobile (static export preview of the JS bundle; for the live app use
`pnpm start` — see "Mobile app on macOS — setup, run, and debug" below):

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

For the full, route-by-route reference (every endpoint, auth tier, webhooks,
use cases, and cost analysis) see:

- `docs/api-reference.txt` — every HTTP API + webhook, conventions, auth tiers
  (kept in sync by `scripts/check_api_docs.py`; the per-service `/openapi.json`
  is the machine-readable source of truth).
- `docs/sdk-developers.txt` — safe local extension environment (Python SDK,
  `AOEPClient.local()`, content packs, what not to do).
- `docs/api-use-cases.txt` — end-to-end recipes (curl + SDK) for real flows.
- `docs/api-cost-value.txt` — cost-to-value analysis per API/provider.
- `docs/integrations-jobs-careers.txt` — how Careers connects to job sites.
- `docs/payments-and-security.txt` — how transactions connect and are secured.

| Service | Important endpoints |
| --- | --- |
| orchestrator | `GET /api/lessons`, `POST /api/sessions`, `POST /api/sessions/{id}/advance`, `POST /api/sessions/{id}/ask`, `/api/live-rooms/*` (join/ask/tick/solo), `/api/group-classes/*`, `/api/training/*`, `/api/cognitive/*`, `/director/plan`, `/assessment/quiz`, `/api/hil/*` |
| curriculum | `/courses/search`, `/home`, `/audio/courses`, `/jobs`, `/jobs/parse`, `/recommend`, `/homework/*`, `/catalog/export`, `/notifications/feed`, `/validate/*`, `/scenes/*` |
| identity | `/auth/signup`, `/auth/login`, `/auth/login-history`, `/onboarding/*`, `/students`, `/profile-shares/context`, `/portfolio`, `/rewards`, `/games/*`, `/language/practice` |
| memory | `/consent`, `/legal/notices`, `/legal/accept`, `/compliance/{region}`, `/retention/purge`, `/flags/*`, `/survey/*`, `/mastery`, `/behavior`, `/learner/{student}/{topic}` |
| integrations | `/webhooks/subscriptions`, `/webhooks/emit`, `/webhooks/inbound/{provider}`, `/payments/webhook/{provider}`, `/lms/*`, `/bridges/*` (Zoom/Teams/Meet), `/notify`, `/calendar/schedule`, `/sso/oidc`, `/finance/payout`, `/entitlements/{customer}`, `/clients` |
| billing | `/plans`, `/payment-methods`, `/payment-methods/by-country`, `/entitlements/can-start`, `/checkout`, `/ads/slot/{id}`, `/ads/networks`, `/ads/revenue` |
| speech | `/languages`, `/tts`, `/tts/engine`, `/tts/voices`, `/delivery/plan`, `/translate`, `/learn/*` |
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

- Drive Mode audio classes using `expo-speech`, with **narration voice profiles**
  (child-friendly, accessible/slower, calm, clear, or Auto from learning profile).
- **Hey Sala** hands-free Q&A in Drive Mode via native speech recognition
  (Siri on iOS, Google on Android; requires a dev/native build).
- **Opt-in driving detection** (GPS speed + motion sensors) with alerts and
  optional auto-launch into Drive Mode.
- **Learning profile survey** shown once after login; persisted to identity.
- Netflix-style home rails and category cards.
- Continue Listening, My List, local progress, streaks, and saved settings.
- Local notifications and alerts inbox.
- Locale picker with 14 fully translated UI locales plus supported-language
  fallback; the chosen language is saved to the account and follows the learner.
- EAS build profiles for development, preview APK, and production app bundle/IPA.

### Mobile app on macOS — setup, run, and debug

Salareen mobile is an **Expo SDK 51** app in `apps/mobile`. On a Mac you can run it
in the **iOS Simulator** and/or an **Android emulator**.

![Salareen mobile app — Home on Android (emulator)](docs/screens/mobile_android_home.webp)

> **Developer note:** Many teams find **native dev builds** (`pnpm run ios` /
> `pnpm run android`) more reliable than **Expo Go** (no separate Expo Go install,
> correct launcher icon, closer to production). Expo Go is still documented below
> for quick JS-only iteration. Full operational detail: **`apps/mobile/RUN.txt`**.

#### Requirements (install once)

| Requirement | Version / notes |
| --- | --- |
| macOS | Apple Silicon or Intel |
| **Xcode** | From the App Store; open once after install |
| **iOS Simulator runtime** | Xcode → **Settings → Platforms** → install the latest **iOS Simulator** (after every major Xcode update). If simulators fail to boot, **reboot the Mac** once. |
| **Node.js** | 18+ (22.x is common on Mac; repo sets 12 GB heap for Metro) |
| **pnpm** | `npm i -g pnpm` — repo standard (`apps/mobile/.npmrc` needs hoisted `node_modules`) |
| **CocoaPods** | `sudo gem install cocoapods` (iOS native builds) |
| **Android Studio** | Optional; only for Android emulator / `pnpm run android` |
| **ANDROID_HOME** | Add to `~/.zshrc`: `export ANDROID_HOME=$HOME/Library/Android/sdk` and `export PATH=$ANDROID_HOME/emulator:$ANDROID_HOME/platform-tools:$PATH` |

Verify toolchain (always start with verbose doctor):

```bash
cd apps/mobile
pnpm run setup                    # one-time wizard: deps + doctor + Expo Go (Path A)
# or if you skip Expo Go:
bash scripts/mobile-install.sh
VERBOSE=1 bash scripts/mobile-doctor.sh
```

#### Choose a dev path

| Path | Best for | Daily command (verbose) | First-run time |
| --- | --- | --- | --- |
| **B — Native dev build** *(recommended)* | Reliable Mac setup; real app icon; notifications | `pnpm run ios:debug` / `pnpm run android:debug` | **10–20 min** (prebuild + CocoaPods/Gradle) |
| **A — Expo Go** | Fastest JS hot-reload only; no native compile | `pnpm run launch:ios:debug` / `pnpm run launch:android:debug` | 5 min + **one-time Expo Go install** on each simulator |

`npm run ios` and `npm run android` work the same as `pnpm run ios` / `pnpm run android`
when run from `apps/mobile`. **Do not** run bare `expo` or `pnpm exec expo` on Mac
(Node heap OOM); all scripts go through `scripts/mobile-expo.sh`.

---

#### Path B — Native dev build (recommended on Mac)

**One-time** (generates `ios/` and `android/`, installs pods / Gradle deps):

```bash
cd apps/mobile
bash scripts/mobile-install.sh
VERBOSE=1 bash scripts/mobile-doctor.sh
open -a Simulator                              # boot iOS Simulator manually
pnpm run ios:debug                             # first run: prebuild + pod install + compile
```

**Android** (boot an AVD in Android Studio first, or let the launch script boot one):

```bash
cd apps/mobile
pnpm run android:debug
```

**Daily dev** (after `ios/` / `android/` exist):

```bash
cd apps/mobile
pnpm run ios:debug          # iOS Simulator
pnpm run android:debug      # Android emulator
```

Start the curriculum API in another terminal (browse/home need it):

```bash
cd services/curriculum && DEPLOY_MODE=local PYTHONPATH=src \
  uvicorn curriculum.main:app --port 8005
```

---

#### Path A — Expo Go (optional; higher setup friction)

Expo Go is a **separate app** that must be installed on each simulator once.

```bash
cd apps/mobile
pnpm run setup                # installs deps + Expo Go on iOS Simulator
pnpm run launch:ios:debug     # Metro + opens project in Expo Go
pnpm run launch:android:debug # boot AVD + Metro + Expo Go
```

If Expo Go is missing: `bash scripts/mobile-install-expo-go-ios.sh` (network once).
Manual: https://expo.dev/go?platform=ios&sdkVersion=51

Expo Orbit is **optional** (desktop helper) — not required.

---

#### macOS — iOS Simulator checklist

1. Install / update **Xcode** from the App Store.
2. Accept license: `sudo xcodebuild -license accept`
3. Install simulator runtime: **Xcode → Settings → Platforms → iOS Simulator** (pick the latest, e.g. iOS 18.x for current Xcode).
4. If simulators hang after an Xcode update: **reboot the Mac**, then:
   ```bash
   xcode-select -p
   xcrun simctl list devices available | head
   open -a Simulator
   ```
5. List simulator UDIDs (for `xcodebuild`):
   ```bash
   xcrun simctl list devices available | grep iPhone
   ```

---

#### macOS — Android emulator checklist

1. Install **Android Studio** → **Device Manager** → **Create Virtual Device** (e.g. Pixel 7, API 34+).
2. Add to `~/.zshrc` and `source ~/.zshrc`:
   ```bash
   export ANDROID_HOME=$HOME/Library/Android/sdk
   export ANDROID_SDK_ROOT=$ANDROID_HOME
   export PATH=$ANDROID_HOME/emulator:$ANDROID_HOME/platform-tools:$PATH
   ```
3. Boot the AVD (Android Studio ▶ or `emulator -avd <name> &`).
4. Confirm: `adb devices` shows an `emulator-*` device.

---

#### Debugging when something fails

Always use **verbose** commands first.

| Step | Command |
| --- | --- |
| 1. Environment check | `VERBOSE=1 bash scripts/mobile-doctor.sh` |
| 2. Kill stale Metro | `bash scripts/mobile-metro-cleanup.sh` |
| 3. Reinstall deps | `bash scripts/mobile-install.sh` |
| 4. iOS native (Expo) | `pnpm run ios:debug` |
| 5. Android native (Expo) | `pnpm run android:debug` |
| 6. iOS **xcodebuild** directly | `pnpm run xcode:debug` (after `ios/` exists) |
| 7. Android **Gradle** directly | `pnpm run gradle:debug` (after `android/` exists) |
| 8. Typecheck | `VERBOSE=1 bash scripts/mobile-typecheck.sh` |

**iOS — `xcodebuild` directly** (when `pnpm run ios:debug` fails opaquely):

```bash
cd apps/mobile
pnpm run prebuild                    # if ios/ missing
SIM_UDID=<your-simulator-udid> pnpm run xcode:debug
```

Example (replace UDID with yours from `xcrun simctl list`):

```bash
/Applications/Xcode.app/Contents/Developer/usr/bin/xcodebuild \
  -workspace ios/Salareen.xcworkspace \
  -configuration Debug \
  -scheme Salareen \
  -destination id=A701BBF9-D0E2-41D9-AD2B-3E7E1461E8C9 \
  build
```

**Android — Gradle verbose** (after prebuild):

```bash
cd apps/mobile/android
./gradlew assembleDebug --info --stacktrace
```

**Common failures**

| Symptom | Fix |
| --- | --- |
| JavaScript heap OOM (~4040 MB) | Use bash scripts / `pnpm run launch:*:debug` — never raw `expo` |
| `pnpm install` says up-to-date but `node_modules` empty | `bash scripts/mobile-install.sh` |
| Simulator won't boot after Xcode update | Install Platforms runtime; reboot Mac |
| Stuck at "Fetching bundled native modules" | `bash scripts/mobile-metro-cleanup.sh` then `bash scripts/mobile-install-expo-go-ios.sh` |
| "Expo Go is not installed" | `pnpm run setup` or `bash scripts/mobile-install-expo-go-ios.sh` |
| Empty browse/home rails | Start curriculum on port 8005 (see below) |
| Wrong directory | All commands from **`apps/mobile`**, not repo root |

---

#### Backend URL (simulator vs device)

`app.json` → `expo.extra.curriculumUrl` (default `http://localhost:8005`).

- **iOS Simulator:** `localhost` is your Mac — works as-is.
- **Android emulator:** app uses `10.0.2.2` automatically (`src/config.ts`).
- **Physical device:** use your Mac's LAN IP, not `localhost`.

```bash
cd services/curriculum && DEPLOY_MODE=local PYTHONPATH=src \
  uvicorn curriculum.main:app --port 8005
```

---

#### Build, typecheck, and release

```bash
cd apps/mobile
pnpm run typecheck:verbose
pnpm run export:verbose              # JS bundles → apps/mobile/dist/
pnpm run eas:build:preview:android   # cloud APK (needs eas-cli + Expo account)
```

Makefile shortcuts from repo root: `make mobile-setup`, `make mobile-doctor-verbose`,
`make mobile-launch-ios-debug`, `make mobile-build`.

Offline native projects: `pnpm run prebuild` then `pnpm run native:build:android`.
EAS profiles: `apps/mobile/eas.json`. Deeper troubleshooting: **`apps/mobile/RUN.txt`**.

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
