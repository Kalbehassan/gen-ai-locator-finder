PYTHON := .venv/bin/python
RUFF := .venv/bin/ruff
MYPY := .venv/bin/mypy
PYTEST := .venv/bin/pytest

.PHONY: install install-browser dev test lint typecheck check docker-clean

install:
	$(PYTHON) -m pip install -e ".[dev]"
	$(PYTHON) -m playwright install chromium

install-browser:
	$(PYTHON) -m playwright install chromium

dev:
	$(PYTHON) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

test:
	$(PYTEST) -q

lint:
	$(RUFF) format --check app tests examples
	$(RUFF) check app tests examples

typecheck:
	$(MYPY) app

check: lint typecheck test

docker-clean:
	docker compose down --volumes --remove-orphans
