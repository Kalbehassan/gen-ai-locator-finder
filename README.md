# Gen-AI Locator Finder

Gen-AI Locator Finder is a local-first AI and Playwright demonstration for discovering resilient UI locators, ranking alternatives, verifying them live, healing failures, and exporting redacted reports.

## Stability

- **Core Stable:** FastAPI, Pydantic v2, Playwright, deterministic locator registry/ranking, local ChromaDB, redaction and report exports.
- **Optional Provider Integrations:** LiteLLM, Google GenAI, Milvus and OpenTelemetry.
- **Experimental Demonstrations:** framework adapters, embeddings and synthetic ML experiments.
- **Future Roadmap:** trained cross-application ranking, stronger visual matching and secret-vault integration.

Untrained or mock models do not claim production accuracy.

## Quick start

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m playwright install chromium
make dev
curl http://127.0.0.1:8000/health
```

The default provider is `MockLLMProvider`, screenshots are off, and ChromaDB uses local storage. No paid API key is required.

## API

```bash
curl -X POST http://127.0.0.1:8000/locate \
  -H 'content-type: application/json' \
  -d '{"url":"https://authorized-example.invalid","username":"fixture-user","password":"fixture-password","login_profile":"standard_form","description":"Find the submit button"}'
```

The API contract includes `success`, `matched`, `best_locator`, `alternatives`, `authentication`, `warnings`, `evidence`, and `suggested_tests`. A real browser agent run verifies the locator against an authorized target.

## Credential security

Never place real credentials in source, `.env.example`, fixtures or reports. Configure separately:

- `LOCATOR_APP_URL`
- `LOCATOR_APP_USERNAME`
- `LOCATOR_APP_PASSWORD`
- `LOCATOR_TENANT`
- `LOCATOR_LOGIN_PROFILE`

Passwords are Pydantic `SecretStr` values and are centrally redacted. Screenshots mask password inputs but should remain private and opt-in.

## Verification

```bash
make check
```

Tests use synthetic credentials and mocked browser behavior. Live Playwright integration should run only against systems you are authorized to test.

## Documentation

- `docs/architecture.md`
- `docs/setup.md`
- `docs/credentials.md`
- `docs/locator-strategies.md`
- `docs/agent-frameworks.md`
- `docs/ml-experiments.md`
- `docs/vector-stores.md`
- `docs/security.md`

## License

MIT. See `LICENSE`.
