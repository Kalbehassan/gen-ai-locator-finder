# Setup

## Requirements

Python 3.11 or newer and Playwright Chromium are required.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m playwright install chromium
cp .env.example .env
```

## Run locally

```bash
make dev
curl http://127.0.0.1:8000/health
```

The default provider is `MockLLMProvider`, the default vector store is local persistent ChromaDB, and screenshots are disabled.

## Quality commands

```bash
make lint
make typecheck
make test
make check
```

## Optional extras

```bash
python -m pip install -e ".[cloud]"
python -m pip install -e ".[vector]"
python -m pip install -e ".[frameworks]"
python -m pip install -e ".[ml]"
```

Optional integrations fail closed or report unavailable capability instead of changing stable behavior.
