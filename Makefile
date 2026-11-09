# One-command workflows. Needs Python 3.11+ (scripts/_python.sh finds one) and the workbook in data/.
SHELL := /bin/bash
VENV ?= .venv
BIN := $(VENV)/bin
WORKBOOK ?= data/KCCS_Sentinel_Reference_Data_Pack.xlsx
PORT ?= 8000
DEMO_NOW ?= 2026-11-08T12:00:00Z

-include .env
export

.PHONY: help install lint format typecheck test check e2e run demo docker-build docker-up docker-down clean

help:  ## list targets
	@grep -E '^[a-z0-9-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-13s %s\n", $$1, $$2}'

$(BIN)/kccs-evidence: pyproject.toml
	@. scripts/_python.sh && "$$PY" -m venv $(VENV)
	$(BIN)/python -m pip install -q --upgrade pip
	$(BIN)/python -m pip install -q -e ".[dev]"
	@touch $@

install: $(BIN)/kccs-evidence  ## create .venv and install the package with dev tools

lint: install  ## ruff lint + format check
	$(BIN)/ruff check src tests
	$(BIN)/ruff format --check src tests

format: install  ## apply ruff formatting and safe fixes
	$(BIN)/ruff format src tests
	$(BIN)/ruff check --fix src tests

typecheck: install  ## mypy
	$(BIN)/mypy

test: install  ## full test suite (workbook-backed tests skip if data/ is empty)
	KCCS_WORKBOOK=$(WORKBOOK) $(BIN)/python -m pytest

check: lint typecheck test  ## everything CI runs

e2e: ## fresh-venv end-to-end run that refreshes evidence/ (47 checks)
	scripts/e2e_check.sh $(WORKBOOK)

workbook:
	@test -f "$(WORKBOOK)" || { echo "Workbook not found at $(WORKBOOK). Copy KCCS_Sentinel_Reference_Data_Pack.xlsx into data/."; exit 1; }

run: install workbook  ## start the API + web UI on http://127.0.0.1:$(PORT)
	KCCS_WORKBOOK=$(WORKBOOK) KCCS_LOG_FORMAT=$${KCCS_LOG_FORMAT:-text} $(BIN)/kccs-evidence serve --port $(PORT)

demo: install workbook  ## CLI walk-through into artifacts/, then the API + UI with a fixed demo clock
	$(BIN)/kccs-evidence demo --workbook $(WORKBOOK) --out-dir artifacts --now $(DEMO_NOW)
	@echo; echo "Open http://127.0.0.1:$(PORT)/ui/  (API docs: http://127.0.0.1:$(PORT)/docs). Ctrl+C to stop."; echo
	KCCS_WORKBOOK=$(WORKBOOK) KCCS_FIXED_NOW=$(DEMO_NOW) KCCS_DB_PATH=artifacts/api/kernel.sqlite \
	  KCCS_ARTIFACTS_DIR=artifacts/api KCCS_LOG_FORMAT=$${KCCS_LOG_FORMAT:-text} $(BIN)/kccs-evidence serve --port $(PORT)

docker-build:  ## build the container image
	docker build -t kccs-evidence-kernel:local .

docker-up: workbook  ## docker compose up --build (http://localhost:8000)
	docker compose up --build

docker-down:  ## stop the compose stack (keeps the state volume)
	docker compose down

clean:  ## remove venvs, caches and generated artifacts (never touches data/ or evidence/)
	rm -rf $(VENV) .venv-e2e artifacts .pytest_cache .mypy_cache .ruff_cache build dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
