# AOEP developer Makefile. Always uses python3 (never python).

PY ?= python3
VENV ?= .venv
VENV_PY := $(VENV)/bin/python
PYTHON_PKGS := packages/shared services/orchestrator services/speech \
	services/perception services/memory services/curriculum services/billing \
	apps/agent-runtime
COMPOSE := infra/compose/docker-compose.yml

.PHONY: help venv install test test-py web-install web-typecheck web-build \
	compose-config k8s-build up down clean

help:
	@echo "Targets:"
	@echo "  install        Create venv and install all Python packages (editable)"
	@echo "  test           Run all Python tests"
	@echo "  web-install    npm install for apps/web"
	@echo "  web-build      Build the Next.js web app"
	@echo "  compose-config Validate the docker compose file"
	@echo "  k8s-build      Render k8s manifests with kustomize"
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
	$(VENV_PY) -m pytest packages/shared/tests services/*/tests apps/agent-runtime/tests -q

web-install:
	cd apps/web && npm install

web-typecheck:
	cd apps/web && npm run typecheck

web-build:
	cd apps/web && npm run build

compose-config:
	docker compose -f $(COMPOSE) config

k8s-build:
	kustomize build infra/k8s

up:
	docker compose -f $(COMPOSE) up -d --build

down:
	docker compose -f $(COMPOSE) down

clean:
	rm -rf $(VENV) apps/web/node_modules apps/web/.next
