aoep_shared — shared library (AOEP / Salareen)
==============================================

Distribution: aoep-shared  (packages/shared/pyproject.toml), editable-installed.
Import as:     aoep_shared

Why it exists
  ALL cross-service logic lives here. If code is used by more than one service,
  it belongs in aoep_shared, not in a service. Services stay thin and get
  swappable implementations by environment only — no code forks between local,
  cloud, and edge.

The core pattern (provider abstraction)
  config.py + factory.py select implementations per component by env
  (DEPLOY_MODE = local | cloud | edge, plus per-component <COMPONENT>_MODE;
  a blank override means "inherit DEPLOY_MODE"). A FastAPI app reads providers
  via app.state.factory.<provider>(). service.py's create_service() builds the
  shared app shell (rate limits, telemetry, cache, and the /health /version
  /__meta /metrics /telemetry/* routes every HTTP service exposes).

Key modules
  providers/        llm, speech, vision, media (LiveKit), payment, object_store,
                    ocr, search, routing, embodiment
  live_room*.py     Salareen multi-user LiveKit rooms + backend/serde/discovery
  group_classes*.py scheduled group-class core
  bridges/          Zoom / Teams / Meet media bridges
  meeting/          presenter personas, clone TTS, smart presenter, mock meetings
  harvest/          crawl -> compose -> generate -> critique -> export pipeline
  homework/         generate / OCR / authorship / grade
  training_agents/  scenario catalog, knowledge base + SQLite store, sessions,
                    roster, tracks; cognitive.py re-exports the cognitive engines
  content_packs.py  data-driven JSON/JSONL packs (data/content_packs/)
  languages.py      27 supported codes + language_name()/normalize_language()
  vision/           YuNet + SFace engine, gallery, engagement
  adaptive.py assessment.py learning_profile.py     pacing, quizzes, profiles
  payments.py entitlements.py plan_pricing.py ads*.py   billing + ads
  compliance.py legal.py retention.py disclosure.py     policy + notices
  telemetry.py observability.py ratelimit.py http_cache.py webhooks.py   ops

Test
  cd packages/shared && python -m pytest        # or: make test (whole repo)

See also: .cursor/skills/platform-architecture, .cursor/skills/backend-service,
docs/architecture.txt.
