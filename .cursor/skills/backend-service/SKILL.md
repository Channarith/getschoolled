---
name: backend-service
description: How to add or modify a FastAPI microservice or a shared provider in the AOEP backend. Use when adding an API endpoint, creating a new service, adding/using a provider (LLM/Speech/Media/Vision/Payment/etc.), reading config, or writing backend tests. Covers the create_service() pattern, app.state (config/factory/telemetry), the aoep_shared provider abstraction, config env wiring, and the per-service test/conftest layout.
---

# Backend service & providers

## Anatomy of a service
`services/<name>/src/<pkg>/main.py` (pkg == name, except speech = `speech_gw`):

```python
from aoep_shared.service import create_service
app = create_service("<name>")   # adds config, factory, telemetry, rate-limit, /health, /version, /metrics
```

`create_service` wires `app.state`:
- `app.state.config` → `AppConfig` (`aoep_shared/config.py`).
- `app.state.factory` → provider factory: `app.state.factory.media()`, `.speech()`,
  `.llm()`, etc. **Always get providers via the factory** so local/cloud selection
  works by env (no code forks).
- `app.state.telemetry` → per-route perf/error store (feeds `/metrics`, admin panel).

Add routes with `@app.get/post(...)`. Late imports of `aoep_shared.*` inside a
handler are common (avoids import cycles / heavy deps at boot); mark them
`# noqa: E402` only when the import must follow app/helper definitions.

## Adding config
1. Add a field to `AppConfig` (dataclass/BaseModel) in `config.py`.
2. Read it in `load_config()` via `get("ENV_NAME", "default")`.
3. Document it in `config/local.env` and `config/cloud.env` (secrets go to the
   k8s Secret, non-secrets to the configmap — see release-and-deploy).

## Providers (swappable by env)
Implementations live in `packages/shared/src/aoep_shared/providers/*.py` with a
`base.py` interface. `DEPLOY_MODE` + `<COMPONENT>_MODE` pick local vs cloud.
Token/HMAC/pure logic is implemented + unit-testable without a running backend
(e.g. `providers/media.py::issue_token` mints a real LiveKit JWT with no server).
Network-only paths raise `NotImplementedError`; keep an offline-safe fallback for
any core teaching path.

## Tests
- Location: `services/<name>/tests/`. Each dir has `conftest.py` that puts its
  `src` (and `packages/shared/src`) on `sys.path`, so `from <pkg>.main import app`
  works. Use FastAPI `TestClient(app)`.
- Startup seeding (bootstrap) runs on app startup — use
  `with TestClient(app) as c:` when a test needs seeded state.
- Mock external HTTP by monkeypatching the isolated call site (e.g.
  `elevenlabs_tts._http_post`) rather than the network.
- Run: `python3 -m pytest services/<name>/tests -q`; keep `ruff` clean on touched
  files.

## Conventions
- `python3` always; pin dependency versions; no new markdown docs (use `docs/*.txt`).
- Update `CHANGELOG.txt` (dated bullet, newest first) for meaningful changes.
