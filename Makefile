# Agentic Online Education Platform - developer entrypoints.
# Always python3. Dev runs services natively; compose runs the full stack.

PY ?= python3
VENV ?= .venv
ACT := . $(VENV)/bin/activate
SERVICES := orchestrator memory speech perception curriculum billing

.PHONY: help setup setup-web test test-web lint-web typecheck-web build-web \
        dev-orchestrator dev-web compose-config clean

help:
	@echo "Targets:"
	@echo "  setup           Create venv and install backend dev deps (editable shared)"
	@echo "  setup-web       Install web deps (pnpm)"
	@echo "  test            Run all Python tests (shared + services + agent-runtime)"
	@echo "  test-web        Typecheck + lint the web app"
	@echo "  build-web       Production build of the web app"
	@echo "  dev-orchestrator  Run the orchestrator API (port 8000)"
	@echo "  dev-web         Run the Next.js dev server (port 3000)"
	@echo "  compose-config  Validate the docker compose stack"

setup:
	$(PY) -m venv $(VENV)
	$(ACT) && pip install --upgrade pip && pip install -r requirements-dev.txt

setup-web:
	cd apps/web && pnpm install

test:
	$(ACT) && cd packages/shared && python -m pytest -q
	$(ACT) && cd apps/agent-runtime && python -m pytest -q
	@for s in $(SERVICES); do \
		echo "== $$s =="; \
		$(ACT) && cd services/$$s && python -m pytest -q || exit 1; \
	done

test-web:
	cd apps/web && pnpm run typecheck && pnpm run lint

build-web:
	cd apps/web && pnpm run build

dev-orchestrator:
	$(ACT) && cd services/orchestrator && uvicorn app.main:app --reload --port 8000

dev-web:
	cd apps/web && pnpm run dev

compose-config:
	docker compose -f infra/compose/docker-compose.yml config >/dev/null && echo "compose OK"

clean:
	rm -rf $(VENV) apps/web/node_modules apps/web/.next
