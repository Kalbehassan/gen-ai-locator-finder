# Architecture

## Stability tiers

- **Core Stable:** Pydantic contracts, FastAPI routes, Playwright lifecycle, deterministic strategy registry, rule ranking, JSON/CSV/XLSX exports, and redaction.
- **Optional Provider Integrations:** LiteLLM, Google GenAI, Milvus, OpenTelemetry, and heavy ML runtimes.
- **Experimental Demonstrations:** optional framework adapters and embedding/training experiments.
- **Future Roadmap:** cross-application learned models, robust visual matching, and centralized secret vault integration.

## Request lifecycle

1. Validate URL and separate credentials.
2. Resolve a named login profile.
3. Launch an isolated Chromium context.
4. Navigate and authenticate only to an authorized target.
5. Capture redacted DOM, accessibility, text and opt-in masked screenshot.
6. Extract elements and generate static/dynamic candidates.
7. Rank candidates with explainable heuristics.
8. Verify against Playwright and repair through alternative strategies.
9. Produce evidence and suggested tests.
10. Redact and export response artifacts.

## Trust boundaries

Credentials are represented by `SecretStr`, never written to logs or reports, and remain separate from target URLs. Browser screenshots are disabled by default and password inputs are blurred and cleared before capture. Optional integrations cannot weaken the default path.
