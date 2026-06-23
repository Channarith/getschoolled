# AOEP developer Makefile. Always uses python3 (never python).

PY ?= python3
VENV ?= .venv
VENV_PY := $(VENV)/bin/python
PYTHON_PKGS := packages/shared services/orchestrator services/speech \
	services/perception services/memory services/curriculum services/billing \
	apps/agent-runtime
COMPOSE := infra/compose/docker-compose.yml

.PHONY: help venv install test test-py test-inventory web-install web-typecheck web-build \
	compose-config k8s-build up down clean qa stress coverage lint regression \
	mobile-install mobile-typecheck mobile-build mobile-prebuild \
	loadtest scale-up scale-down k8s-build-vke k8s-apply-vke

help:
	@echo "Targets:"
	@echo "  install        Create venv and install all Python packages (editable)"
	@echo "  test           Run all Python tests"
	@echo "  test-inventory Count tests + map to the 16 sub-apps (MIN=N to gate)"
	@echo "  coverage       Run tests with coverage (needs pytest-cov)"
	@echo "  lint           Ruff lint the Python sources (needs ruff)"
	@echo "  stress         Stress/perf the running APIs (start services first)"
	@echo "  loadtest       Sustained-RPS load test against one URL"
	@echo "  qa             Comprehensive gate: tests+coverage + web + stress smoke"
	@echo "  web-install    npm install for apps/web"
	@echo "  web-build      Build the Next.js web app"
	@echo "  mobile-install Install Expo mobile deps (apps/mobile)"
	@echo "  mobile-build   Bundle production iOS+Android JS (apps/mobile/dist)"
	@echo "  mobile-prebuild Generate native ios/ and android/ projects (offline-blocked here)"
	@echo "  compose-config Validate the docker compose file"
	@echo "  k8s-build      Render k8s manifests with kustomize"
	@echo "  k8s-build-vke  Render Vultr VKE k8s overlay"
	@echo "  scale-up/down  Start / stop multi-replica local compose overlay"
	@echo "  up / down      Start / stop the full local stack"

venv:
	$(PY) -m venv $(VENV)
	$(VENV_PY) -m pip install --upgrade pip

install: venv
	@for pkg in $(PYTHON_PKGS); do \
		echo "installing $$pkg"; \
		$(VENV_PY) -m pip install -e "$$pkg[test]" || $(VENV_PY) -m pip install -e "$$pkg"; \
	done

test test-py:
	$(VENV_PY) -m pytest packages/shared/tests services/*/tests apps/agent-runtime/tests training/tests scripts/tests qa/tests -q

# Count collected tests + map them to the 16 ecosystem sub-apps (release gate).
# MIN ratchets the per-sub-app minimum upward over time (0 = report only).
MIN ?= 0
test-inventory:
	$(VENV_PY) scripts/test_inventory.py --min $(MIN)

# --- QA / regression / stress --------------------------------------------- #
coverage:
	$(VENV_PY) -m pytest packages/shared/tests services/*/tests apps/agent-runtime/tests training/tests scripts/tests qa/tests -q \
		--cov=packages/shared/src/aoep_shared --cov-report=term-missing:skip-covered

lint:
	$(VENV_PY) -m ruff check packages/shared/src services/*/src qa training

# Stress/perf the running APIs (start services first, e.g. `make up`).
stress:
	$(VENV_PY) qa/stress.py --concurrency 16 --requests 300

# Sustained-RPS load test against a single URL with latency histogram +
# cache-hit / rate-limit / 5xx ratios. Override URL/RPS/DURATION via env:
#   make loadtest URL=http://localhost:8005/audio/categories RPS=500 DURATION=15
URL ?= http://localhost:8005/audio/categories
RPS ?= 200
DURATION ?= 15
loadtest:
	$(VENV_PY) qa/loadtest.py "$(URL)" --rps $(RPS) --duration $(DURATION)

# One comprehensive gate: backend tests (+coverage) + web typecheck/lint + stress smoke.
qa regression:
	$(VENV_PY) qa/regression.py

web-install:
	cd apps/web && npm install

web-typecheck:
	cd apps/web && npm run typecheck

web-build:
	cd apps/web && npm run build

# --- Mobile (Expo: Android + iOS) ----------------------------------------- #
mobile-install:
	cd apps/mobile && pnpm install

mobile-typecheck:
	cd apps/mobile && pnpm typecheck

# Produce production JS bundles for iOS + Android (apps/mobile/dist).
# Native binaries (.apk/.aab/.ipa) build via EAS - see apps/mobile/RUN.txt.
mobile-build: mobile-typecheck
	cd apps/mobile && pnpm run export

# Generate native ios/ + android/ Gradle/Xcode projects from app.json.
# (Requires network access to fetch the prebuild template.)
mobile-prebuild:
	cd apps/mobile && pnpm run prebuild

compose-config:
	docker compose -f $(COMPOSE) config

k8s-build:
	kustomize build infra/k8s

k8s-build-vke:
	kustomize build infra/k8s-vke

k8s-apply-vke:
	kubectl apply -k infra/k8s-vke

up:
	docker compose -f $(COMPOSE) up -d --build

down:
	docker compose -f $(COMPOSE) down

# Multi-replica + nginx-LB local stack. See infra/compose/scale.yml +
# infra/compose/nginx-edge.conf. Hit http://localhost:18500 for the
# load-balanced curriculum service, :18000 for orchestrator.
scale-up:
	docker compose -f $(COMPOSE) -f infra/compose/scale.yml up -d --build \
		--scale curriculum=4 --scale orchestrator=3

scale-down:
	docker compose -f $(COMPOSE) -f infra/compose/scale.yml down

clean:
	rm -rf $(VENV) apps/web/node_modules apps/web/.next
