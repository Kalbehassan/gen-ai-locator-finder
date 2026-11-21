# Contributing

Thank you for contributing to Gen-AI Locator Finder. Contributions must be safe,
reviewable, and reproducible. Do not submit real credentials, customer pages,
production session data, or personally identifiable data.

## Development setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m playwright install chromium
pre-commit install
```

## Pull request expectations

- Keep changes focused and document public behavior.
- Add tests for fixes and new functionality.
- Use Pydantic v2 models and Python 3.11 type hints.
- Run `make check` before opening a pull request.
- Preserve the zero-secret guarantee and run redaction tests.
- Clearly identify Core Stable, Optional Integration, Experimental Demo, or Future Roadmap behavior.
- Never weaken authentication or authorization checks to make tests pass.

## Security reporting

Do not open a public issue for an active vulnerability. Contact the maintainers
through a private channel and include reproduction steps, affected versions, and
possible impact. Redact secrets and PII from every report.

## Commit hygiene

Use descriptive commits, avoid generated `.data` artifacts, and do not commit
`.env`, screenshots, reports, or local browser profiles.
