PY ?= python3
PORT ?= 8210
VENV ?= .venv

.PHONY: help install run test lint clean

help:
	@echo "install  install the lab (editable) with test extras"
	@echo "run      serve the API + demo on http://localhost:$(PORT)/demo/"
	@echo "test     run the pytest suite (no network, camera or API key needed)"
	@echo "lint     ruff check against the monorepo rule set"

install:
	$(PY) -m pip install -e '.[test]'

run:
	PYTHONPATH=src $(PY) -m uvicorn theodore_webcam.main:app --host 0.0.0.0 --port $(PORT)

test:
	PYTHONPATH=src $(PY) -m pytest -q

lint:
	ruff check . --config ../../ruff.toml

clean:
	rm -rf .pytest_cache **/__pycache__ build dist *.egg-info
